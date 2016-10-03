# coding=utf-8
""" Basic functional tests for the database models """
from mycodo.tests.software_tests.conftest import patch_hardware_dependent_imports
patch_hardware_dependent_imports()

from mycodo.databases.models.user_models import Users
from mycodo.databases.models.notes_models import (Notes,
                                                  Uploads)
from mycodo.databases.models.mycodo_models import (Relay,
                                                   RelayConditional,
                                                   Sensor,
                                                   SensorPreset,
                                                   SensorConditional,
                                                   PID,
                                                   PIDPreset,
                                                   PIDConditional,
                                                   Graph,
                                                   DisplayOrder,
                                                   LCD,
                                                   Log,
                                                   Timer,
                                                   SMTP,
                                                   CameraStill,
                                                   CameraStream,
                                                   CameraTimelapse,
                                                   Misc,
                                                   Remote)


# ------------------------------
#   Test Helper Function
# ------------------------------
def _create_basic_model(model, _session):
    """ creates, saves, and returns a model """
    return model().save(_session)


# ---------------------
#   CRUD TESTS
# ---------------------
def test_can_create_basic_models(db):
    """ creates model and verifies that it was made """
    models_to_test = (Users, Relay, RelayConditional, Sensor, SensorPreset,
                      SensorConditional, PID, PIDPreset, PIDConditional, Graph,
                      DisplayOrder, LCD, Log, Timer, SMTP, CameraStill, CameraStream,
                      CameraTimelapse, Misc, Remote, Notes, Uploads)
    for m in models_to_test:
        assert bool(_create_basic_model(model=m, _session=db)), m


def test_can_delete_model(db):
    """ Create and deletes a model using the model's CRUD methods """
    # Creates a user and verifies that the db saved it by checking the PK
    new_user = Users().save(db)
    assert bool(new_user.id)

    # Calls delete() method and verifies that the record is deleted
    pk = new_user.id
    new_user.delete(db)
    assert db.query(Users).filter_by(id=pk).first() is None


def test_can_get_model_by_its_id(db):
    """ tests the method get_by_id() using the pk """
    # create something in the db
    new_user = Users().save(db)
    pk = new_user.id
    assert bool(pk), "Saved new user to DB"

    # fetch the user record using the get_by_id method
    recovered_user = Users.get_by_id(pk, session=db)
    assert recovered_user == new_user
