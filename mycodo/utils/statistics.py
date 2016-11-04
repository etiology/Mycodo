# coding=utf-8
import logging
import csv
import geocoder
import os
import pwd
import random
import resource
import string
import time
from collections import OrderedDict
from influxdb import InfluxDBClient
from sqlalchemy import func

from system_pi import get_git_commit


logger = logging.getLogger(__name__)
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


def add_update_csv(_logger, csv_file, key, value):
    """
    Either add or update the value in the statistics file with the new value.
    If the key exists, update the value.
    If the key doesn't exist, add the key and value.

    """
    try:
        stats_dict = {key: value}
        tempfilename = os.path.splitext(csv_file)[0] + '.bak'
        try:
            os.remove(tempfilename)  # delete any existing temp file
        except OSError as e:
            logger.warning("OS error raised in 'add_update_csv': {err}")
        os.rename(csv_file, tempfilename)

        # create a temporary dictionary from the input file
        with open(tempfilename, mode='r') as infile:
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
        os.remove(tempfilename)  # delete backed-up original
    except Exception as except_msg:
        _logger.exception('[Statistics] Could not update stat csv: '
                          '{}'.format(except_msg))
        os.rename(tempfilename, csv_file)  # rename temp file to original


def get_count(q):
    """Count the number of rows from an SQL query"""
    count_q = q.statement.with_only_columns([func.count()]).order_by(None)
    count = q.session.execute(count_q).scalar()
    return count


def get_pi_revision():
    """
    Return the Raspbery Pi board revision ID from /proc/cpuinfo

    """
    # Extract board revision from cpuinfo file
    myrevision = "0000"
    try:
        f = open('/proc/cpuinfo', 'r')
        for line in f:
            if line[0:8] == 'Revision':
                length = len(line)
                myrevision = line[11:length - 1]
        f.close()
    except Exception as e:

        myrevision = "0000"
    return myrevision


def increment_stat(_logger, stats_csv, stat, amount):
    """
    Increment the value in the statistics file by amount

    """
    stat_dict = return_stat_file_dict(stats_csv)
    add_update_csv(_logger, stats_csv, stat, int(stat_dict[stat]) + amount)


def return_stat_file_dict(stats_csv):
    """
    Read the statistics file and return as keys and values in a dictionary

    """
    with open(stats_csv, mode='r') as infile:
        reader = csv.reader(infile)
        return OrderedDict((row[0], row[1]) for row in reader)


def recreate_stat_file(id_file, stats_csv, stats_interval, mycodo_version):
    """
    Create a statistics file with basic stats

    if anonymous_id is not provided, generate one

    """
    uid_gid = pwd.getpwnam('mycodo').pw_uid
    if not os.path.isfile(id_file):
        anonymous_id = ''.join([random.choice(
            string.ascii_letters + string.digits) for _ in xrange(12)])
        with open(id_file, 'w') as write_file:
            write_file.write('{}'.format(anonymous_id))
        os.chown(id_file, uid_gid, uid_gid)
        os.chmod(id_file, 0664)

    with open(id_file, 'r') as read_file:
        stat_id = read_file.read()

    new_stat_data = [['stat', 'value'],
                     ['id', stat_id],
                     ['next_send', time.time() + stats_interval],
                     ['RPi_revision', get_pi_revision()],
                     ['Mycodo_revision', mycodo_version],
                     ['git_commit', 'None'],
                     ['country', 'None'],
                     ['daemon_startup_seconds', 0.0],
                     ['ram_use_mb', 0.0],
                     ['num_users_admin', 0],
                     ['num_users_guest', 0],
                     ['num_lcds', 0],
                     ['num_lcds_active', 0],
                     ['num_logs', 0],
                     ['num_logs_active', 0],
                     ['num_methods', 0],
                     ['num_methods_in_pid', 0],
                     ['num_pids', 0],
                     ['num_pids_active', 0],
                     ['num_relays', 0],
                     ['num_sensors', 0],
                     ['num_sensors_active', 0],
                     ['num_timers', 0],
                     ['num_timers_active', 0]]

    with open(stats_csv, 'w') as csv_stat_file:
        write_csv = csv.writer(csv_stat_file)
        for row in new_stat_data:
            write_csv.writerow(row)
    os.chown(stats_csv, uid_gid, uid_gid)
    os.chmod(stats_csv, 0664)


def send_stats(_logger, host, port, user, password, dbname,
               mycodo_db_path, user_db_path, stats_csv, mycodo_version,
               session_scope, LCD, Log, Method, PID, Relay, Sensor, Timer, Users):
    """
    Send anonymous usage statistics

    Example use:
        current_stat = return_stat_file_dict()
        add_update_csv(logger, csv_file, 'stat', current_stat['stat'] + 5)
    """
    try:
        client = InfluxDBClient(host, port, user, password, dbname)
        # Prepare stats before sending
        with session_scope(mycodo_db_path) as new_session:
            relays = new_session.query(Relay)
            add_update_csv(_logger, stats_csv, 'num_relays', get_count(relays))

            sensors = new_session.query(Sensor)
            add_update_csv(_logger, stats_csv, 'num_sensors', get_count(sensors))
            add_update_csv(_logger, stats_csv, 'num_sensors_active', get_count(sensors.filter(
                Sensor.activated == True)))

            pids = new_session.query(PID)
            add_update_csv(_logger, stats_csv, 'num_pids', get_count(pids))
            add_update_csv(_logger, stats_csv, 'num_pids_active', get_count(pids.filter(
                PID.activated == True)))

            lcds = new_session.query(LCD)
            add_update_csv(_logger, stats_csv, 'num_lcds', get_count(lcds))
            add_update_csv(_logger, stats_csv, 'num_lcds_active', get_count(lcds.filter(
                LCD.activated == True)))

            logs = new_session.query(Log)
            add_update_csv(_logger, stats_csv, 'num_logs', get_count(logs))
            add_update_csv(_logger, stats_csv, 'num_logs_active', get_count(logs.filter(
                Log.activated == True)))

            methods = new_session.query(Method)
            add_update_csv(_logger, stats_csv, 'num_methods', get_count(methods.filter(
                Method.method_order == 0)))
            add_update_csv(_logger, stats_csv, 'num_methods_in_pid', get_count(pids.filter(
                PID.method_id != '')))

            timers = new_session.query(Timer)
            add_update_csv(_logger, stats_csv, 'num_timers', get_count(timers))
            add_update_csv(_logger, stats_csv, 'num_timers_active', get_count(timers.filter(
                Timer.activated == True)))

        add_update_csv(_logger, stats_csv, 'country', geocoder.ip('me').country)
        add_update_csv(_logger, stats_csv, 'ram_use_mb', resource.getrusage(
            resource.RUSAGE_SELF).ru_maxrss / float(1000))

        user_count = 0
        admin_count = 0
        with session_scope(user_db_path) as db_session:
            users = db_session.query(Users).all()
            for each_user in users:
                user_count += 1
                if each_user.user_restriction == 'admin':
                    admin_count += 1
        add_update_csv(_logger, stats_csv, 'num_users_admin', admin_count)
        add_update_csv(_logger, stats_csv, 'num_users_guest', user_count - admin_count)

        add_update_csv(_logger, stats_csv, 'Mycodo_revision', mycodo_version)

        add_update_csv(_logger, stats_csv, 'git_commit', get_git_commit())

        # Combine stats into list of dictionaries to be pushed to influxdb
        new_stats_dict = return_stat_file_dict(stats_csv)
        formatted_stat_dict = []
        for each_key, each_value in new_stats_dict.iteritems():
            if each_key != 'stat':  # Do not send header row
                formatted_stat_dict = add_stat_dict(formatted_stat_dict,
                                                    new_stats_dict['id'],
                                                    each_key,
                                                    each_value)

        # Send stats to influxdb
        client.write_points(formatted_stat_dict)
        _logger.debug("[Daemon] Sent anonymous usage statistics")
        return 0
    except Exception as except_msg:
        _logger.exception('[Daemon] Could not send anonymous usage statictics: '
                         '{}'.format(except_msg))
        return 1
