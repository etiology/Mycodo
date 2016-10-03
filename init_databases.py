#!/usr/bin/python
# -*- coding: utf-8 -*-
#
#  init_databases.py - Create and update Mycodo SQLite databases
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
import argparse
import getpass
import sys

import sqlalchemy

from mycodo.config import ProductionConfig

from mycodo.databases.models.user_models import Users
from mycodo.databases.utils import session_scope
from mycodo.databases.utils import init_db
from mycodo.databases.utils import populate_db

from mycodo.scripts.utils import test_username
from mycodo.scripts.utils import test_password
from mycodo.scripts.utils import is_email
from mycodo.scripts.utils import query_yes_no


if sys.version[0] == "3":
    raw_input = input  # Make sure this works in PY3


def add_user(admin=False):
    new_user = Users()

    print('\nAdd user to database')

    while True:
        user_name = raw_input('User (a-z, A-Z, 2-64 chars): ')
        if test_username(user_name):
            new_user.user_name = user_name
            break

    while True:
        user_password = getpass.getpass('Password: ')
        user_password_again = getpass.getpass('Password (again): ')
        if user_password != user_password_again:
            print("Passwords don't match")
        else:
            if test_password(user_password):
                new_user.set_password(user_password)
                break

    while True:
        user_email = raw_input('Email: ')
        if is_email(user_email):
            new_user.user_email = user_email
            break

    if admin:
        new_user.user_restriction = 'admin'
    else:
        new_user.user_restriction = 'guest'

    new_user.user_theme = 'dark'
    try:
        with session_scope() as db_session:
            new_user.save(db_session)
        sys.exit(0)
    except sqlalchemy.exc.OperationalError:
        print("Failed to create user.  You most likely need to "
              "create the DB before trying to create users.")
        sys.exit(1)
    except sqlalchemy.exc.IntegrityError:
        print("Username already exists.")
        sys.exit(1)


def delete_user(username):
    """
    finds a user in the database by the name field and deletes it

    :param username: string matching the user's name field (case sensitive)
    :type username: str
    :return: None
    """
    if query_yes_no("Confirm delete user '{}' from user database.".format(username)):
        try:
            with session_scope() as db_session:
                user = db_session.query(Users).filter(Users.user_name == username).one()
                user.delete(db_session)
                print("User deleted.")
                sys.exit(0)
        except sqlalchemy.orm.exc.NoResultFound:
            print("No user found with this name.")
            sys.exit(1)


def change_password(username):
    """
    Updates the password of the user who's name field matches username
    System Exits on Error

    :param username: string matching the user's name field (case sensitive)
    :type username: str
    :return: None - System Exits
    """
    print('Changing password for {}'.format(username))

    with session_scope() as db_session:
        user = db_session.query(Users).filter(Users.user_name == username).one()

        while True:
            user_password = getpass.getpass('Password: ')
            user_password_again = getpass.getpass('Password (again): ')
            if user_password != user_password_again:
                print("Passwords don't match")
            else:
                try:
                    # Verify that the new password meets password requirements
                    if test_password(user_password):
                        user.set_password(user_password)
                        user.save(db_session)
                        sys.exit(0)
                except sqlalchemy.orm.exc.NoResultFound:
                    print("No user found with this name.")
                    sys.exit(1)


def create_dbs(config=ProductionConfig):
    """
    Creates the database and populates it with default data

    Tables are created when the declarative base class has been
    attached to them (usually through an import of the models).
    """

    logging.info("Initializing Database...")
    init_db(config=config)

    logging.info("Populating Default Data")
    populate_db()
    sys.exit(0)


def menu():
    parser = argparse.ArgumentParser(description="Initialize Mycodo Database "
                                                 "structure and manage users")

    parser.add_argument('-i', '--install_db', type=str,
                        choices=['users', 'mycodo', 'notes', 'all'],
                        help="Create new users.db, mycodo.db and/or note.db")

    parser.add_argument('-A', '--addadmin', action='store_true',
                        help="Add admin user to users database")

    parser.add_argument('-a', '--adduser', action='store_true',
                        help="Add user to users database")

    parser.add_argument('-d', '--deleteuser',
                        help="Remove user from users database")

    parser.add_argument('-p', '--pwchange',
                        help="Create a new password for user")

    args = parser.parse_args()

    if args.adduser:
        add_user()

    if args.addadmin:
        add_user(admin=True)

    if args.install_db:
        if args.install_db == 'all':
            create_dbs('', create_all=True)
        else:
            create_dbs(args.install_db)

    if args.deleteuser:
        delete_user(args.deleteuser)

    if args.pwchange:
        change_password(args.pwchange)


if __name__ == "__main__":
    menu()
