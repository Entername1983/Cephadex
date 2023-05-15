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
        'fileHandler': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'DEBUG',
            'formatter': 'simpleFormatter',
            'filename': 'app.log',
            'maxBytes': 1024*1024*5,  # 5MB
            'backupCount': 5,  # keep 5 backup files
        },
    },
    'root': {
        'level': 'DEBUG',
        'handlers': ['consoleHandler', 'fileHandler'],
    },
}