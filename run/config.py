
from config.settings import MAX_CONTENT, SQLALCHEMY_DATABASE_URI, SECRET_KEY, UPLOAD_FOLDER
import os

config_name = os.environ.get('ENVIRONMENT')

def configure_app(app) -> None:
    app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT
    app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = SECRET_KEY
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    ##app.config.from_object('config')
    # Ensure templates are auto-reloaded
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    # Configure session to use filesystem (instead of signed cookies)
    app.config["SESSION_PERMANENT"] = False
    app.config["SESSION_TYPE"] = "filesystem"
    

    
