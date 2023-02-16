# import common settings
from .base import *
from pathlib import Path

SECRET_KEY = 'very secret ...'

DEBUG = True

ALLOWED_HOSTS = []

home = str(Path.home())

EPANET_BIN_PATH = home + '/git/EPANET2.2/SRC_engines/epanet2'

RQ_QUEUES = {
    'crunch': {
        'HOST': 'localhost',
        'PORT': 6379,
        'DB': 0,
        'PASSWORD': 'very_secret',
        'DEFAULT_TIMEOUT': int(MAX_PROCESSING_TIME * 1.05), # user a small buffer
    },
    'delete': {
        'HOST': 'localhost',
        'PORT': 6379,
        'DB': 0,
        'PASSWORD': 'very_secret',
        'DEFAULT_TIMEOUT': 60,
    },
    'cancel': {
        'HOST': 'localhost',
        'PORT': 6379,
        'DB': 0,
        'PASSWORD': 'very_secret',
        'DEFAULT_TIMEOUT': 60,
    },
}
