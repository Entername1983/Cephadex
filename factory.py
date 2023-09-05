
from flask import Flask
from run.logger_setup import setup_app_logger
from run.config import configure_app
from run.extensions import init_extensions
from views.deck_bp import deck_bp

import logging


def create_app():

    app = Flask(__name__)

    configure_app(app)

    app.logger.setLevel(logging.WARNING)

    setup_app_logger()
    init_extensions(app)

 
    return app