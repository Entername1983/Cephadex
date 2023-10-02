
from flask import Flask
from run.logger_setup import setup_app_logger, setup_payment_logger
from run.config import configure_app
from run.extensions import init_extensions

import logging


def create_app():
    app = Flask(__name__)
    configure_app(app)
    app.logger.setLevel(logging.WARNING)
    setup_app_logger()
    init_extensions(app)
    setup_payment_logger()

    return app