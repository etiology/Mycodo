# coding=utf-8
#
#  mycodo_flask.py - Flask web server for Mycodo, for visualizing data,
#                    configuring the system, and controlling the daemon.
#

import datetime
import os
import sys

import flask_login
from flask import (
    flash,
    Flask,
    redirect,
    request,
    url_for
)
from flask_babel import Babel
from flask_babel import gettext
from flask_sslify import SSLify
from werkzeug.contrib.profiler import (
    ProfilerMiddleware,
    MergeStream
)

from mycodo.databases.models import Misc
from mycodo.databases.models import User
from mycodo.config import (
    ProdConfig,
    LANGUAGES,
    INSTALL_DIRECTORY
)
from mycodo.mycodo_flask import (
    admin_routes,
    authentication_routes,
    general_routes,
    method_routes,
    page_routes,
    settings_routes
)
from mycodo.mycodo_flask.general_routes import influx_db
from mycodo.utils.system_pi import assure_path_exists
from mycodo.mycodo_flask.extensions import db


def create_app(config=ProdConfig):
    """
    Application factory:
        http://flask.pocoo.org/docs/0.11/patterns/appfactories/

    :param config: configuration object that holds config constants
    :returns: Flask
    """
    app = Flask(__name__)
    app.config.from_object(config)

    login_manager = flask_login.LoginManager()
    login_manager.init_app(app)

    # Uncomment to enable profiler
    # See scripts/profile_analyzer.py to analyze output
    # app = setup_profiler(app)

    register_extensions(app)
    register_blueprints(app)

    # Translations
    babel = Babel(app)

    @babel.localeselector
    def get_locale():
        misc = Misc.query.first()
        if misc and misc.language != '':
            for key in LANGUAGES:
                if key == misc.language:
                    return key
        return request.accept_languages.best_match(LANGUAGES.keys())

    @login_manager.user_loader
    def user_loader(user_id):
        user = User.query.filter(User.id == user_id).first()
        if not user:
            return
        return user

    @login_manager.unauthorized_handler
    def unauthorized():
        flash(gettext('Please log in to access this page'), "error")
        return redirect(url_for('authentication_routes.do_login'))

    return app


def register_extensions(app):
    """ register extensions to the app """
    app.jinja_env.add_extension('jinja2.ext.do')  # Global values in jinja

    db.init_app(app)
    influx_db.init_app(app)  # attach influx db
    with app.app_context():
        db.create_all()

        # Check user option to force all web connections to use SSL
        misc = Misc.query.first()
        if misc and misc.force_https:
            SSLify(app)


def register_blueprints(_app):
    """ register blueprints to the app """
    _app.register_blueprint(admin_routes.blueprint)  # register admin views
    _app.register_blueprint(authentication_routes.blueprint)  # register login/logout views
    _app.register_blueprint(general_routes.blueprint)  # register general routes
    _app.register_blueprint(method_routes.blueprint)  # register method views
    _app.register_blueprint(page_routes.blueprint)  # register page views
    _app.register_blueprint(settings_routes.blueprint)  # register settings views


def setup_profiler(app):
    """
    Set up a profiler
    Outputs to file and stream
    See profile_analyzer.py in Mycodo/mycodo/scripts/
    """
    app.config['PROFILE'] = True
    new = 'profile-{dt:%Y-%m-%d_%H:%M:%S}'.format(
        dt=datetime.datetime.now())
    profile_path = assure_path_exists(os.path.join(INSTALL_DIRECTORY, new))
    profile_log = os.path.join(profile_path, 'profile.log')
    profile_log_file = open(profile_log, 'w')
    stream = MergeStream(sys.stdout, profile_log_file)
    app.wsgi_app = ProfilerMiddleware(app.wsgi_app, stream, restrictions=[30])
    return app
