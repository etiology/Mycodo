# coding=utf-8
import logging
from contextlib import contextmanager
from sqlalchemy import create_engine

from config import ProductionConfig
from mycodo.databases import Base, SessionFactory
from mycodo.databases.models import AlembicVersion
from mycodo.databases.models import DisplayOrder
from mycodo.databases.models import Misc
from mycodo.databases.models import CameraTimelapse
from mycodo.databases.models import CameraStream
from mycodo.databases.models import CameraStill
from mycodo.databases.models import SMTP


def init_db(config=ProductionConfig):
    """
    setup the database

    This returns the engine because during testing we
    need that object to empty the database between tests
    """
    engine = create_engine(config.SQLALCHEMY_DATABASE_URI)
    Base.metadata.create_all(engine)
    SessionFactory.configure(bind=engine)

    return engine


@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""

    _session = SessionFactory()

    try:
        yield _session
        _session.commit()
    except Exception as e:
        logging.error("Error occurred when committing the session: {err}".format(err=e))
        _session.rollback()
        raise e
    finally:
        _session.close()


def insert_or_ignore(model, session):
    """
    Duplicates INSERT OR IGNORE in SQLite.

    This function only creates an single new entry into the database tables.
    No insert will occur if the table is not empty

    :param model: SQLAlchemy model class
    :param session: SQLAlchemy session
    """
    if not session.query(model).count():
        model().save(session=session)


def populate_db():
    """ populates initial database with values for some tables """
    with session_scope() as session:
        AlembicVersion(version_num='3ab66300800b').save(session)

        insert_or_ignore(DisplayOrder, session)
        insert_or_ignore(CameraTimelapse, session)
        insert_or_ignore(CameraStill, session)
        insert_or_ignore(CameraStream, session)
        insert_or_ignore(Misc, session)
        insert_or_ignore(SMTP, session)
