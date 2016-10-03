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

from sqlalchemy import Column, TEXT
from mycodo.databases import CRUDMixin
from mycodo.databases import Base
from mycodo.databases import DefaultPK


class Notes(CRUDMixin, DefaultPK, Base):
    __tablename__ = "notes"

    time = Column(TEXT)
    user = Column(TEXT)
    title = Column(TEXT)
    note = Column(TEXT)


class Uploads(CRUDMixin, DefaultPK, Base):
    __tablename__ = "uploads"

    name = Column(TEXT)
    file_name = Column(TEXT)
    location = Column(TEXT)
