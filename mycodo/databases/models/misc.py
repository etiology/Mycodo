# coding=utf-8
from mycodo.databases import CRUDMixin
from mycodo.mycodo_flask.extensions import db


class Misc(CRUDMixin, db.Model):
    __tablename__ = "misc"

    id = db.Column(db.Integer, unique=True, primary_key=True)
    dismiss_notification = db.Column(db.Boolean, default=False)  # Dismiss login page license notice
    force_https = db.Column(db.Boolean, default=True)  # Force web interface to use SSL/HTTPS
    hide_alert_info = db.Column(db.Boolean, default=False)
    hide_alert_success = db.Column(db.Boolean, default=False)
    hide_alert_warning = db.Column(db.Boolean, default=False)
    language = db.Column(db.Text, default=None)  # Force the web interface to use a specific language
    login_message = db.Column(db.Text, default='')  # Put a message on the login screen
    relay_stats_cost = db.Column(db.Float, default=0.05)  # Energy cost per kWh
    relay_stats_currency = db.Column(db.Text, default='$')  # Energy cost currency
    relay_stats_dayofmonth = db.Column(db.Integer, default=15)  # Electricity billing day of month
    relay_stats_volts = db.Column(db.Integer, default=120)  # Voltage the alternating current operates
    stats_opt_out = db.Column(db.Boolean, default=False)  # Opt not to send anonymous usage statistics

    def __reper__(self):
        return "<{cls}(id={s.id})>".format(s=self, cls=self.__class__.__name__)
