# coding=utf-8
import csv
import geocoder
import logging
import os
import pwd
import random
import requests
import resource
import string
import time
from collections import OrderedDict
from influxdb import InfluxDBClient
from sqlalchemy import func

# Classes
from mycodo.databases.models import (
    AlembicVersion,
    LCD,
    Method,
    PID,
    Relay,
    Sensor,
    Timer,
    User
)

# Functions
from database import db_retrieve_table_daemon

# Config
from mycodo.config import (
    ID_FILE,
    MYCODO_VERSION,
    SQL_DATABASE_MYCODO,
    STATS_CSV,
    STATS_DATABASE,
    STATS_HOST,
    STATS_INTERVAL,
    STATS_PORT,
    STATS_PASSWORD,
    STATS_USER
)

MYCODO_DB_PATH = 'sqlite:///' + SQL_DATABASE_MYCODO

logger = logging.getLogger("mycodo.stats")


#
# Anonymous usage statistics collection and transmission
#

def add_stat_dict(stats_dict, anonymous_id, measurement, value):
    """
    Format statistics data for entry into Influxdb database
    """
    new_stat_entry = {
        "measurement": measurement,
        "tags": {
            "anonymous_id": anonymous_id
        },
        "fields": {
            "value": value
        }
    }
    stats_dict.append(new_stat_entry)
    return stats_dict


def add_update_csv(csv_file, key, value):
    """
    Either add or update the value in the statistics file with the new value.
    If the key exists, update the value.
    If the key doesn't exist, add the key and value.

    """
    temp_file_name = ''
    try:
        stats_dict = {key: value}
        temp_file_name = os.path.splitext(csv_file)[0] + '.bak'
        if os.path.isfile(temp_file_name):
            try:
                os.remove(temp_file_name)  # delete any existing temp file
            except OSError as e:
                logger.debug(
                    "OS error raised in 'add_update_csv' (no file to delete "
                    "is normal): {err}".format(err=e))
        os.rename(csv_file, temp_file_name)

        # create a temporary dictionary from the input file
        with open(temp_file_name, mode='r') as infile:
            reader = csv.reader(infile)
            header = next(reader)  # skip and save header
            temp_dict = OrderedDict((row[0], row[1]) for row in reader)

        # only add items from my_dict that weren't already present
        temp_dict.update({key: value for (key, value) in stats_dict.items()
                          if key not in temp_dict})

        # only update items from my_dict that are already present
        temp_dict.update({key: value for (key, value) in stats_dict.items()})

        # create updated version of file
        with open(csv_file, mode='w') as outfile:
            writer = csv.writer(outfile)
            writer.writerow(header)
            writer.writerows(temp_dict.items())

        uid_gid = pwd.getpwnam('mycodo').pw_uid
        os.chown(csv_file, uid_gid, uid_gid)
        os.chmod(csv_file, 0664)
        os.remove(temp_file_name)  # delete backed-up original
    except Exception as except_msg:
        logger.exception('[Statistics] Could not update stat csv: '
                         '{}'.format(except_msg))
        os.rename(temp_file_name, csv_file)  # rename temp file to original


def get_count(q):
    """Count the number of rows from an SQL query"""
    count_q = q.statement.with_only_columns([func.count()]).order_by(None)
    count = q.session.execute(count_q).scalar()
    return count


def get_pi_revision():
    """
    Return the Raspberry Pi board revision ID from /proc/cpuinfo

    """
    # Extract board revision from cpuinfo file
    revision = "0000"
    try:
        f = open('/proc/cpuinfo', 'r')
        for line in f:
            if line[0:8] == 'Revision':
                length = len(line)
                revision = line[11:length - 1]
        f.close()
    except Exception as e:
        logger.error("Exception in 'get_pi_revision' call. Error: "
                     "{err}".format(err=e))
        revision = "0000"
    return revision


def increment_stat(stat, amount):
    """
    Increment the value in the statistics file by amount

    """
    stat_dict = return_stat_file_dict(STATS_CSV)
    add_update_csv(STATS_CSV, stat, int(stat_dict[stat]) + amount)


def return_stat_file_dict(csv_file):
    """
    Read the statistics file and return as keys and values in a dictionary

    """
    with open(csv_file, mode='r') as infile:
        reader = csv.reader(infile)
        return OrderedDict((row[0], row[1]) for row in reader)


def recreate_stat_file():
    """
    Create a statistics file with basic stats

    if anonymous_id is not provided, generate one

    """
    uid_gid = pwd.getpwnam('mycodo').pw_uid
    if not os.path.isfile(ID_FILE):
        anonymous_id = ''.join([random.choice(
            string.ascii_letters + string.digits) for _ in xrange(12)])
        with open(ID_FILE, 'w') as write_file:
            write_file.write('{}'.format(anonymous_id))
        os.chown(ID_FILE, uid_gid, uid_gid)
        os.chmod(ID_FILE, 0664)

    with open(ID_FILE, 'r') as read_file:
        stat_id = read_file.read()

    new_stat_data = [
        ['stat', 'value'],
        ['id', stat_id],
        ['uptime', 0.0],
        ['next_send', time.time() + STATS_INTERVAL],
        ['RPi_revision', get_pi_revision()],
        ['Mycodo_revision', MYCODO_VERSION],
        ['alembic_version', 0],
        ['country', 'None'],
        ['daemon_startup_seconds', 0.0],
        ['ram_use_mb', 0.0],
        ['num_users_admin', 0],
        ['num_users_guest', 0],
        ['num_lcds', 0],
        ['num_lcds_active', 0],
        ['num_methods', 0],
        ['num_methods_in_pid', 0],
        ['num_pids', 0],
        ['num_pids_active', 0],
        ['num_relays', 0],
        ['num_sensors', 0],
        ['num_sensors_active', 0],
        ['num_conditionals', 0],
        ['num_conditionals_active', 0],
        ['num_timers', 0],
        ['num_timers_active', 0]
    ]

    with open(STATS_CSV, 'w') as csv_stat_file:
        write_csv = csv.writer(csv_stat_file)
        for row in new_stat_data:
            write_csv.writerow(row)
    os.chown(STATS_CSV, uid_gid, uid_gid)
    os.chmod(STATS_CSV, 0664)


def send_anonymous_stats(start_time):
    """
    Send anonymous usage statistics

    Example use:
        current_stat = return_stat_file_dict(csv_file)
        add_update_csv(csv_file, 'stat', current_stat['stat'] + 5)
    """
    try:
        client = InfluxDBClient(STATS_HOST, STATS_PORT, STATS_USER, STATS_PASSWORD, STATS_DATABASE)
        # Prepare stats before sending
        uptime = (time.time() - start_time) / 86400.0  # Days
        add_update_csv(STATS_CSV, 'uptime', uptime)

        version_num = db_retrieve_table_daemon(
            AlembicVersion, entry='first').version_num
        version_send = version_num if version_num else 'None'
        add_update_csv(STATS_CSV, 'alembic_version', version_send)

        relays = db_retrieve_table_daemon(Relay)
        add_update_csv(STATS_CSV, 'num_relays', get_count(relays))

        sensors = db_retrieve_table_daemon(Sensor)
        add_update_csv(STATS_CSV, 'num_sensors', get_count(sensors))
        add_update_csv(STATS_CSV, 'num_sensors_active',
                       get_count(
                           sensors.filter(Sensor.is_activated == True)))

        conditionals = db_retrieve_table_daemon(Conditional)
        add_update_csv(STATS_CSV, 'num_conditionals', get_count(conditionals))
        add_update_csv(STATS_CSV, 'num_conditionals_active',
                       get_count(
                           conditionals.filter(Conditional.is_activated == True)))

        pids = db_retrieve_table_daemon(PID)
        add_update_csv(STATS_CSV, 'num_pids', get_count(pids))
        add_update_csv(STATS_CSV, 'num_pids_active',
                       get_count(pids.filter(PID.is_activated == True)))

        lcds = db_retrieve_table_daemon(LCD)
        add_update_csv(STATS_CSV, 'num_lcds', get_count(lcds))
        add_update_csv(STATS_CSV, 'num_lcds_active',
                       get_count(lcds.filter(LCD.is_activated == True)))

        methods = db_retrieve_table_daemon(Method)
        add_update_csv(STATS_CSV, 'num_methods',
                       get_count(methods))
        add_update_csv(STATS_CSV, 'num_methods_in_pid',
                       get_count(pids.filter(PID.method_id != '')))

        timers = db_retrieve_table_daemon(Timer)
        add_update_csv(STATS_CSV, 'num_timers', get_count(timers))
        add_update_csv(STATS_CSV, 'num_timers_active',
                       get_count(timers.filter(
                           Timer.is_activated == True)))

        add_update_csv(STATS_CSV, 'country', geocoder.ip('me').country)
        add_update_csv(STATS_CSV, 'ram_use_mb',
                       resource.getrusage(
                           resource.RUSAGE_SELF).ru_maxrss / float(1000))

        user_count = 0
        admin_count = 0
        # TODO: More specific exception or remove try
        try:
            users = db_retrieve_table_daemon(User, entry='all')
            for each_user in users:
                user_count += 1
                if each_user.role == 1:
                    admin_count += 1
        except Exception:
            pass
        add_update_csv(STATS_CSV, 'num_users_admin', admin_count)
        add_update_csv(STATS_CSV, 'num_users_guest',
                       user_count - admin_count)

        add_update_csv(STATS_CSV, 'Mycodo_revision', MYCODO_VERSION)

        # Combine stats into list of dictionaries
        new_stats_dict = return_stat_file_dict(STATS_CSV)
        formatted_stat_dict = []
        for each_key, each_value in new_stats_dict.items():
            if each_key != 'stat':  # Do not send header row
                formatted_stat_dict = add_stat_dict(formatted_stat_dict,
                                                    new_stats_dict['id'],
                                                    each_key,
                                                    each_value)

        # Send stats to secure, remote influxdb server (only write permission)
        client.write_points(formatted_stat_dict)
        logger.debug("Sent anonymous usage statistics")
        return 0
    except requests.ConnectionError:
        logger.error("Could not send anonymous usage statistics: Connection "
                     "timed out (expected if there's no internet)")
    except Exception as except_msg:
        logger.exception(
            "Could not send anonymous usage statistics: {err}".format(
                err=except_msg))
    return 1
