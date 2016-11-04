# coding=utf-8
import logging
import os
import time

logger = logging.getLogger(__name__)


class RaspberryPiCPULoad(object):
    """ Sensor """
    def __init__(self):
        self._cpu_load = 0
        self.running = True
        self._cpu_load_1m = None
        self._cpu_load_5m = None
        self._cpu_load_15m = None

    def read(self):
        """ Take measurement """
        try:
            self._cpu_load_1m, self._cpu_load_5m, self._cpu_load_15m = os.getloadavg()
        except Exception as e:
            logger.error("{cls} raised an error during read() call: {err}".format(cls=type(self).__name__, err=e))
            return 1

    @property
    def cpu_load_1m(self):
        return self._cpu_load_1m

    @property
    def cpu_load_5m(self):
        return self._cpu_load_5m

    @property
    def cpu_load_15m(self):
        return self._cpu_load_15m

    def __iter__(self):
        """Support the iterator protocol."""
        return self

    def next(self):
        """Call the read method and return cpu_load information."""
        if self.read():
            return None
        response = {
            'cpu_load_1m': float("{0:.2f}".format(self.cpu_load_1m)),
            'cpu_load_5m': float("{0:.2f}".format(self.cpu_load_5m)),
            'cpu_load_15m': float("{0:.2f}".format(self.cpu_load_15m))
        }
        return response

    def stopSensor(self):
        self.running = False


if __name__ == "__main__":
    rpi_cpu_load = RaspberryPiCPULoad()

    for measurement in rpi_cpu_load:
        print("CPU Load (1m): {}".format(measurement['cpu_load_1m']))
        print("CPU Load (5m): {}".format(measurement['cpu_load_5m']))
        print("CPU Load (15m): {}".format(measurement['cpu_load_15m']))
        time.sleep(3)
