#!/usr/bin/python
# coding=utf-8

import argparse
import logging
import os
import sys
import smbus
import time
import timeit
import RPi.GPIO as GPIO
from lockfile import LockFile
from MCP342x import MCP342x


class MCP342x_read(object):
    def __init__(self, logger, address, channel, gain, resolution):
        self.logger = logger
        self.i2c_address = address
        self.channel = channel
        self.gain = gain
        self.resolution = resolution
        if GPIO.RPI_INFO['P1_REVISION'] in [2, 3]:
            self.I2C_bus_number = 1
        else:
            self.I2C_bus_number = 0
        self.bus = smbus.SMBus(self.I2C_bus_number)
        self.lock_file = "/var/lock/mycodo_adc_0x{:02X}.pid".format(self.i2c_address)

    def setup_lock(self):
        self.execution_timer = timeit.default_timer()
        try:
            self.lock = LockFile(self.lock_file)
            while not self.lock.i_am_locking():
                try:
                    self.logger.debug("[Analog->Digital Converter 0x{:02X}] "
                                      "Acquiring Lock: {}".format(self.i2c_address,
                                                                  self.lock.path))
                    self.lock.acquire(timeout=60)  # wait up to 60 seconds
                except Exception as e:
                    self.logger.error("{cls} exception in read call.  Error: '{err}'".format(cls=type(self).__name__,
                                                                                             err=e))
                    self.logger.warning(
                        "[Analog->Digital Converter 0x{:02X}] Waited 60 "
                        "seconds. Breaking lock to acquire {}".format(
                            self.i2c_address, self.lock.path))
                    self.lock.break_lock()
                    self.lock.acquire()
            self.logger.debug(
                "[Analog->Digital Converter 0x{:02X}] Acquired Lock: "
                "{}".format(self.i2c_address, self.lock.path))
            self.logger.debug(
                "[Analog->Digital Converter 0x{:02X}] Executed in "
                "{}ms".format(self.i2c_address,
                              (timeit.default_timer() - self.execution_timer) * 1000))
            return 1, "Success"
        except Exception as msg:
            return 0, "Analog->Digital Converter Fail: {}".format(msg)

    def release_lock(self):
        self.lock.release()

    def read(self):
        try:
            time.sleep(0.1)
            self.setup_lock()
            adc = MCP342x(self.bus, self.i2c_address,
                          channel=self.channel - 1,
                          gain=self.gain,
                          resolution=self.resolution)
            response = adc.convert_and_read()
            self.release_lock()
            return 1, response
        except Exception as msg:
            self.release_lock()
            return 0, "Fail: {}".format(msg)


def menu(logger):
    parser = argparse.ArgumentParser(description='Select I2C address and channel of TCA9548A I2C multiplexer')
    parser.add_argument('-a', '--address', metavar='ADDRESS', type=str,
                        help='I2C address of the ADC, only last two digits, (ex. enter "68" if 0x68)',
                        required=True)
    parser.add_argument('-c', '--channel', metavar='CHANNEL', type=int,
                        help='Channel to read the voltage. Options are 1, 2, 3, 4.',
                        required=True)
    parser.add_argument('-g', '--gain', metavar='GAIN', type=int,
                        help='Gain. Options are 1, 2, 4, or 8.',
                        required=True)
    parser.add_argument('-r', '--resolution', metavar='RESOLUTION', type=int,
                        help='How many bits precision? Options are 12, 14, 16, 18.',
                        required=True)

    args = parser.parse_args()

    i2c_address = int(str(args.address), 16)
    adc = MCP342x_read(logger, i2c_address, args.channel, args.gain, args.resolution)
    read_status, read_response = adc.read()
    if read_status:
        print("MCP342x response on channel {}: {} volts".format(args.channel, read_response))
    else:
        print("Error: {}".format(read_response))


if __name__ == "__main__":
    if not os.geteuid() == 0:
        print("Error: Script must be executed as root.\n")
        sys.exit(1)
    logging.basicConfig(level='DEBUG')
    logger = logging.getLogger(__name__)
    menu(logger)


# bus = get_smbus()

# # Create objects for each signal to be sampled
# addr68_ch0 = MCP342x(bus, 0x68, channel=0, resolution=18)
# addr68_ch1 = MCP342x(bus, 0x68, channel=1, resolution=18)
# addr68_ch2 = MCP342x(bus, 0x68, channel=2, resolution=18)
# addr68_ch3 = MCP342x(bus, 0x68, channel=3, resolution=16)

# # Create a list of all the objects. They will be sampled in this
# # order, unless any later objects can be sampled can be moved earlier
# # for simultaneous sampling.
# adcs = [addr68_ch0, addr68_ch1, addr68_ch2, addr68_ch3]
# r = MCP342x.convert_and_read_many(adcs, samples=2)
# print('CH0: {}\nCH1: {}\nCH2: {}\nCh3: {}'.format(r[0], r[1], r[2], r[3]))

# # , scale_factor=2.448579823702253
# # addr68_ch0.convert()
# print('CH0: {}\nCH1: {}\nCH2: {}\nCh3: {}'.format(
#     addr68_ch0.convert_and_read(),
#     addr68_ch1.convert_and_read(),
#     addr68_ch2.convert_and_read(),
#     addr68_ch3.convert_and_read()))
