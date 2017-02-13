# coding=utf-8
""" collection of Page endpoints """
import operator

from flask import current_app
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for
from flask.blueprints import Blueprint

from config import CAMERAS_SUPPORTED
from config import LANGUAGES
from databases.models import Camera
from databases.models import Misc
from databases.models import Relay
from databases.models import Role
from databases.models import SMTP
from databases.models import User
from mycodo import flaskforms
from mycodo.devices.camera import count_cameras_opencv

from mycodo.mycodo_flask.general_routes import inject_mycodo_version
# from mycodo import flaskutils
# from mycodo.mycodo_flask.general_routes import logged_in


blueprint = Blueprint('settings_routes', __name__, static_folder='../static', template_folder='../templates')


@blueprint.context_processor
def inject_dictionary():
    return inject_mycodo_version()


@blueprint.route('/settings/alerts', methods=('GET', 'POST'))
def settings_alerts():
    """ Display alert settings """
    if not logged_in():
        return redirect(url_for('general_routes.home'))

    if not flaskutils.authorized(session, 'Guest'):
        flaskutils.deny_guest_user()
        return redirect(url_for('settings_routes.settings_general'))

    smtp = SMTP.query.first()
    form_email_alert = flaskforms.EmailAlert()

    if request.method == 'POST':
        form_name = request.form['form-name']
        # Update smtp settings table in mycodo SQL database
        if form_name == 'EmailAlert':
            flaskutils.settings_alert_mod(form_email_alert)
        return redirect(url_for('settings_routes.settings_alerts'))

    return render_template('settings/alerts.html',
                           smtp=smtp,
                           form_email_alert=form_email_alert)


@blueprint.route('/settings/camera', methods=('GET', 'POST'))
def settings_camera():
    """ Display camera settings """
    if not logged_in():
        return redirect(url_for('general_routes.home'))

    form_camera = flaskforms.SettingsCamera()

    camera = Camera.query.all()
    relay = Relay.query.all()

    camera_libraries = []
    camera_types = []
    for camera_type, library in CAMERAS_SUPPORTED.items():
        camera_libraries.append(library)
        camera_types.append(camera_type)

    opencv_devices = count_cameras_opencv()

    pi_camera_enabled = False
    try:
        if 'start_x=1' in open('/boot/config.txt').read():
            pi_camera_enabled = True
    except IOError as e:
        current_app.logger.error("Camera IOError raised in '/settings/camera' endpoint: {err}".format(err=e))

    if request.method == 'POST':
        if form_camera.camera_add.data:
            flaskutils.camera_add(form_camera)
        elif form_camera.camera_mod.data:
            flaskutils.camera_mod(form_camera)
        elif form_camera.camera_del.data:
            flaskutils.camera_del(form_camera)
        return redirect(url_for('settings_routes.settings_camera'))

    return render_template('settings/camera.html',
                           camera=camera,
                           camera_libraries=camera_libraries,
                           camera_types=camera_types,
                           form_camera=form_camera,
                           opencv_devices=opencv_devices,
                           pi_camera_enabled=pi_camera_enabled,
                           relay=relay)


@blueprint.route('/settings/general', methods=('GET', 'POST'))
def settings_general():
    """ Display general settings """
    if not logged_in():
        return redirect(url_for('general_routes.home'))

    misc = Misc.query.first()
    form_settings_general = flaskforms.SettingsGeneral()

    languages_sorted = sorted(LANGUAGES.items(), key=operator.itemgetter(1))

    if request.method == 'POST':
        form_name = request.form['form-name']
        if form_name == 'General':
            flaskutils.settings_general_mod(form_settings_general)
        return redirect(url_for('settings_routes.settings_general'))

    return render_template('settings/general.html',
                           misc=misc,
                           languages=languages_sorted,
                           form_settings_general=form_settings_general)


@blueprint.route('/settings/users', methods=('GET', 'POST'))
def settings_users():
    """ Display user settings """
    if not logged_in():
        return redirect(url_for('general_routes.home'))

    if not flaskutils.authorized(session, 'Admin'):
        flaskutils.deny_guest_user()
        return redirect(url_for('settings_routes.settings_general'))

    users = User.query.all()
    user_roles = Role.query.all()
    form_add_user = flaskforms.AddUser()
    form_mod_user = flaskforms.ModUser()
    form_del_user = flaskforms.DelUser()

    if request.method == 'POST':
        form_name = request.form['form-name']
        if form_name == 'addUser':
            flaskutils.user_add(form_add_user)
        elif form_name == 'delUser':
            if flaskutils.user_del(form_del_user) == 'logout':
                return redirect('/logout')
        elif form_name == 'modUser':
            if flaskutils.user_mod(form_mod_user) == 'logout':
                return redirect('/logout')
        return redirect(url_for('settings_routes.settings_users'))

    return render_template('settings/users.html',
                           users=users,
                           user_roles=user_roles,
                           form_add_user=form_add_user,
                           form_mod_user=form_mod_user,
                           form_del_user=form_del_user)
