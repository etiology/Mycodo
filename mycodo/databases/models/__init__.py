# -*- coding: utf-8 -*-
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
"""
    The models package contains all of the SQLAlchemy database
    models used in this app.

    For proper use of these models please use the session_scope
    context manager found in mycodo.databases.utils.  Additionally
    you should use the CRUD (create, read, update, delete) methods
    found in the CRUDMixin located in the mycodo.databases.__init__.

    Look at the model tests for proper use of the CRUD methods.
"""
from .user_models import Users
from .notes_models import Notes
from .notes_models import Uploads
from .mycodo_models import AlembicVersion
from .mycodo_models import Method
from .mycodo_models import Relay
from .mycodo_models import RelayConditional
from .mycodo_models import Sensor
from .mycodo_models import SensorPreset
from .mycodo_models import SensorConditional
from .mycodo_models import PID
from .mycodo_models import PIDPreset
from .mycodo_models import PIDConditional
from .mycodo_models import Graph
from .mycodo_models import DisplayOrder
from .mycodo_models import LCD
from .mycodo_models import Log
from .mycodo_models import Timer
from .mycodo_models import SMTP
from .mycodo_models import CameraStill
from .mycodo_models import CameraStream
from .mycodo_models import CameraTimelapse
from .mycodo_models import Misc
from .mycodo_models import Remote