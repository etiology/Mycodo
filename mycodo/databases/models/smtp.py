# -*- coding: utf-8 -*-
from mycodo.mycodo_flask.extensions import db
from mycodo.databases import CRUDMixin


class SMTP(CRUDMixin, db.Model):
    __tablename__ = "smtp"

    id = db.Column(db.Integer, unique=True, primary_key=True)
    host = db.Column(db.Text, default='smtp.gmail.com')
    ssl = db.Column(db.Boolean, default=1)
    port = db.Column(db.Integer, default=465)
    user = db.Column(db.Text, default='email@gmail.com')
    passw = db.Column(db.Text, default='password')
    email_from = db.Column(db.Text, default='email@gmail.com')
    hourly_max = db.Column(db.Integer, default=2)

    def __reper__(self):
        return "<{cls}(id={s.id})>".format(s=self, cls=self.__class__.__name__)
