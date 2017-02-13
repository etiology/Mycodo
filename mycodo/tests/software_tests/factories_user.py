# coding=utf-8
""" A collection of model factories using factory boy """
import factory
from databases import models


class UserFactory(factory.Factory):
    """ A factory for creating user models """
    class Meta(object):
        model = models.User

    user_name = factory.Faker('name')
    user_email = factory.Faker('email')


# Another, different, factory for the same object
class AdminFactory(factory.Factory):
    """ A factory for creating admin user models """
    class Meta(object):
        model = models.User

    user_name = factory.Faker('name')
    user_email = factory.Faker('email')
    user_role = 1  # Admin


# Guest factory
class GuestFactory(factory.Factory):
    """ A factory for creating admin user models """
    class Meta(object):
        model = models.User

    user_name = factory.Faker('name')
    user_email = factory.Faker('email')
    user_role = 4  # Guest
