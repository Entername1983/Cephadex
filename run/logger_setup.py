import logging
import logging.handlers
from logging.handlers import RotatingFileHandler
import sys
import os

LOGGING_LEVEL = os.environ.get('LOGGING_LEVEL', 'INFO').upper()
LOGGING_LEVEL_CONST = getattr(logging, LOGGING_LEVEL, logging.INFO)





def setup_app_logger():
    logger = logging.getLogger('flask_app')
    logger.setLevel(LOGGING_LEVEL_CONST)

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG)  # Set the level for this handler

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    stdout_handler.setFormatter(formatter)

    logger.addHandler(stdout_handler)

    if not os.path.exists('logs'):
        os.makedirs('logs')

    file_handler = RotatingFileHandler('logs/flask_app.log', maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    error_file_handler = RotatingFileHandler('logs/flask_app_errors.log', maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
    error_file_handler.setLevel(logging.ERROR) 
    error_file_handler.setFormatter(formatter) 

    # Suppressing Flask's built-in Werkzeug logger
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.ERROR)

    logger.addHandler(error_file_handler)
    return logger

def setup_processing_logger():
    processing_logger = logging.getLogger('job_processing')
    processing_logger.setLevel(LOGGING_LEVEL_CONST)

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    stdout_handler.setFormatter(formatter)

    processing_logger.addHandler(stdout_handler)
    
    if not os.path.exists('logs'):
        os.makedirs('logs')

    file_handler = RotatingFileHandler('logs/job_processing.log', maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    processing_logger.addHandler(file_handler)

    error_file_handler = RotatingFileHandler('logs/job_processing_errors.log', maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
    error_file_handler.setLevel(logging.ERROR)  
    error_file_handler.setFormatter(formatter) 
    processing_logger.addHandler(error_file_handler)

    return processing_logger


def setup_subrollover_logger():
    subrollover_logger = logging.getLogger('subrollover')
    subrollover_logger.setLevel(LOGGING_LEVEL_CONST)
    
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG)  # Set the level for this handler

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    stdout_handler.setFormatter(formatter)

    subrollover_logger.addHandler(stdout_handler)

    if not os.path.exists('logs'):
        os.makedirs('logs')

    file_handler = RotatingFileHandler('logs/subrollover.log', maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    subrollover_logger.addHandler(file_handler)

    error_file_handler = RotatingFileHandler('logs/subrollover.log', maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
    error_file_handler.setLevel(logging.ERROR) 
    error_file_handler.setFormatter(formatter) 

    subrollover_logger.addHandler(error_file_handler)
    return subrollover_logger



def setup_paymenet_logger():
    payment_logger = logging.getLogger('payment')
    payment_logger.setLevel(LOGGING_LEVEL_CONST)
    return payment_logger