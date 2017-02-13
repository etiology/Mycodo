# coding=utf-8
from mycodo_flask.extensions import db
from databases import CRUDMixin
import config


class AlembicVersion(CRUDMixin, db.Model):
    __tablename__ = "alembic_version"

    version_num = db.Column(db.String(32), primary_key=True, nullable=False, default=config.ALEMBIC_VERSION)

    def __reper__(self):
        return "<{cls}(version_number={s.version_num})>".format(s=self, cls=self.__class__.__name__)
