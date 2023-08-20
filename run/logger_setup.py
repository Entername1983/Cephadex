import logging
import logging.handlers

def setup_app_logger():
    logger = logging.getLogger('flask_app')
    # Configuration for the Flask app logger...
    return logger

def setup_processing_logger():
    processing_logger = logging.getLogger('processing')
    # Configuration for the background task logger...
    return processing_logger