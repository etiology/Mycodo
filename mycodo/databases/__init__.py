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
import logging

from sqlalchemy import Column, INTEGER
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# setup the database
Base = declarative_base()
SessionFactory = sessionmaker()


# --------------------------
#   Model Mixin Classes
# --------------------------
class CRUDMixin(object):
    """
    Basic Create, Read, Update and Delete methods

    Models that inherit from this class automatically get these CRUD methods
    """

    def save(self, session):
        """ creates the model in the database """

        try:
            session.add(self)
            session.commit()

            return self
        except Exception as e:
            session.rollback()
            logging.error("Unable to save {model} due to error: {err}".format(model=self, err=e))
            raise e

    def delete(self, session):
        """ deletes the record from the database """
        try:
            session.delete(self)
            session.commit()
        except Exception as e:
            """ many things can go wrong during the commit() so we have a broad except clause """
            logging.error("Failed to delete '{record}' due to error: '{err}'".format(record=self, err=e))


class DefaultPK(object):
    """
    Adds a integer based primary key and get_by_id method to models that inherit from this class

    """
    __tableargs__ = {'extends_existing': True}
    id = Column(INTEGER, unique=True, primary_key=True)

    @classmethod
    def get_by_id(cls, _id, session):
        """ fetch a record by it's primary key """
        return session.query(cls).filter_by(id=_id).first()