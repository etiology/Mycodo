# coding=utf-8
""" Verify that the default db is setup as expected """
import os
# Patch the GPIO imports
from mycodo.tests.software_tests.conftest import patch_hardware_dependent_imports
patch_hardware_dependent_imports()

from mycodo.databases.utils import init_db
from mycodo.databases.utils import session_scope
from mycodo.databases.utils import populate_db
from mycodo.databases.utils import insert_or_ignore

from mycodo.databases.models.mycodo_models import DisplayOrder
from mycodo.databases.models.mycodo_models import CameraTimelapse
from mycodo.databases.models.mycodo_models import CameraStill
from mycodo.databases.models.mycodo_models import CameraStream
from mycodo.databases.models.mycodo_models import Misc
from mycodo.databases.models.mycodo_models import SMTP


def test_init_db_creates_database_file(tmp_file_config):
    """ verify that our init creates a database file """
    # init and add something to the db
    init_db(config=tmp_file_config)

    # ---------------------------------------------------------------
    # Verify that the new DB has data in it (tables were created)
    #
    # This actually requires that we imported something that
    # referenced the different models before we called init_db().
    # For this test it's ok since we are importing populate_db and
    # testing it in another area. The import alone will add tables
    # to the Base before we call init_db().
    #
    # The import is required because the Base doesn't have any
    # models loaded into it until we import something that used it.
    # The DB is only populated with tables if those tables are known
    # to the Base when we call Base.metadata.create_all(bind=engine)
    assert os.path.getsize(tmp_file_config.db_path) > 0  # DB file is no longer empty


def test_populate_db_matches_expected_setup(tmp_file_config):
    """
    Verifies that the populate_db function creates
    the required models with their expected values
    """
    # run our populate_db()
    init_db(config=tmp_file_config)
    populate_db()

    with session_scope() as session:
        # ------------------------
        # Default DisplayOrder
        # ------------------------
        assert session.query(DisplayOrder).count() == 1
        display_order = session.query(DisplayOrder).first()
        assert not display_order.graph
        assert not display_order.log
        assert not display_order.pid
        assert not display_order.relay
        assert not display_order.sensor

        # ------------------------
        # Default CameraTimelapse
        # ------------------------
        assert session.query(CameraTimelapse).count() == 1
        camera_timelapse = session.query(CameraTimelapse).first()
        assert not camera_timelapse.relay_id
        assert not camera_timelapse.cmd_pre_camera
        assert not camera_timelapse.cmd_post_camera
        assert camera_timelapse.file_timestamp == 1
        assert camera_timelapse.display_last == 1
        assert camera_timelapse.prefix == 'Timelapse'
        assert camera_timelapse.path == '/var/www/mycodo/camera-timelapse'
        assert camera_timelapse.extra_parameters == ('--nopreview --contrast 20 --sharpness 60 --awb auto '
                                                     '--quality 20 --vflip --hflip --width 800 --height 600')
        # ------------------------
        # Default CameraStill
        # ------------------------
        assert session.query(CameraStill).count() == 1
        camera_still = session.query(CameraStill).first()
        assert not camera_still.relay_id
        assert not camera_still.cmd_pre_camera
        assert not camera_still.cmd_post_camera
        assert camera_still.rotation == 0
        assert camera_still.hflip is False
        assert camera_still.vflip is False
        assert camera_still.timestamp == 1
        assert camera_still.display_last == 1
        assert camera_still.extra_parameters == '--vflip --hflip --width 800 --height 600'

        # ------------------------
        # Default CameraStream
        # ------------------------
        assert session.query(CameraStream).count() == 1
        camera_stream = session.query(CameraStream).first()
        assert not camera_stream.relay_id
        assert not camera_stream.cmd_pre_camera
        assert not camera_stream.cmd_post_camera
        assert camera_stream.extra_parameters == ('--contrast 20 --sharpness 60 --awb auto --quality 20 '
                                                  '--vflip --hflip --nopreview --width 800 --height 600')

        # ------------------------
        # Default Misc
        # ------------------------
        assert session.query(Misc).count() == 1
        misc = session.query(Misc).first()
        assert not misc.login_message
        assert misc.force_https is True
        assert misc.dismiss_notification == 0
        assert misc.hide_alert_success is False
        assert misc.hide_alert_info is False
        assert misc.hide_alert_warning is False
        assert misc.stats_opt_out is False
        assert misc.relay_stats_volts == 120
        assert misc.relay_stats_cost == 0.05
        assert misc.relay_stats_currency == "$"
        assert misc.relay_stats_dayofmonth == 15

        # ------------------------
        # Default SMTP
        # ------------------------
        assert session.query(SMTP).count() == 1
        smpt = session.query(SMTP).first()
        assert smpt.host == 'smtp.gmail.com'
        assert smpt.ssl == 1
        assert smpt.port == 465
        assert smpt.user == 'email@gmail.com'
        assert smpt.passw == 'password'
        assert smpt.email_from == 'email@gmail.com'
        assert smpt.hourly_max == 2


def test_insert_or_ignore(db):
    """ verify that new models aren't saved if entries already exist """
    assert db.query(SMTP).count() == 0, "SMTP table is empty"

    insert_or_ignore(model=SMTP, session=db)
    assert db.query(SMTP).count() == 1, "SMTP table has 1 entry"

    insert_or_ignore(model=SMTP, session=db)
    assert db.query(SMTP).count() == 1, "SMTP table still has 1 entry"
