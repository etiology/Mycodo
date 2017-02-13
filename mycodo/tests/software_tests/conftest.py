# coding=utf-8
""" pytest file """
#  Hardware specific libs are found through out the flask app pages
#  and the following mock work will patch them so that we can pretend
#  that we have them installed:
from mock import patch, MagicMock

patch.dict("sys.modules",
           RPi=MagicMock(),
           picamera=MagicMock(),
           AM2315=MagicMock(),
           tentacle_pi=MagicMock(),
           Adafruit_BMP=MagicMock(),
           Adafruit_TMP=MagicMock(),
           w1thermsensor=MagicMock(),
           sht_sensor=MagicMock(),
           smbus=MagicMock(),
           ).start()

import pytest
from config import TestConfig
from mycodo_flask.app import create_app
from mycodo_flask.extensions import db as _db
from databases.models import User
from webtest import TestApp


@pytest.yield_fixture()
def app():
    """Create a flask app test fixture """
    _app = create_app(config=TestConfig)

    ctx = _app.test_request_context()
    ctx.push()

    yield _app

    ctx.pop()


@pytest.fixture()
def testapp(app):
    """ A basic web app

    :param app: flask app
    :return: webtest.TestApp
    """
    create_admin_user(app.config['MYCODO_DB_PATH'])
    return TestApp(app)


@pytest.fixture()
def testapp_no_admin_user(app):
    """ A basic web app

    :param app: flask app
    :return: webtest.TestApp
    """
    return TestApp(app)


def login_user(app, username, password):
    """
    returns a test context with a modified
    session for the user login status

    :returns: None
    """

    res = app.get('/login')
    form = res.forms['login_form']

    form['username'] = username
    form['password'] = password
    form.submit().maybe_follow()

    return None


@pytest.yield_fixture()
def db(app):
    _db.app = app
    _db.create_all()
    yield _db
    _db.drop_all()


def create_admin_user(db):
    """ mycodo_flask exits if there is no user called admin. So we create one """
    User(user_name='test', user_role=1).save()
