import os
import openai
import stripe


openai.api_key = os.environ.get("OPENAI_API_KEY")
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
endpoint_secret = os.environ.get("STRIPE_SIGNING_SECRET")
AUTH2_CLIENT_ID = os.environ.get("AUTH2_CLIENT_ID")
SEND_GRID_KEY = os.environ.get("SEND_GRID_KEY")
UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER")
SECRET_KEY = os.environ.get("SECRET_KEY")
DEBUG = os.environ.get("DEBUG")
SQLALCHEMY_DATABASE_URI = os.environ.get("SQLALCHEMY_DATABASE_URI")
SQLALCHEMY_TRACK_MODIFICATIONS = os.environ.get("SQLALCHEMY_TRACK_MODIFICATIONS")
ALLOWED_EXTENSIONS = os.environ.get("ALLOWED_EXTENSIONS")
# = os.environ.get("FLASKDEBUG")
MAX_CONTENT = os.environ.get("MAX_CONTENT")
ENVIRONMENT = os.environ.get('ENVIRONMENT')
APP_URL = os.environ.get('APP_URL')

ALLOWED_TAGS = [    'a', 'abbr', 'acronym', 'b', 'br', 'code', 'em', 'i', 'li',    'ol', 'strong', 'ul', 'p', 'pre', 'blockquote', 'hr', 'img',    'table', 'thead', 'tbody', 'tfoot', 'tr', 'th', 'td', 'div',    'span', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']
ALLOWED_ATTRIBUTES = {
    '*': ['class', 'style'],
    'a': ['href', 'title'],
    'abbr': ['title'],
    'acronym': ['title'],
    'img': ['alt', 'src'],
    'table': ['border', 'cellpadding', 'cellspacing'],
    'th': ['scope'],
    'td': ['colspan', 'rowspan'],
    'iframe': ['src', 'width', 'height', 'frameborder', 'allow', 'allowfullscreen']
}

## Token related processing
TOKENS_PER_PAGE = 341
PAGES_PER_MIN = 3
ACCEPTABLE_ERROR_RATIO = 0.2
if MAX_CONTENT is not None:
    MAX_CONTENT = int(MAX_CONTENT)


##ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx', 'pptx', 'wav', 'mp3'}
ALLOWED_IMAGES = {'png', 'jpg', 'jpeg', 'gif', 'svg'}
