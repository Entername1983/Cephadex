from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy

def init_extensions(app):
    db = SQLAlchemy()
    bcrypt = Bcrypt(app)
    migrate = Migrate(app, db)
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    socketio = SocketIO(app, cors_allowed_origins="*")
    return db, bcrypt, migrate, login_manager, socketio