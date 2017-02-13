#!/usr/bin/python
# -*- coding: utf-8 -*-
#
import logging
import bcrypt
import functools
import gzip
import os
import re
import requests
import sqlalchemy
import time
from collections import OrderedDict
from datetime import datetime
from cStringIO import StringIO as IO
from flask import (
    after_this_request,
    flash,
    redirect,
    request,
    session,
    url_for
)
from flask_babel import gettext
from RPi import GPIO

from mycodo_flask.extensions import db

import databases

from mycodo_client import DaemonControl

# Functions
from scripts.utils import (
    test_username,
    test_password
)
from utils.send_data import send_email
from utils.system_pi import csv_to_list_of_int

# Config
from config import (
    CAMERAS_SUPPORTED,
    INSTALL_DIRECTORY
)

logger = logging.getLogger(__name__)


#
# Method Development
#

def is_positive_integer(number_string):
    try:
        if int(number_string) < 0:
            flash(gettext("Duration must be a positive integer"), "error")
            return False
    except ValueError:
        flash(gettext("Duration must be a valid integer"), "error")
        return False
    return True


def validate_method_data(form_data, this_method):
    if form_data.method_select.data == 'setpoint':
        if this_method.method_type == 'Date':
            if (not form_data.startTime.data or
                    not form_data.endTime.data or
                    form_data.startSetpoint.data == ''):
                flash(gettext("Required: Start date/time, end date/time, "
                              "start setpoint"), "error")
                return 1
            try:
                start_time = datetime.strptime(form_data.startTime.data,
                                               '%Y-%m-%d %H:%M:%S')
                end_time = datetime.strptime(form_data.endTime.data,
                                             '%Y-%m-%d %H:%M:%S')
            except ValueError:
                flash(gettext("Invalid Date/Time format. Correct format: "
                              "DD/MM/YYYY HH:MM:SS"), "error")
                return 1
            if end_time <= start_time:
                flash(gettext("The end time/date must be after the start "
                              "time/date."), "error")
                return 1

        elif this_method.method_type == 'Daily':
            if (not form_data.startDailyTime.data or
                    not form_data.endDailyTime.data or
                    form_data.startSetpoint.data == ''):
                flash(gettext("Required: Start time, end time, start "
                              "setpoint"), "error")
                return 1
            try:
                start_time = datetime.strptime(form_data.startDailyTime.data,
                                               '%H:%M:%S')
                end_time = datetime.strptime(form_data.endDailyTime.data,
                                             '%H:%M:%S')
            except ValueError:
                flash(gettext("Invalid Date/Time format. Correct format: "
                              "HH:MM:SS"), "error")
                return 1
            if end_time <= start_time:
                flash(gettext("The end time must be after the start time."),
                      "error")
                return 1

        elif this_method.method_type == 'Duration':
            if (not form_data.DurationSec.data or
                    form_data.startSetpoint.data == ''):
                flash(gettext("Required: Duration, start setpoint"),
                      "error")
                return 1
            if not is_positive_integer(form_data.DurationSec.data):
                return 1

    elif form_data.method_select.data == 'relay':
        if this_method.method_type == 'Date':
            if (not form_data.relayTime.data or
                    not form_data.relayID.data or
                    not form_data.relayState.data):
                flash(gettext("Required: Date/Time, Relay ID, and Relay "
                              "State"), "error")
                return 1
            try:
                datetime.strptime(form_data.relayTime.data,
                                  '%Y-%m-%d %H:%M:%S')
            except ValueError:
                flash(gettext("Invalid Date/Time format. Correct format: "
                              "DD-MM-YYYY HH:MM:SS"), "error")
                return 1
        elif this_method.method_type == 'Duration':
            if (not form_data.DurationSec.data or
                    not form_data.relayID.data or
                    not form_data.relayState.data):
                flash(gettext("Required: Duration, Relay ID, and Relay State"),
                      "error")
                return 1
            if not is_positive_integer(form_data.DurationSec.data):
                return 1
        elif this_method.method_type == 'Daily':
            if (not form_data.relayDailyTime.data or
                    not form_data.relayID.data or
                    not form_data.relayState.data):
                flash(gettext("Required: Time, Relay ID, and Relay State"),
                      "error")
                return 1
            try:
                datetime.strptime(form_data.relayDailyTime.data,
                                  '%H:%M:%S')
            except ValueError:
                flash(gettext("Invalid Date/Time format. Correct format: "
                              "HH:MM:SS"), "error")
                return 1


def method_create(form_create_method, method_id):
    action = '{action} {controller}'.format(
        action=gettext("Create"),
        controller=gettext("Method"))
    error = []

    try:
        new_method = databases.models.Method()
        new_method.method_id = method_id
        if form_create_method.name.data:
            new_method.name = form_create_method.name.data
        new_method.method_type = form_create_method.method_type.data
        if form_create_method.method_type.data == 'DailySine':
            new_method.amplitude = 1.0
            new_method.frequency = 1.0
            new_method.shift_angle = 0.0
            new_method.shift_y = 1.0
        if form_create_method.method_type.data == 'DailyBezier':
            new_method.shift_angle = 0.0
            new_method.x0 = 20.0
            new_method.y0 = 20.0
            new_method.x1 = 10.0
            new_method.y1 = 13.5
            new_method.x2 = 22.5
            new_method.y2 = 30.0
            new_method.x3 = 0.0
            new_method.y3 = 20.0
        new_method.method_order = 0
        new_method.controller_type = form_create_method.controller_type.data
        db.session.add(new_method)
        db.session.commit()
        return 0
    except Exception as except_msg:
        error.append(except_msg)
    flash_success_errors(error, action, url_for('method_routes.method_list'))


def method_add(form_add_method, method):
    action = '{action} {controller}'.format(
        action=gettext("Add"),
        controller=gettext("databases.models.Method"))
    error = []

    try:
        # Validate input time data
        this_method = method.filter(databases.models.Method.method_id == form_add_method.method_id.data)
        this_method = this_method.filter(databases.models.Method.method_order == 0).first()
        if validate_method_data(form_add_method, this_method):
            return 1

        if this_method.method_type == 'DailySine':
            mod_method = databases.models.Method.query.filter(
                databases.models.Method.method_id == form_add_method.method_id.data).first()
            mod_method.amplitude = form_add_method.amplitude.data
            mod_method.frequency = form_add_method.frequency.data
            mod_method.shift_angle = form_add_method.shiftAngle.data
            mod_method.shift_y = form_add_method.shiftY.data
            db.session.commit()
            return 0

        if this_method.method_type == 'DailyBezier':
            if not 0 <= form_add_method.shiftAngle.data <= 360:
                flash(gettext("Error: Angle Shift is out of range. It must be "
                              "<= 0 and <= 360."), "error")
                return 1
            if form_add_method.x0.data <= form_add_method.x3.data:
                flash(gettext("Error: X0 must be greater than X3."), "error")
                return 1
            mod_method = databases.models.Method.query.filter(
                databases.models.Method.method_id == form_add_method.method_id.data).first()
            mod_method.shift_angle = form_add_method.shiftAngle.data
            mod_method.x0 = form_add_method.x0.data
            mod_method.y0 = form_add_method.y0.data
            mod_method.x1 = form_add_method.x1.data
            mod_method.y1 = form_add_method.y1.data
            mod_method.x2 = form_add_method.x2.data
            mod_method.y2 = form_add_method.y2.data
            mod_method.x3 = form_add_method.x3.data
            mod_method.y3 = form_add_method.y3.data
            db.session.commit()
            return 0

        if form_add_method.method_select.data == 'setpoint':
            if this_method.method_type == 'Date':
                start_time = datetime.strptime(form_add_method.startTime.data,
                                               '%Y-%m-%d %H:%M:%S')
                end_time = datetime.strptime(form_add_method.endTime.data,
                                             '%Y-%m-%d %H:%M:%S')
            elif this_method.method_type == 'Daily':
                start_time = datetime.strptime(form_add_method.startDailyTime.data,
                                               '%H:%M:%S')
                end_time = datetime.strptime(form_add_method.endDailyTime.data,
                                             '%H:%M:%S')

            if this_method.method_type in ['Date', 'Daily']:
                # Check if the start time comes after the last entry's end time
                last_method = method.filter(databases.models.Method.method_id == this_method.method_id)
                last_method = last_method.filter(databases.models.Method.method_order > 0)
                last_method = last_method.filter(databases.models.Method.relay_id == None)
                last_method = last_method.order_by(databases.models.Method.method_order.desc()).first()
                if last_method is not None:
                    if this_method.method_type == 'Date':
                        last_method_end_time = datetime.strptime(last_method.time_end,
                                                                 '%Y-%m-%d %H:%M:%S')
                    elif this_method.method_type == 'Daily':
                        last_method_end_time = datetime.strptime(last_method.time_end,
                                                                 '%H:%M:%S')

                    if start_time < last_method_end_time:
                        flash(gettext("The new entry start time (%(st)s) "
                                      "cannot overlap the last entry's end "
                                      "time (%(et)s). Note: They may be the "
                                      "same time.",
                                      st=last_method_end_time,
                                      et=start_time),
                              "error")
                        return 1

        elif form_add_method.method_select.data == 'relay':
            if this_method.method_type == 'Date':
                start_time = datetime.strptime(form_add_method.relayTime.data,
                                               '%Y-%m-%d %H:%M:%S')
            elif this_method.method_type == 'Daily':
                start_time = datetime.strptime(form_add_method.relayDailyTime.data,
                                               '%H:%M:%S')

        new_method = databases.models.Method()
        new_method.method_id = form_add_method.method_id.data

        # Get last number in ordered list, increment for new entry
        method_last = method.order_by(databases.models.Method.method_order.desc()).first()
        new_method.method_order = method_last.method_order+1

        if this_method.method_type == 'Date':
            if form_add_method.method_select.data == 'setpoint':
                new_method.time_start = start_time.strftime('%Y-%m-%d %H:%M:%S')
                new_method.time_end = end_time.strftime('%Y-%m-%d %H:%M:%S')
            if form_add_method.method_select.data == 'relay':
                new_method.time_start = form_add_method.relayTime.data
        elif this_method.method_type == 'Daily':
            if form_add_method.method_select.data == 'setpoint':
                new_method.time_start = start_time.strftime('%H:%M:%S')
                new_method.time_end = end_time.strftime('%H:%M:%S')
            if form_add_method.method_select.data == 'relay':
                new_method.time_start = form_add_method.relayDailyTime.data
        elif this_method.method_type == 'Duration':
            new_method.duration_sec = form_add_method.DurationSec.data

        if form_add_method.method_select.data == 'setpoint':
            new_method.setpoint_start = form_add_method.startSetpoint.data
            new_method.setpoint_end = form_add_method.endSetpoint.data
        elif form_add_method.method_select.data == 'relay':
            new_method.relay_id = form_add_method.relayID.data
            new_method.relay_state = form_add_method.relayState.data
            new_method.relay_duration = form_add_method.relayDurationSec.data

        db.session.add(new_method)
        db.session.commit()

        if form_add_method.method_select.data == 'setpoint':
            if this_method.method_type == 'Date':
                flash(gettext("Added duration to method from %(st)s to "
                              "%(end)s", st=start_time, end=end_time),
                      "success")
            elif this_method.method_type == 'Daily':
                flash(gettext("Added duration to method from %(st)s to "
                              "%(end)s",
                              st=start_time.strftime('%H:%M:%S'),
                              end=end_time.strftime('%H:%M:%S')),
                      "success")
            elif this_method.method_type == 'Duration':
                flash(gettext("Added duration to method for %(sec)s seconds",
                              sec=form_add_method.DurationSec.data), "success")
        elif form_add_method.method_select.data == 'relay':
            if this_method.method_type == 'Date':
                flash(gettext("Added relay modulation to method at start "
                              "time: %(tm)s", tm=start_time), "success")
            elif this_method.method_type == 'Daily':
                flash(gettext("Added relay modulation to method at start "
                              "time: %(tm)s",
                              tm=start_time.strftime('%H:%M:%S')), "success")
            elif this_method.method_type == 'Duration':
                flash(gettext("Added relay modulation to method at start "
                              "time: %(tm)s",
                              tm=form_add_method.DurationSec.data), "success")

    except Exception as except_msg:
        error.append(except_msg)
    flash_success_errors(error, action, url_for('method_routes.method_list'))


def method_mod(form_mod_method, method):
    action = '{action} {controller}'.format(
        action=gettext("Modify"),
        controller=gettext("databases.models.Method"))
    error = []

    try:
        if form_mod_method.Delete.data:
            delete_entry_with_id(databases.models.Method, form_mod_method.method_id.data)
            return 0

        if form_mod_method.name.data:
            mod_method = databases.models.Method.query.filter(
                databases.models.Method.method_id == form_mod_method.method_id.data)
            mod_method = mod_method.filter(databases.models.Method.method_order == 0).first()
            mod_method.name = form_mod_method.name.data
            db.session.commit()
            return 0

        # Ensure data data is valid
        this_method = method.filter(databases.models.Method.id == form_mod_method.method_id.data).first()
        method_set = method.filter(databases.models.Method.method_id == this_method.method_id)
        method_set = method_set.filter(databases.models.Method.method_order == 0).first()
        if validate_method_data(form_mod_method, method_set):
            return 1

        mod_method = databases.models.Method.query.filter(
            databases.models.Method.id == form_mod_method.method_id.data).first()

        if form_mod_method.method_select.data == 'setpoint':
            if method_set.method_type == 'Date':
                start_time = datetime.strptime(form_mod_method.startTime.data, '%Y-%m-%d %H:%M:%S')
                end_time = datetime.strptime(form_mod_method.endTime.data, '%Y-%m-%d %H:%M:%S')

                # Ensure the start time comes after the previous entry's end time
                # and the end time comes before the next entry's start time
                # method_id_set is the id given to all method entries, 'method_id', not 'id'

                previous_method = method.order_by(databases.models.Method.method_order.desc()).filter(
                    databases.models.Method.method_order < this_method.method_order).first()
                next_method = method.order_by(databases.models.Method.method_order.asc()).filter(
                    databases.models.Method.method_order > this_method.method_order).first()

                if previous_method is not None and previous_method.time_end is not None:
                    previous_end_time = datetime.strptime(
                        previous_method.time_end, '%Y-%m-%d %H:%M:%S')
                    if previous_end_time is not None and start_time < previous_end_time:
                        error.append(
                            gettext("The entry start time (%(st)s) cannot "
                                    "overlap the previous entry's end time "
                                    "(%(et)s)",
                                    st=start_time, et=previous_end_time))

                if next_method is not None and next_method.time_start is not None:
                    next_start_time = datetime.strptime(
                        next_method.time_start, '%Y-%m-%d %H:%M:%S')
                    if next_start_time is not None and end_time > next_start_time:
                        error.append(
                            gettext("The entry end time (%(et)s) cannot "
                                    "overlap the next entry's start time "
                                    "(%(st)s)",
                                    et=end_time, st=next_start_time))

                mod_method.time_start = start_time.strftime('%Y-%m-%d %H:%M:%S')
                mod_method.time_end = end_time.strftime('%Y-%m-%d %H:%M:%S')

            elif method_set.method_type == 'Duration':
                mod_method.duration_sec = form_mod_method.DurationSec.data

            elif method_set.method_type == 'Daily':
                mod_method.time_start = form_mod_method.startDailyTime.data
                mod_method.time_end = form_mod_method.endDailyTime.data

            mod_method.setpoint_start = form_mod_method.startSetpoint.data
            mod_method.setpoint_end = form_mod_method.endSetpoint.data

        elif form_mod_method.method_select.data == 'relay':
            if method_set.method_type == 'Date':
                mod_method.time_start = form_mod_method.relayTime.data
            elif method_set.method_type == 'Duration':
                mod_method.duration_sec = form_mod_method.DurationSec.data
            mod_method.relay_id = form_mod_method.relayID.data
            mod_method.relay_state = form_mod_method.relayState.data
            mod_method.relay_duration = form_mod_method.relayDurationSec.data

        elif method_set.method_type == 'DailySine':
            if form_mod_method.method_select.data == 'relay':
                mod_method.time_start = form_mod_method.relayTime.data
                mod_method.relay_id = form_mod_method.relayID.data
                mod_method.relay_state = form_mod_method.relayState.data
                mod_method.relay_duration = form_mod_method.relayDurationSec.data

        if not error:
            db.session.commit()

    except Exception as except_msg:
        error.append(except_msg)
    flash_success_errors(error, action, url_for('method_routes.method_list'))


def method_del(method_id):
    action = '{action} {controller}'.format(
        action=gettext("Delete"),
        controller=gettext("databases.models.Method"))
    error = []

    try:
        delete_entry_with_id(databases.models.Method,
                             method_id)
    except Exception as except_msg:
        error.append(except_msg)
    flash_success_errors(error, action, url_for('method_routes.method_list'))


#
# Authenticate remote hosts
#

def check_new_credentials(address, user, passw):
    credentials = {
        'user': user,
        'passw': passw
    }
    url = 'https://{}/newremote/'.format(address)
    try:
        r = requests.get(url, params=credentials, verify=False)
        return r.json()
    except Exception as msg:
        return {
            'status': 1,
            'message': "Error connecting to host: {err}".format(err=msg)
        }


def auth_credentials(address, user, password_hash):
    credentials = {
        'user': user,
        'pw_hash': password_hash
    }
    url = 'https://{}/auth/'.format(address)
    try:
        r = requests.get(url, params=credentials, verify=False)
        return int(r.text)
    except Exception as e:
        logger.error(
            "'auth_credentials' raised an exception: {err}".format(err=e))
        return 1


def remote_host_add(form_setup, display_order):
    if deny_guest_user():
        return redirect(url_for('general_routes.home'))

    if form_setup.validate():
        try:
            pw_check = check_new_credentials(form_setup.host.data,
                                             form_setup.username.data,
                                             form_setup.password.data)
            if pw_check['status']:
                flash(pw_check['message'], "error")
                return 1
            new_remote_host = databases.models.Remote()
            new_remote_host.host = form_setup.host.data
            new_remote_host.username = form_setup.username.data
            new_remote_host.password_hash = pw_check['message']
            try:
                db.session.add(new_remote_host)
                db.session.commit()
                flash(gettext("Remote Host %(host)s with ID %(id)s (%(uuid)s)"
                              " successfully added",
                              host=form_setup.host.data,
                              id=new_remote_host.id,
                              uuid=new_remote_host.unique_id),
                      "success")

                databases.models.DisplayOrder.query.first().remote_host = add_display_order(
                    display_order, new_remote_host.id)
                db.session.commit()
            except sqlalchemy.exc.OperationalError as except_msg:
                flash(gettext("Remote Host Error: %(msg)s", msg=except_msg),
                      "error")
            except sqlalchemy.exc.IntegrityError as except_msg:
                flash(gettext("Remote Host Error: %(msg)s", msg=except_msg),
                      "error")
        except Exception as except_msg:
            flash(gettext("Remote Host Error: %(msg)s", msg=except_msg),
                  "error")
    else:
        flash_form_errors(form_setup)


def remote_host_del(form_setup):
    if deny_guest_user():
        return redirect(url_for('general_routes.home'))

    try:
        delete_entry_with_id(databases.models.Remote,
                             form_setup.remote_id.data)
        display_order = csv_to_list_of_int(databases.models.DisplayOrder.query.first().remote_host)
        display_order.remove(int(form_setup.remote_id.data))
        databases.models.DisplayOrder.query.first().remote_host = list_to_csv(display_order)
        db.session.commit()
    except Exception as except_msg:
        flash(gettext("Remote Host Error: %(msg)s", msg=except_msg), "error")


#
# Manipulate relay settings while daemon is running
#

def manipulate_relay(action, relay_id, setup_pin=False):
    """
    Add, delete, and modify relay settings while the daemon is active

    :param relay_id: relay ID in the SQL database
    :type relay_id: str
    :param action: add, del, or mod
    :type action: str
    :param setup_pin: Initialize new pin (if changed)
    :type setup_pin: bool
    """
    control = DaemonControl()
    return_values = control.relay_setup(action, relay_id, setup_pin)
    if return_values[0]:
        flash(gettext("Error: %(err)s",
                      err='{action} Relay: Daemon response: {msg}'.format(
                          action=action,
                          msg=return_values[1])),
              "error")
    else:
        flash(gettext("Success: %(err)s",
                      err='{action} Relay: Daemon response: {msg}'.format(
                          action=action,
                          msg=return_values[1])),
              "success")


#
# Activate/deactivate controller
#

def activate_deactivate_controller(controller_action,
                                   controller_type,
                                   controller_id):
    """
    Activate or deactivate controller

    :param controller_action: Activate or deactivate
    :type controller_action: str
    :param controller_type: The controller type (LCD, PID, Sensor, Timer)
    :type controller_type: str
    :param controller_id: Controller with ID to activate or deactivate
    :type controller_id: str
    """
    if deny_guest_user():
        return redirect(url_for('general_routes.home'))

    if controller_action == 'activate':
        activated = True
    else:
        activated = False

    translated_names = {
        "LCD": gettext("LCD"),
        "PID": gettext("PID"),
        "Sensor": gettext("Sensor"),
        "Timer": gettext("Timer")
    }

    try:
        if controller_type == 'LCD':
            mod_controller = databases.models.LCD.query.filter(
                databases.models.LCD.id == int(controller_id)).first()
        elif controller_type == 'PID':
            mod_controller = databases.models.PID.query.filter(
                databases.models.PID.id == int(controller_id)).first()
        elif controller_type == 'Sensor':
            mod_controller = databases.models.Sensor.query.filter(
                databases.models.Sensor.id == int(controller_id)).first()
        elif controller_type == 'Timer':
            mod_controller = databases.models.Timer.query.filter(
                databases.models.Timer.id == int(controller_id)).first()
        mod_controller.is_activated = activated
        db.session.commit()

        if activated:
            flash(gettext("%(cont)s controller activated in SQL database",
                          cont=translated_names[controller_type]),
                  "success")
        else:
            flash(gettext("%(cont)s controller deactivated in SQL database",
                          cont=translated_names[controller_type]),
                  "success")
    except Exception as except_msg:
        flash(gettext("Error: %(err)s",
                      err='SQL: {msg}'.format(msg=except_msg)),
              "error")

    try:
        control = DaemonControl()
        if controller_action == 'activate':
            return_values = control.activate_controller(controller_type,
                                                        int(controller_id))
        else:
            return_values = control.deactivate_controller(controller_type,
                                                          int(controller_id))
        if return_values[0]:
            flash("{err}".format(err=return_values[1]), "error")
        else:
            flash("{err}".format(err=return_values[1]), "success")
    except Exception as except_msg:
        flash(gettext("Error: %(err)s",
                      err='Daemon: {msg}'.format(msg=except_msg)),
              "error")


#
# Choices
#

# return a dictionary of all available measurements
# Used to produce a multi-select form input for creating/modifying custom graphs
def choices_sensors(sensor):
    choices = OrderedDict()
    # populate form multi-select choices for sensors and measurements
    for each_sensor in sensor:
        if each_sensor.device in ['RPiCPULoad']:
            value = '{},cpu_load_1m'.format(each_sensor.id)
            display = '{} ({}) CPU Load (1m)'.format(
                each_sensor.id, each_sensor.name)
            choices.update({value: display})
            value = '{},cpu_load_5m'.format(each_sensor.id)
            display = '{} ({}) CPU Load (5m)'.format(
                each_sensor.id, each_sensor.name)
            choices.update({value: display})
            value = '{},cpu_load_15m'.format(each_sensor.id)
            display = '{} ({}) CPU Load (15m)'.format(
                each_sensor.id, each_sensor.name)
            choices.update({value: display})
        if each_sensor.device == 'CHIRP':
            value = '{},moisture'.format(each_sensor.id)
            display = '{} ({}) Moisture'.format(
                each_sensor.id, each_sensor.name)
            choices.update({value: display})
        if each_sensor.device in ['AM2315', 'ATLAS_PT1000', 'BME280', 'BMP',
                                  'CHIRP', 'DHT11', 'DHT22', 'DS18B20',
                                  'HTU21D', 'RPi', 'SHT1x_7x', 'SHT2x']:
            value = '{},temperature'.format(each_sensor.id)
            display = '{} ({}) Temperature'.format(
                each_sensor.id, each_sensor.name)
            choices.update({value: display})
        if each_sensor.device == 'TMP006':
            value = '{},temperature_object'.format(each_sensor.id)
            display = '{} ({}) Temperature (Object)'.format(
                each_sensor.id, each_sensor.name)
            choices.update({value: display})
            value = '{},temperature_die'.format(each_sensor.id)
            display = '{} ({}) Temperature (Die)'.format(
                each_sensor.id, each_sensor.name)
            choices.update({value: display})
        if each_sensor.device in ['AM2315', 'BME280', 'DHT11', 'DHT22', 'HTU21D',
                                  'SHT1x_7x', 'SHT2x']:
            value = '{},humidity'.format(each_sensor.id)
            display = '{} ({}) Humidity'.format(
                each_sensor.id, each_sensor.name)
            choices.update({value: display})
            value = '{},dewpoint'.format(each_sensor.id)
            display = '{} ({}) Dew Point'.format(
                each_sensor.id, each_sensor.name)
            choices.update({value: display})
        if each_sensor.device == 'K30':
            value = '{},co2'.format(each_sensor.id)
            display = '{} ({}) CO2'.format(
                each_sensor.id, each_sensor.name)
            choices.update({value: display})
        if each_sensor.device in ['BME280', 'BMP']:
            value = '{},pressure'.format(each_sensor.id)
            display = '{} ({}) Pressure'.format(
                each_sensor.id, each_sensor.name)
            choices.update({value: display})
            value = '{},altitude'.format(each_sensor.id)
            display = '{} ({}) Altitude'.format(
                each_sensor.id, each_sensor.name)
            choices.update({value: display})
        if each_sensor.device == 'EDGE':
            value = '{},edge'.format(each_sensor.id)
            display = '{} ({}) Edge'.format(
                each_sensor.id, each_sensor.name)
            choices.update({value: display})
        if each_sensor.device in ['ADS1x15', 'MCP342x']:
            value = '{},voltage'.format(each_sensor.id)
            display = '{} ({}) Volts'.format(
                each_sensor.id, each_sensor.name)
            choices.update({value: display})
            value = '{},{}'.format(each_sensor.id, each_sensor.adc_measure)
            display = '{} ({}) {}'.format(
                each_sensor.id, each_sensor.name, each_sensor.adc_measure)
            choices.update({value: display})
        if each_sensor.device in ['CHIRP', 'TSL2561']:
            value = '{},lux'.format(each_sensor.id)
            display = '{} ({}) Lux'.format(
                each_sensor.id, each_sensor.name)
            choices.update({value: display})
    return choices


# Return a dictionary of all available ids and names
# produce a multi-select form input for creating/modifying custom graphs
def choices_id_name(table):
    choices = OrderedDict()
    # populate form multi-select choices for relays
    for each_entry in table:
        value = each_entry.id
        display = '{id} ({name})'.format(id=each_entry.id,
                                         name=each_entry.name)
        choices.update({value:display})
    return choices


#
# Graph
#

def graph_add(form_add_graph, display_order):
    action = '{action} {controller}'.format(
        action=gettext("Add"),
        controller=gettext("Graph"))
    error = []

    if (form_add_graph.name.data and form_add_graph.width.data and
            form_add_graph.height.data and form_add_graph.xAxisDuration.data and
            form_add_graph.refreshDuration.data):
        new_graph = databases.models.Graph()
        new_graph.name = form_add_graph.name.data
        if form_add_graph.pidIDs.data:
            pid_ids_joined = ",".join(str(form_add_graph.pidIDs.data))
            new_graph.pid_ids = pid_ids_joined
        if form_add_graph.relayIDs.data:
            relay_ids_joined = ",".join(str(form_add_graph.relayIDs.data))
            new_graph.relay_ids = relay_ids_joined
        if form_add_graph.sensorIDs.data:
            sensor_ids_joined = ";".join(form_add_graph.sensorIDs.data)
            new_graph.sensor_ids_measurements = sensor_ids_joined
        new_graph.width = form_add_graph.width.data
        new_graph.height = form_add_graph.height.data
        new_graph.x_axis_duration = form_add_graph.xAxisDuration.data
        new_graph.refresh_duration = form_add_graph.refreshDuration.data
        new_graph.enable_navbar = form_add_graph.enableNavbar.data
        new_graph.enable_rangeselect = form_add_graph.enableRangeSelect.data
        new_graph.enable_export = form_add_graph.enableExport.data
        try:
            new_graph.save()
            flash(gettext(
                "Graph with ID %(id)s successfully added",
                id=new_graph.id),
                "success")

            databases.models.DisplayOrder.query.first().graph = add_display_order(
                display_order, new_graph.id)
            db.session.commit()
        except sqlalchemy.exc.OperationalError as except_msg:
            error.append(except_msg)
        except sqlalchemy.exc.IntegrityError as except_msg:
            error.append(except_msg)
        flash_success_errors(error, action, url_for('page_routes.page_graph'))
    else:
        flash_form_errors(form_add_graph)


def graph_mod(form_mod_graph, request_form):
    action = '{action} {controller}'.format(
        action=gettext("Modify"),
        controller=gettext("Graph"))
    error = []

    if form_mod_graph.validate():
        def is_rgb_color(color_hex):
            return bool(re.compile(r'#[a-fA-F0-9]{6}$').match(color_hex))

        # Get variable number of color inputs, turn into CSV string
        colors = {}
        f = request_form
        for key in f.keys():
            if 'color_number' in key:
                for value in f.getlist(key):
                    if not is_rgb_color(value):
                        flash(gettext("Invalid hex color value"), "error")
                        return redirect(url_for('page_routes.page_graph'))
                    colors[key[12:]] = value

        sorted_list = [(k, colors[k]) for k in sorted(colors)]

        short_list = []
        for each_color in sorted_list:
            short_list.append(each_color[1])
        sorted_colors_string = ",".join(short_list)

        try:
            mod_graph = databases.models.Graph.query.filter(
                databases.models.Graph.id == form_mod_graph.graph_id.data).first()
            mod_graph.custom_colors = sorted_colors_string
            mod_graph.use_custom_colors = form_mod_graph.use_custom_colors.data
            mod_graph.name = form_mod_graph.name.data
            if form_mod_graph.pidIDs.data:
                pid_ids_joined = ",".join(str(form_mod_graph.pidIDs.data))
                mod_graph.pid_ids = pid_ids_joined
            if form_mod_graph.relayIDs.data:
                relay_ids_joined = ",".join(str(form_mod_graph.relayIDs.data))
                mod_graph.relay_ids = relay_ids_joined
            if form_mod_graph.sensorIDs.data:
                sensor_ids_joined = ";".join(form_mod_graph.sensorIDs.data)
                mod_graph.sensor_ids_measurements = sensor_ids_joined
            mod_graph.width = form_mod_graph.width.data
            mod_graph.height = form_mod_graph.height.data
            mod_graph.x_axis_duration = form_mod_graph.xAxisDuration.data
            mod_graph.refresh_duration = form_mod_graph.refreshDuration.data
            mod_graph.enable_navbar = form_mod_graph.enableNavbar.data
            mod_graph.enable_export = form_mod_graph.enableExport.data
            mod_graph.enable_rangeselect = form_mod_graph.enableRangeSelect.data
            db.session.commit()
        except sqlalchemy.exc.OperationalError as except_msg:
            error.append(except_msg)
        except sqlalchemy.exc.IntegrityError as except_msg:
            error.append(except_msg)
        flash_success_errors(error, action, url_for('page_routes.page_graph'))
    else:
        flash_form_errors(form_mod_graph)


def graph_del(form_del_graph):
    action = '{action} {controller}'.format(
        action=gettext("Delete"),
        controller=gettext("Graph"))
    error = []

    if form_del_graph.validate():
        try:
            delete_entry_with_id(databases.models.Graph,
                                 form_del_graph.graph_id.data)
            display_order = csv_to_list_of_int(databases.models.DisplayOrder.query.first().graph)
            display_order.remove(int(form_del_graph.graph_id.data))
            databases.models.DisplayOrder.query.first().graph = list_to_csv(display_order)
            db.session.commit()
        except Exception as except_msg:
            error.append(except_msg)
        flash_success_errors(error, action, url_for('page_routes.page_graph'))
    else:
        flash_form_errors(form_del_graph)


def graph_reorder(form_order_graph, display_order):
    action = '{action} {controller}'.format(
        action=gettext("Reorder"),
        controller=gettext("Graph"))
    error = []

    if form_order_graph.validate():
        try:
            if form_order_graph.orderGraphUp.data:
                status, reord_list = reorder_list(
                    display_order,
                    form_order_graph.orderGraph_id.data,
                    'up')
            elif form_order_graph.orderGraphDown.data:
                status, reord_list = reorder_list(
                    display_order,
                    form_order_graph.orderGraph_id.data,
                    'down')
            if status == 'success':
                order_graph = databases.models.DisplayOrder.query.first()
                order_graph.graph = ','.join(reord_list)
                db.session.commit()
            else:
                error.append(reord_list)
        except Exception as except_msg:
            error.append(except_msg)
        flash_success_errors(error, action, url_for('page_routes.page_graph'))
    else:
        flash_form_errors(form_order_graph)


#
# LCD Manipulation
#

def lcd_add(form_add_lcd):
    action = '{action} {controller}'.format(
        action=gettext("Add"),
        controller=gettext("LCD"))
    error = []

    if form_add_lcd.validate():
        for _ in range(0, form_add_lcd.numberLCDs.data):
            try:
                new_lcd = databases.models.LCD().save
                display_order = csv_to_list_of_int(databases.models.DisplayOrder.query.first().lcd)
                databases.models.DisplayOrder.query.first().lcd = add_display_order(
                    display_order, new_lcd.id)
                db.session.commit()
            except sqlalchemy.exc.OperationalError as except_msg:
                error.append(except_msg)
            except sqlalchemy.exc.IntegrityError as except_msg:
                error.append(except_msg)
            flash_success_errors(error, action, url_for('page_routes.page_lcd'))
    else:
        flash_form_errors(form_add_lcd)


def lcd_mod(form_mod_lcd):
    action = '{action} {controller}'.format(
        action=gettext("Modify"),
        controller=gettext("LCD"))
    error = []

    if form_mod_lcd.validate():
        try:
            mod_lcd = databases.models.LCD.query.filter(
                databases.models.LCD.id == form_mod_lcd.modLCD_id.data).first()
            if mod_lcd.is_activated:
                flash(gettext("Deactivate LCD controller before modifying"
                              " its settings."), "error")
                return redirect('/lcd')
            mod_lcd = databases.models.LCD.query.filter(
                databases.models.LCD.id == form_mod_lcd.modLCD_id.data).first()
            mod_lcd.name = form_mod_lcd.modName.data
            mod_lcd.location = form_mod_lcd.modLocation.data
            mod_lcd.multiplexer_address = form_mod_lcd.modMultiplexAddress.data
            mod_lcd.multiplexer_channel = form_mod_lcd.modMultiplexChannel.data
            mod_lcd.period = form_mod_lcd.modPeriod.data
            mod_lcd.x_characters = form_mod_lcd.modLCDType.data.split("x")[0]
            mod_lcd.y_lines = form_mod_lcd.modLCDType.data.split("x")[1]
            if form_mod_lcd.modLine1SensorIDMeasurement.data:
                mod_lcd.line_1_sensor_id = form_mod_lcd.modLine1SensorIDMeasurement.data.split(",")[0]
                mod_lcd.line_1_measurement = form_mod_lcd.modLine1SensorIDMeasurement.data.split(",")[1]
            else:
                mod_lcd.line_1_sensor_id = ''
                mod_lcd.line_1_measurement = ''
            if form_mod_lcd.modLine2SensorIDMeasurement.data:
                mod_lcd.line_2_sensor_id = form_mod_lcd.modLine2SensorIDMeasurement.data.split(",")[0]
                mod_lcd.line_2_measurement = form_mod_lcd.modLine2SensorIDMeasurement.data.split(",")[1]
            else:
                mod_lcd.line_2_sensor_id = ''
                mod_lcd.line_2_measurement = ''
            if form_mod_lcd.modLine3SensorIDMeasurement.data:
                mod_lcd.line_3_sensor_id = form_mod_lcd.modLine3SensorIDMeasurement.data.split(",")[0]
                mod_lcd.line_3_measurement = form_mod_lcd.modLine3SensorIDMeasurement.data.split(",")[1]
            else:
                mod_lcd.line_3_sensor_id = ''
                mod_lcd.line_3_measurement = ''
            if form_mod_lcd.modLine4SensorIDMeasurement.data:
                mod_lcd.line_4_sensor_id = form_mod_lcd.modLine4SensorIDMeasurement.data.split(",")[0]
                mod_lcd.line_4_measurement = form_mod_lcd.modLine4SensorIDMeasurement.data.split(",")[1]
            else:
                mod_lcd.line_4_sensor_id = ''
                mod_lcd.line_4_measurement = ''
            db.session.commit()
        except Exception as except_msg:
            error.append(except_msg)
        flash_success_errors(error, action, url_for('page_routes.page_lcd'))
    else:
        flash_form_errors(form_mod_lcd)


def lcd_del(form_del_lcd):
    action = '{action} {controller}'.format(
        action=gettext("Delete"),
        controller=gettext("LCD"))
    error = []

    if form_del_lcd.validate():
        try:
            delete_entry_with_id(databases.models.LCD,
                                 form_del_lcd.delLCD_id.data)
            display_order = csv_to_list_of_int(databases.models.DisplayOrder.query.first().lcd)
            display_order.remove(int(form_del_lcd.delLCD_id.data))
            databases.models.DisplayOrder.query.first().lcd = list_to_csv(display_order)
            db.session.commit()
        except Exception as except_msg:
            error.append(except_msg)
        flash_success_errors(error, action, url_for('page_routes.page_lcd'))
    else:
        flash_form_errors(form_del_lcd)


def lcd_reorder(form_order_lcd, display_order):
    action = '{action} {controller}'.format(
        action=gettext("Reorder"),
        controller=gettext("LCD"))
    error = []

    if form_order_lcd.validate():
        try:
            if form_order_lcd.orderLCDUp.data:
                status, reord_list = reorder_list(
                    display_order,
                    form_order_lcd.orderLCD_id.data,
                    'up')
            elif form_order_lcd.orderLCDDown.data:
                status, reord_list = reorder_list(
                    display_order,
                    form_order_lcd.orderLCD_id.data,
                    'down')
            if status == 'success':
                databases.models.DisplayOrder.query.first().lcd = ','.join(reord_list)
                db.session.commit()
            else:
                error.append(reord_list)
        except Exception as except_msg:
            error.append(except_msg)
        flash_success_errors(error, action, url_for('page_routes.page_lcd'))
    else:
        flash_form_errors(form_order_lcd)


def lcd_activate(form_activate_lcd):
    action = '{action} {controller}'.format(
        action=gettext("Activate"),
        controller=gettext("LCD"))
    error = []

    if form_activate_lcd.validate():
        try:
            # All sensors the LCD depends on must be active to activate the LCD
            lcd = databases.models.LCD.query.filter(
                databases.models.LCD.id == form_activate_lcd.activateLCD_id.data).first()
            if lcd.y_lines == 2:
                lcd_lines = [lcd.line_1_sensor_id,
                             lcd.line_2_sensor_id]
            else:
                lcd_lines = [lcd.line_1_sensor_id,
                             lcd.line_2_sensor_id,
                             lcd.line_3_sensor_id,
                             lcd.line_4_sensor_id]
            # Filter only sensors that will be displayed
            sensor = databases.models.Sensor.query.filter(
                databases.models.Sensor.id.in_(lcd_lines)).all()
            # Check if any sensors are not active
            for each_sensor in sensor:
                if not each_sensor.is_activated:
                    flash(gettext(
                        "Cannot activate controller if the associated "
                        "sensor controller is inactive"), "error")
                    return redirect('/lcd')
            activate_deactivate_controller(
                'activate', 'LCD', form_activate_lcd.activateLCD_id.data)
        except Exception as except_msg:
            error.append(except_msg)
        flash_success_errors(error, action, url_for('page_routes.page_lcd'))
    else:
        flash_form_errors(form_activate_lcd)


def lcd_deactivate(form_deactivate_lcd):
    if form_deactivate_lcd.validate():
        activate_deactivate_controller(
            'deactivate', 'LCD', form_deactivate_lcd.deactivateLCD_id.data)
    else:
        flash_form_errors(form_deactivate_lcd)


def lcd_reset_flashing(form_reset_flashing_lcd):
    if form_reset_flashing_lcd.validate():
        control = DaemonControl()
        return_value, return_msg = control.flash_lcd(
            form_reset_flashing_lcd.flashLCD_id.data, 0)
        if not return_value:
            flash(gettext("Error: %(msg)s", msg=return_msg), "error")
    else:
        flash_form_errors(form_reset_flashing_lcd)


#
# PID manipulation
#

def pid_add(form_add_pid):
    action = '{action} {controller}'.format(
        action=gettext("Add"),
        controller=gettext("PID"))
    error = []

    if form_add_pid.validate():
        for _ in range(0, form_add_pid.numberPIDs.data):
            try:
                new_pid = databases.models.PID().save()
                display_order = csv_to_list_of_int(databases.models.DisplayOrder.query.first().pid)
                databases.models.DisplayOrder.query.first().pid = add_display_order(
                    display_order, new_pid.id)
                db.session.commit()
            except sqlalchemy.exc.OperationalError as except_msg:
                error.append(except_msg)
            except sqlalchemy.exc.IntegrityError as except_msg:
                error.append(except_msg)
        flash_success_errors(error, action, url_for('page_routes.page_pid'))
    else:
        flash_form_errors(form_add_pid)


def pid_mod(form_mod_pid):
    action = '{action} {controller}'.format(
        action=gettext("Modify"),
        controller=gettext("PID"))
    error = []

    if form_mod_pid.validate():
        try:
            sensor = databases.models.Sensor.query.filter(
                databases.models.Sensor.id == form_mod_pid.modSensorID.data).first()
            if not sensor:
                error.append(gettext("A valid sensor ID is required"))
            elif (
                  (sensor.device_type == 'tsensor' and
                   form_mod_pid.modMeasurement.data not in ['temperature']) or

                  (sensor.device_type == 'tmpsensor' and
                   form_mod_pid.modMeasurement.data not in ['temperature_object',
                                                            'temperature_die']) or

                  (sensor.device_type == 'htsensor' and
                   form_mod_pid.modMeasurement.data not in ['temperature',
                                                            'humidity',
                                                            'dewpoint']) or

                  (sensor.device_type == 'co2sensor' and
                   form_mod_pid.modMeasurement.data not in ['co2']) or

                  (sensor.device_type == 'luxsensor' and
                   form_mod_pid.modMeasurement.data not in ['lux']) or

                  (sensor.device_type == 'moistsensor' and
                   form_mod_pid.modMeasurement.data not in ['temperature',
                                                            'lux',
                                                            'moisture']) or

                  (sensor.device_type == 'presssensor' and
                   form_mod_pid.modMeasurement.data not in ['temperature',
                                                            'pressure',
                                                            'altitude'])
            ):
                error.append(gettext(
                    "Select a Measure Type that is compatible with the "
                    "chosen sensor"))
            if not error:
                mod_pid = databases.models.PID.query.filter(
                    databases.models.PID.id == form_mod_pid.modPID_id.data).first()
                mod_pid.name = form_mod_pid.modName.data
                mod_pid.sensor_id = form_mod_pid.modSensorID.data
                mod_pid.measurement = form_mod_pid.modMeasurement.data
                mod_pid.direction = form_mod_pid.modDirection.data
                mod_pid.period = form_mod_pid.modPeriod.data
                mod_pid.setpoint = form_mod_pid.modSetpoint.data
                mod_pid.p = form_mod_pid.modKp.data
                mod_pid.i = form_mod_pid.modKi.data
                mod_pid.d = form_mod_pid.modKd.data
                mod_pid.integrator_min = form_mod_pid.modIntegratorMin.data
                mod_pid.integrator_max = form_mod_pid.modIntegratorMax.data
                mod_pid.raise_relay_id = form_mod_pid.modRaiseRelayID.data
                mod_pid.raise_min_duration = form_mod_pid.modRaiseMinDuration.data
                mod_pid.raise_max_duration = form_mod_pid.modRaiseMaxDuration.data
                mod_pid.lower_relay_id = form_mod_pid.modLowerRelayID.data
                mod_pid.lower_min_duration = form_mod_pid.modLowerMinDuration.data
                mod_pid.lower_max_duration = form_mod_pid.modLowerMaxDuration.data
                mod_pid.method_id = form_mod_pid.mod_method_id.data
                db.session.commit()
                # If the controller is active or paused, refresh variables in thread
                if mod_pid.is_activated:
                    control = DaemonControl()
                    return_value = control.pid_mod(form_mod_pid.modPID_id.data)
                    flash(gettext(
                        "PID Controller settings refresh response: %(resp)s",
                        resp=return_value), "success")
        except Exception as except_msg:
            error.append(except_msg)
        flash_success_errors(error, action, url_for('page_routes.page_pid'))
    else:
        flash_form_errors(form_mod_pid)


def pid_del(pid_id):
    action = '{action} {controller}'.format(
        action=gettext("Delete"),
        controller=gettext("PID"))
    error = []

    try:
        pid = databases.models.PID.query.filter(
            databases.models.PID.id == pid_id).first()
        if pid.is_activated:
            pid_deactivate(pid_id)

        delete_entry_with_id(databases.models.PID,
                             pid_id)
        display_order = csv_to_list_of_int(databases.models.DisplayOrder.query.first().pid)
        display_order.remove(int(pid_id))
        databases.models.DisplayOrder.query.first().pid = list_to_csv(display_order)
        db.session.commit()
    except Exception as except_msg:
        error.append(except_msg)

    flash_success_errors(error, action, url_for('page_routes.page_pid'))


def pid_reorder(pid_id, display_order, direction):
    action = '{action} {controller}'.format(
        action=gettext("Reorder"),
        controller=gettext("PID"))
    error = []

    try:
        if direction == 'up':
            status, reord_list = reorder_list(display_order, pid_id, 'up')
        elif direction == 'down':
            status, reord_list = reorder_list(display_order, pid_id, 'down')
        if status == 'success':
            databases.models.DisplayOrder.query.first().pid = ','.join(reord_list)
            db.session.commit()
        else:
            error.append(reord_list)
    except Exception as except_msg:
        error.append(except_msg)

    flash_success_errors(error, action, url_for('page_routes.page_pid'))


def has_required_pid_values(pid_id):
    pid = databases.models.PID.query.filter(
        databases.models.PID.id == pid_id).first()
    error = False
    # TODO: Add more settings-checks before allowing controller to be activated
    if not pid.sensor_id:
        flash(gettext("A valid sensor is required"), "error")
        error = True
    if not pid.measurement:
        flash(gettext("A valid Measure Type is required"), "error")
        error = True
    if not pid.raise_relay_id and not pid.lower_relay_id:
        flash(gettext("A Raise Relay ID and/or a Lower Relay ID is "
                      "required"), "error")
        error = True
    if error:
        return redirect('/pid')


def pid_activate(pid_id):
    if has_required_pid_values(pid_id):
        return redirect(url_for('page_routes.page_pid'))

    action = '{action} {controller}'.format(
        action=gettext("Actuate"),
        controller=gettext("PID"))
    error = []

    # Check if associated sensor is activated
    pid = databases.models.PID.query.filter(
        databases.models.PID.id == pid_id).first()
    sensor = databases.models.Sensor.query.filter(
        databases.models.Sensor.id == pid.sensor_id).first()

    if not sensor.is_activated:
        error.append(gettext(
            "Cannot activate PID controller if the associated sensor "
            "controller is inactive"))
    else:
        # Signal the duration method can run because it's been
        # properly initiated (non-power failure)
        mod_method = databases.models.Method.query.filter(
            databases.models.Method.id == pid.method_id).first()
        if mod_method and mod_method.method_type == 'Duration':
            mod_method.method_start_time = 'Ready'
            db.session.commit()

        time.sleep(1)
        activate_deactivate_controller('activate',
                                       'PID',
                                       pid_id)

    flash_success_errors(error, action, url_for('page_routes.page_pid'))


def pid_deactivate(pid_id):
    pid = databases.models.PID.query.filter(
        databases.models.PID.id == pid_id).first()
    pid.is_activated = False
    db.session.commit()
    time.sleep(1)
    activate_deactivate_controller('deactivate',
                                   'PID',
                                   pid_id)


def pid_manipulate(pid_id, action):
    if action not in ['Hold', 'Pause', 'Resume']:
        flash(gettext("Invalid PID action: %(act)s", act=action), "error")
        return 1

    try:
        mod_pid = databases.models.PID.query.filter(
            databases.models.PID.id == pid_id).first()
        if action == 'Hold':
            mod_pid.is_held = True
            mod_pid.is_paused = False
        elif action == 'Pause':
            mod_pid.is_paused = True
            mod_pid.is_held = False
        elif action == 'Resume':
            mod_pid.is_activated = True
            mod_pid.is_held = False
            mod_pid.is_paused = False
        db.session.commit()

        control = DaemonControl()
        if action == 'Hold':
            return_value = control.pid_hold(pid_id)
        elif action == 'Pause':
            return_value = control.pid_pause(pid_id)
        elif action == 'Resume':
            return_value = control.pid_resume(pid_id)
        flash(gettext("Daemon response to PID controller %(act)s command: "
                      "%(rval)s", act=action, rval=return_value), "success")
    except Exception as err:
        flash(gettext("PID Error: %(msg)s", msg=err), "error")


#
# Relay manipulation
#

def relay_on_off(form_relay):
    action = '{action} {controller}'.format(
        action=gettext("Actuate"),
        controller=gettext("Relay"))
    error = []

    try:
        control = DaemonControl()
        if int(form_relay.relay_pin.data) <= 0:
            error.append(gettext("Cannot modulate relay with a GPIO of 0"))
        elif form_relay.sec_on_submit.data:
            if float(form_relay.sec_on.data) <= 0:
                error.append(gettext("Value must be greater than 0"))
            else:
                return_value = control.relay_on(form_relay.relay_id.data,
                                                float(form_relay.sec_on.data))
                flash(gettext("Relay turned on for %(sec)s seconds: %(rvalue)s",
                              sec=form_relay.sec_on.data,
                              rvalue=return_value),
                      "success")
        elif form_relay.turn_on.data:
            return_value = control.relay_on(form_relay.relay_id.data, 0)
            flash(gettext("Relay turned on: %(rvalue)s",
                          rvalue=return_value), "success")
        elif form_relay.turn_off.data:
            return_value = control.relay_off(form_relay.relay_id.data)
            flash(gettext("Relay turned off: %(rvalue)s",
                          rvalue=return_value), "success")
    except ValueError as except_msg:
        error.append('{err}: {msg}'.format(
            err=gettext("Invalid value"),
            msg=except_msg))
    except Exception as except_msg:
        error.append(except_msg)

    flash_success_errors(error, action, url_for('page_routes.page_relay'))


def relay_add(form_add_relay):
    action = '{action} {controller}'.format(
        action=gettext("Add"),
        controller=gettext("Relay"))
    error = []

    if form_add_relay.validate():
        for _ in range(0, form_add_relay.numberRelays.data):
            try:
                new_relay = databases.models.Relay().save()
                display_order = csv_to_list_of_int(databases.models.DisplayOrder.query.first().relay)
                databases.models.DisplayOrder.query.first().relay = add_display_order(
                    display_order, new_relay.id)
                db.session.commit()
                manipulate_relay(gettext('Add'), new_relay.id)
            except sqlalchemy.exc.OperationalError as except_msg:
                error.append(except_msg)
            except sqlalchemy.exc.IntegrityError as except_msg:
                error.append(except_msg)
        flash_success_errors(error, action, url_for('page_routes.page_relay'))
    else:
        flash_form_errors(form_add_relay)


def relay_mod(form_relay):
    action = '{action} {controller}'.format(
        action=gettext("Modify"),
        controller=gettext("Relay"))
    error = []

    if form_relay.validate():
        try:
            mod_relay = databases.models.Relay.query.filter(
                databases.models.Relay.id == form_relay.relay_id.data).first()
            mod_relay.name = form_relay.name.data
            setup_pin = False
            if mod_relay.pin is not form_relay.gpio.data:
                setup_pin = True
            mod_relay.pin = form_relay.gpio.data
            mod_relay.amps = form_relay.amps.data
            mod_relay.trigger = form_relay.trigger.data
            mod_relay.on_at_start = form_relay.on_at_start.data
            db.session.commit()
            manipulate_relay(gettext('Modify'),
                             form_relay.relay_id.data,
                             setup_pin)
        except Exception as except_msg:
            error.append(except_msg)
        flash_success_errors(error, action, url_for('page_routes.page_relay'))
    else:
        flash_form_errors(form_relay)


def relay_del(form_relay):
    action = '{action} {controller}'.format(
        action=gettext("Delete"),
        controller=gettext("Relay"))
    error = []

    if form_relay.validate():
        try:
            delete_entry_with_id(databases.models.Relay,
                                 form_relay.relay_id.data)
            display_order = csv_to_list_of_int(databases.models.DisplayOrder.query.first().relay)
            display_order.remove(int(form_relay.relay_id.data))
            databases.models.DisplayOrder.query.first().relay = list_to_csv(display_order)
            db.session.commit()
            manipulate_relay(gettext('Delete'), form_relay.relay_id.data)
        except Exception as except_msg:
            error.append(except_msg)
        flash_success_errors(error, action, url_for('page_routes.page_relay'))
    else:
        flash_form_errors(form_relay)


def relay_reorder(form_relay, display_order):
    action = '{action} {controller}'.format(
        action=gettext("Reorder"),
        controller=gettext("Relay"))
    error = []

    if form_relay.validate():
        try:
            if form_relay.order_up.data:
                status, reord_list = reorder_list(
                    display_order,
                    form_relay.relay_id.data,
                    'up')
            elif form_relay.order_down.data:
                status, reord_list = reorder_list(
                    display_order,
                    form_relay.relay_id.data,
                    'down')
            if status == 'success':
                databases.models.DisplayOrder.query.first().relay = ','.join(reord_list)
                db.session.commit()
            else:
                error.append(reord_list)
        except Exception as except_msg:
            error.append(except_msg)
        flash_success_errors(error, action, url_for('page_routes.page_relay'))
    else:
        flash_form_errors(form_relay)


#
# Relay conditional manipulation
#

def relay_conditional_add(form_add_relay_cond):
    action = '{action} {controller}'.format(
        action=gettext("Add"),
        controller=gettext("Relay Conditional"))
    error = []

    if form_add_relay_cond.validate():
        for _ in range(0, form_add_relay_cond.numberRelayConditionals.data):
            try:
                databases.models.RelayConditional().save
            except sqlalchemy.exc.OperationalError as except_msg:
                error.append(except_msg)
            except sqlalchemy.exc.IntegrityError as except_msg:
                error.append(except_msg)
        flash_success_errors(error, action, url_for('page_routes.page_sensor'))
    else:
        flash_form_errors(form_add_relay_cond)


def relay_conditional_mod(form_relay_cond):
    action = None
    error = []

    try:
        if form_relay_cond.activate.data:
            action = '{action} {controller}'.format(
                action=gettext("Activate"),
                controller=gettext("Relay Conditional"))
            relay_cond = databases.models.RelayConditional.query.filter(
                databases.models.RelayConditional.id == form_relay_cond.relay_id.data).first()
            relay_cond.is_activated = True
            db.session.commit()
        elif form_relay_cond.deactivate.data:
            action = '{action} {controller}'.format(
                action=gettext("Deactivate"),
                controller=gettext("Relay Conditional"))
            relay_cond = databases.models.RelayConditional.query.filter(
                databases.models.RelayConditional.id == form_relay_cond.relay_id.data).first()
            relay_cond.is_activated = False
            db.session.commit()
        elif form_relay_cond.delete.data:
            action = '{action} {controller}'.format(
                action=gettext("Delete"),
                controller=gettext("Relay Conditional"))
            delete_entry_with_id(databases.models.RelayConditional,
                                 form_relay_cond.relay_id.data)
        elif (form_relay_cond.save.data and
                form_relay_cond.validate()):
            action = '{action} {controller}'.format(
                action=gettext("Modify"),
                controller=gettext("Relay Conditional"))
            mod_relay = databases.models.RelayConditional.query.filter(
                databases.models.RelayConditional.id == form_relay_cond.relay_id.data).first()
            mod_relay.name = form_relay_cond.name.data
            mod_relay.if_relay_id = form_relay_cond.if_relay_id.data
            mod_relay.if_action = form_relay_cond.if_relay_action.data
            mod_relay.if_duration = form_relay_cond.if_relay_duration.data
            mod_relay.do_relay_id = form_relay_cond.do_relay_id.data
            mod_relay.do_action = form_relay_cond.do_relay_action.data
            mod_relay.do_duration = form_relay_cond.do_relay_duration.data
            mod_relay.execute_command = form_relay_cond.do_execute.data
            mod_relay.email_notify = form_relay_cond.do_notify.data
            mod_relay.flash_lcd = form_relay_cond.do_flash_lcd.data
            db.session.commit()
        else:
            flash_form_errors(form_relay_cond)
            return redirect(url_for('page_routes.page_relay'))
    except Exception as except_msg:
        error.append(except_msg)

    flash_success_errors(error, action, url_for('page_routes.page_sensor'))


#
# Sensor manipulation
#

def sensor_add(form_add_sensor):
    action = '{action} {controller}'.format(
        action=gettext("Add"),
        controller=gettext("Sensor"))
    error = []

    if form_add_sensor.validate():
        for _ in range(0, form_add_sensor.numberSensors.data):
            display_order = csv_to_list_of_int(databases.models.DisplayOrder.query.first().sensor)
            new_sensor = databases.models.Sensor()
            new_sensor.device = form_add_sensor.sensor.data
            new_sensor.name = '{}'.format(form_add_sensor.sensor.data)
            if GPIO.RPI_INFO['P1_REVISION'] in [2, 3]:
                new_sensor.i2c_bus = 1
                new_sensor.multiplexer_bus = 1
            else:
                new_sensor.i2c_bus = 0
                new_sensor.multiplexer_bus = 0

            # Process monitors
            if form_add_sensor.sensor.data == 'RPiCPULoad':
                new_sensor.device_type = 'cpu_load'
                new_sensor.measurements = 'cpu_load_1m,cpu_load_5m,cpu_load_15m'
                new_sensor.location = 'RPi'
            elif form_add_sensor.sensor.data == 'EDGE':
                new_sensor.device_type = 'edgedetect'
                new_sensor.measurements = 'edge'

            # Environmental Sensors
            # Temperature
            elif form_add_sensor.sensor.data in ['ATLAS_PT1000', 'DS18B20',
                                                 'RPi', 'TMP006']:
                new_sensor.device_type = 'tsensor'
                new_sensor.measurements = 'temperature'
                if form_add_sensor.sensor.data == 'ATLAS_PT1000':
                    new_sensor.location = '0x66'
                elif form_add_sensor.sensor.data == 'RPi':
                    new_sensor.location = 'RPi'
                elif form_add_sensor.sensor.data == 'TMP006':
                    new_sensor.measurements = 'temperature_object,temperature_die'
                    new_sensor.location = '0x40'

            # Temperature/Humidity
            elif form_add_sensor.sensor.data in ['AM2315', 'DHT11', 'DHT22',
                                                 'HTU21D', 'SHT1x_7x',
                                                 'SHT2x']:
                new_sensor.device_type = 'htsensor'
                new_sensor.measurements = 'dewpoint,humidity,temperature'
                if form_add_sensor.sensor.data == 'AM2315':
                    new_sensor.location = '0x5c'
                elif form_add_sensor.sensor.data == 'HTU21D':
                    new_sensor.location = '0x40'
                elif form_add_sensor.sensor.data == 'SHT2x':
                    new_sensor.location = '0x40'

            # Chirp moisture sensor
            elif form_add_sensor.sensor.data == 'CHIRP':
                new_sensor.device_type = 'moistsensor'
                new_sensor.measurements = 'lux,moisture,temperature'
                new_sensor.location = '0x20'

            # CO2
            elif form_add_sensor.sensor.data == 'K30':
                new_sensor.device_type = 'co2sensor'
                new_sensor.measurements = 'co2'
                new_sensor.location = 'Tx/Rx'

            # Pressure
            elif form_add_sensor.sensor.data in ['BME280', 'BMP']:
                new_sensor.device_type = 'presssensor'
                if form_add_sensor.sensor.data == 'BME280':
                    new_sensor.measurements = 'altitude,humidity,pressure,temperature'
                    new_sensor.location = '0x76'
                elif form_add_sensor.sensor.data == 'BMP':
                    new_sensor.measurements = 'altitude,pressure,temperature'
                    new_sensor.location = '0x77'

            # Light
            elif form_add_sensor.sensor.data == 'TSL2561':
                new_sensor.device_type = 'luxsensor'
                new_sensor.measurements = 'lux'
                new_sensor.location = '0x39'

            # Analog to Digital Converters
            elif form_add_sensor.sensor.data in ['ADS1x15', 'MCP342x']:
                new_sensor.device_type = 'analogsensor'
                new_sensor.measurements = 'voltage'
                if form_add_sensor.sensor.data == 'ADS1x15':
                    new_sensor.location = '0x48'
                    new_sensor.adc_volts_min = -4.096
                    new_sensor.adc_volts_max = 4.096
                elif form_add_sensor.sensor.data == 'MCP342x':
                    new_sensor.location = '0x68'
                    new_sensor.adc_volts_min = -2.048
                    new_sensor.adc_volts_max = 2.048

            try:
                new_sensor.save()

                databases.models.DisplayOrder.query.first().sensor = add_display_order(
                    display_order, new_sensor.id)
                db.session.commit()

                flash(gettext(
                    "%(type)s Sensor with ID %(id)s (%(uuid)s) successfully added",
                    type=form_add_sensor.sensor.data,
                    id=new_sensor.id,
                    uuid=new_sensor.unique_id),
                      "success")
            except sqlalchemy.exc.OperationalError as except_msg:
                error.append(except_msg)
            except sqlalchemy.exc.IntegrityError as except_msg:
                error.append(except_msg)
        flash_success_errors(error, action, url_for('page_routes.page_sensor'))
    else:
        flash_form_errors(form_add_sensor)


def sensor_mod(form_mod_sensor):
    action = '{action} {controller}'.format(
        action=gettext("Modify"),
        controller=gettext("Sensor"))
    error = []

    try:
        mod_sensor = databases.models.Sensor.query.filter(
            databases.models.Sensor.id == form_mod_sensor.modSensor_id.data).first()

        # if not form_mod_sensor.modLocation.data:
        #     error.append(gettext(
        #         "Invalid device GPIO/I2C address/location"))
        if mod_sensor.is_activated:
            error.append(gettext(
                "Deactivate sensor controller before modifying its "
                "settings"))
        if (mod_sensor.device == 'AM2315' and
                form_mod_sensor.modPeriod.data < 7):
            error.append(gettext(
                "Choose a Read Period equal to or greater than 7. The "
                "AM2315 may become unresponsive if the period is "
                "below 7."))
        if ((form_mod_sensor.modPeriod.data < mod_sensor.pre_relay_duration) and
                mod_sensor.pre_relay_duration):
            error.append(gettext(
                "The Read Period cannot be less than the Pre-Relay "
                "Duration"))

        if not error:
            mod_sensor.name = form_mod_sensor.modName.data
            mod_sensor.i2c_bus = form_mod_sensor.modBus.data
            mod_sensor.location = form_mod_sensor.modLocation.data
            mod_sensor.power_pin = form_mod_sensor.modPowerPin.data
            mod_sensor.power_state = form_mod_sensor.modPowerState.data
            mod_sensor.multiplexer_address = form_mod_sensor.modMultiplexAddress.data
            mod_sensor.multiplexer_bus = form_mod_sensor.modMultiplexBus.data
            mod_sensor.multiplexer_channel = form_mod_sensor.modMultiplexChannel.data
            mod_sensor.adc_channel = form_mod_sensor.modADCChannel.data
            mod_sensor.adc_gain = form_mod_sensor.modADCGain.data
            mod_sensor.adc_resolution = form_mod_sensor.modADCResolution.data
            mod_sensor.adc_measure = form_mod_sensor.modADCMeasure.data.replace(" ", "_")
            mod_sensor.adc_measure_units = form_mod_sensor.modADCMeasureUnits.data
            mod_sensor.adc_volts_min = form_mod_sensor.modADCVoltsMin.data
            mod_sensor.adc_volts_max = form_mod_sensor.modADCVoltsMax.data
            mod_sensor.adc_units_min = form_mod_sensor.modADCUnitsMin.data
            mod_sensor.adc_units_max = form_mod_sensor.modADCUnitsMax.data
            mod_sensor.switch_edge = form_mod_sensor.modSwitchEdge.data
            mod_sensor.switch_bouncetime = form_mod_sensor.modSwitchBounceTime.data
            mod_sensor.switch_reset_period = form_mod_sensor.modSwitchResetPeriod.data
            mod_sensor.pre_relay_id = form_mod_sensor.modPreRelayID.data
            mod_sensor.pre_relay_duration = form_mod_sensor.modPreRelayDuration.data
            mod_sensor.period = form_mod_sensor.modPeriod.data
            mod_sensor.sht_clock_pin = form_mod_sensor.modSHTClockPin.data
            mod_sensor.sht_voltage = form_mod_sensor.modSHTVoltage.data
            db.session.commit()
    except Exception as except_msg:
        error.append(except_msg)

    flash_success_errors(error, action, url_for('page_routes.page_sensor'))


def sensor_del(form_mod_sensor):
    action = '{action} {controller}'.format(
        action=gettext("Delete"),
        controller=gettext("Sensor"))
    error = []

    try:
        sensor = databases.models.Sensor.query.filter(
            databases.models.Sensor.id == form_mod_sensor.modSensor_id.data).first()
        if sensor.is_activated:
            sensor_deactivate_associated_controllers(
                form_mod_sensor.modSensor_id.data)
            activate_deactivate_controller(
                'deactivate', 'Sensor',
                form_mod_sensor.modSensor_id.data)

        sensor_cond =databases.models. SensorConditional.query.all()
        for each_sensor_cond in sensor_cond:
            if each_sensor_cond.sensor_id == form_mod_sensor.modSensor_id.data:
                delete_entry_with_iddatabases.models(databases.models.SensorConditional,
                                     each_sensor_cond.id)

        delete_entry_with_id(databases.models.Sensor,
                             form_mod_sensor.modSensor_id.data)
        try:
            display_order = csv_to_list_of_int(databases.models.DisplayOrder.query.first().sensor)
            display_order.remove(int(form_mod_sensor.modSensor_id.data))
            databases.models.DisplayOrder.query.first().sensor = list_to_csv(display_order)
        except:  # id not in list
            pass
        db.session.commit()
    except Exception as except_msg:
        error.append(except_msg)

    flash_success_errors(error, action, url_for('page_routes.page_sensor'))


def sensor_reorder(form_mod_sensor, display_order):
    action = '{action} {controller}'.format(
        action=gettext("Reorder"),
        controller=gettext("Sensor"))
    error = []

    try:
        status = None
        if form_mod_sensor.orderSensorUp.data:
            status, reord_list = reorder_list(
                display_order, form_mod_sensor.modSensor_id.data, 'up')
        elif form_mod_sensor.orderSensorDown.data:
            status, reord_list = reorder_list(
                display_order, form_mod_sensor.modSensor_id.data, 'down')
        if status == 'success':
            order_sensor = databases.models.DisplayOrder.query.first()
            order_sensor.sensor = ','.join(reord_list)
            db.session.commit()
        elif status == 'error':
            error.append(reord_list)
    except Exception as except_msg:
        error.append(except_msg)

    flash_success_errors(error, action, url_for('page_routes.page_sensor'))


def sensor_activate(form_mod_sensor):
    sensor = databases.models.Sensor.query.filter(
        databases.models.Sensor.id == form_mod_sensor.modSensor_id.data).first()
    if not sensor.location:
        flash("Cannot activate sensor without the GPIO/I2C Address/Port "
              "to communicate with it set.", "error")
        return redirect('/sensor')
    activate_deactivate_controller('activate',
                                   'Sensor',
                                   form_mod_sensor.modSensor_id.data)


def sensor_deactivate(form_mod_sensor):
    sensor_deactivate_associated_controllers(
        form_mod_sensor.modSensor_id.data)
    activate_deactivate_controller('deactivate',
                                   'Sensor',
                                   form_mod_sensor.modSensor_id.data)


# Deactivate any active PID or LCD controllers using this sensor
def sensor_deactivate_associated_controllers(sensor_id):
    pid = (databases.models.PID.query
           .filter(databases.models.PID.sensor_id == sensor_id)
           .filter(databases.models.PID.is_activated == True)
           ).all()
    if pid:
        for each_pid in pid:
            activate_deactivate_controller('deactivate',
                                           'PID',
                                           each_pid.id)
    lcd = databases.models.LCD.query.filter(databases.models.LCD.is_activated)
    for each_lcd in lcd:
        if sensor_id in [each_lcd.line_1_sensor_id,
                         each_lcd.line_2_sensor_id,
                         each_lcd.line_3_sensor_id,
                         each_lcd.line_4_sensor_id]:
            activate_deactivate_controller('deactivate',
                                           'LCD',
                                           each_lcd.id)


#
# Sensor conditional manipulation
#

def sensor_conditional_add(form_mod_sensor):
    action = '{action} {controller}'.format(
        action=gettext("Add"),
        controller=gettext("Sensor Conditional"))
    error = []

    try:
        new_sensor_cond = databases.models.SensorConditional()
        new_sensor_cond.sensor_id = form_mod_sensor.modSensor_id.data
        new_sensor_cond.save()
        check_refresh_conditional(form_mod_sensor.modSensor_id.data,
                                  'add',
                                  new_sensor_cond.id)
    except sqlalchemy.exc.OperationalError as except_msg:
        error.append(except_msg)
    except sqlalchemy.exc.IntegrityError as except_msg:
        error.append(except_msg)

    flash_success_errors(error, action, url_for('page_routes.page_sensor'))


def sensor_conditional_mod(form_mod_sensor_cond):
    action = None
    error = []

    if form_mod_sensor_cond.delSubmit.data:
        action = '{action} {controller}'.format(
            action=gettext("Delete"),
            controller=gettext("Sensor Conditional"))
        try:
            delete_entry_with_id(databases.models.SensorConditional, form_mod_sensor_cond.modCondSensor_id.data)
            check_refresh_conditional(
                form_mod_sensor_cond.modSensor_id.data,
                'del',
                form_mod_sensor_cond.modCondSensor_id.data)
        except Exception as except_msg:
            error.append(except_msg)
    elif (form_mod_sensor_cond.modSubmit.data and
            form_mod_sensor_cond.validate()):
        action = '{action} {controller}'.format(
            action=gettext("Modify"),
            controller=gettext("Sensor Conditional"))
        try:
            if (form_mod_sensor_cond.DoRecord.data == 'photoemail' or form_mod_sensor_cond.DoRecord.data == 'videoemail') and not form_mod_sensor_cond.DoNotify.data:
                error.append(gettext("A notification email address is "
                                     "required if the record and email "
                                     "option is selected"))
            else:
                mod_sensor =databases.models. SensorConditional.query.filter(
                    databases.models.SensorConditional.id == form_mod_sensor_cond.modCondSensor_id.data).first()
                mod_sensor.name = form_mod_sensor_cond.modCondName.data
                mod_sensor.period = form_mod_sensor_cond.Period.data
                mod_sensor.measurement_type = form_mod_sensor_cond.MeasureType.data
                mod_sensor.edge_select = form_mod_sensor_cond.EdgeSelect.data
                mod_sensor.edge_detected = form_mod_sensor_cond.EdgeDetected.data
                mod_sensor.gpio_state = form_mod_sensor_cond.GPIOState.data
                mod_sensor.direction = form_mod_sensor_cond.Direction.data
                mod_sensor.setpoint = form_mod_sensor_cond.Setpoint.data
                mod_sensor.relay_id = form_mod_sensor_cond.modCondRelayID.data
                mod_sensor.relay_state = form_mod_sensor_cond.RelayState.data
                mod_sensor.relay_on_duration = form_mod_sensor_cond.RelayDuration.data
                mod_sensor.execute_command = form_mod_sensor_cond.DoExecute.data
                mod_sensor.email_notify = form_mod_sensor_cond.DoNotify.data
                mod_sensor.flash_lcd = form_mod_sensor_cond.DoFlashLCD.data
                mod_sensor.camera_record = form_mod_sensor_cond.DoRecord.data
                db.session.commit()
                check_refresh_conditional(
                    form_mod_sensor_cond.modSensor_id.data,
                    'mod',
                    form_mod_sensor_cond.modCondSensor_id.data)
        except Exception as except_msg:
            error.append(except_msg)
    elif form_mod_sensor_cond.activateSubmit.data:
        action = '{action} {controller}'.format(
            action=gettext("Activate"),
            controller=gettext("Sensor Conditional"))
        try:
            mod_sensor = databases.models.SensorConditional.query.filter(
                databases.models.SensorConditional.id == form_mod_sensor_cond.modCondSensor_id.data).first()
            sensor = databases.models.Sensor.query.filter(
                databases.models.Sensor.id == mod_sensor.sensor_id).first()

            device_specific_configured = False
            cond_configured = False

            # Ensure device-specific settings configured properly
            if sensor.device == 'EDGE' and mod_sensor.edge_detected:
                device_specific_configured = True
            elif (sensor.device != 'EDGE' and
                    mod_sensor.period and
                    mod_sensor.measurement_type and
                    mod_sensor.direction):
                device_specific_configured = True

            # Ensure universal conditional settings configured properly
            if ((mod_sensor.relay_id and mod_sensor.relay_state) or
                    mod_sensor.execute_command or
                    mod_sensor.email_notify or
                    mod_sensor.flash_lcd or
                    mod_sensor.camera_record):
                cond_configured = True

            if device_specific_configured and cond_configured:
                mod_sensor.is_activated = True
                db.session.commit()
                check_refresh_conditional(
                    form_mod_sensor_cond.modSensor_id.data,
                    'mod',
                    form_mod_sensor_cond.modCondSensor_id.data)
            else:
                error.append(gettext(
                    "Cannot activate sensor conditional %(cond)s because "
                    "of an incomplete configuration",
                    cond=form_mod_sensor_cond.modCondSensor_id.data))
        except Exception as except_msg:
            error.append(except_msg)
    elif form_mod_sensor_cond.deactivateSubmit.data:
        action = '{action} {controller}'.format(
            action=gettext("Deactivate"),
            controller=gettext("Sensor Conditional"))
        try:
            mod_sensor = databases.models.SensorConditional.query.filter(
                databases.models.SensorConditional.id == form_mod_sensor_cond.modCondSensor_id.data).first()
            mod_sensor.is_activated = False
            db.session.commit()
            check_refresh_conditional(
                form_mod_sensor_cond.modSensor_id.data,
                'mod',
                form_mod_sensor_cond.modCondSensor_id.data)
        except Exception as except_msg:
            error.append(except_msg)

    flash_success_errors(error, action, url_for('page_routes.page_sensor'))


def check_refresh_conditional(sensor_id, cond_mod, cond_id):
    sensor = (databases.models.Sensor.query
              .filter(databases.models.Sensor.id == sensor_id)
              .filter(databases.models.Sensor.is_activated == True)
              ).first()
    if sensor:
        control = DaemonControl()
        control.refresh_sensor_conditionals(sensor_id, cond_mod, cond_id)


#
# Timers
#

def timer_add(form_add_timer, timer_type, display_order):
    action = '{action} {controller}'.format(
        action=gettext("Add"),
        controller=gettext("Timer"))
    error = []

    if form_add_timer.validate():
        new_timer = databases.models.Timer()
        new_timer.name = form_add_timer.name.data
        new_timer.relay_id = form_add_timer.relayID.data
        if timer_type == 'time':
            new_timer.timer_type = 'time'
            new_timer.state = form_add_timer.state.data
            new_timer.time_start = form_add_timer.timeStart.data
            new_timer.duration_on = form_add_timer.timeOnDurationOn.data
            new_timer.duration_off = 0
        elif timer_type == 'timespan':
            new_timer.timer_type = 'timespan'
            new_timer.state = form_add_timer.state.data
            new_timer.time_start = form_add_timer.timeStart.data
            new_timer.time_end = form_add_timer.timeEnd.data
        elif timer_type == 'duration':
            if (form_add_timer.durationOn.data <= 0 or
                    form_add_timer.durationOff.data <= 0):
                error.append(gettext("Durations must be greater than 0"))
            else:
                new_timer.timer_type = 'duration'
                new_timer.duration_on = form_add_timer.durationOn.data
                new_timer.duration_off = form_add_timer.durationOff.data

        if not error:
            try:
                new_timer.save()
                databases.models.DisplayOrder.query.first().timer = add_display_order(
                    display_order, new_timer.id)
                db.session.commit()
            except sqlalchemy.exc.OperationalError as except_msg:
                error.append(except_msg)
            except sqlalchemy.exc.IntegrityError  as except_msg:
                error.append(except_msg)

        flash_success_errors(error, action, url_for('page_routes.page_timer'))
    else:
        flash_form_errors(form_add_timer)


def timer_mod(form_timer):
    action = '{action} {controller}'.format(
        action=gettext("Modify"),
        controller=gettext("Timer"))
    error = []

    try:
        mod_timer = databases.models.Timer.query.filter(
            databases.models.Timer.id == form_timer.timer_id.data).first()
        if mod_timer.is_activated:
            error.append(gettext("Deactivate timer controller before "
                                 "modifying its settings"))
            return redirect(url_for('page_routes.page_timer'))
        else:
            mod_timer.name = form_timer.name.data
            mod_timer.relay_id = form_timer.relayID.data
            if mod_timer.timer_type == 'time':
                mod_timer.state = form_timer.state.data
                mod_timer.time_start = form_timer.timeStart.data
                mod_timer.duration_on = form_timer.timeOnDurationOn.data
            elif mod_timer.timer_type == 'timespan':
                mod_timer.state = form_timer.state.data
                mod_timer.time_start = form_timer.timeStart.data
                mod_timer.time_end = form_timer.timeEnd.data
            elif mod_timer.timer_type == 'duration':
                mod_timer.duration_on = form_timer.durationOn.data
                mod_timer.duration_off = form_timer.durationOff.data
            db.session.commit()
    except Exception as except_msg:
        error.append(except_msg)

    flash_success_errors(error, action, url_for('page_routes.page_timer'))


def timer_del(form_timer):
    action = '{action} {controller}'.format(
        action=gettext("Delete"),
        controller=gettext("Timer"))
    error = []

    try:
        delete_entry_with_id(databases.models.Timer,
                             form_timer.timer_id.data)
        display_order = csv_to_list_of_int(databases.models.DisplayOrder.query.first().timer)
        display_order.remove(int(form_timer.timer_id.data))
        databases.models.DisplayOrder.query.first().timer = list_to_csv(display_order)
        db.session.commit()
    except Exception as except_msg:
        error.append(except_msg)

    flash_success_errors(error, action, url_for('page_routes.page_timer'))


def timer_reorder(form_timer, display_order):
    action = '{action} {controller}'.format(
        action=gettext("Reorder"),
        controller=gettext("Timer"))
    error = []

    try:
        status = ''
        reord_list = ''
        if form_timer.orderTimerUp.data:
            status, reord_list = reorder_list(display_order,
                                              form_timer.timer_id.data,
                                              'up')
        elif form_timer.orderTimerDown.data:
            status, reord_list = reorder_list(display_order,
                                              form_timer.timer_id.data,
                                              'down')
        if status == 'success':
            databases.models.DisplayOrder.query.first().timer = ','.join(reord_list)
            db.session.commit()
        else:
            error.append(reord_list)
    except Exception as except_msg:
        error.append(except_msg)

    flash_success_errors(error, action, url_for('page_routes.page_timer'))


def timer_activate(form_timer):
    activate_deactivate_controller(
        'activate', 'Timer', form_timer.timer_id.data)


def timer_deactivate(form_timer):
    activate_deactivate_controller(
        'deactivate', 'Timer', form_timer.timer_id.data)


#
# User manipulation
#

def user_add(form_add_user):
    action = '{action} {controller}'.format(
        action=gettext("Add"),
        controller=gettext("User"))
    error = []

    if form_add_user.validate():
        new_user = databases.models.User()
        if not test_username(form_add_user.addUsername.data):
            error.append(gettext(
                "Invalid user name. Must be between 2 and 64 characters "
                "and only contain letters and numbers."))

        if not test_password(form_add_user.addPassword.data):
            error.append(gettext(
                "Invalid password. Must be between 6 and 64 characters "
                "and only contain letters, numbers, and symbols."))

        if form_add_user.addPassword.data != form_add_user.addPassword_repeat.data:
            error.append(gettext("Passwords do not match. Please try again."))

        if not error:
            new_user.user_name = form_add_user.addUsername.data
            new_user.user_email = form_add_user.addEmail.data
            new_user.set_password(form_add_user.addPassword.data)
            role = databases.models.Role.query.filter(
                databases.models.Role.name == form_add_user.addGroup.data).first().id
            new_user.user_role = role
            new_user.user_theme = 'slate'
            try:
                new_user.save()
            except sqlalchemy.exc.OperationalError as except_msg:
                error.append(except_msg)
            except sqlalchemy.exc.IntegrityError as except_msg:
                error.append(except_msg)

        flash_success_errors(error, action, url_for('settings_routes.settings_users'))
    else:
        flash_form_errors(form_add_user)


def user_mod(form_mod_user):
    action = '{action} {controller}'.format(
        action=gettext("Modify"),
        controller=gettext("User"))
    error = []

    try:
        mod_user = databases.models.User.query.filter(
            databases.models.User.user_name == form_mod_user.modUsername.data).first()
        mod_user.user_email = form_mod_user.modEmail.data
        # Only change the password if it's entered in the form
        logout_user = False
        if form_mod_user.modPassword.data != '':
            if not test_password(form_mod_user.modPassword.data):
                error.append(gettext("Invalid password"))
            if form_mod_user.modPassword.data == form_mod_user.modPassword_repeat.data:
                mod_user.user_password_hash = bcrypt.hashpw(
                    form_mod_user.modPassword.data.encode('utf-8'),
                    bcrypt.gensalt())
                if session['user_name'] == form_mod_user.modUsername.data:
                    logout_user = True
            else:
                error.append(gettext("Passwords do not match. Please try again."))

        if not error:
            role = databases.models.Role.query.filter(
                databases.models.Role.name == form_mod_user.modGroup.data).first().id
            mod_user.user_role = role
            mod_user.user_theme = form_mod_user.modTheme.data
            if session['user_name'] == form_mod_user.modUsername.data:
                session['user_theme'] = form_mod_user.modTheme.data
            db.session.commit()
            if logout_user:
                return 'logout'
    except Exception as except_msg:
        error.append(except_msg)

    flash_success_errors(error, action, url_for('settings_routes.settings_users'))


def user_del(form_del_user):
    try:
        if form_del_user.validate():
            delete_user(form_del_user.delUsername.data)
            if form_del_user.delUsername.data == session['user_name']:
                return 'logout'
        else:
            flash_form_errors(form_del_user)
    except Exception as except_msg:
        flash(gettext("Error: %(msg)s",
                      msg='{action} {user}: {err}'.format(
                          action=gettext("Delete"),
                          user=form_del_user.delUsername.data,
                          err=except_msg)),
              "error")


#
# Settings modifications
#

def settings_general_mod(form_mod_general):
    """ Modify General settings """
    action = '{action} {controller}'.format(
        action=gettext("Modify"),
        controller=gettext("General Settings"))
    error = []

    try:
        if form_mod_general.validate():
            mod_misc = databases.models.Misc.query.first()
            force_https = mod_misc.force_https
            mod_misc.language = form_mod_general.language.data
            mod_misc.force_https = form_mod_general.forceHTTPS.data
            mod_misc.hide_alert_success = form_mod_general.hideAlertSuccess.data
            mod_misc.hide_alert_info = form_mod_general.hideAlertInfo.data
            mod_misc.relay_stats_volts = form_mod_general.relayStatsVolts.data
            mod_misc.relay_stats_cost = form_mod_general.relayStatsCost.data
            mod_misc.relay_stats_currency = form_mod_general.relayStatsCurrency.data
            mod_misc.relay_stats_dayofmonth = form_mod_general.relayStatsDayOfMonth.data
            mod_misc.hide_alert_warning = form_mod_general.hideAlertWarning.data
            mod_misc.stats_opt_out = form_mod_general.stats_opt_out.data
            db.session.commit()

            if force_https != form_mod_general.forceHTTPS.data:
                # Force HTTPS option changed.
                # Reload web server with new settings.
                wsgi_file = INSTALL_DIRECTORY+'/mycodo_flask.wsgi'
                with open(wsgi_file, 'a'):
                    os.utime(wsgi_file, None)
        else:
            flash_form_errors(form_mod_general)
    except Exception as except_msg:
        error.append(except_msg)

    flash_success_errors(error, action, url_for('settings_routes.settings_general'))


def settings_alert_mod(form_mod_alert):
    """ Modify Alert settings """
    action = '{action} {controller}'.format(
        action=gettext("Modify"),
        controller=gettext("Alert Settings"))
    error = []

    try:
        if form_mod_alert.validate():
            mod_smtp = databases.models.SMTP.query.one()
            if form_mod_alert.sendTestEmail.data:
                send_email(
                    mod_smtp.host, mod_smtp.ssl, mod_smtp.port,
                    mod_smtp.user, mod_smtp.passw, mod_smtp.email_from,
                    form_mod_alert.testEmailTo.data,
                    "This is a test email from Mycodo")
                flash(gettext("Test email sent to %(recip)s. Check your "
                              "inbox to see if it was successful.",
                              recip=form_mod_alert.testEmailTo.data),
                      "success")
                return redirect(url_for('settings_routes.settings_alerts'))
            else:
                mod_smtp.host = form_mod_alert.smtpHost.data
                mod_smtp.port = form_mod_alert.smtpPort.data
                mod_smtp.ssl = form_mod_alert.sslEnable.data
                mod_smtp.user = form_mod_alert.smtpUser.data
                if form_mod_alert.smtpPassword.data:
                    mod_smtp.passw = form_mod_alert.smtpPassword.data
                mod_smtp.email_from = form_mod_alert.smtpFromEmail.data
                mod_smtp.hourly_max = form_mod_alert.smtpMaxPerHour.data
                db.session.commit()
        else:
            flash_form_errors(form_mod_alert)
    except Exception as except_msg:
        error.append(except_msg)

    flash_success_errors(error, action, url_for('settings_routes.settings_alerts'))


def camera_add(form_camera):
    action = '{action} {controller}'.format(
        action=gettext("Add"),
        controller=gettext("Camera"))
    error = []

    if form_camera.validate():
        new_camera = databases.models.Camera()
        if databases.models.Camera.query.filter(databases.models.Camera.name == form_camera.name.data).count():
            flash("You must choose a unique name", "error")
            return redirect(url_for('settings_routes.settings_camera'))
        new_camera.name = form_camera.name.data
        new_camera.camera_type = form_camera.camera_type.data
        new_camera.library = CAMERAS_SUPPORTED[form_camera.camera_type.data]
        if not error:
            try:
                new_camera.save()
            except sqlalchemy.exc.OperationalError as except_msg:
                error.append(except_msg)
            except sqlalchemy.exc.IntegrityError  as except_msg:
                error.append(except_msg)

        flash_success_errors(error, action, url_for('settings_routes.settings_camera'))
    else:
        flash_form_errors(form_camera)


def camera_mod(form_camera):
    action = '{action} {controller}'.format(
        action=gettext("Modify"),
        controller=gettext("Camera"))
    error = []

    try:
        if (databases.models.Camera.query
                    .filter(databases.models.Camera.id != form_camera.camera_id.data)
                    .filter(databases.models.Camera.name == form_camera.name.data).count()):
            flash("You must choose a unique name", "error")
            return redirect(url_for('settings_routes.settings_camera'))

        mod_camera = databases.models.Camera.query.filter(
            databases.models.Camera.id == form_camera.camera_id.data).first()
        mod_camera.name = form_camera.name.data
        mod_camera.camera_type = form_camera.camera_type.data
        mod_camera.library = form_camera.library.data
        mod_camera.opencv_device = form_camera.opencv_device.data
        mod_camera.hflip = form_camera.hflip.data
        mod_camera.vflip = form_camera.vflip.data
        mod_camera.rotation = form_camera.rotation.data
        mod_camera.height = form_camera.height.data
        mod_camera.width = form_camera.width.data
        mod_camera.brightness = form_camera.brightness.data
        mod_camera.contrast = form_camera.contrast.data
        mod_camera.exposure = form_camera.exposure.data
        mod_camera.gain = form_camera.gain.data
        mod_camera.hue = form_camera.hue.data
        mod_camera.saturation = form_camera.saturation.data
        mod_camera.white_balance = form_camera.white_balance.data
        mod_camera.relay_id = form_camera.relay_id.data
        mod_camera.cmd_pre_camera = form_camera.cmd_pre_camera.data
        mod_camera.cmd_post_camera = form_camera.cmd_post_camera.data
        mod_camera.relay_id = form_camera.relay_id.data
        db.session.commit()
    except Exception as except_msg:
        error.append(except_msg)

    flash_success_errors(error, action, url_for('settings_routes.settings_camera'))


def camera_del(form_camera):
    action = '{action} {controller}'.format(
        action=gettext("Delete"),
        controller=gettext("Camera"))
    error = []
    try:
        delete_entry_with_id(databases.models.Camera,
                             int(form_camera.camera_id.data))
    except Exception as except_msg:
        error.append(except_msg)

    flash_success_errors(error, action, url_for('settings_routes.settings_camera'))


#
# Miscellaneous
#

def authorized(session, role_name, role_id=None):
    if role_id:
        user = databases.models.User.query.filter(databases.models.User.id == role_id).first()
    else:
        user = databases.models.User.query.filter(databases.models.Role.name == role_name).first()
    if user and user.role.name == session['user_role']:
            return True
    return False


def db_retrieve_table(table, first=False, device_id=''):
    """ Return table data from database SQL query """
    if first:
        return_table = table.query.first()
    elif device_id:
        return_table = table.query.filter(
            table.id == device_id).first()
    else:
        return_table = table.query.all()
    return return_table


def delete_user(username):
    """ Delete user from SQL database """
    try:
        user = databases.models.User.query.filter(
            databases.models.User.user_name == username).first()
        user.delete(db.session)
        flash(gettext("Success: %(msg)s",
                      msg='{action} {user}'.format(
                          action=gettext("Delete"),
                          user=username)),
              "success")
        return 1
    except sqlalchemy.orm.exc.NoResultFound:
        flash(gettext("Error: %(err)s",
                      err=gettext("User not found")),
              "error")
        return 0


def delete_entry_with_id(table, entry_id):
    """ Delete SQL database entry with specific id """
    try:
        entries = table.query.filter(
            table.id == entry_id).first()
        db.session.delete(entries)
        db.session.commit()
        flash(gettext("Success: %(msg)s",
                      msg='{action} {id}'.format(
                          action=gettext("Delete"),
                          id=entry_id)),
              "success")
        return 1
    except sqlalchemy.orm.exc.NoResultFound:
        flash(gettext("Error: %(err)s",
                      err=gettext("Entry with ID %(id)s not found",
                                  id=entry_id)),
              "error")
        flash(gettext("Error: %(msg)s",
                      msg='{action} {id}: {err}'.format(
                          action=gettext("Delete"),
                          id=entry_id,
                          err=gettext("Entry with ID %(id)s not found",
                                      id=entry_id))),
              "success")
        return 0


def deny_guest_user():
    if not authorized(session, 'Guest'):
        flash(gettext("Guests are not permitted to do that"), "error")
        return True


def flash_form_errors(form):
    """ Flashes form errors for easier display """
    for field, errors in form.errors.items():
        for error in errors:
            flash(gettext(u"Error in the %(field)s field - %(err)s",
                          field=getattr(form, field).label.text,
                          err=error),
                  "error")


def flash_success_errors(error, action, redirect_url):
    if error:
        for each_error in error:
            flash(gettext("Error: %(msg)s",
                          msg='{action}: {err}'.format(
                              action=action,
                              err=each_error)),
                  "error")
        return redirect(redirect_url)
    else:
        flash(gettext("Success: %(msg)s",
                      msg=action),
              "success")


def gzipped(f):
    """
    Allows gzipping the response of any view.
    Just add '@gzipped' after the '@app'.
    Used mainly for sending large amounts of data for graphs.
    """
    @functools.wraps(f)
    def view_func(*args, **kwargs):
        @after_this_request
        def zipper(response):
            accept_encoding = request.headers.get('Accept-Encoding', '')

            if 'gzip' not in accept_encoding.lower():
                return response

            response.direct_passthrough = False

            if (response.status_code < 200 or
                response.status_code >= 300 or
                'Content-Encoding' in response.headers):
                return response
            gzip_buffer = IO()
            gzip_file = gzip.GzipFile(mode='wb',
                                      fileobj=gzip_buffer)

            gzip_file.write(response.data)
            gzip_file.close()

            response.data = gzip_buffer.getvalue()
            response.headers['Content-Encoding'] = 'gzip'
            response.headers['Vary'] = 'Accept-Encoding'
            response.headers['Content-Length'] = len(response.data)

            return response

        return f(*args, **kwargs)

    return view_func


def add_display_order(display_order, device_id):
    """ Add integer ID to list of string IDs """
    if display_order:
        display_order.append(device_id)
        display_order = [str(i) for i in display_order]
        return ','.join(display_order)
    return str(device_id)


def list_to_csv(display_order):
    str_csv = [str(i) for i in display_order]
    return ','.join(str_csv)


def reorder_list(modified_list, item, direction):
    """ Reorder entry in a comma-separated list either up or down """
    from_position = modified_list.index(item)
    if direction == "up":
        if from_position == 0:
            return 'error', gettext('Cannot move above the first item in the list')
        to_position = from_position - 1
    elif direction == 'down':
        if from_position == len(modified_list) - 1:
            return 'error', gettext('Cannot move below the last item in the list')
        to_position = from_position + 1
    else:
        return 'error', []
    modified_list.insert(to_position, modified_list.pop(from_position))
    return 'success', modified_list


def test_sql():
    try:
        num_entries = 1000000
        factor_info = 25000
        databases.models.PID.query.delete()
        db.session.commit()
        logger.error("Starting SQL uuid generation test: "
                     "{n} entries...".format(n=num_entries))
        before_count = databases.models.PID.query.count()
        run_times = []
        a = datetime.now()
        for x in range(1, num_entries + 1):
            db.session.add(databases.models.PID())
            if x % factor_info == 0:
                db.session.commit()
                after_count = databases.models.PID.query.count()
                b = datetime.now()
                run_times.append(float((b - a).total_seconds()))
                logger.error("Run Time: {time:.2f} sec, "
                             "New entries: {new}, "
                             "Total entries: {tot}".format(
                                time=run_times[-1],
                                new=after_count - before_count,
                                tot=databases.models.PID.query.count()))
                before_count = databases.models.PID.query.count()
                a = datetime.now()
        avg_run_time = sum(run_times) / float(len(run_times))
        logger.error("Finished. Total: {tot} entries. "
                     "Averages: {avg:.2f} sec, "
                     "{epm:.2f} entries/min".format(
                        tot=databases.models.PID.query.count(),
                        avg=avg_run_time,
                        epm=(factor_info / avg_run_time) * 60.0))
    except Exception as msg:
        logger.error("Error creating entries: {err}".format(err=msg))
