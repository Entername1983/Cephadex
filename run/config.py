
from config.settings import UPLOAD_FOLDER
import os
import openai
import stripe

config_name = os.environ.get('ENVIRONMENT')

def configure_app(app) -> None:

    app.config['MAX_CONTENT_LENGTH'] = 104857600
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("SQLALCHEMY_DATABASE_URI")
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    ##app.config.from_object('config')
    # Ensure templates are auto-reloaded
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    # Configure session to use filesystem (instead of signed cookies)
    app.config["SESSION_PERMANENT"] = False
    app.config["SESSION_TYPE"] = "filesystem"
    openai.api_key = os.environ.get("OPENAI_API_KEY")
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

endpoint_secret = os.environ.get("STRIPE_SIGNING_SECRET")

    
