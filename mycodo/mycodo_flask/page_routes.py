# coding=utf-8
""" collection of Page endpoints """
import logging
import os
import csv
import datetime
import glob
import pwd
import subprocess
import time
from collections import OrderedDict

from flask import (
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for
)
from flask_babel import gettext
from flask.blueprints import Blueprint

# Classes
from databases.models import (
    db,
    Camera,
    DisplayOrder,
    Graph,
    LCD,
    Method,
    Misc,
    PID,
    Relay,
    RelayConditional,
    Sensor,
    SensorConditional,
    Timer,
    User
)
from mycodo.devices.camera import CameraStream

# Functions
from mycodo import flaskforms
from mycodo import flaskutils
from mycodo.mycodo_flask.authentication_routes import logged_in
from mycodo.mycodo_flask.general_routes import (
    inject_mycodo_version
)
from mycodo.devices.camera import camera_record
from mycodo.utils.database import db_retrieve_table_daemon
from mycodo.utils.influx import sum_relay_usage
from mycodo.utils.system_pi import csv_to_list_of_int


# Config
from config import (
    DAEMON_LOG_FILE,
    FILE_TIMELAPSE_PARAM,
    HTTP_LOG_FILE,
    INSTALL_DIRECTORY,
    LOGIN_LOG_FILE,
    LOCK_FILE_TIMELAPSE,
    MEASUREMENT_UNITS,
    PATH_CAMERA_STILL,
    PATH_CAMERA_TIMELAPSE,
    RESTORE_LOG_FILE,
    UPGRADE_LOG_FILE,
)

logger = logging.getLogger('mycodo.mycodo_flask.pages')

blueprint = Blueprint('page_routes',
                      __name__,
                      static_folder='../static',
                      template_folder='../templates')


@blueprint.context_processor
def inject_dictionary():
    return inject_mycodo_version()


@blueprint.context_processor
def epoch_to_time_string():
    def format_timestamp(epoch):
        return datetime.datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M:%S")
    return dict(format_timestamp=format_timestamp)


@blueprint.route('/camera', methods=('GET', 'POST'))
def page_camera():
    """
    Page to start/stop video stream or time-lapse, or capture a still image.
    Displays most recent still image and time-lapse image.
    """
    if not logged_in():
        return redirect(url_for('general_routes.home'))

    form_camera = flaskforms.Camera()
    camera = Camera.query.all()

    # Check if a video stream is active
    for each_camera in camera:
        if each_camera.stream_started and not CameraStream().is_running():
            each_camera.stream_started = False
            db.session.commit()

    if request.method == 'POST':
        if not flaskutils.authorized(session, 'Guest'):
            flaskutils.deny_guest_user()
            return redirect('/camera')

        mod_camera = Camera.query.filter(Camera.id == form_camera.camera_id.data).first()
        if form_camera.capture_still.data:
            if mod_camera.stream_started:
                flash(gettext("Cannot capture still image if stream is active."))
                return redirect('/camera')
            if CameraStream().is_running():
                CameraStream().terminate_controller()  # Stop camera stream
                time.sleep(2)
            camera_record('photo', mod_camera)
        elif form_camera.start_timelapse.data:
            if mod_camera.stream_started:
                flash(gettext("Cannot start time-lapse if stream is active."))
                return redirect('/camera')
            now = time.time()
            mod_camera.timelapse_started = True
            mod_camera.timelapse_start_time = now
            mod_camera.timelapse_end_time = now + form_camera.timelapse_runtime_sec.data
            mod_camera.timelapse_interval = form_camera.timelapse_interval.data
            mod_camera.timelapse_next_capture = now
            mod_camera.timelapse_capture_number = 0
            db.session.commit()
        elif form_camera.pause_timelapse.data:
            mod_camera.timelapse_paused = True
            db.session.commit()
        elif form_camera.resume_timelapse.data:
            mod_camera.timelapse_paused = False
            db.session.commit()
        elif form_camera.stop_timelapse.data:
            mod_camera.timelapse_started = False
            mod_camera.timelapse_start_time = None
            mod_camera.timelapse_end_time = None
            mod_camera.timelapse_interval = None
            mod_camera.timelapse_next_capture = None
            mod_camera.timelapse_capture_number = None
            db.session.commit()
        elif form_camera.start_stream.data:
            if mod_camera.timelapse_started:
                flash(gettext("Cannot start stream if time-lapse is active."))
                return redirect('/camera')
            mod_camera.stream_started = True
            db.session.commit()
        elif form_camera.stop_stream.data:
            if CameraStream().is_running():
                CameraStream().terminate_controller()
            mod_camera.stream_started = False
            db.session.commit()
        return redirect('/camera')

    # Get the full path and timestamps of latest still and time-lapse images
    latest_img_still_ts = {}
    latest_img_still = {}
    latest_img_tl_ts = {}
    latest_img_tl = {}
    for each_camera in camera:
        try:
            latest_still_img_full_path = max(glob.iglob(
                '{path_still}/Still-{cam_id}-*.jpg'.format(
                    path_still=PATH_CAMERA_STILL,
                    cam_id=each_camera.id)),
                key=os.path.getmtime)
        except ValueError:
            latest_still_img_full_path = None
        if latest_still_img_full_path:
            ts = os.path.getmtime(latest_still_img_full_path)
            latest_img_still_ts[each_camera.id] = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
            latest_img_still[each_camera.id] = os.path.basename(latest_still_img_full_path)
        else:
            latest_img_still[each_camera.id] = None

        try:
            latest_time_lapse_img_full_path = max(glob.iglob(
                '{path_tl}/Timelapse-{cam_id}-*.jpg'.format(
                    path_tl=PATH_CAMERA_TIMELAPSE,
                    cam_id=each_camera.id)),
                key=os.path.getmtime)
        except ValueError:
            latest_time_lapse_img_full_path = None
        if latest_time_lapse_img_full_path:
            ts = os.path.getmtime(latest_time_lapse_img_full_path)
            latest_img_tl_ts[each_camera.id] = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
            latest_img_tl[each_camera.id] = os.path.basename(
                latest_time_lapse_img_full_path)
        else:
            latest_img_tl[each_camera.id] = None

    time_now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    return render_template('pages/camera.html',
                           camera=camera,
                           form_camera=form_camera,
                           latest_img_still=latest_img_still,
                           latest_img_still_ts=latest_img_still_ts,
                           latest_img_tl=latest_img_tl,
                           latest_img_tl_ts=latest_img_tl_ts,
                           time_now=time_now)


@blueprint.route('/export', methods=('GET', 'POST'))
def page_export():
    """
    Export measurement data in CSV format
    """
    if not logged_in():
        return redirect(url_for('general_routes.home'))

    export_options = flaskforms.ExportOptions()
    relay = Relay.query.all()
    sensor = Sensor.query.all()
    relay_choices = flaskutils.choices_id_name(relay)
    sensor_choices = flaskutils.choices_sensors(sensor)

    if request.method == 'POST':
        start_time = export_options.date_range.data.split(' - ')[0]
        start_seconds = int(time.mktime(
            time.strptime(start_time, '%m/%d/%Y %H:%M')))
        end_time = export_options.date_range.data.split(' - ')[1]
        end_seconds = int(time.mktime(
            time.strptime(end_time, '%m/%d/%Y %H:%M')))

        device_id = export_options.measurement.data.split(',')[0]
        measurement = export_options.measurement.data.split(',')[1]

        if measurement == 'duration_sec':
            unique_id = db_retrieve_table_daemon(
                Relay, device_id=device_id).unique_id
        else:
            unique_id = db_retrieve_table_daemon(
                Sensor, device_id=device_id).unique_id

        url = '/export_data/{meas}/{id}/{start}/{end}'.format(
            meas=measurement,
            id=unique_id,
            start=start_seconds, end=end_seconds)
        return redirect(url)

    # Generate start end end times for date/time picker
    end_picker = datetime.datetime.now().strftime('%m/%d/%Y %H:%M')
    start_picker = datetime.datetime.now() - datetime.timedelta(hours=6)
    start_picker = start_picker.strftime('%m/%d/%Y %H:%M')

    return render_template('tools/export.html',
                           start_picker=start_picker,
                           end_picker=end_picker,
                           exportOptions=export_options,
                           relay_choices=relay_choices,
                           sensor_choices=sensor_choices)


@blueprint.route('/graph', methods=('GET', 'POST'))
def page_graph():
    """
    Generate custom graphs to display sensor data retrieved from influxdb.
    """
    if not logged_in():
        return redirect(url_for('general_routes.home'))

    # Create form objects
    form_mod_graph = flaskforms.ModGraph()
    form_del_graph = flaskforms.DelGraph()
    form_order_graph = flaskforms.OrderGraph()
    form_add_graph = flaskforms.AddGraph()

    # Retrieve the order to display graphs
    display_order = csv_to_list_of_int(DisplayOrder.query.first().graph)

    # Retrieve tables from SQL database
    graph = Graph.query.all()
    pid = PID.query.all()
    relay = Relay.query.all()
    sensor = Sensor.query.all()

    # Retrieve all choices to populate form drop-down menu
    pid_choices = flaskutils.choices_id_name(pid)
    relay_choices = flaskutils.choices_id_name(relay)
    sensor_choices = flaskutils.choices_sensors(sensor)

    # Add multi-select values as form choices, for validation
    form_mod_graph.pidIDs.choices = []
    form_mod_graph.relayIDs.choices = []
    form_mod_graph.sensorIDs.choices = []
    for key, value in pid_choices.iteritems():
        form_mod_graph.pidIDs.choices.append((key, value))
    for key, value in relay_choices.iteritems():
        form_mod_graph.relayIDs.choices.append((key, value))
    for key, value in sensor_choices.iteritems():
        form_mod_graph.sensorIDs.choices.append((key, value))

    # Generate dictionary of custom colors for each graph
    dict_colors = dict_custom_colors(graph)

    # Detect which form on the page was submitted
    if request.method == 'POST':
        form_name = request.form['form-name']
        if not flaskutils.authorized(session, 'Guest'):
            flaskutils.deny_guest_user()
            return redirect('/graph')
        elif form_name == 'modGraph':
            flaskutils.graph_mod(form_mod_graph, request.form)
        elif form_name == 'delGraph':
            flaskutils.graph_del(form_del_graph)
        elif form_name == 'orderGraph':
            flaskutils.graph_reorder(form_order_graph, display_order)
        elif form_name == 'addGraph':
            flaskutils.graph_add(form_add_graph, display_order)
        return redirect('/graph')

    return render_template('pages/graph.html',
                           graph=graph,
                           pid=pid,
                           relay=relay,
                           sensor=sensor,
                           pid_choices=pid_choices,
                           relay_choices=relay_choices,
                           sensor_choices=sensor_choices,
                           dict_colors=dict_colors,
                           measurement_units=MEASUREMENT_UNITS,
                           displayOrder=display_order,
                           form_mod_graph=form_mod_graph,
                           form_del_graph=form_del_graph,
                           form_order_graph=form_order_graph,
                           form_add_graph=form_add_graph)


@blueprint.route('/graph-async', methods=('GET', 'POST'))
def page_graph_async():
    """ Generate graphs using asynchronous data retrieval """
    if not logged_in():
        return redirect(url_for('general_routes.home'))

    sensor = Sensor.query.all()
    sensor_choices = flaskutils.choices_sensors(sensor)
    sensor_choices_split = OrderedDict()
    for key, _ in sensor_choices.iteritems():
        order = key.split(",")
        # Separate sensor IDs and measurement types
        sensor_choices_split.update({order[0]: order[1]})

    selected_id = None
    selected_measure = None
    if request.method == 'POST':
        selected_id = request.form['selected_measure'].split(",")[0]
        selected_measure = request.form['selected_measure'].split(",")[1]

    return render_template('pages/graph-async.html',
                           sensor=sensor,
                           sensor_choices=sensor_choices,
                           sensor_choices_split=sensor_choices_split,
                           selected_id=selected_id,
                           selected_measure=selected_measure)


@blueprint.route('/help', methods=('GET', 'POST'))
def page_help():
    """ Display Mycodo manual/help """
    if not logged_in():
        return redirect(url_for('general_routes.home'))

    return render_template('manual.html')


@blueprint.route('/info', methods=('GET', 'POST'))
def page_info():
    """ Display page with system information from command line tools """
    if not logged_in():
        return redirect(url_for('general_routes.home'))

    uptime = subprocess.Popen(
        "uptime", stdout=subprocess.PIPE, shell=True)
    (uptime_output, _) = uptime.communicate()
    uptime.wait()

    uname = subprocess.Popen(
        "uname -a", stdout=subprocess.PIPE, shell=True)
    (uname_output, _) = uname.communicate()
    uname.wait()

    gpio = subprocess.Popen(
        "gpio readall", stdout=subprocess.PIPE, shell=True)
    (gpio_output, _) = gpio.communicate()
    gpio.wait()

    df = subprocess.Popen(
        "df -h", stdout=subprocess.PIPE, shell=True)
    (df_output, _) = df.communicate()
    df.wait()

    free = subprocess.Popen(
        "free -h", stdout=subprocess.PIPE, shell=True)
    (free_output, _) = free.communicate()
    free.wait()

    ifconfig = subprocess.Popen(
        "ifconfig -a", stdout=subprocess.PIPE, shell=True)
    (ifconfig_output, _) = ifconfig.communicate()
    ifconfig.wait()

    return render_template('tools/info.html',
                           gpio_readall=gpio_output,
                           df=df_output,
                           free=free_output,
                           ifconfig=ifconfig_output,
                           uname=uname_output,
                           uptime=uptime_output)


@blueprint.route('/lcd', methods=('GET', 'POST'))
def page_lcd():
    """ Display LCD output settings """
    if not logged_in():
        return redirect(url_for('general_routes.home'))

    lcd = LCD.query.all()
    pid = PID.query.all()
    relay = Relay.query.all()
    sensor = Sensor.query.all()

    display_order = csv_to_list_of_int(DisplayOrder.query.first().lcd)

    form_activate_lcd = flaskforms.ActivateLCD()
    form_add_lcd = flaskforms.AddLCD()
    form_deactivate_lcd = flaskforms.DeactivateLCD()
    form_del_lcd = flaskforms.DelLCD()
    form_mod_lcd = flaskforms.ModLCD()
    form_order_lcd = flaskforms.OrderLCD()
    form_reset_flashing_lcd = flaskforms.ResetFlashingLCD()

    if request.method == 'POST':
        form_name = request.form['form-name']
        if not flaskutils.authorized(session, 'Guest'):
            flaskutils.deny_guest_user()
        elif form_name == 'orderLCD':
            flaskutils.lcd_reorder(form_order_lcd, display_order)
        elif form_name == 'addLCD':
            flaskutils.lcd_add(form_add_lcd)
        elif form_name == 'modLCD':
            flaskutils.lcd_mod(form_mod_lcd)
        elif form_name == 'delLCD':
            flaskutils.lcd_del(form_del_lcd)
        elif form_name == 'activateLCD':
            flaskutils.lcd_activate(form_activate_lcd)
        elif form_name == 'deactivateLCD':
            flaskutils.lcd_deactivate(form_deactivate_lcd)
        elif form_name == 'resetFlashingLCD':
            flaskutils.lcd_reset_flashing(form_reset_flashing_lcd)
        return redirect('/lcd')

    return render_template('pages/lcd.html',
                           lcd=lcd,
                           pid=pid,
                           relay=relay,
                           sensor=sensor,
                           displayOrder=display_order,
                           form_order_lcd=form_order_lcd,
                           form_add_lcd=form_add_lcd,
                           form_mod_lcd=form_mod_lcd,
                           form_del_lcd=form_del_lcd,
                           form_activate_lcd=form_activate_lcd,
                           form_deactivate_lcd=form_deactivate_lcd,
                           form_reset_flashing_lcd=form_reset_flashing_lcd)


@blueprint.route('/live', methods=('GET', 'POST'))
def page_live():
    """ Page of recent and updating sensor data """
    if not logged_in():
        return redirect(url_for('general_routes.home'))

    # Retrieve tables for the data displayed on the live page
    pid = PID.query.all()
    relay = Relay.query.all()
    sensor = Sensor.query.all()
    timer = Timer.query.all()

    # Display orders
    pid_display_order = csv_to_list_of_int(DisplayOrder.query.first().pid)
    sensor_display_order = csv_to_list_of_int(DisplayOrder.query.first().sensor)

    # Filter only activated sensors
    sensor_order_sorted = []
    if sensor_display_order:
        for each_sensor_order in sensor_display_order:
            for each_sensor in sensor:
                if (each_sensor_order == each_sensor.id and
                        each_sensor.is_activated):
                    sensor_order_sorted.append(each_sensor.id)

    # Retrieve only parent method columns
    method = Method.query.filter(
        Method.method_order == 0).all()

    return render_template('pages/live.html',
                           method=method,
                           pid=pid,
                           relay=relay,
                           sensor=sensor,
                           timer=timer,
                           pidDisplayOrder=pid_display_order,
                           sensorDisplayOrderSorted=sensor_order_sorted)


@blueprint.route('/logview', methods=('GET', 'POST'))
def page_logview():
    """ Display the last (n) lines from a log file """
    if not logged_in():
        return redirect(url_for('general_routes.home'))

    form_log_view = flaskforms.LogView()
    log_output = None
    lines = 30
    logfile = ''
    if request.method == 'POST':
        if not flaskutils.authorized(session, 'Guest'):
            flaskutils.deny_guest_user()
            return redirect('/logview')
        if form_log_view.lines.data:
            lines = form_log_view.lines.data
        if form_log_view.loglogin.data:
            logfile = LOGIN_LOG_FILE
        elif form_log_view.loghttp.data:
            logfile = HTTP_LOG_FILE
        elif form_log_view.logdaemon.data:
            logfile = DAEMON_LOG_FILE
        elif form_log_view.logupgrade.data:
            logfile = UPGRADE_LOG_FILE
        elif form_log_view.logrestore.data:
            logfile = RESTORE_LOG_FILE

        # Get contents from file
        if os.path.isfile(logfile):
            log = subprocess.Popen('tail -n ' + str(lines) + ' ' + logfile,
                                   stdout=subprocess.PIPE,
                                   shell=True)
            (log_output, _) = log.communicate()
            log.wait()
        else:
            log_output = 404

    return render_template('tools/logview.html',
                           form_log_view=form_log_view,
                           lines=lines,
                           logfile=logfile,
                           log_output=log_output)


@blueprint.route('/notes', methods=('GET', 'POST'))
def page_notes():
    """ Display notes viewer/editor """
    if not logged_in():
        return redirect(url_for('general_routes.home'))

    return render_template('tools/notes.html')


@blueprint.route('/pid', methods=('GET', 'POST'))
def page_pid():
    """ Display PID settings """
    if not logged_in():
        return redirect(url_for('general_routes.home'))

    pids = PID.query.all()
    relay = Relay.query.all()
    sensor = Sensor.query.all()

    display_order = csv_to_list_of_int(DisplayOrder.query.first().pid)

    form_add_pid = flaskforms.AddPID()
    form_mod_pid = flaskforms.ModPID()

    method = Method.query.filter(
        Method.method_order == 0).all()

    if request.method == 'POST':
        form_name = request.form['form-name']
        if not flaskutils.authorized(session, 'Guest'):
            flaskutils.deny_guest_user()
        elif form_name == 'addPID':
            flaskutils.pid_add(form_add_pid)
        elif form_name == 'modPID':
            if form_mod_pid.mod_pid_del.data:
                flaskutils.pid_del(
                    form_mod_pid.modPID_id.data)
            elif form_mod_pid.mod_pid_order_up.data:
                flaskutils.pid_reorder(
                    form_mod_pid.modPID_id.data, display_order, 'up')
            elif form_mod_pid.mod_pid_order_down.data:
                flaskutils.pid_reorder(
                    form_mod_pid.modPID_id.data, display_order, 'down')
            elif form_mod_pid.mod_pid_activate.data:
                flaskutils.pid_activate(
                    form_mod_pid.modPID_id.data)
            elif form_mod_pid.mod_pid_deactivate.data:
                flaskutils.pid_deactivate(
                    form_mod_pid.modPID_id.data)
            elif form_mod_pid.mod_pid_hold.data:
                flaskutils.pid_manipulate(
                    form_mod_pid.modPID_id.data, 'Hold')
            elif form_mod_pid.mod_pid_pause.data:
                flaskutils.pid_manipulate(
                    form_mod_pid.modPID_id.data, 'Pause')
            elif form_mod_pid.mod_pid_resume.data:
                flaskutils.pid_manipulate(
                    form_mod_pid.modPID_id.data, 'Resume')
            else:
                flaskutils.pid_mod(form_mod_pid)

        return redirect('/pid')

    return render_template('pages/pid.html',
                           method=method,
                           pids=pids,
                           relay=relay,
                           sensor=sensor,
                           displayOrder=display_order,
                           form_add_pid=form_add_pid,
                           form_mod_pid=form_mod_pid)


@blueprint.route('/relay', methods=('GET', 'POST'))
def page_relay():
    """ Display relay status and config """
    if not logged_in():
        return redirect(url_for('general_routes.home'))

    lcd = LCD.query.all()
    relay = Relay.query.all()
    relayconditional = RelayConditional.query.all()
    users = User.query.all()

    display_order = csv_to_list_of_int(DisplayOrder.query.first().relay)

    form_add_relay = flaskforms.AddRelay()
    form_mod_relay = flaskforms.ModRelay()
    form_add_relay_cond = flaskforms.AddRelayConditional()
    form_mod_relay_cond = flaskforms.ModRelayConditional()

    if request.method == 'POST':
        form_name = request.form['form-name']
        if not flaskutils.authorized(session, 'Guest'):
            flaskutils.deny_guest_user()
        elif form_name == 'addRelay':
            flaskutils.relay_add(form_add_relay)
        elif form_name == 'modRelay':
            if (form_mod_relay.turn_on.data or
                    form_mod_relay.turn_off.data or
                    form_mod_relay.sec_on_submit.data):
                flaskutils.relay_on_off(form_mod_relay)
            elif form_mod_relay.save.data:
                flaskutils.relay_mod(form_mod_relay)
            elif form_mod_relay.delete.data:
                flaskutils.relay_del(form_mod_relay)
            elif form_mod_relay.order_up.data or form_mod_relay.order_down.data:
                flaskutils.relay_reorder(form_mod_relay, display_order)
        elif form_name == 'addRelayConditional':
            flaskutils.relay_conditional_add(form_add_relay_cond)
        elif form_name == 'modRelayConditional':
            flaskutils.relay_conditional_mod(form_mod_relay_cond)
        return redirect('/relay')

    return render_template('pages/relay.html',
                           lcd=lcd,
                           relay=relay,
                           relayconditional=relayconditional,
                           users=users,
                           displayOrder=display_order,
                           form_add_relay=form_add_relay,
                           form_mod_relay=form_mod_relay,
                           form_add_relay_cond=form_add_relay_cond,
                           form_mod_relay_cond=form_mod_relay_cond)


@blueprint.route('/sensor', methods=('GET', 'POST'))
def page_sensor():
    """ Display sensor settings """
    if not logged_in():
        return redirect(url_for('general_routes.home'))

    # TCA9548A I2C multiplexer
    multiplexer_addresses = [
        '0x70',
        '0x71',
        '0x72',
        '0x73',
        '0x74',
        '0x75',
        '0x76',
        '0x77'
    ]
    multiplexer_channels = list(range(0, 9))

    form_add_sensor = flaskforms.AddSensor()
    form_mod_sensor = flaskforms.ModSensor()
    form_mod_sensor_cond = flaskforms.ModSensorConditional()

    lcd = LCD.query.all()
    pid = PID.query.all()
    relay = Relay.query.all()
    sensor = Sensor.query.all()
    sensor_conditional = SensorConditional.query.all()
    users = User.query.all()
    display_order = csv_to_list_of_int(DisplayOrder.query.first().sensor)

    # If DS18B20 sensors added, compile a list of detected sensors
    ds18b20_sensors = []
    if Sensor.query.filter(Sensor.device == 'DS18B20').count():
        from w1thermsensor import W1ThermSensor
        for each_sensor in W1ThermSensor.get_available_sensors():
            ds18b20_sensors.append(each_sensor.id)

    # Create list of file names from the sensor_options directory
    # Used in generating the correct options for each sensor/device
    sensor_template_list = []
    sensor_path = "{path}/mycodo/mycodo_flask/templates/pages/sensor_options/".format(
        path=INSTALL_DIRECTORY)
    for (_, _, file_names) in os.walk(sensor_path):
        sensor_template_list.extend(file_names)
        break
    sensor_templates = []
    for each_file_name in sensor_template_list:
        sensor_templates.append(each_file_name.split(".")[0])

    if request.method == 'POST':
        form_name = request.form['form-name']
        if not flaskutils.authorized(session, 'Guest'):
            flaskutils.deny_guest_user()
        elif form_name == 'addSensor':
            flaskutils.sensor_add(form_add_sensor)
        elif form_name == 'modSensor':
            if form_mod_sensor.modSensorSubmit.data:
                flaskutils.sensor_mod(form_mod_sensor)
            elif form_mod_sensor.delSensorSubmit.data:
                flaskutils.sensor_del(form_mod_sensor)
            elif (form_mod_sensor.orderSensorUp.data or
                    form_mod_sensor.orderSensorDown.data):
                flaskutils.sensor_reorder(form_mod_sensor, display_order)
            elif form_mod_sensor.activateSensorSubmit.data:
                flaskutils.sensor_activate(form_mod_sensor)
            elif form_mod_sensor.deactivateSensorSubmit.data:
                flaskutils.sensor_deactivate(form_mod_sensor)
            elif form_mod_sensor.sensorCondAddSubmit.data:
                flaskutils.sensor_conditional_add(form_mod_sensor)
        elif form_name == 'modSensorConditional':
            flaskutils.sensor_conditional_mod(form_mod_sensor_cond)
        return redirect('/sensor')

    return render_template('pages/sensor.html',
                           displayOrder=display_order,
                           ds18b20_sensors=ds18b20_sensors,
                           form_add_sensor=form_add_sensor,
                           form_mod_sensor=form_mod_sensor,
                           form_mod_sensor_cond=form_mod_sensor_cond,
                           lcd=lcd,
                           multiplexer_addresses=multiplexer_addresses,
                           multiplexer_channels=multiplexer_channels,
                           pid=pid,
                           relay=relay,
                           sensor=sensor,
                           sensor_conditional=sensor_conditional,
                           sensor_templates=sensor_templates,
                           users=users)


@blueprint.route('/timer', methods=('GET', 'POST'))
def page_timer():
    """ Display Timer settings """
    if not logged_in():
        return redirect(url_for('general_routes.home'))

    timer = Timer.query.all()
    relay = Relay.query.all()
    relay_choices = flaskutils.choices_id_name(relay)

    display_order = csv_to_list_of_int(DisplayOrder.query.first().timer)

    form_timer = flaskforms.Timer()

    if request.method == 'POST':
        form_name = request.form['form-name']
        if not flaskutils.authorized(session, 'Guest'):
            flaskutils.deny_guest_user()
        elif form_name == 'addTimer':
            flaskutils.timer_add(form_timer,
                                 request.form['timer_type'],
                                 display_order)
        elif form_name == 'modTimer':
            if form_timer.timerDel.data:
                flaskutils.timer_del(form_timer)
            elif (form_timer.orderTimerUp.data or
                    form_timer.orderTimerDown.data):
                flaskutils.timer_reorder(form_timer, display_order)
            elif form_timer.activate.data:
                flaskutils.timer_activate(form_timer)
            elif form_timer.deactivate.data:
                flaskutils.timer_deactivate(form_timer)
            elif form_timer.timerMod.data:
                flaskutils.timer_mod(form_timer)
        return redirect('/timer')

    return render_template('pages/timer.html',
                           timer=timer,
                           displayOrder=display_order,
                           relay_choices=relay_choices,
                           form_timer=form_timer)


@blueprint.route('/usage', methods=('GET', 'POST'))
def page_usage():
    """ Display relay usage (duration and energy usage/cost) """
    if not logged_in():
        return redirect(url_for('general_routes.home'))

    misc = Misc.query.first()
    relay = Relay.query.all()

    display_order = csv_to_list_of_int(DisplayOrder.query.first().relay)

    # Calculate the number of seconds since the (n)th day of tyhe month
    # Enables usage/cost assessments to align with a power bill cycle
    now = datetime.date.today()
    past_month_seconds = 0
    day = misc.relay_stats_dayofmonth
    if 4 <= day <= 20 or 24 <= day <= 30:
        date_suffix = 'th'
    else:
        date_suffix = ['st', 'nd', 'rd'][day % 10 - 1]
    if misc.relay_stats_dayofmonth == datetime.datetime.today().day:
        dt_now = datetime.datetime.now()
        past_month_seconds = (dt_now - dt_now.replace(
            hour=0, minute=0, second=0, microsecond=0)).total_seconds()
    elif misc.relay_stats_dayofmonth > datetime.datetime.today().day:
        first_day = now.replace(day=1)
        last_month = first_day - datetime.timedelta(days=1)
        past_month = last_month.replace(day=misc.relay_stats_dayofmonth)
        past_month_seconds = (now - past_month).total_seconds()
    elif misc.relay_stats_dayofmonth < datetime.datetime.today().day:
        past_month = now.replace(day=misc.relay_stats_dayofmonth)
        past_month_seconds = (now - past_month).total_seconds()

    # Calculate relay on duration for different time periods
    relay_each_duration = {}
    relay_sum_duration = dict.fromkeys(
        ['1d', '1w', '1m', '1m-date', '1y'], 0)
    relay_sum_kwh = dict.fromkeys(
        ['1d', '1w', '1m', '1m-date', '1y'], 0)
    for each_relay in relay:
        relay_each_duration[each_relay.id] = {}
        relay_each_duration[each_relay.id]['1d'] = sum_relay_usage(
            each_relay.id, 86400) / 3600
        relay_each_duration[each_relay.id]['1w'] = sum_relay_usage(
            each_relay.id, 604800) / 3600
        relay_each_duration[each_relay.id]['1m'] = sum_relay_usage(
            each_relay.id, 2629743) / 3600
        relay_each_duration[each_relay.id]['1m-date'] = sum_relay_usage(
            each_relay.id, int(past_month_seconds)) / 3600
        relay_each_duration[each_relay.id]['1y'] = sum_relay_usage(
            each_relay.id, 31556926) / 3600
        relay_sum_duration['1d'] += relay_each_duration[each_relay.id]['1d']
        relay_sum_duration['1w'] += relay_each_duration[each_relay.id]['1w']
        relay_sum_duration['1m'] += relay_each_duration[each_relay.id]['1m']
        relay_sum_duration['1m-date'] += relay_each_duration[each_relay.id]['1m-date']
        relay_sum_duration['1y'] += relay_each_duration[each_relay.id]['1y']
        relay_sum_kwh['1d'] += (
            misc.relay_stats_volts * each_relay.amps *
            relay_each_duration[each_relay.id]['1d'] / 1000)
        relay_sum_kwh['1w'] += (
            misc.relay_stats_volts * each_relay.amps *
            relay_each_duration[each_relay.id]['1w'] / 1000)
        relay_sum_kwh['1m'] += (
            misc.relay_stats_volts * each_relay.amps *
            relay_each_duration[each_relay.id]['1m'] / 1000)
        relay_sum_kwh['1m-date'] += (
            misc.relay_stats_volts * each_relay.amps *
            relay_each_duration[each_relay.id]['1m-date'] / 1000)
        relay_sum_kwh['1y'] += (
            misc.relay_stats_volts * each_relay.amps *
            relay_each_duration[each_relay.id]['1y'] / 1000)

    return render_template('tools/usage.html',
                           display_order=display_order,
                           misc=misc,
                           relay=relay,
                           relay_each_duration=relay_each_duration,
                           relay_sum_duration=relay_sum_duration,
                           relay_sum_kwh=relay_sum_kwh,
                           date_suffix=date_suffix)


def dict_custom_colors(graph):
    """
    Generate lists of custom colors from CSV strings saved in the database.
    If custom colors aren't already saved, fill in with a default palette.

    :param graph: graph SQL object
    :return: dictionary of graph_ids and lists of custom colors
    """
    # Count how many lines will need a custom color input
    dark_themes = ['cyborg', 'darkly', 'slate', 'sun', 'superhero']
    if session['user_theme'] in dark_themes:
        default_palette = [
            '#2b908f', '#90ee7e', '#f45b5b', '#7798BF', '#aaeeee', '#ff0066',
            '#eeaaee', '#55BF3B', '#DF5353', '#7798BF', '#aaeeee'
        ]
    else:
        default_palette = [
            '#7cb5ec', '#434348', '#90ed7d', '#f7a35c', '#8085e9', '#f15c80',
            '#e4d354', '#2b908f', '#f45b5b', '#91e8e1'
        ]

    color_count = OrderedDict()
    for each_graph in graph:
        # Get current saved colors
        if each_graph.custom_colors:  # Split into list
            colors = each_graph.custom_colors.split(',')
        else:  # Create empty list
            colors = []
        # Fill end of list with empty strings
        while len(colors) < len(default_palette):
            colors.append('')

        # Populate empty strings with default colors
        for x, _ in enumerate(default_palette):
            if colors[x] == '':
                colors[x] = default_palette[x]

        index = 0
        index_sum = 0
        total = []
        if each_graph.sensor_ids_measurements:
            for each_set in each_graph.sensor_ids_measurements.split(';'):
                if (index < len(each_graph.sensor_ids_measurements.split(';')) and
                        len(colors) > index):
                    total.append([
                        '{id} {measure}'.format(
                            id=each_set.split(',')[0],
                            measure=each_set.split(',')[1]),
                        colors[index]])
                else:
                    total.append([
                        '{id} {measure}'.format(
                            id=each_set.split(',')[0],
                            measure=each_set.split(',')[1]),
                        '#FF00AA'])
                index += 1
            index_sum += index

        if each_graph.relay_ids:
            index = 0
            for each_set in each_graph.relay_ids.split(','):
                if (index < len(each_graph.relay_ids.split(',')) and
                        len(colors) > index_sum + index):
                    total.append([
                        '{id} Relay'.format(id=each_set.split(',')[0]),
                        colors[index_sum+index]])
                else:
                    total.append([
                        '{id} Relay'.format(id=each_set.split(',')[0]),
                        '#FF00AA'])
                index += 1
            index_sum += index

        if each_graph.pid_ids:
            index = 0
            for each_set in each_graph.pid_ids.split(','):
                if (index < len(each_graph.pid_ids.split(',')) and
                        len(colors) > index_sum + index):
                    total.append([
                        '{id} PID Setpoint'.format(id=each_set.split(',')[0]),
                        colors[index_sum+index]])
                else:
                    total.append([
                        '{id} PID Setpoint'.format(id=each_set.split(',')[0]),
                        '#FF00AA'])
                index += 1

        color_count.update({each_graph.id: total})

    return color_count


def gen(camera):
    """ Video streaming generator function """
    while True:
        frame = camera.get_frame()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


def is_time_lapse_locked():
    """Check if a time-lapse is active"""
    time_lapse_locked = os.path.isfile(LOCK_FILE_TIMELAPSE)
    if time_lapse_locked and not os.path.isfile(FILE_TIMELAPSE_PARAM):
        os.remove(LOCK_FILE_TIMELAPSE)
    elif not time_lapse_locked and os.path.isfile(FILE_TIMELAPSE_PARAM):
        os.remove(FILE_TIMELAPSE_PARAM)
    return os.path.isfile(LOCK_FILE_TIMELAPSE)
