# coding=utf-8
""" Conftest file for test_db_init only """
import pytest
from mock import MagicMock
import os
from tempfile import mkstemp


@pytest.yield_fixture()
def tmp_file():
    """ returns the path of a temp file """
    fpath = mkstemp()[1]  # get just the file path

    yield fpath
    os.unlink(fpath)


@pytest.fixture()
def tmp_file_config(tmp_file):
    """ creates a config object that uses a tmp_file as the database uri """
    config = MagicMock()
    config.SQLALCHEMY_DATABASE_URI = "sqlite:///" + tmp_file
    config.db_path = tmp_file

    assert config.db_path == tmp_file, "tmp_file_config fixture failure: db_path does not match"
    assert os.path.isfile(config.db_path), "tmp_file_config fixture failure. db_path doesn't exist: {}".format(tmp_file)
    assert os.path.getsize(config.db_path) == 0, "tmp_file_config fixture's db is not empty: {}".format(tmp_file)

    return config
