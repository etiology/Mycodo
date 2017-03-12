# coding=utf-8
import logging
import datetime
import grp
import os
import pwd
import socket
import subprocess

logger = logging.getLogger("mycodo.system_pi")


def time_between_range(start_time, end_time):
    """
    Check if the current time is between start_time and end_time

    :return: 1 is within range, 0 if not within range
    :rtype: int
    """
    start_hour = int(start_time.split(":")[0])
    start_min = int(start_time.split(":")[1])
    end_hour = int(end_time.split(":")[0])
    end_min = int(end_time.split(":")[1])
    now_time = datetime.datetime.now().time()
    now_time = now_time.replace(second=0, microsecond=0)
    if ((start_hour < end_hour) or
            (start_hour == end_hour and start_min < end_min)):
        if datetime.time(start_hour, start_min) <= now_time <= datetime.time(end_hour, end_min):
            return 1  # Yes now within range
    else:
        if now_time >= datetime.time(start_hour, start_min) or now_time <= datetime.time(end_hour, end_min):
            return 1  # Yes now within range
    return 0  # No now not within range


def cmd_output(command, su_mycodo=True):
    """
    Executed command and returns a list of lines from the output
    """
    full_cmd = '{}'.format(command)
    if su_mycodo:
        full_cmd = 'su mycodo && {}'.format(command)
    cmd = subprocess.Popen(full_cmd, stdout=subprocess.PIPE, shell=True)
    cmd_out, cmd_err = cmd.communicate()
    cmd_status = cmd.wait()
    return cmd_out, cmd_err, cmd_status


def internet(host="8.8.8.8", port=53, timeout=3):
    """
    Checks if there is an internet connection
    Host: 8.8.8.8 (google-public-dns-a.google.com)
    OpenPort: 53/tcp
    Service: domain (DNS/TCP)
    """
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET,
                      socket.SOCK_STREAM).connect((host, port))
        return True
    except Exception as e:
        logger.error(
            "Function 'internet()' raised exception: {err}".format(err=e))
    return False


def assure_path_exists(path):
    """ Create path if it doesn't exist """
    if not os.path.exists(path):
        os.makedirs(path)
        os.chmod(path, 0774)
        set_user_grp(path, 'mycodo', 'mycodo')
    return path


def csv_to_list_of_int(str_csv):
    """ return a list of integers from a string of csv integers """
    if str_csv:
        list_int = []
        for x in str_csv.split(','):
            list_int.append(int(x))
        return list_int


def find_owner(filename):
    """ Return the owner of a file """
    return pwd.getpwuid(os.stat(filename).st_uid).pw_name


def get_sec(time_str):
    """ Convert HH:MM:SS string into number of seconds """
    h, m, s = time_str.split(':')
    return int(h) * 3600 + int(m) * 60 + int(s)


def is_int(test_var, check_range=None):
    """
    Test if var is integer (and also between range)
    check_range should be a list of minimum and maximum values
    e.g. check_range=[0, 100]
    """
    try:
        value = int(test_var)
    except ValueError:
        return False

    if check_range:
        if not (check_range[0] <= int(test_var) <= check_range[1]):
            return False

    return True


def set_user_grp(filepath, user, group):
    """ Set the UID and GUID of a file """
    uid = pwd.getpwnam(user).pw_uid
    gid = grp.getgrnam(group).gr_gid
    os.chown(filepath, uid, gid)
