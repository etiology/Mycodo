# coding=utf-8
from flask import Flask


def test_can_create_app_fixture(app):
    """ verify that we can generate an app fixture """
    assert app and isinstance(app, Flask)
