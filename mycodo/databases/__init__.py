#!/usr/bin/python
# -*- coding: utf-8 -*-
#
#  update-database.py - Create and update Mycodo SQLite databases
#
#  Copyright (C) 2015  Kyle T. Gabriel
#
#  This file is part of Mycodo
#
#  Mycodo is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Mycodo is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Mycodo. If not, see <http://www.gnu.org/licenses/>.
#
#  Contact at kylegabriel.com
from mycodo_flask.extensions import db
from flask import current_app
from uuid import uuid4


class CRUDMixin(object):
    """
    Basic Create, Read, Update and Delete methods
    Models that inherit from this class automatically get these CRUD methods
    """

    def save(self):
        """ creates the model in the database """

        try:
            db.session.add(self)
            db.session.commit()
            return self
        except Exception as error:
            db.session.rollback()
            current_app.logging.error(
                "Unable to save {model} due to error: {err}".format(
                    model=self, err=error))
            raise error

    def delete(self, session=db.session):
        """ deletes the record from the database """
        try:
            session.delete(self)
            session.commit()
        except Exception as error:
            current_app.logger.error(
                "Failed to delete '{record}' due to error: '{err}'".format(
                    record=self, err=error))


def set_uuid():
    return str(uuid4())
