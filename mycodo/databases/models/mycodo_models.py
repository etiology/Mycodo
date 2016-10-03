#!/usr/bin/python
# -*- coding: utf-8 -*-
#
#  update-database.py - Create and update Mycodo SQLite databases
#
#  Copyright (C) 2015  Kyle T. Gabriel
#
#  This file is part of Mycodo
#
#  Mycodo is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Mycodo is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Mycodo. If not, see <http://www.gnu.org/licenses/>.
#
#  Contact at kylegabriel.com
from RPi import GPIO
import datetime

from sqlalchemy import Column, TEXT, INT, REAL, DATETIME, BOOLEAN, String
from mycodo.databases import Base
from mycodo.databases import CRUDMixin, DefaultPK


class AlembicVersion(CRUDMixin, Base):
    __tablename__ = "alembic_version"
    version_num = Column(String(32), primary_key=True, nullable=False)


class Method(CRUDMixin, DefaultPK, Base):
    __tablename__ = "method"

    name = Column(TEXT)
    method_id = Column(TEXT)
    method_type = Column(TEXT)
    method_order = Column(INT)
    start_time = Column(TEXT)
    end_time = Column(TEXT)
    duration_sec = Column(INT)
    relay_id = Column(TEXT)
    relay_state = Column(TEXT)
    relay_duration = Column(REAL)
    start_setpoint = Column(REAL)
    end_setpoint = Column(REAL)
    amplitude = Column(REAL)
    frequency = Column(REAL)
    shift_angle = Column(REAL)
    shift_y = Column(REAL)
    x0 = Column(REAL)
    y0 = Column(REAL)
    x1 = Column(REAL)
    y1 = Column(REAL)
    x2 = Column(REAL)
    y2 = Column(REAL)
    x3 = Column(REAL)
    y3 = Column(REAL)


class Relay(CRUDMixin, DefaultPK, Base):
    __tablename__ = "relays"

    name = Column(TEXT)
    pin = Column(INT)
    amps = Column(REAL)
    trigger = Column(INT)
    start_state = Column(INT)
    on_until = Column(DATETIME)
    last_duration = Column(REAL)
    on_duration = Column(BOOLEAN)

    def _is_setup(self):
        """
        This function checks to see if the GPIO pin is setup and ready to use.  This is for safety
        and to make sure we don't blow anything.

        # TODO Make it do that.

        :return: Is it safe to manipulate this relay?
        :rtype: bool
        """
        return True

    def setup_pin(self):
        """
        Setup pin for this relay

        :rtype: None
        """
        # TODO add some extra checks here.  Maybe verify BCM?
        GPIO.setup(self.pin, GPIO.OUT)

    def turn_off(self):
        """
        Turn this relay off

        :rtype: None
        """
        if self._is_setup():
            self.on_duration = False
            self.on_until = datetime.datetime.now()
            GPIO.output(self.pin, not self.trigger)

    def turn_on(self):
        """
        Turn this relay on

        :rtype: None
        """
        if self._is_setup():
            GPIO.output(self.pin, self.trigger)

    def is_on(self):
        """
        :return: Whether the relay is currently "ON"
        :rtype: bool
        """
        return self.trigger == GPIO.input(self.pin)


class RelayConditional(CRUDMixin, DefaultPK, Base):
    __tablename__ = "relayconditional"

    name = Column(TEXT)
    activated = Column(BOOLEAN)
    if_relay_id = Column(TEXT)
    if_action = Column(TEXT)
    if_duration = Column(REAL)
    do_relay_id = Column(TEXT)
    do_action = Column(TEXT)
    do_duration = Column(REAL)
    execute_command = Column(TEXT)
    email_notify = Column(TEXT)
    flash_lcd = Column(TEXT)


class Sensor(CRUDMixin, DefaultPK, Base):
    __tablename__ = "sensor"

    name = Column(TEXT)
    activated = Column(INT)
    device = Column(TEXT) 
    device_type = Column(TEXT)
    i2c_bus = Column(INT)
    location = Column(TEXT)
    multiplexer_address = Column(TEXT)
    multiplexer_bus = Column(INT)
    multiplexer_channel = Column(INT)
    adc_channel = Column(INT)
    adc_gain = Column(INT)
    adc_resolution = Column(INT)
    adc_measure = Column(TEXT)
    adc_measure_units = Column(TEXT)
    adc_volts_min = Column(REAL)
    adc_volts_max = Column(REAL)
    adc_units_min = Column(REAL)
    adc_units_max = Column(REAL)
    switch_edge = Column(TEXT)
    switch_bouncetime = Column(INT)
    switch_reset_period = Column(INT)
    pre_relay_id = Column(TEXT)
    pre_relay_duration = Column(REAL)
    graph = Column(INT)
    period = Column(INT)
    sht_clock_pin = Column(INT)
    sht_voltage = Column(REAL)

    def is_activated(self):
        """
        :return: Whether the sensor is currently activated
        :rtype: bool
        """
        return self.activated


class SensorPreset(CRUDMixin, DefaultPK, Base):
    __tablename__ = "sensorpreset"

    name = Column(TEXT)
    device = Column(TEXT) 
    device_type = Column(TEXT)
    location = Column(TEXT)
    multiplex = Column(TEXT)
    pre_relay_id = Column(TEXT)
    pre_period = Column(INT)
    graph = Column(INT)
    period = Column(INT)
    sht_clock_pin = Column(INT)
    sht_voltage = Column(REAL)


class SensorConditional(CRUDMixin, DefaultPK, Base):
    __tablename__ = "sensorconditional"

    name = Column(TEXT)
    activated = Column(INT)
    sensor_id = Column(TEXT)
    period = Column(INT)
    measurement_type = Column(TEXT)
    edge_detected = Column(TEXT)
    direction = Column(TEXT) # 'above' or 'below' setpoint
    setpoint = Column(REAL)
    relay_id = Column(TEXT)
    relay_state = Column(TEXT) # 'on' or 'off'
    relay_on_duration = Column(REAL)
    execute_command = Column(TEXT)
    email_notify = Column(TEXT)
    flash_lcd = Column(TEXT)
    camera_record = Column(TEXT)


class PID(CRUDMixin, DefaultPK, Base):
    __tablename__ = "pid"

    name = Column(TEXT)
    activated = Column(INT)
    sensor_id = Column(TEXT)
    measure_type = Column(TEXT)
    direction = Column(TEXT)
    period = Column(INT)
    setpoint = Column(REAL)
    method_id = Column(TEXT)
    p = Column(REAL)
    i = Column(REAL)
    d = Column(REAL)
    integrator_min = Column(REAL)
    integrator_max = Column(REAL)
    raise_relay_id = Column(TEXT)
    raise_min_duration = Column(INT)
    raise_max_duration = Column(INT)
    lower_relay_id = Column(TEXT)
    lower_min_duration = Column(INT)
    lower_max_duration = Column(INT)


class PIDPreset(CRUDMixin, DefaultPK, Base):
    __tablename__ = "pidpreset"

    name = Column(TEXT)
    sensor_id = Column(TEXT)
    measure_type = Column(TEXT)
    direction = Column(TEXT)
    period = Column(INT)
    setpoint = Column(REAL)
    p = Column(REAL)
    i = Column(REAL)
    d = Column(REAL)
    raise_relay_id = Column(TEXT)
    raise_min_duration = Column(INT)
    raise_max_duration = Column(INT)
    lower_relay_id = Column(TEXT)
    lower_min_duration = Column(INT)
    lower_max_duration = Column(INT)


class PIDConditional(CRUDMixin, DefaultPK, Base):
    """
    PID conditionals


    Every PID period, perform math on the PID input (sensor measurement), then
    activate relay_id for a duration of time based on the PID output.

    This is early conception. Future support for PWM, stepper motor, or other output.

    """
    __tablename__ = 'pidconditional'

    name = Column(TEXT)
    activated = Column(INT)
    pid_id = Column(TEXT)
    relay_id = Column(TEXT)
    relay_math = Column(TEXT)
    relay_on_duration = Column(INT)
    command = Column(TEXT)
    notify = Column(TEXT)


class Graph(CRUDMixin, DefaultPK, Base):
    __tablename__ = "graph"
    name = Column(TEXT)
    pid_ids = Column(TEXT)
    relay_ids = Column(TEXT)
    sensor_ids = Column(TEXT)
    width = Column(INT)
    height = Column(INT)
    x_axis_duration = Column(INT)
    refresh_duration = Column(INT)
    enable_navbar = Column(BOOLEAN)
    enable_rangeselect = Column(BOOLEAN)
    enable_export = Column(BOOLEAN)


class DisplayOrder(CRUDMixin, DefaultPK, Base):
    __tablename__ = "displayorder"

    graph = Column(TEXT, default='')
    lcd = Column(TEXT)
    log = Column(TEXT, default='')
    pid = Column(TEXT, default='')
    relay = Column(TEXT, default='')
    remote_host = Column(TEXT)
    sensor = Column(TEXT, default='')
    timer = Column(TEXT)


class LCD(CRUDMixin, DefaultPK, Base):
    __tablename__ = "lcd"

    name = Column(TEXT)
    activated = Column(INT)
    pin = Column(TEXT)
    multiplexer_address = Column(TEXT)
    multiplexer_channel = Column(INT)
    period = Column(INT)
    x_characters = Column(INT)
    y_lines = Column(INT)
    line_1_sensor_id = Column(TEXT)
    line_1_measurement = Column(TEXT)
    line_2_sensor_id = Column(TEXT)
    line_2_measurement = Column(TEXT)
    line_3_sensor_id = Column(TEXT)
    line_3_measurement = Column(TEXT)
    line_4_sensor_id = Column(TEXT)
    line_4_measurement = Column(TEXT)


class Log(CRUDMixin, DefaultPK, Base):
    __tablename__ = "log"

    name = Column(TEXT)
    sensor_id = Column(TEXT)
    measure_type = Column(TEXT)
    activated = Column(INT)
    period = Column(INT)


class Timer(CRUDMixin, DefaultPK, Base):
    __tablename__ = "timer"

    name = Column(TEXT)
    activated = Column(INT)
    relay_id = Column(TEXT)
    state = Column(TEXT) # 'on' or 'off'
    time_on = Column(TEXT)
    duration_on = Column(REAL)
    duration_off = Column(REAL)


class SMTP(CRUDMixin, DefaultPK, Base):
    __tablename__ = "smtp"

    host = Column(TEXT, default='smtp.gmail.com')
    ssl = Column(INT, default=1)
    port = Column(INT, default=465)
    user = Column(TEXT, default='email@gmail.com')
    passw = Column(TEXT, default='password')
    email_from = Column(TEXT, default='email@gmail.com')
    hourly_max = Column(INT, default=2)


class CameraStill(CRUDMixin, DefaultPK, Base):
    __tablename__ = "camerastill"

    hflip = Column(BOOLEAN, default=False)
    vflip = Column(BOOLEAN, default=False)
    rotation = Column(INT, default=0)
    relay_id = Column(TEXT)
    timestamp = Column(INT, default=1)
    display_last = Column(INT, default=1)
    cmd_pre_camera = Column(TEXT)
    cmd_post_camera = Column(TEXT)
    extra_parameters = Column(TEXT, default='--vflip --hflip --width 800 --height 600')


class CameraStream(CRUDMixin, DefaultPK, Base):
    __tablename__ = "camerastream"

    relay_id = Column(TEXT)
    cmd_pre_camera = Column(TEXT)
    cmd_post_camera = Column(TEXT)
    extra_parameters = Column(TEXT, default=('--contrast 20 --sharpness 60 --awb auto --quality 20 '
                                             '--vflip --hflip --nopreview --width 800 --height 600'))


class CameraTimelapse(CRUDMixin, DefaultPK, Base):
    __tablename__ = "cameratimelapse"

    relay_id = Column(TEXT)
    path = Column(TEXT, default='/var/www/mycodo/camera-timelapse')
    prefix = Column(TEXT, default='Timelapse')
    file_timestamp = Column(INT, default=1)
    display_last = Column(INT, default=1)
    cmd_pre_camera = Column(TEXT)
    cmd_post_camera = Column(TEXT)
    extra_parameters = Column(TEXT, default=('--nopreview --contrast 20 --sharpness 60 --awb auto '
                                             '--quality 20 --vflip --hflip --width 800 --height 600'))


class Misc(CRUDMixin, DefaultPK, Base):
    __tablename__ = "misc"

    force_https = Column(BOOLEAN, default=True)
    dismiss_notification = Column(INT, default=0)
    hide_alert_success = Column(BOOLEAN, default=False)
    hide_alert_info = Column(BOOLEAN, default=False)
    hide_alert_warning = Column(BOOLEAN, default=False)
    stats_opt_out = Column(BOOLEAN, default=False)
    login_message = Column(TEXT)
    relay_stats_volts = Column(INT, default=120)
    relay_stats_cost = Column(REAL, default=0.05)
    relay_stats_currency = Column(TEXT, default='$')
    relay_stats_dayofmonth = Column(INT, default=15)


class Remote(CRUDMixin, DefaultPK, Base):
    __tablename__ = "remote"

    activated = Column(INT)
    host = Column(TEXT)
    username = Column(TEXT)
    password_hash = Column(TEXT)
