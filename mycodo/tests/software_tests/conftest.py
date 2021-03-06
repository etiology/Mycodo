# coding=utf-8
""" pytest file """
import pytest
import logging
import tempfile
import shutil
import os
from mycodo.databases.utils import session_scope
from mycodo.databases.users_db.models import Users


def uri_to_path(uri):
    """ splits a URI back into a path """
    return str(uri).split('sqlite:///')[1]


@pytest.yield_fixture()
def tmp_file():
    """
    make a tmp file in an empty tmp dir and
    remove it after it is used
    """

    parent_dir = tempfile.mkdtemp()
    _, tmp_path = tempfile.mkstemp(dir=parent_dir)

    yield tmp_path

    if os.path.isdir(parent_dir):
        shutil.rmtree(parent_dir)


@pytest.fixture()
def db_config(tmp_file, mycodo_db_uri, user_db_uri, notes_db_uri):
    """ Creates a config object to setup and databases during tests """
    class Config(object):
        SQL_DATABASE_USER = tmp_file
        SQL_DATABASE_MYCODO = uri_to_path(mycodo_db_uri)
        SQL_DATABASE_NOTE = uri_to_path(notes_db_uri)

        MYCODO_DB_PATH = mycodo_db_uri
        NOTES_DB_PATH = notes_db_uri
        USER_DB_PATH = user_db_uri

    return Config


@pytest.fixture()
def mycodo_db_uri(tmp_file):
    """ returns the sqlalchemy URI as the MYCODO_DB_PATH """
    return ''.join(['sqlite:///', tmp_file, '_mycodo_db'])


@pytest.fixture()
def user_db_uri(tmp_file):
    """ returns the sqlalchemy URI as the USER_DB_PATH """
    return ''.join(['sqlite:///', tmp_file, '_user_db'])


@pytest.fixture()
def notes_db_uri(tmp_file):
    """ returns the sqlalchemy URI as the USER_DB_PATH """
    return ''.join(['sqlite:///', tmp_file, '_notes_db'])


def create_admin_user(user_db_uri):
    """ mycodo_flask exits if there is no user called admin. So we create one """

    with session_scope(user_db_uri) as db_session:
        if not db_session.query(Users).filter_by(user_restriction='admin').count():
            logging.info("--> Creating new 'test' user as an admin")
            db_session.add(Users(user_name='test', user_restriction='admin'))
            db_session.commit()
        else:
            logging.warning("--> Dirty User DB: Admin user was already setup in: '{uri}'".format(uri=user_db_uri))