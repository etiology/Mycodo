# coding=utf-8
""" General conftest """
import pytest
from mock import (patch, MagicMock)
patch.dict("sys.modules", RPi=MagicMock()).start()

from config import TestConfig
from mycodo.databases.utils import init_db, SessionFactory, Base


@pytest.yield_fixture()
def db():
    """ returns a db fixture """
    engine = init_db(TestConfig)
    _session = SessionFactory()

    yield _session

    Base.metadata.drop_all(engine)


def patch_hardware_dependent_imports():
    """
    This project uses libraries that can only be installed
    on a raspberry pi.  This causes import errors during testing.

    This function uses mock to patch the import so that
    we can ignore it.
    """
    # ---------- RPi.GPIO Patch ---------------
    from mock import (patch, MagicMock)
    patch.dict("sys.modules", RPi=MagicMock()).start()
    # now we can import modules that use RPi.GPIO