
import logging
from logging.handlers import RotatingFileHandler
import os

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'handlers': {
        'default': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/app.log',
            'maxBytes': 1024*1024*5,  # 5 MB
            'backupCount': 5,
            'formatter': 'standard',
        },
        'processing': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/processing.log',
            'maxBytes': 1024*1024*5,  # 5 MB
            'backupCount': 5,
            'formatter': 'standard',
        },
        'rollover': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/rollover.log',
            'maxBytes': 1024*1024*5,  # 5 MB
            'backupCount': 5,
            'formatter': 'standard',
        },
    },
    'loggers': {
        'werkzeug': {
            'handlers': ['default'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'pdfminer': {
            'handlers': ['default'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'processing': {
            'handlers': ['processing'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'rollover': {
            'handlers': ['rollover'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}


def setup_logging():
    if not os.path.exists('logs'):
        os.makedirs('logs')
    logging.config.dictConfig(LOGGING_CONFIG)