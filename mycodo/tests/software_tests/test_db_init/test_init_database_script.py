# coding=utf-8
""" Tests the init_databases script """
import os
import mock
from mycodo.tests.software_tests.conftest import patch_hardware_dependent_imports
patch_hardware_dependent_imports()

from init_databases import create_dbs


@mock.patch('init_databases.sys.exit')  # prevent the script termination from compromising test
def test_can_create_database(mock_exit, tmp_file_config):
    """ calls the create_dbs function """
    assert os.path.isfile(tmp_file_config.db_path), 'expected tmp file to exist'
    assert os.path.getsize(tmp_file_config.db_path) == 0, 'expected tmp file to be empty'

    create_dbs(tmp_file_config)
    print(tmp_file_config.db_path)
    assert os.path.getsize(tmp_file_config.db_path) > 0, 'expected db file to not be empty'
    assert mock_exit.called  # script exits after it creates db


@mock.patch('init_databases.sys')  # prevent the script termination from compromising test
def test_can_create_every_model_after_db_is_created(_, tmp_file_config):
    """ Verify that we can add entries to every table after create_dbs is ran """
    create_dbs(tmp_file_config)

    # Delayed import so that we don't compromise the test.  These imports modify the
    # declarative base class which is used to create tables.  Calling this before
    # create_dbs() may artificially load tables that the script wouldn't normally load.
    from mycodo.databases import models as m
    from mycodo.databases.utils import session_scope

    models_to_test = (m.Users, m.Notes, m.Uploads, m.Method, m.Relay, m.RelayConditional, m.Sensor,
                      m.SensorPreset, m.SensorConditional, m.PID, m.PIDPreset, m.PIDConditional, m.Graph, m.DisplayOrder,
                      m.LCD, m.Log, m.Timer, m.SMTP, m.CameraStill, m.CameraStream, m.CameraTimelapse, m.Misc, m.Remote)

    with session_scope() as s:
        for tbl in models_to_test:
            assert bool(tbl().save(s).id)
        # # special constructor cases
        assert bool(m.AlembicVersion(version_num='some version').save(s).version_num)
