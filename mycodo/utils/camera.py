# coding=utf-8
import logging
import datetime
import picamera
import time

from system_pi import assure_path_exists
from system_pi import set_user_grp

logger = logging.getLogger(__name__)


#
# Camera record
#
def camera_record(install_directory, record_type, settings, duration_sec=None, start_time=None, capture_number=None):
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    if record_type == 'photo':
        path = '{}/camera-stills'.format(install_directory)
        filename = 'Still-{}.jpg'.format(timestamp)
        path_file = '{}/{}'.format(path, filename)
    elif record_type == 'timelapse':
        path = '{}/camera-timelapse'.format(install_directory)
        filename = '{}-img-{:05d}.jpg'.format(start_time, capture_number)
        path_file = '{}/{}'.format(path, filename)
    elif record_type == 'video':
        path = '{}/camera-video'.format(install_directory)
        filename = 'Video-{}.h264'.format(timestamp)
        path_file = '{}/{}'.format(path, filename)

    logging.debug("Camera path is: {path}".format(path=path))
    assure_path_exists(path)

    with picamera.PiCamera() as camera:
        camera.resolution = (1296, 972)
        camera.hflip = settings.hflip
        camera.vflip = settings.vflip
        camera.rotation = settings.rotation
        camera.start_preview()
        time.sleep(2)  # Camera warm-up time

        if record_type == 'photo' or record_type == 'timelapse':
            camera.capture(path_file, use_video_port=True)
        elif record_type == 'video':
            camera.start_recording(path_file, format='h264', quality=20)
            camera.wait_recording(duration_sec)
            camera.stop_recording()

    try:
        set_user_grp(path_file, 'mycodo', 'mycodo')
    except Exception as e:
        logger.error("Exception raised in 'camera_record' when setting user grp: {err}".format(err=e))
