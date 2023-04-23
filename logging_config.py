LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simpleFormatter': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'handlers': {
        'consoleHandler': {
            'class': 'logging.StreamHandler',
            'level': 'DEBUG',
            'formatter': 'simpleFormatter',
            'stream': 'ext://sys.stdout',
        },
    },
    'loggers': {
        '': {
            'level': 'DEBUG',
            'handlers': ['consoleHandler'],
        },
        'werkzeug': {
            'level': 'INFO',
            'handlers': ['consoleHandler'],
            'propagate': False,
        },
        'flask.app': {
            'level': 'DEBUG',
            'handlers': ['consoleHandler'],
            'propagate': False,
        },
    },
}