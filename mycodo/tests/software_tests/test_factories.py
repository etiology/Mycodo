# coding=utf-8
""" make sure the fixtures are behaving as expected """
from mycodo.tests.software_tests.factories_user import (
    AdminFactory,
    GuestFactory,
    UserFactory
)


# --------------------------
#   Factory Tests
# --------------------------
def create_user_from_factory(factory, user_role=None):
    """ Uses a factory to create a user and attempts to save it """
    new_user = factory()
    assert new_user.user_name, "Failed to create a 'user_name' using {factory}".format(factory=factory)
    assert new_user.user_email, "Failed to create a 'user_email' using {factory}".format(factory=factory)
    assert new_user.user_role == user_role


def test_user_factories_creates_valid_user():
    """ Use UserFactory to create new user"""
    create_user_from_factory(UserFactory)


def test_admin_factories_creates_valid_user():
    """ Use AdminFactory to create new user"""
    create_user_from_factory(AdminFactory, user_role=1)


def test_guest_factories_creates_valid_user():
    """ Use GuestFactory to create new user"""
    create_user_from_factory(GuestFactory, user_role=4)
