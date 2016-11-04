# coding=utf-8
import logging
import time
import RPi.GPIO as GPIO
from tentacle_pi.TSL2561 import TSL2561

logger = logging.getLogger(__name__)


class TSL2561_read(object):
    """ Sensor """
    def __init__(self, address, bus):
        self._lux = None
        self.i2c_address = address
        self.i2c_bus = bus
        self.running = True

    def read(self):
        """ Take measurement """
        try:
            tsl = TSL2561(self.i2c_address, "/dev/i2c-" + str(self.i2c_bus))
            tsl.enable_autogain()
            # tsl.set_gain(16)
            tsl.set_time(0x00)
            self._lux = tsl.lux()
        except Exception as e:
            logger.error("{cls} raised an error during read() call: {err}".format(cls=type(self).__name__, err=e))
            return 1

    @property
    def lux(self):
        return self._lux

    def __iter__(self):
        """
        Support the iterator protocol.
        """
        return self

    def next(self):
        """
        Call the read method and return lux information.
        """
        if self.read():
            return None
        response = {
            'lux': self.lux
        }
        return response

    def stopSensor(self):
        self.running = False


if __name__ == "__main__":
    if GPIO.RPI_INFO['P1_REVISION'] in [2, 3]:
        I2C_bus_number = 1
    else:
        I2C_bus_number = 0
    tsl2561 = TSL2561_read('0x39', I2C_bus_number)

    for measurement in tsl2561:
        print("Lumenosity: {} lux".format(measurement['lux']))
        time.sleep(3)
