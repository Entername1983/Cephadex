
from flask import Flask
from run.logger_setup import setup_app_logger
from run.config import configure_app
from run.extensions import init_extensions
from views.deck_bp import deck_bp
from views.extract_bp import extract_bp
from views.game_bp import game_bp
from views.info_bp import info_bp
from views.quiz_bp import quiz_bp
from views.study_bp import study_bp
from views.user_bp import user_bp
from views.group_bp import group_bp
import logging


def create_app():
    app = Flask(__name__)
    configure_app(app)
    app.register_blueprint(deck_bp, url_prefix='/deck_bp')
    app.register_blueprint(extract_bp, url_prefix='/extract_bp')
    app.register_blueprint(game_bp, url_prefix='/game_bp')
    app.register_blueprint(info_bp, url_prefix='/info_bp')
    app.register_blueprint(quiz_bp, url_prefix='/quiz_bp')
    app.register_blueprint(study_bp, url_prefix='/study_bp')
    app.register_blueprint(user_bp, url_prefix='/user_bp')
    app.register_blueprint(group_bp, url_prefix='/group_bp')
    app.logger.setLevel(logging.WARNING)


    setup_app_logger()
    init_extensions(app)

 
    return app