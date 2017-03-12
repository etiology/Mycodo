# -*- coding: utf-8 -*-
from mycodo.mycodo_flask.extensions import db
from mycodo.databases import CRUDMixin
from mycodo.databases import set_uuid


class Sensor(CRUDMixin, db.Model):
    __tablename__ = "sensor"

    id = db.Column(db.Integer, unique=True, primary_key=True)
    unique_id = db.Column(db.String, nullable=False, unique=True, default=set_uuid)  # ID for influxdb entries
    name = db.Column(db.Text, default='Sensor')
    is_activated = db.Column(db.Boolean, default=False)
    is_preset = db.Column(db.Boolean, default=False)  # Is config saved as a preset?
    preset_name = db.Column(db.Text, default=None)  # Name for preset
    device = db.Column(db.Text, default='')  # Device name, such as DHT11, DHT22, DS18B20
    device_type = db.Column(db.Text, default='')
    period = db.Column(db.Float, default=15.0)  # Duration between readings
    i2c_bus = db.Column(db.Integer, default='')  # I2C bus the sensor is connected to
    location = db.Column(db.Text, default='')  # GPIO pin or i2c address to communicate with sensor
    power_pin = db.Column(db.Integer, default=0)  # GPIO pin to turn HIGH/LOW to power sensor
    power_state = db.Column(db.Integer, default=True)  # State that powers sensor (1=HIGH, 0=LOW)
    measurements = db.Column(db.Text, default='')  # Measurements separated by commas
    multiplexer_address = db.Column(db.Text, default=None)
    multiplexer_bus = db.Column(db.Integer, default=1)
    multiplexer_channel = db.Column(db.Integer, default=0)
    switch_edge = db.Column(db.Text, default='rising')
    switch_bouncetime = db.Column(db.Integer, default=50)
    switch_reset_period = db.Column(db.Integer, default=10)
    pre_relay_id = db.Column(db.Integer, db.ForeignKey('relay.id'), default=None)  # Relay to turn on before sensor read
    pre_relay_duration = db.Column(db.Float, default=0.0)  # Duration to turn relay on before sensor read
    sht_clock_pin = db.Column(db.Integer, default=None)
    sht_voltage = db.Column(db.Text, default='3.5')

    # Analog to digital converter options
    adc_channel = db.Column(db.Integer, default=0)
    adc_gain = db.Column(db.Integer, default=1)
    adc_resolution = db.Column(db.Integer, default=18)
    adc_measure = db.Column(db.Text, default='Condition')
    adc_measure_units = db.Column(db.Text, default='unit')
    adc_volts_min = db.Column(db.Float, default=None)
    adc_volts_max = db.Column(db.Float, default=None)
    adc_units_min = db.Column(db.Float, default=0)
    adc_units_max = db.Column(db.Float, default=10)

    def is_active(self):
        """
        :return: Whether the sensor is currently activated
        :rtype: bool
        """
        return self.is_activated

    def __reper__(self):
        return "<{cls}(id={s.id})>".format(s=self, cls=self.__class__.__name__)
