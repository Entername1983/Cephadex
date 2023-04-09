import openai 
import os
from bs4 import BeautifulSoup
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Mapped
from flask import Flask, flash, redirect, render_template, request, session, url_for, Response, send_file, jsonify
from flask_session import Session
from tempfile import mkdtemp
import pytz
from pytz import common_timezones
from sqlalchemy_utils import database_exists, create_database
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from wtforms import StringField, PasswordField, SubmitField, RadioField, SelectField, BooleanField, TextAreaField
from flask_wtf.file import FileField, FileRequired
from wtforms_sqlalchemy.fields import QuerySelectField
from wtforms.validators import InputRequired, Length, ValidationError, EqualTo, Optional, URL
from flask_wtf import FlaskForm
from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename
from cardcreator import create_image, creator
from extractors import send_question_generator, why_wrong_generator, explain_more, split_text, regenerate_definition, count_tokens, add_period, extract_from_wiki, extract_from_youtube, text_extractor, create_pdf, check_comma_list, get_video_id, text_extractor
from google.oauth2 import id_token
from google.auth.transport import requests
import sys
from sqlalchemy.sql import func
import logging
import logging.handlers
from logging.handlers import RotatingFileHandler
import json
from datetime import datetime, timedelta
import datetime as dt
from flask_migrate import Migrate
import urllib.parse
from urllib.parse import unquote
from helpers import remove_punctuation, apology
import difflib
from anki import anki_import_all, anki_import_deck, anki_create_deck, anki_create_card, find_notes, check_anki_connect
from flask import abort
from celery import Celery
import time
import schedule
from beta import BetaKeys
from config import UPLOAD_FOLDER, SECRET_KEY, DEBUG, BROKER, SQLALCHEMY_DATABASE_URI, MAX_CONTENT, SQLALCHEMY_TRACK_MODIFICATIONS, ALLOWED_EXTENSIONS
from models import db, Job, TestResult, QuestionResult, Question, Test, Feedback, ResponseData, DeckFiles, Subscriber, Deck, SharedDecks, Card
from models import UsageRecord, SubscriptionPlan, User, cards, source_files, cards_shared, questions, distribution, UserSettings
import configparser
import logging.config
from events import event_tracker

config_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logging_config.ini')

logging.config.fileConfig(config_file_path)


openai.api_key = os.environ.get("OPENAI_API_KEY")
os.environ["FLASK_DEBUG"] = "1"
# Configure application
app = Flask(__name__)
app.config.from_object('config')


bcrypt = Bcrypt(app)
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = SECRET_KEY
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.debug('debug message')
werkzeug_logger.info('info message')
werkzeug_logger.warning('warn message')  
werkzeug_logger.error('error message')
werkzeug_logger.critical('critical message')

app.logger.addHandler(logging.StreamHandler(sys.stdout))
app.logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
app.logger.handlers[0].setFormatter(formatter)  # set formatter for the first handler
app.logger.disabled = True

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx', 'pptx', 'wav', 'mp3'}

migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


print("APP STARTING")
######################## WTFORMS ###########################################          
class RegSub(FlaskForm):
    first_name = StringField('First Name', validators=[InputRequired()], render_kw={"placeholder": "First Name"})
    last_name = StringField('Last Name', validators=[InputRequired()], render_kw= {"placeholder": "Last Name"})           
    email = StringField(validators=[InputRequired(), EqualTo('conf_email', message = 'Emails must match'), Length(min=5, max=100)], render_kw={"placeholder": "Email"})
    conf_email = StringField(validators=[InputRequired(), Length(min=5, max=100)], render_kw={"placeholder": "Confirm Email"})        
    submit = SubmitField('Subscribe')
    
      
class RegisterForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(min=4, max=20)], render_kw={"placeholder": "Username"})
    password = PasswordField(validators=[InputRequired(), Length(min=8, max=80)], render_kw={"placeholder": "Password"})
    conf_password = PasswordField(validators=[InputRequired(), EqualTo('password', message = 'Passwords must match'), Length(min=8, max=80)], render_kw={"placeholder": "Confirm Password"})
    email = StringField(validators=[InputRequired(), EqualTo('conf_email', message = 'Emails must match'), Length(min=5, max=100)], render_kw={"placeholder": "Email"})
    conf_email = StringField(validators=[InputRequired(), Length(min=5, max=100)], render_kw={"placeholder": "Confirm Email"})
    first_name = StringField(validators=[InputRequired(), Length(min=4, max=50)], render_kw={"placeholder": "First Name"})
    last_name = StringField(validators=[InputRequired(), Length(min=4, max=50)], render_kw={"placeholder": "Last Name"})
    timezone = SelectField('Timezone',
                           choices=[('', 'Choose a time zone')] + [(tz, tz) for tz in common_timezones],
                           default=None,
                           render_kw={'class': 'form-select', 'id': 'timezone', 'placeholder': 'Choose timezone'})
    submit = SubmitField('Register')

    def validate_username(self, username):
        existing_user_username = User.query.filter_by(username=username.data).first()
        if existing_user_username:
            raise ValidationError("Username is already taken")
            
    def validate_email(self, email):
        existing_user_email = User.query.filter_by(email=email.data).first()
        if existing_user_email:
            raise ValidationError("Email is already taken")
        

        
class LoginForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(min=4, max=20)], render_kw={"placeholder": "Username"})
    password = PasswordField(validators=[InputRequired(), Length(min=8, max=80)], render_kw={"placeholder": "Password"})
    submit = SubmitField('Login')
class ChangePassForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(min=4, max=20)], render_kw={"placeholder": "Username"})
    password = PasswordField(validators=[InputRequired(), Length(min=8, max=80)], render_kw={"placeholder": "Password"})
    new_password = PasswordField(validators=[InputRequired(), Length(min=8, max=80)], render_kw={"placeholder": "New Password"})
    conf_new_password = PasswordField(validators=[InputRequired(), EqualTo('new_password', message = 'passwords must match'), Length(min=8, max=80)], render_kw={"placeholder": "Confirm New Password"})
    submit = SubmitField('Change Password')
        
    def confirm_new_pass(self, new_password, conf_new_password):
        if new_password.data != conf_new_password.data:
            raise ValidationError("Passwords must match")
        
        
        
class TryOut(FlaskForm):
    text_input = StringField('Text Input', validators=[Length(max=250)], render_kw={"placeholder": "Paste your text here (max 250 characters)"})

    prompt = RadioField('Prompt', choices=[('Definitions', 'Definitions'), ('Mcq', 'Multiple choice questions'), ('Translate', 'Translate'), ('Cloze', 'Fill in the blank'),
                                           ('Comprehension', 'Comprehension'), ('Custom', 'Custom')], default='Definitions')
    languages = SelectField('Languages', choices=[("",  "Choose a language"), ("English",  "English"), ("Arabic", "Arabic"), ("Bulgarian", "Bulgarian"), ("Chinese", "Chinese"), ("Croatian",  "Croatian"), 
                                                  ("Czech",  "Czech"), ("Dutch", "Dutch"), ("Dothraki",  "Dothraki"), ("Elvish", "Elvish"), ("English",  "English"), 
                                                  ("Estonian", "Estonian"), ("Farsi", "Farsi"), ("French",  "French"), ("German", "German"), ("Greek",  "Greek"),
                                                  ("Hebrew", "Hebrew"), ("Hindi", "Hindi"), ("Hungarian", "Hungarian"), ("Indonesian", "Indonesian"),
                                                  ("Italian", "Italian"), ("Japanese", "Japanese"), ("Korean", "Korean"), ("Klingon", "Klingon"),
                                                  ("Latvian", "Latvian"), ("Lithuanian", "Lithuanian"), ("Malay", "Malay"), ("Norwegian", "Norwegian"),
                                                  ("Polish", "Polish"), ("Portuguese", "Portuguese"), ("Romanian", "Romanian"), ("Russian",  "Russian"),
                                                  ("Spanish", "Spanish"), ("Serbian", "Serbian"), ("Swahili", "Swahili"), ("Swedish", "Swedish"),
                                                  ("Tagalog", "Tagalog"), ("Thai", "Thai"), ("Turkish", "Turkish"), ("Urdu",  "Urdu"),
                                                  ( "Vietnamese", "Vietnamese")], default = None)
    custom_term = StringField('Custom extraction', render_kw={"placeholder": "What do you want us to get out of the text?"})
    custom_content = StringField('Custom content', render_kw={"placeholder": "What do you want us to do with what you extracted?"})
    submit = SubmitField("Generate", render_kw={"id": "extract-submit"})
    
    

        
class UploadFileForm(FlaskForm):
    file = FileField("File")
    name = StringField("Deck name", render_kw={"placeholder": "Name your deck"})
    description = StringField("Description", render_kw={"placeholder": "Describe your deck"})
    submit = SubmitField("Generate", render_kw={"id": "extract-submit"})
    deck_list = QuerySelectField("Choose a deck", query_factory=lambda: Deck.query.filter(Deck.user_id == current_user.id), allow_blank=True, get_label='name', render_kw={"placeholder": "Choose an existing deck"})
    prompt = RadioField('Prompt', choices=[('Definitions', 'Definitions'), ('Mcq', 'MCQ'), ('Translate', 'Translate'), ('Cloze', 'Fill in the blank'),
                                           ('Formulas', 'Formulas'), ('Theories', 'Theories'), ('Rhyme', 'Rhyme'), ('Comprehension', 'Comprehension'),
                                           ('People', 'People'), ('Vocab_builder', 'Vocabulary builder'), ('Transcribe', 'Transcribe'),  ('Summarize', 'Summarize (coming soon)'),
                                           ('Turn2notes', 'Turn to notes (coming soon)'), ('Custom', 'Custom')], default='Definitions')
    generate_images = BooleanField('Generate_images')
    save_text = BooleanField('Save_text')
    languages = SelectField('Languages', choices=[("", "If you want your transcription translated selected a language"), ("English",  "English"), ("Arabic", "Arabic"), ("Bulgarian", "Bulgarian"), ("Chinese", "Chinese"), ("Croatian",  "Croatian"), 
                                                  ("Czech",  "Czech"), ("Dutch", "Dutch"), ("Dothraki",  "Dothraki"), ("Elvish", "Elvish"), ("English",  "English"), 
                                                  ("Estonian", "Estonian"), ("Farsi", "Farsi"), ("French",  "French"), ("German", "German"), ("Greek",  "Greek"),
                                                  ("Hebrew", "Hebrew"), ("Hindi", "Hindi"), ("Hungarian", "Hungarian"), ("Indonesian", "Indonesian"),
                                                  ("Italian", "Italian"), ("Japanese", "Japanese"), ("Korean", "Korean"), ("Klingon", "Klingon"),
                                                  ("Latvian", "Latvian"), ("Lithuanian", "Lithuanian"), ("Malay", "Malay"), ("Norwegian", "Norwegian"),
                                                  ("Polish", "Polish"), ("Portuguese", "Portuguese"), ("Romanian", "Romanian"), ("Russian",  "Russian"),
                                                  ("Spanish", "Spanish"), ("Serbian", "Serbian"), ("Swahili", "Swahili"), ("Swedish", "Swedish"),
                                                  ("Tagalog", "Tagalog"), ("Thai", "Thai"), ("Turkish", "Turkish"), ("Urdu",  "Urdu"),
                                                  ( "Vietnamese", "Vietnamese")], default = None)
    
    text_input = StringField('Text Input', render_kw={"placeholder": "Paste your text here"})
    link_input = StringField('Link Input', render_kw={"placeholder": "Paste your link here"}, validators=[Optional()])
    qmin_option = StringField("Minimum number of items", render_kw={"placeholder": "Minimum"})
    qmax_option = StringField("Maximum number of items", render_kw={"placeholder": "Maximum"})
    subject = SelectField('Subject', choices=[('', ''),('Art', 'Art'), ('Anatomy', 'Anatomy'), ('Astron', 'Astronomy'), ('Bus', 'Business'), 
                                              ('Bio', 'Biology'), ('Chem', 'Chemistry'), ('CS', 'Computer Science'), ('Econ', 'Economics'), 
                                              ('Eng', 'Engineering'), ('Film', 'Film'), ('Geo', 'Geography'), ('Hist', 'History'), 
                                              ('Lit', 'Literature'), ('Law', 'Law'),
                                              ('Math', 'Math'), ('Music', 'Music'), ('Med', 'Medecine'), 
                                              ('Politics', 'Politics'), ('Physics', 'Physics'), ('Psych', 'Psychology'), ('Phil', 'Philosophy'), ('Phys', 'Physiology'),
                                              ('Science', 'Science'), ('Soc', 'Sociology'),], default = None, render_kw={"placeholder": "Select subject"})
    length = SelectField('Length', choices=[('', ''), ('long', 'Long'), ('short', 'Short')], default = None,  render_kw={"placeholder": ""})
    main_lang = SelectField('Main Language', choices=[('', ''), ("Arabic", "Arabic"), ("Bulgarian", "Bulgarian"), ("Chinese", "Chinese"), ("Croatian",  "Croatian"), 
                                                  ("Czech",  "Czech"), ("Dutch", "Dutch"), ("Dothraki",  "Dothraki"), ("Elvish", "Elvish"), ("English",  "English"), 
                                                  ("Estonian", "Estonian"), ("Farsi", "Farsi"), ("French",  "French"), ("German", "German"), ("Greek",  "Greek"),
                                                  ("Hebrew", "Hebrew"), ("Hindi", "Hindi"), ("Hungarian", "Hungarian"), ("Indonesian", "Indonesian"),
                                                  ("Italian", "Italian"), ("Japanese", "Japanese"), ("Korean", "Korean"), ("Klingon", "Klingon"),
                                                  ("Latvian", "Latvian"), ("Lithuanian", "Lithuanian"), ("Malay", "Malay"), ("Norwegian", "Norwegian"),
                                                  ("Polish", "Polish"), ("Portuguese", "Portuguese"), ("Romanian", "Romanian"), ("Russian",  "Russian"),
                                                  ("Spanish", "Spanish"), ("Serbian", "Serbian"), ("Swahili", "Swahili"), ("Swedish", "Swedish"),
                                                  ("Tagalog", "Tagalog"), ("Thai", "Thai"), ("Turkish", "Turkish"), ("Urdu",  "Urdu"),
                                                  ( "Vietnamese", "Vietnamese")], default = None, render_kw={"placeholder": ""})
    custom_term = StringField('Custom extraction', render_kw={"placeholder": "What do you want us to get out of the text?"})
    custom_content = StringField('Custom content', render_kw={"placeholder": "What do you want us to do with what you extracted?"})
    ##def validate_deck_list(self, name, deck_list):
       ## if name == '' and deck_list == '':            
        ##    raise ValidationError("You must select an existing deck OR enter a name for a new deck")
        ##elif name != '' and deck_list != '':            
        ##    raise ValidationError("You must select an existing deck OR enter a name for a new deck")
    
   ## def validate_name(self, name):
       ## deck_object = Deck.query.filter_by(name=name.data).first()
       ## if deck_object:
##raise ValidationError("Deck name already exists")
        
    
    ##def validate(self):
        ##count = 0
       ## if self.file.data:
       ##     count += 1
      ###  if self.text_input.data:
      ##      count += 1
      ##  if self.link_input.data:
      ##      count += 1
      ##  if count != 1:
      ##      raise ValidationError('Please select one and only one option: a file, input text, or input link.')
      ##  if self.prompt.data == 'Translate' and not self.languages.data:
       ##     raise ValidationError('Please select a language for translation.')
      ##  return True  
        
class EditCard(FlaskForm):
    term = StringField()
    content = StringField()
    submit = SubmitField("Save")
class EditDeck(FlaskForm):
    name = StringField()
    description = StringField()
    submit = SubmitField("Save")
class AddTermForm(FlaskForm):
    term = StringField(validators=[InputRequired(), Length(min=1, max=50)])
    content = StringField(validators=[InputRequired(), Length(min=1, max=50)])
    submit = SubmitField("Save")
    

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    
    ##TODO ONLY FOR http AND LOCALHOST, FOR GOOGLE AUTH
    response.headers["Referrer-Policy"] = "no-referrer-when-downgrade"
    return response    


print("APP STARTING2")

@app.route("/", methods=["GET", "POST"])
def index():
    print("entered index")
    logging.info("entered index logging")
    form = TryOut()
    terms = []
    if form.validate_on_submit():
        print("form validated")
        text = form.text_input.data
        prompt_options = {
            'main_opt': form.prompt.data or None,
            'trans_opt': form.languages.data or None,
            'lang_opt': None,
            'detail_lvl_opt': "long",
            'min_opt':  None,
            'max_opt':  None,
            'images_opt':  None,
            'save_text_opt':  None,
            'subject_opt':  None,
            'custom_term':  form.custom_term.data or None,
            'custom_content': form.custom_content.data or None,
        }
        print(text)
        print(prompt_options)
        
        response = creator(text, prompt_options)
        terms = response[0]
        for item in terms:
            print(item['A'])
            print(item['B'])
        
        event_tracker(None, "tryout", json.dumps(prompt_options), json.dumps(terms))
        return render_template('index.html', form = form, terms = terms, option = prompt_options['main_opt'])
            
    return render_template('index.html', form = form)

    
    
@app.route("/googleSignIn", methods=["POST"])
def googleSignIn():
    #Security validation
    print("entered google sign in")
    csrf_token_cookie = request.cookies.get('g_csrf_token')
    if not csrf_token_cookie:
        print('No CSRF token in Cookie.')#webapp2.abort(400, 'No CSRF token in Cookie.')
        return jsonify({'error': 'No CSRF token in Cookie'}), 400
    csrf_token_body = request.form.get('g_csrf_token')
    if not csrf_token_body:
        print('No CSRF token in post body.')#webapp2.abort(400, 'No CSRF token in post body.')
        return jsonify({'error': 'No CSRF token in post body.'}), 400
    if csrf_token_cookie != csrf_token_body:
        print('Failed to verify double submit cookie.')#webapp2.abort(400, 'Failed to verify double submit cookie.')
        return jsonify({'error': 'Failed to verify double submit cookie.'}), 400
    try:
        #encrypted credential
        credential = request.form.get('credential')
        # Decrypt credential, third parameter comes from google API console client ID
        idinfo = id_token.verify_oauth2_token(credential, requests.Request(),'945000040547-5j6598rtn7ikp4n0h4npsrvbkdk0il5u.apps.googleusercontent.com')
        # ID token is valid. Get the user's Google Account ID from the decoded token. (UniqueID to use for login)
        userid = idinfo['sub']
        
        user = User.query.filter_by(external_id=userid).first()
        
        if (user):
            login_user(user)
            flash('You have been logged in!', 'success')
            event_tracker(user.id, "login", "google")
            return redirect(url_for('index'))
        
        else:
            print("entered not user, preparing to register")
            session['google_id_token'] = idinfo['sub']
            if idinfo.get('email'):
                session['google_email'] = idinfo['email']
            else: 
                session['google_email'] = "n/a"
            if idinfo.get('given_name'):
                session['given_name'] = idinfo['given_name']
            else: 
                session['given_name'] = "Anonymous"
            print(session['given_name'])
            if idinfo.get('family_name'):
                session['family_name'] = idinfo['family_name']
            else: 
                session['family_name'] = "Anonymous"
            print(session['family_name'])
            return redirect(url_for('register'))
    
    except ValueError:
        # Invalid token
        pass
    return render_template('index.html', title='Index')

@app.route('/check_username/<username>', methods=["GET", "POST"])
def check_username(username):
    user = User.query.filter_by(username=username).first()

    # Check if username already exists
    user = User.query.filter_by(username=username).first()
    if user is not None:
        response = jsonify({'username_taken': True})
        response.status_code = 200
        return response
    else:
        response = jsonify({'username_taken': False})
        response.status_code = 200
        return response
    

@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if request.method == 'POST':
        print("entered register post request")
        # Get the user's name and password from the form data
        username = request.form['username']
        ##timezone = request.form['password']
        ##role = request.form['role']
        contacted = request.form.get('contacted')
        subscribe = request.form.get('subscribe')
        betakey = request.form.get('betakey')
        timezone = form.timezone.data
        if timezone == None:
            timezone = "Europe/Dublin"
        print(contacted)
        print(subscribe)
        if contacted == 'contacted':
            contacted = True
        else:
            contacted = False
        # Get the user's email address and ID token from the session
        email = session['google_email']
        userid= session['google_id_token']
        given_name = session['given_name']
        family_name = session['family_name']
        account_type = "free"
        subscription_plan = 1
        if betakey:
            if betakey in BetaKeys:
                subscription_plan = 3
                account_type = betakey
            else:
                return apology("Invalid Beta Key", 403)
        user = User(email=email, first_name=given_name, account_type = account_type, last_name=family_name,external_id=userid,
                    external_type='google', subscription_plan = subscription_plan, contacted_email=contacted, username=username,
                    timezone = timezone, subscription_start_date = datetime.utcnow())
        user_settings = UserSettings(user=user.id)
        if subscribe == "subscribe":
            sub_exists = Subscriber.query.filter_by(email=email).first()
            if not sub_exists:
                timestamp = datetime.utcnow()
                subscriber = Subscriber(email=email, first_name=given_name, last_name=family_name, timestamp = timestamp)
                db.session.add(subscriber)
        event_tracker(user.id, "register", "google")
        db.session.add(user_settings)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("You have been registered and logged in!", "success")
        return redirect(url_for('index'))
    return render_template('register.html', title='Register', form = form)
    
    ##register_form = RegisterForm()
    ## if register_form.validate_on_submit():
    ## hashed_password = bcrypt.generate_password_hash(register_form.password.data)
    ## user = User(username=.username.data, email=register_form.email.data, password=hashed_password, first_name=register_form.first_name.data, last_name=register_form.last_name.data)
    ## db.session.add(user)
    ## db.session.commit()
    ## flash("Your account has been created! You are now able to log in", "info")


@app.route('/login', methods=['GET', 'POST'])
def login():
    print("entered login")
    app.logger.info('0')
    email = request.form.get('email')
    form = TryOut()
    print(email)
    if email is not None:
        user = User.query.filter(User.email.ilike(email)).first()
        print(user)
        if user:
            if bcrypt.check_password_hash(user.password, request.form.get('password')):
                print("password correct")
                login_user(user)
                flash('You have been logged in!', 'success')
                return render_template('index.html', title='Index')
        else:
            flash('Login Unsuccessful. Please check username and password')
            return render_template('index.html', title='Index')
    return render_template('index.html', title='Index', form=form)


@app.route('/subscribe', methods=['GET', 'POST'])
def subscribe():
    subscribe_form = RegSub()
    if subscribe_form.validate_on_submit():
        subscriber = Subscriber(email=subscribe_form.email.data, first_name=subscribe_form.first_name.data, last_name=subscribe_form.last_name.data, timestamp = datetime.utcnow())
        db.session.add(subscriber)
        db.session.commit()
        flash('You are now subscribed to our newsletter!')

    return render_template('subscribe.html', title='Subscribe', form=subscribe_form)



@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    flash('You have been logged out!')
    return redirect(url_for('index'))




@app.route("/viewdecks", methods = ["GET", "POST"])
@login_required
def viewdecks():
    user_settings = UserSettings.query.filter_by(user=current_user.id).first()
    if user_settings == None:
        print("user settings not found")
        user_settings = UserSettings(user=current_user.id)
        db.session.add(user_settings)
        db.session.commit()
    
    
    shared_decks = SharedDecks.query.all()
   ## check if user has any pending tests
    tests = Test.query.filter(Test.taker.contains(current_user)).all()
    user = current_user
    email = current_user.email
    shared_decks = SharedDecks.query.filter(SharedDecks.receiver.ilike(f"%{email}%")).all()
    decks = Deck.query.filter(Deck.user_id == current_user.id).all()
    if request.method == 'GET':
        sort_method =request.args.get('sort')
        search_query = None
        search_query = request.args.get('search', '').strip()
        if sort_method != 'default':
            if sort_method == 'name_asc':
                decks = Deck.query.filter(Deck.user_id == current_user.id).order_by(Deck.name.asc()).all()
            elif sort_method == 'name_desc':
                decks = Deck.query.filter(Deck.user_id == current_user.id).order_by(Deck.name.desc()).all()
            elif sort_method == "cards_due_asc":
                decks = sorted(decks, key=lambda deck: deck.qty_cards_due())
            elif sort_method == "cards_due_desc":
                decks = sorted(decks, key=lambda deck: deck.qty_cards_due(), reverse=True) 
            elif sort_method == "category_asc":
                decks = Deck.query.filter(Deck.user_id == current_user.id).order_by(Deck.category.asc()).all()
            elif sort_method == "create_time_asc":
                decks = Deck.query.filter(Deck.user_id == current_user.id).order_by(Deck.time_created.asc()).all()
            elif sort_method == "create_time_dsc":
                decks = Deck.query.filter(Deck.user_id == current_user.id).order_by(Deck.time_created.desc()).all()          
        elif search_query:
            print("entered search_query")
            decks = Deck.query.filter(Deck.name.ilike(f'%{search_query}%')).all()   
        return render_template('viewdecks.html', decks=decks, shared_decks = shared_decks, tests=tests, user = user, settings = user_settings)
    if request.method == 'POST':
        deck_id = request.form['deck_id']
        deck = Deck.query.filter(Deck.id == deck_id).first()
        new_name = request.form['new_name']
        if new_name != '':
            deck.name = new_name
            db.session.commit()
        return render_template('viewdecks.html', decks=decks, shared_decks = shared_decks, tests=tests, user = user, settings = user_settings
        )
    return render_template('viewdecks.html', decks=decks, shared_decks = shared_decks, tests=tests, user = user, settings = user_settings)


@app.route("/createdeck", methods = ["GET", "POST"])
@login_required
def create_deck():
    return render_template("createdeck.html", title="Create Deck")

@app.route("/accountsettings", methods = ["GET", "POST"])
@login_required
def account_settings():
    return render_template("accountsettings.html", title="Account Settings")

@app.route("/study", methods = ["GET", "POST"])
@login_required
def study():
    return render_template("study.html", title="Study")

@app.route("/currentdeck/<deck_id>", methods = ["POST", "GET"])
@login_required
def currentdeck(deck_id):
    deck = Deck.query.filter_by(id=deck_id, user_id=current_user.id).first()
    cards = Card.query.filter(Card.decks.any(id=deck_id)).order_by(Card.id.desc()).all()
    if request.method == 'POST':
        term = request.form['term'] ## new term for card
        content = request.form['content'] ## new content for card
        id = request.form['id'] ## id of card to be edited
        card = Card.query.filter_by(id=id).first()
        if term != "":
            card.term = term
        if content != "":
            card.content = content
        db.session.commit()
    return render_template("currentdeck.html", title="Card Editor", deck=deck, cards=cards)

@app.route("/edit_deck/<deck_id>", methods = ["POST", "GET"])
@login_required
def edit_deck(deck_id):
    deck = Deck.query.filter_by(id=deck_id, user_id=current_user.id).first()
    cards = Card.query.filter(Card.decks.any(id=deck_id)).order_by(Card.id.desc()).all()
    if request.method == 'POST':
        term = request.form['term'] ## new term for card
        content = request.form['content'] ## new content for card
        id = request.form['id'] ## id of card to be edited
        card = Card.query.filter_by(id=id).first()
        if term != "":
            card.term = term
        if content != "":
            card.content = content
        db.session.commit()
    return render_template("edit_deck.html", title="Card Editor", deck=deck, cards=cards)                                
    
@app.route("/delete/<int:id>", methods = ["POST", "GET"])
@login_required
def delete(id):
    deck_to_delete = Deck.query.get_or_404(id)
    if(current_user.id != deck_to_delete.user_id):
        return jsonify({'error': 'Deck not assigned to user'}), 403
    db.session.delete(deck_to_delete)
    db.session.commit()
    return redirect(url_for('viewdecks'))

@app.route("/rename_deck/<int:id>/<string:new_name>", methods = ["POST", "GET"])
@login_required
def rename_deck(id, new_name):
    deck = Deck.query.get_or_404(id)
    if(current_user.id != deck.user_id):
        return jsonify({'error': 'Deck not assigned to user'}), 403
    deck.rename(new_name)
    db.session.commit()
    return redirect(url_for('viewdecks'))
    
@app.route("/account", methods = ["POST", "GET"])
@login_required
def account():
    form = RegisterForm()
    user = User.query.filter_by(id=current_user.id).first()
    subscriber = Subscriber.query.filter_by(email=user.email).first()
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        username = request.form.get('username')
        gender = request.form.get('gender')
        email_checkbox = request.form.get('email-checkbox')
        role = request.form.get('role')
        timezone = form.timezone.data
        print("email checkbox")
        print(email_checkbox)
        if email_checkbox == "contacted":
            user.contacted_email = True
        elif email_checkbox == None:
            user.contacted_email = False
        subscribe_checkbox = request.form.get('subscriber-checkbox')
        print(subscribe_checkbox)
        if first_name != "":
            user.first_name = first_name
        if last_name != "":
            user.last_name = last_name
        if timezone != "":
            user.timezone = timezone
        if username != "":
            if User.query.filter_by(username=username).first() is not None and username != user.username:
                flash("Username already taken")
            else:
                user.username = username
        if gender != "":
            user.gender = gender
        if role != "":
            user.role = role
        if subscribe_checkbox == "subscribe":
            if not Subscriber.query.filter_by(email=user.email).first():
                subscriber = Subscriber(email=user.email, first_name=user.first_name, last_name=user.last_name, timestamp = datetime.utcnow())
                db.session.add(subscriber)
                db.session.commit()
                print("subscribe")
                flash("You have been subscribed to our mailing list")
        elif subscribe_checkbox == "":
            subscriber = Subscriber.query.filter_by(email=user.email).first()
            db.session.delete(subscriber)
            db.session.commit()
            flash("You have been unsubscribed from our mailing list")
        else:
            if Subscriber.query.filter_by(email=user.email).first():
                subscriber = Subscriber.query.filter_by(email=user.email).first()
                db.session.delete(subscriber)
                db.session.commit()
                flash("You have been unsubscribed from our mailing list")
        db.session.commit()
        flash("Your account has been updated")
    return render_template("account.html", title="Account", form = form, user = user, subscriber = subscriber)

@app.route('/update_profile_pic', methods=['POST'])
def update_profile_pic():
  # get the uploaded file
  profile_picture = request.files['profile-pic']
  if profile_picture:
  # save the file to our server
    pic = os.path.join('static', 'profile_pictures', profile_picture.filename)
    user = User.query.filter_by(id=current_user.id).first()
    ##save the file to the server
    profile_picture.save(pic)
    user.pic = pic
    db.session.commit()
  else:
      flash('No file selected')
  return redirect(url_for('account'))


@app.route("/deletecard/<int:deck_id>/<int:card_id>", methods = ["POST"])
@login_required
def deletecard(deck_id, card_id):
    print("entered delete card")
    deck = Deck.query.get_or_404(deck_id)
    if(current_user.id != deck.user_id):
        print("deck not assigned to user")
        return apology('Deck not assigned to user', 403)
    card_to_delete = Card.query.get_or_404(card_id)
    print("what is happening here?")
    print(card_to_delete)
    if card_to_delete != None:
        print("going to to delete this card now")
        db.session.delete(card_to_delete)
        db.session.commit()
        flash("Card deleted")
        return jsonify({"status": "success", "message": "Card deleted"})
    else:
        return jsonify({"status": "error", "message": "Card not found"})
    ##cards = deck.cards
 ##   return render_template('carousel.html', title="Deck", deck=deck, cards=cards)

@app.route("/addterms/<int:deck_id>", methods = ["POST", "GET"])
@login_required
def addterms(deck_id):
    form = AddTermForm()
    deck = Deck.query.filter_by(id=deck_id, user_id=current_user.id).first()
    if(current_user.id != deck.user_id):
       return apology('Deck not assigned to user', 403)
    cards = Card.query.filter(Card.decks.any(id=deck_id)).order_by(Card.id.desc()).all()
    if form.validate_on_submit():
        key = form.term.data
        value = form.content.data
        entry = Card(term=key, content=value)
        db.session.add(entry)
        deck.cards.append(entry)  
        db.session.commit()
        deck = Deck.query.filter_by(id=deck_id, user_id=current_user.id).first()
        cards = Card.query.filter(Card.decks.any(id=deck_id)).order_by(Card.id.desc()).all()
        return render_template("addterms.html".format(deck=deck), title="Add Terms", form=form, cards=cards, deck=deck)
    return render_template("addterms.html".format(deck=deck), title="Add Terms", form=form, cards=cards, deck=deck)

@app.route("/downloadascsv/<int:deck_id>", methods = ["POST", "GET"])
@login_required
def downloadascsv(deck_id):
    event_tracker(current_user.id, "downloadascsv")
    print("entered download as csv")
    deck = Deck.query.filter_by(id=deck_id).first()
    if(current_user.id != deck.user_id):
       return jsonify({'error': 'Deck not assigned to user'}), 403
    termsstrings = []
    for card in deck.cards:
        print("entered cards")
        print(card.term)
        if card.boc_2 == None:
            card.boc_2 = "null"
        if card.boc_3 == None:
            card.boc_3 = "null"
        if card.boc_4 == None:
            card.boc_4 = "null"
        ## replace commas with semicolons
        string = card.term.replace(",", ";")  + "," + card.content.replace(",", ";")  + "," + card.boc_2.replace(",", ";")  + "," + card.boc_3.replace(",", ";")  + "," + card.boc_4.replace(",", ";")  + "," + card.category.replace(",", ";")  + "\n"
        termsstrings.append(string)            
    csvstring = "".join(termsstrings)        
    return Response(csvstring, mimetype="text/csv")

@app.route("/regenerate_def", methods = ["POST", "GET"])
@login_required
def regenerate_def():
    event_tracker(current_user.id, "regenerate_def")
    print("entered regen")
    card_id = request.form["id"]
    print(card_id)
    card = Card.query.filter(Card.id==card_id).first()
    prompt_options = process_prompt_options_regen(card)
    term = card.term 
    content = regenerate_definition(term, prompt_options)[0]
    print("in card")
    print(card.content)
    card.content = content
    print(card.content)
    try:
        db.session.add(card)
        db.session.commit()
        print("card updated succesfully")
    except:
        print("An error occurred while updating the card")      
    return jsonify({'content': content})

def process_prompt_options_regen(card):
    if card.prompt_option == None:
        card.prompt_option = "Definitions"
    prompt_options = {
        'main_opt': card.prompt_option,
        'subject_opt': card.prompt_option2,
        'trans_opt': card.trans_option,
        'lang_opt': card.trans_option,
        'detail_lvl_opt': card.len_option,
    }
    return prompt_options


@app.route("/get-due-cards/<deck_id>", methods= ["POST", "GET"])
def get_due_cards(deck_id):
    deck = Deck.query.get(deck_id)
    ## later add in option to modify number of new cards to be shown
    n=20
    if(current_user.id != deck.user_id):
        return apology('Deck not assigned to user', 403)
    if deck is None:
        return apology('Deck not found', 404)
    return deck.get_due_cards(n)


@app.route("/new_user_settings", methods = ["POST", "GET"])
@login_required
def new_user_settings():
    print("entered new user settings")
    data = request.get_json()
    checked = data.get('checked')
    if checked:
        print("option is checked")
        user_settings = UserSettings.query.filter_by(user=current_user.id).first()
        user_settings.new_user_study = False
        print(user_settings.new_user_study)
        db.session.add(user_settings)
        db.session.commit()
    return jsonify({'success': True})

@app.route("/new_user_settings_create", methods = ["POST", "GET"])
@login_required
def new_user_settings_create():
    print("entered new user settings")
    data = request.get_json()
    checked = data.get('checked')
    if checked:
        print("option is checked")
        user_settings = UserSettings.query.filter_by(user=current_user.id).first()
        user_settings.new_user = False
        db.session.add(user_settings)
        db.session.commit()
    return jsonify({'success': True})

@app.route("/new_user_settings_viewdecks", methods = ["POST", "GET"])
@login_required
def new_user_settings_viewdecks():
    print("entered new user settings")
    data = request.get_json()
    checked = data.get('checked')
    if checked:
        print("option is checked")
        user_settings = UserSettings.query.filter_by(user=current_user.id).first()
        user_settings.new_user_decks = False
        db.session.add(user_settings)
        db.session.commit()
    return jsonify({'success': True})


@app.route("/study_deck/<int:deck_id>", methods = ["POST", "GET"])
def study_deck(deck_id):
    user_settings = UserSettings.query.filter_by(user=current_user.id).first()
    if user_settings == None:
        print("user settings not found")
        user_settings = UserSettings(user=current_user.id)
        db.session.add(user_settings)
        db.session.commit()
    event_tracker(current_user.id, "study_deck", deck_id)
    deck = Deck.query.get(deck_id)
    if(current_user.id != deck.user_id):
        return apology('Deck not assigned to user', 403)
    return render_template("study_deck.html", title="Study deck", deck=deck_id, deck0 = deck,  settings = user_settings) 

@app.route("/study_deck_all", methods = ["POST", "GET"])   
@login_required   
def study_deck_all():
    event_tracker(current_user.id, "study_deck_all")
    user_settings = UserSettings.query.filter_by(user=current_user.id).first()
    if user_settings == None:
        user_settings = UserSettings(user=current_user.id)
        db.session.add(user_settings)
        db.session.commit()
    ## loads all decks for a user
    ## get list of decks for user with id user id
    decks = Deck.query.filter(Deck.user_id == current_user.id).all()
    decks_data = [{'id': deck.id} for deck in decks]
    decks_json = json.dumps(decks_data)
    return render_template('study_deck_all.html', title='Study all decks', decks_json=decks_json, decks=decks, settings = user_settings)

@app.route("/increment/<card_id>", methods = ["POST", "GET"])
def increment(card_id):
    card = Card.query.get(card_id)
    deck = Deck.query.filter(Deck.cards.any(id=card_id)).first()
    if(current_user.id != deck.user_id):
        return apology('Deck not assigned to user', 403)
    if card is None:
            return apology('Card not found', 404)
    card.increment()
    card.update_time()
    return jsonify({'success': 'Card incremented'}), 200
    

@app.route("/decrement/<card_id>", methods = ["POST"])
def decrement(card_id):
    card = Card.query.get(card_id)
    
    deck = Deck.query.filter(Deck.cards.any(id=card_id)).first()
    if(current_user.id != deck.user_id):
        return apology('Deck not assigned to user', 403)
    
    if card is None:
        return apology('Card not found', 404)
    card.decrement()
    card.update_time()
    return jsonify({'success': 'Card decremented'}), 200

@app.route("/forcestudy/<deck_id>")
def force_study(deck_id):
    event_tracker(current_user.id, "force_study", deck_id)
    deck = Deck.query.get(deck_id)
    if(current_user.id != deck.user_id):
         return apology('Deck not assigned to user', 403)
    if deck is None:
        return apology('Deck not found', 404)
    return deck.force_study()
    
@app.route("/casualmode/<int:deck_id>")
def casual_mode(deck_id):
    return render_template("casualmode.html", title="Casual Mode", deck=deck_id)   

@app.route('/generate_img/<int:deck_id>', methods=['GET', 'POST'])
def generate_img(deck_id):
    event_tracker(current_user.id, "generate_img", deck_id)
    deck = Deck.query.get(deck_id)
    if(current_user.id != deck.user_id):
         return apology('Deck not assigned to user', 403)
    if deck is None:
        return apology('Deck not found', 404)
    for card in deck.cards:
        try:
            card.img = create_image(card.term)
            db.session.commit()
        except:
            pass
    return redirect(("/currentdeck/{deck}").format(deck=deck_id))
    
@app.route("/carousel/<int:deck_id>", methods = ["GET", "POST"])
def carousel(deck_id):
    deck = Deck.query.filter_by(id=deck_id, user_id=current_user.id).first()
    cards = Card.query.filter(Card.decks_backref.any(id=deck_id)).order_by(Card.id.desc()).all()
    if(current_user.id != deck.user_id):
         return apology('Deck not assigned to user', 403)
    if request.method == 'POST' and 'term' in request.form:
        term = request.form['term'] ## new term for card
        content = request.form['content']
        boc_2 = request.form.get('boc_2')
        boc_3 = request.form.get('boc_3')
        boc_4 = request.form.get('boc_4')
        id = request.form['id'] ## id of card to be edited
        formula = request.form.get('formula')
        card = Card.query.filter_by(id=id).first()
        if term != "":
            if card.term != None:
                card.term = term.strip()
        if content != "":
            if card.content != None:
                card.content = content.strip()
        if boc_2 != "":
            if boc_2 != None:
                card.boc_2 = boc_2.strip()
        if boc_3 != "":
            if boc_3 != None:
                card.boc_3 = boc_3.strip()
        if boc_4 != "":
            if boc_4 != None:
                card.boc_4 = boc_4.strip()
        if formula != "":
            if formula != None:
                card.formula = formula.strip()
        db.session.commit()
    if request.method == 'POST' and 'new_term' in request.form:
        entry = Card(term=request.form['new_term'], content=request.form['new_content'], boc_2=request.form['new_boc_2'],
                     boc_3=request.form['new_boc_3'], boc_4=request.form['new_boc_4'], category=request.form['new_category'],
                     time_created=datetime.utcnow())
        deck.cards.append(entry)
        db.session.commit()
    if request.method == 'POST' and 'new_deck_name' in request.form:
        deck.name = request.form['new_deck_name']
        deck.description = request.form['new_deck_description']
        deck.subject = request.form['new_deck_subject']
        deck.topic = request.form['new_deck_topic']
        db.session.commit()   
    return render_template("carousel.html", title="Carousel", deck=deck, cards=cards) 

@app.route("/add_new_card/<int:deck_id>", methods = ["GET", "POST"])
def add_new_card(deck_id):
    print("entered add new card")
    deck = Deck.query.filter_by(id=deck_id, user_id=current_user.id).first()
    if(current_user.id != deck.user_id):
        return apology('Deck not assigned to user', 403)
    entry = Card(term=request.form['new_term'] , content=request.form['new_content'], boc_2=request.form['new_boc_2'],
                 boc_3=request.form['new_boc_3'], boc_4=request.form['new_boc_4'],
                 category=request.form['new_category'])
    db.session().add(entry)
    deck.cards.append(entry)
    db.session.commit()
    return 'Card saved successfully'

@app.route("/landingpage", methods = ["GET", "POST"])
def landingpage():
    return render_template("landingpage.html", title="Landing Page")

@app.route("/terms_and_conditions")
def terms_and_conditions():
    return render_template("terms_and_conditions.html", title="Terms and Conditions")

@login_required
@app.route("/delete_account", methods = ["POST"])
def delete_account():
    user = User.query.filter_by(id=current_user.id).first()
    if user.email == request.form['del_email']:
        user.account_status = 'inactive'
        user.expiration = datetime.utcnow()
        user.account_expiration_reason = "Deleted"
        db.session.commit()
        flash("We'are sorry to see you go. Your account is now inactive and will be permanently deleted within 48 hours.")
    return redirect(url_for('logout'))

@app.route("/extract", methods = ["GET", "POST"])
@login_required
def extract():
    user_settings = UserSettings.query.filter_by(user=current_user.id).first()
    if user_settings == None:
        print("user settings not found")
        user_settings = UserSettings(user=current_user.id)
        db.session.add(user_settings)
        db.session.commit()
        
    ## plan level requried for genereting images
    form = UploadFileForm()

    if form.validate_on_submit():
        now = datetime.utcnow().isoformat()
        deck, text, prompt_options = handle_form_submission(form)
        tokens = count_tokens(text)
        texts = None
        print(type(text))
        if text != None and len(text) > 0:      
            if perform_operation(current_user.id, prompt_options['main_opt'], tokens) == False:
                flash('You have reached your monthly usage limit. Please upgrade your account to continue.')
                event_tracker(current_user.id, 'extract_start', 'fail', "limit_reached")
                return redirect(url_for('account'))
            else:
                if prompt_options['main_opt'] != 'Transcribe':
                    print("splitting text")
                    texts= split_text(text)
                if texts == None:
                    texts = text
                if not isinstance(texts, list):
                    texts = [texts]
                counter = 0
                for text in texts:
                    print(type(text))
                    print(text)
                    total_len = len(texts)
                    counter = counter + 1
                    payload_dict = {'deck': deck.id, 'text': text, 'prompt_options': prompt_options}
                    payload = json.dumps(payload_dict)
                    current_user_id = current_user.id
                    slug = str(current_user_id) + now
                    print("counter")
                    print(counter)
                    print(total_len)
                    task_type = prompt_options['main_opt']
                    data = Job(slug=slug, user = current_user_id, task_type=task_type, payload=payload, item_number = counter, item_quantity = total_len)
                    event_tracker(current_user.id, 'extract_start', 'success', payload)
                    if counter == total_len:
                        session['slug'] = slug
                    db.session.add(data)
                    db.session.commit()
                flash('Yor cards are being created, once finished they will appear in your decks.  In the meantime feel free to create more decks or start studying!')
        return redirect('/viewdecks')
    return render_template("extract.html", title="Extract", form=form, settings = user_settings)

## Functions for extract:
def handle_form_submission(form):
    prompt_options = process_prompt_options(form)
    deck = get_or_create_deck(form, prompt_options)
    text = get_text_from_form_input(form)
    text = text.replace('\u00a0', '')
    return deck, text, prompt_options

def process_prompt_options(form):
    prompt_options = {
        'main_opt': form.prompt.data or None,
        'subject_opt': form.subject.data or None,
        'trans_opt': form.languages.data or None,
        'lang_opt': form.main_lang.data or None,
        'detail_lvl_opt': form.length.data or None,
        'min_opt': form.qmin_option.data or None,
        'max_opt': form.qmax_option.data or None,
        'images_opt': form.generate_images.data or None,
        'save_text_opt': form.save_text.data or None,
        'custom_term': form.custom_term.data or None,
        'custom_content': form.custom_content.data or None,
    }
    return prompt_options

def get_or_create_deck(form, prompt_options):
    main_opt = prompt_options['main_opt']
    if form.deck_list.data:
        deck = form.deck_list.data
    else:
        time = datetime.utcnow().isoformat()
        deck_name = form.name.data or "".join(main_opt + "deck" + time)
        deck_description = form.description.data or "".join(main_opt + "deck")
        deck = Deck(name=deck_name, description=deck_description)
        db.session.add(deck)
    deck.user_id = current_user.id
    return deck

def get_text_from_form_input(form):
    if form.file.data:
        text = get_text_from_file(form.file.data)
    elif form.text_input.data and form.text_input.data.strip():
        text = form.text_input.data
    elif form.link_input.data and form.link_input.data.strip():
        text = get_text_from_link(form.link_input.data)
    else:
        text = None
    return text

def get_text_from_file(file_data):
    file = file_data
    print("filename", )
    print(file.filename)
    current_user_id = current_user.id
    now = datetime.utcnow()
    filename = file.filename
    extension = os.path.splitext(filename)[1].lower()
    ##if extension not in ALLOWED_EXTENSIONS:
      ###  print("filetype not supported")
      ####  flash('File type not supported')
       ## return redirect(url_for('extract'))
    file.filename = "file" + str(current_user_id) + str(now) + extension

    print(file.filename)
    folder_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), app.config['UPLOAD_FOLDER'])
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    file_loc = (os.path.join(os.path.abspath(os.path.dirname(__file__)),app.config['UPLOAD_FOLDER'],secure_filename(file.filename)))
    file.save(file_loc)
    text = text_extractor(file_loc)
    return text

def get_text_from_link(link_input):
    text = None
    link_input = link_input
    if "wikipedia" in link_input:
        if check_comma_list(link_input):
            link_input = link_input.split(",")
            for link in link_input:
                part = extract_from_wiki(link_input)
            if text == None:
                text = part
            text = text + part
        else:
            text = extract_from_wiki(link_input)   
    else:
        if check_comma_list(link_input):
            link_input = link_input.split(",")
            for link in link_input:
                link = get_video_id(link)
                part = extract_from_youtube(link)
                if text == None:
                    text = part
                text = text + part
        else:
            link_input = get_video_id(link_input)
            text = extract_from_youtube(link_input)
    return text



@app.route("/sea_dox/<int:deck_id>", methods=["GET", "POST"])
def sea_dox(deck_id):
    ## GET DECK
    deck = Deck.query.get_or_404(deck_id)
    ## GET source files
    files = deck.deck_files
    ##files = DeckFiles.query.filter(DeckFiles.decks.any(id=deck_id)).order_by(DeckFiles.file_name.desc()).all()
    if request.method == 'GET':
        print("entered get request")
        sort_method =request.args.get('sort')
        search_query = None
        search_query = request.args.get('search', '').strip()
        if sort_method != 'default':
                if sort_method == 'name_asc':
                    files = DeckFiles.query.filter(DeckFiles.decks.any(id=deck_id)).order_by(DeckFiles.file_name.asc()).all()
                if sort_method == 'name_desc':
                    files = DeckFiles.query.filter(DeckFiles.decks.any(id=deck_id)).order_by(DeckFiles.file_name.desc()).all()
                if sort_method == 'type':
                    files = DeckFiles.query.filter(DeckFiles.decks.any(id=deck_id)).order_by(DeckFiles.create_type.asc()).all()
                if sort_method == 'date':
                    files = DeckFiles.query.filter(DeckFiles.decks.any(id=deck_id)).order_by(DeckFiles.time_created.desc()).all()
        elif search_query:
                files = DeckFiles.query.filter(DeckFiles.decks.any(id=deck_id)).filter(DeckFiles.file_name.contains(search_query)).all()
        return render_template("sea_dox.html", title="Sea Dox", files=files, deck = deck)
    if request.method == 'POST':
        file_id = request.form['file_id']
        file = DeckFiles.query.get_or_404(file_id)
        new_name = request.form['new_name']
        if new_name != '':
            file.file_name = new_name
            db.session.commit()
        return render_template("sea_dox.html", title="Sea Dox", files=files, deck = deck)
    return render_template("sea_dox.html", title="Sea Dox", files=files, deck = deck)

@app.route("/source_file/<int:file_id>", methods=["GET", "POST"])
def source_file(file_id):
    ## GET FILE
    file = DeckFiles.query.get_or_404(file_id)
    return render_template("source_file.html", title="Source File", file=file)

@app.route("/download_source/<int:file_id>", methods=["GET", "POST"])
def download_source(file_id):
    ## GET FILE
    event_tracker(current_user.id, "download_source", file_id)
    file = DeckFiles.query.get_or_404(file_id)
    name = file.file_name +".pdf"
    text = file.text_string
    ## turn file.text_string into a pdf
    pdf_buffer = create_pdf(text)
    return send_file(pdf_buffer, download_name = name)

@app.route("/delete_file/<int:deck_id>/<int:file_id>/", methods=["GET", "POST"])
def delete_file(deck_id, file_id):
    print("entered delete file")
    event_tracker(current_user.id, "delete_file", file_id)
    file = DeckFiles.query.get_or_404(file_id)
    deck = Deck.query.get_or_404(deck_id)
    db.session.delete(file)
    db.session.commit()
    return redirect(("/sea_dox/{deck}").format(deck=deck.id)) 

@app.route("/share_deck/<int:deck_id>/<string:user_email>/", methods=["GET", "POST"])
def share_deck(deck_id, user_email):
    sender_id = current_user.email
    deck_to_copy = Deck.query.get_or_404(deck_id)
    event_tracker(current_user.id, "share_deck", deck_id)
    if check_comma_list(user_email):
        users_emails = user_email.split(",")
        for email in users_emails:
            email = unquote(email).strip()
            shared_deck = SharedDecks(name="Copy of " + deck_to_copy.name, description=deck_to_copy.description, sender = sender_id, time_created=datetime.utcnow(), receiver=email)
            db.session.add(shared_deck)
            for card in deck_to_copy.cards:
                new_card = Card(term=card.term, content=card.content, boc_2=card.boc_2, boc_3=card.boc_3, boc_4=card.boc_4, img=card.img, sound=card.sound, subject=card.subject, topic=card.topic, category=card.category, prompt_option=card.prompt_option, prompt_option2=card.prompt_option2, trans_option=card.trans_option, len_option=card.len_option, qmin_option=card.qmin_option, qmax_option=card.qmax_option, diff_lvl=card.diff_lvl)
                shared_deck.cards.append(new_card)
            db.session.commit()
        return redirect(url_for('viewdecks'))
    else:
        email = unquote(user_email)
        shared_deck = SharedDecks(name="Copy of " + deck_to_copy.name, description=deck_to_copy.description, sender = sender_id, time_created=datetime.utcnow(), receiver=email)
        db.session.add(shared_deck)
        for card in deck_to_copy.cards:
            new_card = Card(term=card.term, content=card.content, boc_2=card.boc_2, boc_3=card.boc_3, boc_4=card.boc_4, img=card.img, sound=card.sound, subject=card.subject, topic=card.topic, category=card.category, prompt_option=card.prompt_option, prompt_option2=card.prompt_option2, trans_option=card.trans_option, len_option=card.len_option, qmin_option=card.qmin_option, qmax_option=card.qmax_option, diff_lvl=card.diff_lvl)
            shared_deck.cards.append(new_card)
        db.session.commit()
        return redirect(url_for('viewdecks'))

@app.route("/approve_shared/<int:deck_id>/", methods=["GET", "POST"])
def approve_shared(deck_id):
    event_tracker(current_user.id, "approve_shared", deck_id)
    shared_deck = SharedDecks.query.get_or_404(deck_id)
    new_deck = Deck(user_id = current_user.id, name=shared_deck.name, description=shared_deck.description, shared=True, sharer=shared_deck.sender, time_created=datetime.utcnow())
    db.session.add(new_deck)
    for card in shared_deck.cards:
        new_card = Card(term=card.term, content=card.content, boc_2=card.boc_2, boc_3=card.boc_3, boc_4=card.boc_4, img=card.img, sound=card.sound, subject=card.subject, topic=card.topic, category=card.category, prompt_option=card.prompt_option, prompt_option2=card.prompt_option2, trans_option=card.trans_option, len_option=card.len_option, qmin_option=card.qmin_option, qmax_option=card.qmax_option, diff_lvl=card.diff_lvl)
        new_deck.cards.append(new_card)
    db.session.commit()
    shared_deck.delete()
    db.session.commit()
    success = True
    return jsonify({'success': success})


@app.route("/reject_shared/<int:deck_id>/", methods=["GET", "POST"])
def reject_shared(deck_id):
    event_tracker(current_user.id, "reject_shared", deck_id)
    print("entered reject shared")
    shared_deck = SharedDecks.query.get_or_404(deck_id)
    shared_deck.delete()
    db.session.commit()
    success = True
    return jsonify({'success': success})


@app.route("/feedback", methods=["GET", "POST"])
def feedback():
    if request.method == 'POST' and 'message_feedback' in request.form:
        entry = Feedback(name=request.form['name_feedback'], email=request.form['email_feedback'], message=request.form['message_feedback'], type_feedback=request.form['type_feedback'])
        entry.send_feedback()
        flash("Thank you for your feedback!", "success")
    return render_template('index.html', title='Index')

@app.route("/build_test/<int:deck_id>", methods=["GET", "POST"])
def build_test(deck_id):
    event_tracker(current_user.id, "build_test", deck_id)
    deck = Deck.query.get_or_404(deck_id)
    creator = current_user
    if request.method == "POST":
        test_questions = request.form.getlist('selected_cards[]')
        name = deck.name + " Test" + " " + str(datetime.now())
        new_test = Test(creator=current_user.id)
        db.session.add(new_test)
        new_test.name = name
        for question in test_questions:
            card = Card.query.get_or_404(question)
            question = Question()
            db.session.add(question)
            question.points = int(1)
            question.content = card.content
            question.term = card.term
            question.prompt_option = card.prompt_option
            if card.category == "Mcq":
                question.question = card.term
                question.boc_2 = card.boc_2
                question.boc_3 = card.boc_3
                question.boc_4 = card.boc_4
                question.q_type = "mcq"
            elif card.category == "Cloze":
                question.question = card.term
                question.q_type = "cloze"
            else:
                ## switching them around so that the test gives them a definition and they have to write the word
                question.question = card.content
                question.q_type = "jeopardy"
            db.session.add(question)
            new_test.questions.append(question)
        db.session.commit()
        return redirect('/assign_test/{test.id}'.format(test=new_test))
    return render_template('build_test.html', title='Test Builder', deck=deck, creator=creator)

@app.route("/assign_test/<int:test_id>", methods=["GET", "POST"])
def assign_test(test_id):
        event_tracker(current_user.id, "assign_test", test_id)
        test = Test.query.get_or_404(test_id)
        print(request.form)
        if request.method == 'POST' and 'test-name' in request.form:
            print("entered post request3")
            test.name= request.form['test-name']
            test.creator = current_user.id
            due_date = request.form.get('due-date')
            if due_date:
                due_date = dt.datetime.strptime(due_date[:16],'%Y-%m-%dT%H:%M')
                test.due_date = due_date
            test.subject = request.form['subject']
            test.topic = request.form['topic']
            test.instructions = request.form['instructions']
            test.description = request.form['description']
            time_limit = request.form.get('time-limit')
            if time_limit != '':
                time_limit = int(time_limit)
                test.time_limit = time_limit
            
            answer_reveal = request.form.get('answer-reveal', False)
            result_reveal = request.form.get('result-reveal', False)
            shuffle = request.form.get('shuffle', False)
            if answer_reveal == 'answer-reveal':
                test.answer_reveal = True
            if result_reveal == 'result-reveal':
                test.result_reveal = True
            if shuffle == 'shuffle':
                test.shuffle = True
            test.count_questions()
            test.sum_points()
            db.session.commit()
        return render_template('assign_test.html', title='Assign test', test=test, )
    
@app.route('/update_card', methods=['POST'])
def update_card():
    print("entered updated card")
    question_id = request.form['question-id']
    question = Question.query.get(question_id)
    question.question = request.form['question']
    question.points = request.form['points']
    category = request.form['category']
    question.term = request.form['answer']
    if category == 'mcq':
        print("recognized mcq")
        question.boc_2 = request.form['boc_2']
        question.boc_3 = request.form['boc_3']
        question.boc_4 = request.form['boc_4']
    db.session.commit()
    return jsonify(success=True)


@app.route("/delete_question/<int:test_id>/<int:question_id>", methods = ["POST", "GET"])
@login_required
def delete_question(test_id, question_id):
    question_to_delete = Question.query.get_or_404(question_id)
    db.session.delete(question_to_delete)
    db.session.commit()
    return redirect(('/assign_test/{test_id}'.format(test_id = test_id)))

@app.route("/delete_test/<int:test_id>/", methods = ["POST", "GET"])
@login_required
def delete_test(test_id):
    test_to_delete = Test.query.get_or_404(test_id)
    db.session.delete(test_to_delete)
    db.session.commit()
    return redirect('/test_results_overview/')


@app.route("/assign/<int:test_id>/<string:user_email>/", methods=["GET", "POST"])
def assign(test_id, user_email):
    test = Test.query.filter_by(id=test_id).first()
    test.count_questions()
    test.sum_points()
    not_users = []
    if check_comma_list(user_email):
        print(user_email)
        users_emails = user_email.split(",")
        for email in users_emails:
            email = unquote(email).strip()
            taker = User.query.filter_by(email=email).first()
            if taker == None:
                not_users.append(email)
            else:
                test.taker.append(taker)
    else:
        email = unquote(user_email)
        taker = User.query.filter_by(email=email).first()
        if taker == None:
            not_users.append(email)

        else:
            test.taker.append(taker)
    db.session.commit()
    if not_users == []:
        flash('Test assigned!', 'success')
    else:
        flash(f"Could not locate the following users: {not_users}", "danger")
    return redirect('/assign_test/{test_id}'.format(test_id = test_id))


@app.route("/take_test/<int:test_id>/<int:user_id>/", methods=["GET", "POST"])
def take_test(test_id, user_id):
    event_tracker(current_user.id, "take_test", test_id)
    test_result = TestResult.query.filter_by(test_id = test_id, taker = user_id).first()
    test = Test.query.get_or_404(test_id)
    if test_result is None:
        start_time = datetime.utcnow()
        test_result = TestResult(test_id = test_id, taker = user_id, start_time = start_time, creator=test.creator)
        taker = User.query.get_or_404(user_id)
        db.session.add(test_result)
        if request.method == 'POST':
            for question in test.questions:
                question_id = question.id
                to_call = "answer"+str(question_id)
                answer = request.form.get(to_call, '')
                answer = answer.strip()
                result = QuestionResult(test_id = test.id, taker = current_user.id, question_id = question.id, answer = answer)
                db.session.add(result)
                db.session.commit()
            end_time = request.form.get('end-time')
            end_time = datetime.strptime(end_time, '%Y-%m-%dT%H:%M:%S.%fZ')
            test_result.end_time = end_time
            db.session.commit()
            return redirect('/test_results/{test_id}/{user_id}'.format(test_id = test_id, user_id = user_id))
        return render_template('take_test.html', test=test, taker=taker, start_time = start_time)
    else:
        test.taker.remove(current_user)
        db.session.commit()
        flash('you have already taken this test', 'danger')
        return redirect('/test_results_overview/')

@app.route("/test_results/<int:test_id>/<int:user_id>/", methods=["GET", "POST"])
def test_results(test_id, user_id):       
    point_counter = 0
    correct_counter = 0
    test = Test.query.get_or_404(test_id)
    creator = test.creator
    taker = User.query.get_or_404(user_id)
    for question in test.questions:
        answer = QuestionResult.query.filter_by(test_id = test_id, taker = user_id, question_id = question.id).first()
        answer_given = remove_punctuation(answer.answer).lower().strip()
        if question.q_type == "jeopardy":
            answer_expected = remove_punctuation(question.term).lower().strip()
        elif question.q_type == "cloze":
            answer_expected = remove_punctuation(question.content).lower().strip()
        elif question.q_type == "mcq":
            answer_expected = remove_punctuation(question.content).lower().strip()
        print(answer_given, answer_expected)
        matcher = difflib.SequenceMatcher(None, answer_given.lower(), answer_expected.lower())
        if matcher.ratio() > 0.9:
            point_counter += question.points
            correct_counter += 1
            answer.points = int(question.points)
        else:
            answer.points = 0
        if not answer.points:
            answer.points = 0
    test = db.session.query(Test).filter_by(id=test_id).first()
    test_result = TestResult.query.filter_by(test_id = test_id, taker = user_id).first()
    test_result.points = point_counter
    test_result.correct = correct_counter
    test_result.correct = creator
    taker = current_user
    if taker in test.taker:
        test.taker.remove(taker)
    db.session.add(test_result)
    db.session.commit()
    return render_template('test_results.html', test=test, taker=taker, results=test_result)    

@app.route("/test_results_overview/", methods=["GET", "POST"])
def test_results_overview():
    user = current_user
    tests_created = Test.query.filter_by(creator = user.id).all()
    ## results of tests taken
    test_results_taken = TestResult.query.filter_by(taker = user.id).all()
    ## results of tests given
    test_results_given = TestResult.query.filter_by(creator = user.id).all()
    tests = []
    for result in test_results_taken:
        test = Test.query.filter_by(id=result.test_id).first()
        tests.append(test)
    ## if the test has been deleted and there are are no results for user then delete
    for test in test_results_given:
        exist_test = Test.query.filter_by (id = test.test_id).first()
        if not exist_test:
            if not test.taker:
                db.session.delete(test)
                db.session.commit()
    return render_template('test_results_overview.html', taken = test_results_taken, given = test_results_given, created = tests_created,tests=tests)

@app.route("/test_result_details/<int:test_id>/", methods=["GET", "POST"])
def test_result_details(test_id):
    results = TestResult.query.filter_by(test_id = test_id).all()
    test = Test.query.filter_by(id = test_id).first()
    # Get the list of taker ids from the TestResult objects
    taker_ids = [result.taker for result in results]
    # Filter the User objects by the taker ids
    takers = User.query.filter(User.id.in_(taker_ids)).all()
    return render_template('test_result_details.html', results = results, test = test, takers = takers)

@app.route("/test_created/<int:test_id>/", methods=["GET", "POST"])
def test_created(test_id):
    test = Test.query.get_or_404(test_id)
    if request.method == 'POST' and 'test-name' in request.form:
        test.name= request.form['test-name']
        test.creator = current_user.id
        due_date = request.form.get('due-date')
        if due_date:
            due_date = dt.datetime.strptime(due_date,'%Y-%m-%dT%H:%M')
            test.due_date = due_date
        test.subject = request.form['subject']
        test.topic = request.form['topic']
        test.instructions = request.form['instructions']
        test.description = request.form['description']
        test.time_limit = request.form['time-limit']
        answer_reveal = request.form.get('answer-reveal', False)
        result_reveal = request.form.get('result-reveal', False)
        shuffle = request.form.get('shuffle', False)
        if answer_reveal == 'answer-reveal':
            test.answer_reveal = True
        if result_reveal == 'result-reveal':
            test.result_reveal = True
        if shuffle == 'shuffle':
            test.shuffle = True
        test.count_questions()
        test.sum_points()
        db.session.commit()
    return render_template('test_created.html', test=test)
   
@app.route("/test_result/<int:result_id>/", methods=["GET", "POST"])
def test_result(result_id):
    result = TestResult.query.filter_by(id = result_id, taker = current_user.id).first()
    test = Test.query.filter_by(id = result.test_id).first()
    return render_template('test_result.html', result=result, test=test)

@app.route("/test_answers/<int:test_id>/<int:taker_id>/", methods=["GET", "POST"])
def test_answers(test_id, taker_id):
    test = Test.query.filter_by(id = test_id).first()
    result = TestResult.query.filter_by(test_id = test_id, taker = taker_id).first()
    question_results = QuestionResult.query.filter_by(test_id = test.id, taker=taker_id).all()
    result.sum_points()   
    if result.creator != current_user.id:
        flash('you are not allowed to view this page', 'danger')
        return redirect('/test_results_overview/')
    else:
        if request.method == "POST":
            for question_result in question_results:
                question_points_id = 'points' + str(question_result.id)
                points_entered = int(request.form.get(question_points_id))
                question_result.points = int(points_entered)
                for question in test.questions:
                    if question_result.points == question.points:
                        question_result.correct = True
            result.sum_points()        
            db.session.commit()
        return render_template('test_answers.html', result=result, question_results=question_results, test=test)
    
@app.route("/test_print/<int:test_id>/", methods=["GET", "POST"])
def test_print(test_id):
    test = Test.query.filter_by(id = test_id).first()
    return render_template('test_print.html', test=test)

@app.route("/sea_source/<int:file_id>/", methods=["GET", "POST"])
def sea_source(file_id):
    source = DeckFiles.query.filter_by(id = file_id).first()

    return render_template('sea_source.html',file=source)

@app.route("/import_deck/", methods=["GET", "POST"])
def import_deck():
    ## IMPORT ALL DECKS FROM ANKI
    if check_anki_connect() == True:
        if request.method == "POST" and "import-all" in request.form:
            decks = anki_import_all()
            decks = json.loads(decks)
            for deck in decks:
                for key, value in deck.items():
                    if value != []:
                        description = "anki import"
                        deck = Deck(name = key, description = description, user_id = current_user.id)
                        db.session.add(deck)
                        db.session.commit()
                        for i in range(len(value)):
                            for j in range(len(value[i])):
                                card = value[i][j]
                                cardId = card['cardId']
                                content = card['fields']['Back']['value']
                                term = card['fields']['Front']['value']
                                srs_interval = card['srs_interval']*1440
                                entry = Card(term = term, content = content, srs_interval = srs_interval, category = "anki")
                                db.session.add(entry)
                                deck.cards.append(entry)
                        db.session.commit()
            event_tracker(current_user.id, "import-anki", "success")

            flash("Decks imported", "success")
            return redirect(url_for('viewdecks'))
        if request.method == "POST" and "import-by-name" in request.form:
            deck_names = request.form['deck-name']
            if not check_comma_list(deck_names):
                deck_names = [deck_names]
            deck_names = deck_names.split(",")
            for name in deck_names:
                deck = anki_import_deck(name)
                deck = json.loads(deck)
                cards = deck[0][name]
                description = "anki import"
                deck = Deck(name = name, description = description, user_id = current_user.id)
                db.session.add(deck)
                db.session.commit()
                for i in range(len(cards)):
                    card = cards[i][0]
                    print(card)
                    cardId = card['cardId']
                    content = card['fields']['Back']['value']
                    term = card['fields']['Front']['value']
                    srs_interval = card['srs_interval']*1440
                    entry = Card(term = term, content = content, srs_interval = srs_interval)
                    db.session.add(entry)
                    deck.cards.append(entry)
                db.session.commit()
            event_tracker(current_user.id, "import-anki", "success")
            flash("Decks imported", "success")
            return redirect(url_for('viewdecks'))
    else:
        event_tracker(current_user.id, "import-anki", "fail")

        return apology('Please make sure you are a) on a desktop b) have Anki installed and running c) have the AnkiConnect plugin installed and enabled.', 400)     
    return render_template('import_deck.html')

@app.route("/export_deck/<int:deck_id>/", methods=["GET", "POST"])
@login_required
def export_deck(deck_id):
    if check_anki_connect() == True:
        deck = Deck.query.get_or_404(deck_id)
        if deck.user != current_user:
            flash('you are not allowed to view this page', 'danger')
            return redirect('/home/')
        cards = deck.cards
        anki_create_deck(deck.name)
        for card in cards:
            query = card.term
            notes = find_notes(query)
            print(notes)
            if notes == False:
                srs_interval = str(int(card.srs_interval/1440))
                anki_create_card(deck.name, card.term, card.content)
        event_tracker(current_user.id, "export-anki", "success")
        flash("Deck exported", "success")
        return redirect(url_for('viewdecks'))
    else:
        event_tracker(current_user.id, "export-anki", "fail")

        return apology('Please make sure you are a) on a desktop b) have Anki installed and running c) have the AnkiConnect plugin installed and enabled.', 400)

@app.route("/about/", methods=['GET', 'POST'])
def about():
    return render_template('about.html')


@app.route("/query", methods=["POST"])
def query():
    print("entered query")
    # The id of the queried request comes in with a new request
    # sent from the frontend JS code
    job_id = request.form["id"]
    # Now we can ask database about the state of that request
    data = Job.query.filter_by(slug=job_id).first()
    # And return a response containing the state and the result
    print(data)
    if data is None:
        return jsonify({"state": None, "result": None})
    return jsonify(
        {
            "state": data.state,
            "result": data.result,
        }
    )

@app.route("/notification_complete", methods=["POST"])
def notification_complete():
    print("entered notification")
    slug_id= request.form["id"]
    slug = Job.query.filter_by(slug=slug_id).first()
    print("WWWWWWHHHHA")
    print("Slug", slug)
    jobs = Job.query.filter_by(slug=slug.slug).all()
    print(jobs)
    for job in jobs:
        print(job)
        print(job.result)
        job.result = 2
        print(job.result)
    db.session.commit()
    return jsonify("success")
 
 
@app.route("/documentation/", methods=['GET', 'POST'])
def documentation():
    return render_template('documentation.html')
#################  USAGE CHECKS  ###############################################################################################

def perform_operation(user_id, operation_type, n):
    # Check the user's remaining count for this time period
    user = User.query.filter_by(id=user_id).first()
    print("checking operation", operation_type, n)
    sub_start_date = current_user.subscription_start_date
    usage_record = UsageRecord.query.filter_by(user_id=user.id).order_by(UsageRecord.date.desc()).first()
    subscription_plan = SubscriptionPlan.query.filter_by(id=user.subscription_plan).first()
    if usage_record is None:
        remaining_count = subscription_plan.limit_count
    else:
        remaining_count = usage_record.remaining_count
    if remaining_count - n <= 0:
        return False
    # Perform the operation and update the usage record
    # Update the usage record
    new_record = UsageRecord(user_id=user.id, operation_type=operation_type, time_period='month', limit_count=subscription_plan.limit_count)
    if usage_record is None:
        new_record.operation_count = n
        new_record.remaining_count = subscription_plan.limit_count - n
    else:
        new_record.operation_count = usage_record.operation_count + n
        new_record.remaining_count = usage_record.remaining_count - n
    db.session.add(new_record)

def check_subscription_plan(user):
    subscription_plan = SubscriptionPlan.query.filter_by(id=user.subscription_plan).first()
    return subscription_plan


####################  MORE INFO ABOUT CARDS ################################################

@app.route("/explain_further/<int:card_id>/", methods=['GET', 'POST'])
def explain_further(card_id):
    card = Card.query.filter_by(id=card_id).first()
    if card is None:
        return render_template('404.html')
    term = card.term
    subject = card.subject
    content = card.content
    response = explain_more(term, subject, content)
    
    json_response = {"response": response}
    return json_response

@app.route("/why_wrong/<int:card_id>/", methods=['GET', 'POST'])
def why_wrong(card_id):
    print("why wrong")
    card = Card.query.filter_by(id=card_id).first()
    if card is None:
        return render_template('404.html')
    ww_prompt = why_wrong_builder(card_id)
    response = why_wrong_generator(ww_prompt)
    json_response = {"response": response}
    return json_response    
    
def why_wrong_builder(card_id):
    card = Card.query.filter_by(id=card_id).first()
    ww_prompt = {
        "term": card.term,
        "subject": card.subject,
        "content": card.content,
        "boc_2": card.boc_2,
        "boc_3": card.boc_3,
        "boc_4": card.boc_4,
        "category": card.category,
        "card_id": card.id
    }
    return ww_prompt


@app.route("/send_question/<int:card_id>/", methods=['GET', 'POST'])
def send_question(card_id):
    print("send question")
    card = Card.query.filter_by(id=card_id).first()
    latest_paragraph = request.form.get('latest_paragraph')
    question = request.form.get('question')
    term = card.term
    content = card.content
    response = send_question_generator(term, content, latest_paragraph, question)
    json_response = {"response": response}
    return json_response   

@app.route("/news/", methods=['GET', 'POST'])
def news():
    return render_template('news.html')
       

###################### TO BE REORGANIZED ###############################################################################################


def split_string(string):
    items = string.split("&-&-&")
    return items
################## CURRENTLY UNUSED ###############################################################################################

@app.route("/change_password", methods=["GET", "POST"])
def change_pass():
    form = ChangePassForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user:
            if bcrypt.check_password_hash(user.password, form.password.data):
                hashed_password = bcrypt.generate_password_hash(form.new_password.data)
                user.password = hashed_password
                db.session.commit()
    flash('Your password has been updated!')
    return redirect(url_for('index'))




  ## OBSOLETE CODE BELOW ###############################################################################################  
############################################################################################################    





if __name__ == "__main__":
    app.run(debug=False)
else:
    # For Alembic
    from models import db
    db.init_app(app)