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

# import subprocess

import bcrypt
from sqlalchemy import Column, VARCHAR, INTEGER
from mycodo.databases import Base
from mycodo.databases import DefaultPK
from mycodo.databases import CRUDMixin


class Users(CRUDMixin, DefaultPK, Base):
    """ simple user class """
    __tablename__ = "users"

    user_name = Column(VARCHAR(64), unique=True, index=True)
    user_password_hash = Column(VARCHAR(255))
    user_email = Column(VARCHAR(64), unique=True, index=True)
    user_restriction = Column(VARCHAR(64))
    user_theme = Column(VARCHAR(64))

    def set_password(self, new_password):
        """ Saves a password hash """
        self.user_password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())

    def check_password(self, password):
        """ Verifies that when password is hashed it matches the stored password hash """
        hashes_match = bcrypt.hashpw(password.encode('utf-8'), self.user_password_hash.encode('utf-8'))
        return hashes_match
