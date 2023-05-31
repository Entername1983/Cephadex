import openai 
import os
from bs4 import BeautifulSoup
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import or_, and_, insert, not_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Mapped
from flask import g, Flask, flash, redirect, render_template, request, session, url_for, Response, send_file, jsonify, current_app
from flask_session import Session
from tempfile import mkdtemp
import pytz
from pytz import common_timezones
from sqlalchemy_utils import database_exists, create_database
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from wtforms import DateField, IntegerField, StringField, PasswordField, SubmitField, RadioField, SelectField, BooleanField, TextAreaField
from email_validator import validate_email, EmailNotValidError
from flask_wtf.file import FileField, FileAllowed, FileRequired, FileSize
from wtforms_sqlalchemy.fields import QuerySelectField
from wtforms.validators import InputRequired, Length, ValidationError, EqualTo, Optional, URL, DataRequired, Email
from flask_wtf import FlaskForm
from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename
from werkzeug.datastructures import ImmutableDict
from cardcreator import create_image, creator
from extractors import send_question_generator, why_wrong_generator, explain_more, regenerate_definition, add_period, extract_from_wiki, extract_from_youtube, text_extractor, create_pdf, check_comma_list, get_video_id, text_extractor
from helpers import split_text, count_tokens
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
from anki import request_anki_permission, anki_import_all, anki_import_deck, anki_create_deck, anki_create_card, find_notes, check_anki_connect
from flask import abort
from celery import Celery
import time
import schedule
from beta import BetaKeys
from config import UPLOAD_FOLDER, SECRET_KEY, DEBUG, BROKER, SQLALCHEMY_DATABASE_URI, MAX_CONTENT, SQLALCHEMY_TRACK_MODIFICATIONS, ALLOWED_EXTENSIONS, FLASK_DEBUG
from models import db, Job, TestResult, QuestionResult, Question, Test, Feedback, ResponseData, DeckFiles, Subscriber, Deck, SharedDecks, Card
from models import JobNotification, DeletedAccounts, StripeEvents, GroupInvite, Group, user_group_association, UsageRecord, SubscriptionPlan, User, cards, source_files, cards_shared, questions, distribution, UserSettings, deck_relationships
import configparser
import logging.config
from events import event_tracker
from flask_talisman import Talisman
from logging.config import dictConfig
from logging_config import LOGGING_CONFIG
from Crypto.Cipher import AES
from bleach import clean
from json import JSONEncoder
from flask_wtf.csrf import generate_csrf
import stripe
from threading import Thread
import uuid
import codecs
import random
from forms import RegSub, RegisterForm, LoginForm, ChangePassForm, TryOut, DeckOrg, UploadFileForm
from forms import EditCard, EditDeck, AddTermForm, AccountForm, DeleteAccountForm, UpdateProfilePicForm, FeedbackForm
from forms import SearchAndSortForm, Share, BuildTest, UpdateCardForm, GroupForm, UpdateFileNameForm
from pydub import AudioSegment
import subprocess
from pydub.utils import mediainfo
from extractors import audio_processing
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from send_email import send_email
from forms import Unsubscribe
from error_handlers import YoutubeError

dictConfig(LOGGING_CONFIG)

openai.api_key = os.environ.get("OPENAI_API_KEY")
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
endpoint_secret = os.environ.get("STRIPE_SIGNING_SECRET")
AUTH2_CLIENT_ID = os.environ.get("AUTH2_CLIENT_ID")

SEND_GRID_KEY = os.environ.get("SEND_GRID_KEY")

os.environ["FLASK_DEBUG"] = FLASK_DEBUG
# Configure application
app = Flask(__name__)
app.config.from_object('config')

### AUTO ESCAPE"
jinja_options = ImmutableDict(
 extensions=[
  'jinja2.ext.autoescape', 'jinja2.ext.with_' 
 ])

app.jinja_env.autoescape = True
### BLEACH ALLOWED TAGS
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
TOKENS_PER_PAGE = 682
PAGES_PER_MIN = 3


bcrypt = Bcrypt(app)
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = SECRET_KEY
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx', 'pptx', 'wav', 'mp3'}
ALLOWED_IMAGES = {'png', 'jpg', 'jpeg', 'gif', 'svg'}

migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"

@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf())

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
logger.debug("app started")

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    
    ##TODO ONLY FOR http AND LOCALHOST, FOR GOOGLE AUTH
    response.headers["Referrer-Policy"] = "no-referrer-when-downgrade"
    return response    

@app.before_request
def before_request():
    print("before request")
    if request.path == '/import_anki':
        print("anki import")
        g.feedback_form = None
    else:
        print("feedback")
        g.feedback_form = FeedbackForm()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('viewdecks'))
    else:
        return redirect(url_for('index'))

@app.route("/", methods=["GET", "POST"])
def index():
    form = TryOut()
    terms = []
    if not current_user.is_authenticated:
        if form.validate_on_submit():
            logger.debug("form validated")
            text = clean(form.select_text.data)
            prompt_options = {
                'main_opt': clean(form.prompt.data) or None,
                'trans_opt': clean(form.languages.data) or None,
                'lang_opt': None,
                'detail_lvl_opt': "long",
                'min_opt':  None,
                'max_opt':  None,
                'images_opt':  None,
                'save_text_opt':  None,
                'subject_opt':  None,
                'custom_term':  clean(form.custom_term.data) or None,
                'custom_content': clean(form.custom_content.data) or None,
            }
            logger.debug(prompt_options)
            
            response = creator(text, prompt_options)
            terms = response[0]
            for item in terms:
                logger.debug(item['A'])
                logger.debug(item['B'])
            event_tracker(None, "tryout", json.dumps(prompt_options), json.dumps(terms))
            return render_template('index.html', form = form,
                                    terms = terms, option = prompt_options['main_opt'])
        else:
            return render_template('index.html', form = form)
    else:
        cache_buster = random.randint(1, 999999)
        return redirect(url_for("viewdecks")+'?v=' + str(cache_buster))

@app.route("/googleSignIn", methods=["POST"])
def googleSignIn():
    #Security validation
    form = TryOut()
    logger.debug("entered google sign in")
    csrf_token_cookie = request.cookies.get('g_csrf_token')
    if not csrf_token_cookie:
        logger.debug('No CSRF token in Cookie.')
        return jsonify({'error': 'No CSRF token in Cookie'}), 400
    csrf_token_body = request.form.get('g_csrf_token')
    if not csrf_token_body:
        logger.debug('No CSRF token in post body.')
        return jsonify({'error': 'No CSRF token in post body.'}), 400
    if csrf_token_cookie != csrf_token_body:
        logger.debug('Failed to verify double submit cookie.')
        return jsonify({'error': 'Failed to verify double submit cookie.'}), 400
    try:
        #encrypted credential
        
        credential = request.form.get('credential')
        # Decrypt credential, third parameter comes from google API console client ID
        idinfo = id_token.verify_oauth2_token(credential,
                                               requests.Request(), AUTH2_CLIENT_ID)
        # ID token is valid. Get the user's Google Account ID from the decoded token.
        #  (UniqueID to use for login)
        userid = idinfo['sub']
        user = User.query.filter_by(external_id=userid).first()
        if (user):
            login_user(user)
            flash('You have been logged in!', 'success')
            event_tracker(user.id, "login", "google")
            return redirect(url_for('viewdecks'))
        
        else:
            logger.debug("entered not user, preparing to register")
            session['google_id_token'] = idinfo['sub']
            if idinfo.get('email'):
                session['google_email'] = idinfo['email']
            else: 
                session['google_email'] = "n/a"
            if idinfo.get('given_name'):
                session['given_name'] = idinfo['given_name']
            else: 
                session['given_name'] = "Anonymous"
            logger.debug(session['given_name'])
            if idinfo.get('family_name'):
                session['family_name'] = idinfo['family_name']
            else: 
                session['family_name'] = "Anonymous"
            logger.debug(session['family_name'])
            return redirect(url_for('register'))
    
    except ValueError as ve:
        logger.debug(f"google sign in value error: {str(ve)}")
        pass
    return render_template('index.html', title='Index', form = form)

@app.route('/testing1', methods = ['GET', 'POST'])
def testing1():
    return render_template('testing1.html')

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
        
@app.route('/update_sidebar_state', methods=['POST'])
def update_sidebar_state():
    is_collapsed = request.form.get('sidebar-collapsed') == 'true'
    session['sidebar-collapsed'] = is_collapsed
    return '', 204  # return 204 No Content response

 
@app.route("/register", methods=["GET", "POST"])
def register():
    try:
        form = RegisterForm()
        if request.method == 'POST':
            logger.debug("entered register post request")
            # Get the user's name and password from the form data
            username = request.form['username']
            ##timezone = request.form['password']
            ##role = request.form['role']
            contacted = request.form.get('contacted')
            subscribe = request.form.get('subscribe')
            betakey = request.form.get('betakey')
            role = request.form.get('role')
            timezone = form.timezone.data
            if timezone == None:
                timezone = "Europe/Dublin"
            logger.debug(contacted)
            logger.debug(subscribe)

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
            user = User(email=email, first_name=given_name, account_type = account_type,
                        last_name=family_name,external_id=userid,
                        external_type='google', subscription_plan = subscription_plan,
                        contacted_email=True, username=username,
                        timezone = timezone,
                        subscription_start_date = dt.datetime.now(dt.timezone.utc),
                        role = role)
            send_email(email, given_name, 'welcome')
            user_settings = UserSettings(user=user.id)
            if subscribe == "subscribe":
                sub_exists = Subscriber.query.filter_by(email=email).first()
                if not sub_exists:
                    timestamp = dt.datetime.now(dt.timezone.utc)
                    subscriber = Subscriber(email=email, first_name=given_name,
                                             last_name=family_name, timestamp = timestamp)
                    db.session.add(subscriber)
            event_tracker(user.id, "register", "google")
            db.session.add(user_settings)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("You have been registered and logged in!", "success")
            return redirect(url_for('viewdecks'))
        return render_template('register.html', title='Register', form = form)
        
    except Exception as e:
        logger.debug(e)
        logger.debug("error registering user")


@app.route('/subscribe', methods=['GET', 'POST'])
def subscribe():
    try:
        subscribe_form = RegSub()
        if subscribe_form.validate_on_submit():
            subscriber = Subscriber(email=subscribe_form.email.data,
                                    first_name=subscribe_form.first_name.data,
                                    last_name=subscribe_form.last_name.data,
                                    timestamp = dt.datetime.now(dt.timezone.utc))
            db.session.add(subscriber)
            db.session.commit()
            flash('You are now subscribed to our newsletter!')

        return render_template('subscribe.html', title='Subscribe', form=subscribe_form)
    except Exception as e:
        logger.debug(e)
        logger.debug("error subscribing user")

@app.route('/subscribe2', methods=['GET', 'POST'])
def subscribe2():
    try:
        data = request.json
        first_name = clean(data['first-name'])
        last_name = clean(data['last-name'])
        email = data['email']
        existing_subscriber = Subscriber.query.filter_by(email=email).first()
        if existing_subscriber and existing_subscriber != None:
            flash("You are already subscribed!")
            return jsonify({'status': 'failure', 'message': 'You are already subscribed!'})
        else:
            logger.debug(email)
            logger.debug("not subscribed, subscribing")
            subscriber = Subscriber(email=email, first_name=first_name,
                                     last_name=last_name, timestamp = dt.datetime.now(dt.timezone.utc))
            db.session.add(subscriber)
            db.session.commit()
            flash("Thanks for subscribing!")
            return jsonify({'status': 'success', 'message': 'Subscription successful!'})
    except Exception as e:
        logger.debug(e)
        logger.debug("error subscribing user")
@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    flash('You have been logged out!')
    return redirect(url_for('index'))

@app.route("/unsubscribe", methods=["GET", "POST"])
def unsubscribe():
    form = Unsubscribe()
    if request.method == 'POST':
        email = request.form['email']
        newsletter = request.form.get('newsletter')
        contacted = request.form.get('contacted')
        subscriber = Subscriber.query.filter_by(email=email).first()
        user = User.query.filter_by(email=email).first()
        print(email, contacted, newsletter)
        if contacted == 'y':
            print("contacted yes")
            user.contacted_email = False
            flash("You will no longer receive emails from us regarding your account")
        if subscriber:
            if newsletter == 'y':
                print("newsletter yes")
                db.session.delete(subscriber)
                flash("You will no longer receive our newsletter")
        db.session.commit()
        return redirect(url_for('unsubscribe'))
    return render_template('unsubscribe.html', title='Unsubscribe', form = form)



@app.route("/viewdecks", methods = ["GET", "POST"])
@login_required
def viewdecks():
    share_form = Share()
    user_settings = UserSettings.query.filter_by(user=current_user.id).first()
    if user_settings == None:
        logger.debug("user settings not found")
        user_settings = UserSettings(user=current_user.id)
        db.session.add(user_settings)
        db.session.commit()
   ## check if user has any pending tests
    tests = Test.query.filter(Test.taker.contains(current_user)).all()
    user = current_user
    email = current_user.email
    shared_decks = (
            SharedDecks.query
            .filter(SharedDecks.receiver == current_user.id).all()
    )
    decks = Deck.query.filter(Deck.user_id == current_user.id).all()
    if request.method == 'GET':
        sort_method = None
        search_query = None
        if request.args.get('sort'):
            sort_method = clean(request.args.get('sort'))
        if request.args.get('search'):
            search_query = clean(request.args.get('search', '').strip())
        if sort_method:
            column, order = sort_method.split('_')
            order_by = (
                getattr(getattr(Deck, column),
                order)() if column in 
                ['name', 'category', 'time_created'] else None
            )
            if order_by:
                decks = Deck.query.filter(Deck.user_id == current_user.id).order_by(order_by).all()
            elif column == "cards_due":
                decks = sorted(decks, key=lambda deck: deck.qty_cards_due(),
                                reverse=order == 'desc')
        if search_query:
            decks = Deck.query.filter(Deck.name.ilike(f'%{search_query}%')).all()
    return render_template('viewdecks.html', decks=decks, shared_decks = shared_decks,
                            tests=tests, user = user, settings = user_settings,
                            share_form = share_form)

@app.route("/createdeck", methods = ["GET", "POST"])
@login_required
def create_deck():
    return render_template("createdeck.html", title="Create Decgik")

@app.route("/accountsettings", methods = ["GET", "POST"])
@login_required
def account_settings():
    return render_template("accountsettings.html", title="Account Settings")

@app.route("/study", methods = ["GET", "POST"])
@login_required
def study():
    return render_template("study.html", title="Study")

@app.route("/delete/<int:id>", methods=["DELETE"])
@login_required
def delete(id):
    deck_to_delete = Deck.query.get_or_404(id)
    if current_user.id != deck_to_delete.user_id:
        return jsonify({'error': 'Deck not assigned to user'}), 403
    db.session.delete(deck_to_delete)
    db.session.commit()
    return jsonify({'message': 'Deck deleted successfully'})

@app.route("/rename_deck/<int:id>/<string:new_name>", methods = ["POST", "GET"])
@login_required
def rename_deck(id, new_name):
    c_id = id
    c_new_name = clean(new_name)
    deck = Deck.query.get_or_404(c_id)
    if(current_user.id != deck.user_id):
        return jsonify({'error': 'Deck not assigned to user'}), 403
    deck.rename(clean(c_new_name))
    db.session.commit()
    return redirect(url_for('viewdecks'))
    
@app.route("/account", methods = ["POST", "GET"])
@login_required
def account():
    form = AccountForm()
    user = User.query.filter_by(id=current_user.id).first()
    subscriber = Subscriber.query.filter_by(email=user.email).first()
    form_del = DeleteAccountForm()
    form2 = UpdateProfilePicForm()
    try:
        if form.validate_on_submit():
            user.first_name = form.first_name.data
            user.last_name = form.last_name.data
            user.username = form.username.data
            if form.gender.data != "":
                user.gender = form.gender.data
            if form.role.data != "":
                user.role = form.role.data
            print(form.timezone.data)
            if form.timezone.data != "":
                user.timezone = form.timezone.data
            user.timezone = form.timezone.data
            
            user.contacted_email = form.contacted_email.data
            ###logger.debug("contacted", form.contacted_email.data)
            db.session.commit()
            if form.subscribe.data:
                if not subscriber:
                    subscriber = Subscriber(email=user.email, first_name=user.first_name,
                                            last_name=user.last_name,
                                            timestamp=dt.datetime.now(dt.timezone.utc))
                    db.session.add(subscriber)
                    db.session.commit()
                    flash("You have been subscribed to our mailing list")
            else:
                if subscriber:
                    db.session.delete(subscriber)
                    db.session.commit()
                    subscriber = Subscriber.query.filter_by(email=user.email).first()
                    flash("You have been unsubscribed from our mailing list")

            db.session.commit
            flash("Your account has been updated")
        return render_template("account.html", title="Account",
                                form_del = form_del, form = form,
                                user = user, subscriber = subscriber, form2 = form2)
    except Exception as e:
        logger.debug(e)
        flash("There was an error updating your account")
        return redirect(url_for('account'))

@app.route('/update_profile_pic', methods=['POST'])
@login_required
def update_profile_pic():
    form = UpdateProfilePicForm()
    if form.validate_on_submit():
        logger.debug("form validated")
        profile_picture = form.profile_pic.data
        if profile_picture:
            logger.debug("recognized file")
            # Generate a random and secure filename
            filename = secure_filename(profile_picture.filename)

            # Save the file to our server
            pic_path = os.path.join('static', 'profile_pictures', filename)
            profile_picture.save(pic_path)

            # Update the user's profile picture
            user = User.query.filter_by(id=current_user.id).first()
            user.pic = pic_path
            db.session.commit()
        else:
            flash('No file selected')
    else:
        for error in form.profile_pic.errors:
            flash(error)
    return redirect(url_for('account'))

@app.route("/deletecard/<int:deck_id>/<int:card_id>", methods = ["POST"])
@login_required
def deletecard(deck_id, card_id):
    c_deck_id = deck_id
    c_card_id = card_id
    deck = Deck.query.get_or_404(c_deck_id)
    if(current_user.id != deck.user_id):
        return apology('Deck not assigned to user', 403)
    card_to_delete = Card.query.get_or_404(c_card_id)
    if card_to_delete != None:
        db.session.delete(card_to_delete)
        db.session.commit()
        return jsonify({"status": "success", "message": "Card deleted"})
    else:
        return jsonify({"status": "error", "message": "Card not found"})

@app.route("/downloadascsv/<int:deck_id>", methods = ["POST", "GET"])
@login_required
def downloadascsv(deck_id):
    c_deck_id = deck_id
    event_tracker(current_user.id, "downloadascsv")
    logger.debug("entered download as csv")
    deck = Deck.query.filter_by(id=c_deck_id).first()
    if(current_user.id != deck.user_id):
       return jsonify({'error': 'Deck not assigned to user'}), 403
    termsstrings = []
    for card in deck.cards:
        logger.debug("entered cards")
        logger.debug(card.term)
        if card.boc_2 == None:
            card.boc_2 = "null"
        if card.boc_3 == None:
            card.boc_3 = "null"
        if card.boc_4 == None:
            card.boc_4 = "null"
        ## replace commas with semicolons
        fields = [card.term, card.content, card.boc_2,
                card.boc_3, card.boc_4, card.category]
        string = ",".join(field.replace(",", ";") for field in fields) + "\n"
        termsstrings.append(string)            
    csvstring = "".join(termsstrings)        
    return Response(csvstring, mimetype="text/csv")

@app.route("/regenerate_def", methods = ["POST", "GET"])
@login_required
def regenerate_def():
    event_tracker(current_user.id, "regenerate_def")
    card_id = clean(request.form["id"])
    card = Card.query.filter(Card.id==card_id).first()
    prompt_options = process_prompt_options_regen(card)
    term = card.term 
    content = regenerate_definition(term, prompt_options)[0]
    card.content = content
    try:
        db.session.commit()
        logger.debug("card updated succesfully")
        logger.debug(card.id)
        logger.debug(card.content)
    except Exception as e:
        logger.debug("An error occurred while updating the card %s", e)      
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
@login_required
def get_due_cards(deck_id):
    logger.debug("entered get due cards")
    c_deck_id = deck_id
    deck = Deck.query.get(clean(c_deck_id))
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
    logger.debug("entered new user settings")
    data = request.get_json()
    checked = data.get('checked')
    if checked:
        logger.debug("option is checked")
        user_settings = UserSettings.query.filter_by(user=current_user.id).first()
        user_settings.new_user_study = False
        logger.debug(user_settings.new_user_study)
        db.session.add(user_settings)
        db.session.commit()
    return jsonify({'success': True})

@app.route("/new_user_settings_create", methods = ["POST", "GET"])
@login_required
def new_user_settings_create():
    logger.debug("entered new user settings")
    data = request.get_json()
    checked = data.get('checked')
    if checked:
        logger.debug("option is checked")
        user_settings = UserSettings.query.filter_by(user=current_user.id).first()
        user_settings.new_user = False
        db.session.add(user_settings)
        db.session.commit()
    return jsonify({'success': True})

@app.route("/new_user_settings_viewdecks", methods = ["POST", "GET"])
@login_required
def new_user_settings_viewdecks():
    logger.debug("entered new user settings")
    data = request.get_json()
    checked = data.get('checked')
    if checked:
        logger.debug("option is checked")
        user_settings = UserSettings.query.filter_by(user=current_user.id).first()
        user_settings.new_user_decks = False
        db.session.add(user_settings)
        db.session.commit()
    return jsonify({'success': True})

@app.route("/study_deck/<int:deck_id>", methods = ["POST", "GET"])
@login_required
def study_deck(deck_id):
    c_deck_id = deck_id
    user_settings = UserSettings.query.filter_by(user=current_user.id).first()
    if user_settings == None:
        logger.debug("user settings not found")
        user_settings = UserSettings(user=current_user.id)
        db.session.add(user_settings)
        db.session.commit()
    event_tracker(current_user.id, "study_deck", c_deck_id)
    deck = Deck.query.get(c_deck_id)
    if(current_user.id != deck.user_id):
        return apology('Deck not assigned to user', 403)
    return render_template("study_deck.html", title="Study deck",
                            deck=deck_id, deck0 = deck,  settings = user_settings) 

@app.route("/update_study_data/<int:deck_id>", methods = ["POST", "GET"])
@login_required
def update_study_data(deck_id):
    deck0 = Deck.query.get(deck_id)
    total_answered = deck0.total_answered()
    correct_answers = deck0.correct_incorrect()[0]
    if total_answered > 0:
        percentage = (correct_answers / total_answered) * 100
    else:
        percentage = 0    
    cards_due = deck0.cards_due()

    return jsonify({
        'total_answered': total_answered,
        'percentage': f'{percentage:.1f}%',
        'cards_due': cards_due
    })

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
    return render_template('study_deck_all.html', title='Study all decks',
                            decks_json=decks_json, decks=decks, settings = user_settings)

@app.route("/increment/<card_id>", methods = ["POST", "GET"])
@login_required
def increment(card_id):
    c_card_id = card_id
    card = Card.query.get(c_card_id)
    deck = Deck.query.filter(Deck.cards.any(id=c_card_id)).first()
    if(current_user.id != deck.user_id):
        return apology('Deck not assigned to user', 403)
    if card is None:
            return apology('Card not found', 404)
    card.increment()
    card.update_time()
    return jsonify({'success': 'Card incremented'}), 200
    

@app.route("/decrement/<card_id>", methods = ["POST"])
@login_required
def decrement(card_id):
    c_card_id = card_id
    card = Card.query.get(c_card_id)
    deck = Deck.query.filter(Deck.cards.any(id=c_card_id)).first()
    if(current_user.id != deck.user_id):
        return apology('Deck not assigned to user', 403)
    if card is None:
        return apology('Card not found', 404)
    card.decrement()
    card.update_time()
    return jsonify({'success': 'Card decremented'}), 200

@app.route("/forcestudy/<deck_id>")
def force_study(deck_id):
    c_deck_id = deck_id
    event_tracker(current_user.id, "force_study", c_deck_id)
    deck = Deck.query.get(c_deck_id)
    if(current_user.id != deck.user_id):
         return apology('Deck not assigned to user', 403)
    if deck is None:
        return apology('Deck not found', 404)
    return deck.force_study()
    
@app.route("/casualmode/<int:deck_id>")
@login_required
def casual_mode(deck_id):
    return render_template("casualmode.html", title="Casual Mode", deck=deck_id)   

@app.route('/generate_img/<int:deck_id>', methods=['GET', 'POST'])
@login_required
def generate_img(deck_id):
    c_deck_id = deck_id
    event_tracker(current_user.id, "generate_img", c_deck_id)
    deck = Deck.query.get(c_deck_id)
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
       
def create_parent_child_relationship(parent_deck_id, child_deck_id):
    new_relationship = insert(deck_relationships).values(parent_deck=parent_deck_id,
                    child_deck=child_deck_id)
    session.execute(new_relationship)
    session.commit()

@app.route("/add_card/<int:deck_id>", methods=["POST"])
@login_required
def add_card(deck_id):
    form = DeckOrg(request.form)
    print("entered add new card")
    if form.validate_on_submit():
        entry = Card(
            term=form.new_term.data,
            content=form.new_content.data,
            boc_2=form.new_boc_2.data,
            boc_3=form.new_boc_3.data,
            boc_4=form.new_boc_4.data,
            category=form.new_category.data,
            time_created=dt.datetime.now(dt.timezone.utc),
        )
        deck = Deck.query.filter_by(id=deck_id, user_id=current_user.id).first()
        if deck:
            deck.cards.append(entry)
            db.session.commit()
            return jsonify(success=True)
    return jsonify(success=False)

@app.route("/edit_card_new", methods=["POST"])
@login_required
def edit_card_new():
    print("entered edit card")
    data = request.get_json()
    print(data)
    if data:
        card_id = data["id"]
        card = Card.query.filter_by(id=card_id).first()
        if 'term' in data:
            term = data["term"]
            card.term = term
        if 'content' in data:
            if data["content"] != "":
                content = data["content"]
                card.content = content
        if 'boc_2' in data:
            boc_2 = data["boc_2"]
            card.boc_2 = boc_2
        if 'boc_3' in data:
            boc_3 = data["boc_3"]
            card.boc_3 = boc_3
        if 'boc_4' in data:
            boc_4 = data["boc_4"]
            card.boc_4 = boc_4
        db.session.commit()
        return jsonify(success=True)
    return jsonify(success=False)


@app.route("/carousel/<int:deck_id>", methods = ["GET", "POST"])
@login_required
def carousel(deck_id):
    c_deck_id = deck_id
    deck = Deck.query.filter_by(id=c_deck_id, user_id=current_user.id).first()

    form = DeckOrg(obj=deck)
    cards = (
            Card.query.filter(Card.decks_backref.any(id=deck_id))
            .order_by(Card.id.desc()).all()
    )
    if(current_user.id != deck.user_id):
         return apology('Deck not assigned to user', 403)
         """
    if form.validate_on_submit():
        print("entered validate on submit")
        if form.term.data:
            print("form term data")
            term = form.term.data
            print(term)
            content = form.content.data
            boc_2 = form.boc_2.data
            boc_3 = form.boc_3.data
            boc_4 = form.boc_4.data
            id = form.id.data
            formula = form.formula.data
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
"""
    return render_template("carousel.html", title="Carousel",
                            deck=deck, cards=cards, form=form)

@app.route("/edit_card", methods=["POST"])
@login_required
def edit_card():
    logger.debug("edit_card")
    form = DeckOrg(request.form)

    if form.validate():
        id = form.id.data
        card = Card.query.filter_by(id=id).first()

        if card:
            card.term = form.term.data.strip()
            card.content = form.content.data.strip()
            card.boc_2 = form.boc_2.data.strip()
            card.boc_3 = form.boc_3.data.strip()
            card.boc_4 = form.boc_4.data.strip()
            card.formula = form.formula.data.strip()

            db.session.commit()
            return jsonify({"status": "success"})
        else:
            return jsonify({"status": "error", "message": "Card not found"}), 404
    else:
        return jsonify({"status": "error", "message": "Invalid form data"}), 400

@app.route("/landingpage", methods = ["GET", "POST"])
def landingpage():
    return render_template("landingpage.html", title="Landing Page")

@app.route("/terms_and_conditions")
def terms_and_conditions():
    return render_template("terms_and_conditions.html", title="Terms and Conditions")

@login_required
@app.route("/delete_account", methods=["GET", "POST"])
def delete_account():
    form = DeleteAccountForm()

    if form.validate_on_submit():
        user = User.query.filter_by(id=current_user.id).first()
        if user.email == form.del_email.data:
            user.account_status = 'inactive'
            user.expiration = dt.datetime.now(dt.timezone.utc)
            user.account_expiration_reason = "Deleted"
            if form.reason.data == 'other':
                reason = form.other_reason.data
            else:
                reason = form.reason.data

            if form.more.data:
                details = form.more.data
            else:
                details = None

            deleted_entry = DeletedAccounts(user_id=current_user.id,
                    email = current_user.email, date_created = current_user.time_created,
                    date_deleted = dt.datetime.now(dt.timezone.utc), reason=reason,
                    reason_details = details)
            db.session.add(deleted_entry)
            db.session.commit()
        
            flash('We are sorry to see you go. Your account is now inactive and will be'
                  'permanently deleted within 48 hours.')
            return redirect(url_for('logout'))

    return render_template('delete_account.html', form_del=form)

@app.route("/import_public_deck/<int:deck_id>", methods = ["GET", "POST"])
@login_required
def import_public_deck(deck_id):
    c_deck_id = deck_id
    logger.debug("entered public decks")
    deck = Deck.query.filter_by(id=c_deck_id, public=True).first()
    if deck is None:
        return apology("Deck not found", 404)
    else:
        shared_deck = SharedDecks(name="Copy of " + deck.name,
                                description=deck.description,
                                time_created=dt.datetime.now(dt.timezone.utc),
                                receiver=current_user.id)
        db.session.add(shared_deck)
        for card in deck.cards:
            new_card = Card(term=card.term, content=card.content,
                            boc_2=card.boc_2, boc_3=card.boc_3, boc_4=card.boc_4,
                            img=card.img,sound=card.sound, subject=card.subject,
                            topic=card.topic, category=card.category,
                            prompt_option=card.prompt_option, 
                            prompt_option2=card.prompt_option2,
                            trans_option=card.trans_option,
                            len_option=card.len_option,
                            qmin_option=card.qmin_option,
                            qmax_option=card.qmax_option,
                            diff_lvl=card.diff_lvl)
            shared_deck.cards.append(new_card)
        db.session.commit()
        logger.debug(shared_deck)
    return jsonify({"success": True})




def send_audio_file(file, deck_id, prompt_options, slug):
        # Generate a random string of 5 digits
    upload_folder = app.config['UPLOAD_FOLDER']
    random_string = ''.join(random.choices('0123456789', k=5))

    # Get the original file name and extension
    original_filename = file.filename
    filename, extension = os.path.splitext(original_filename)

    # Create a new file name
    new_filename = f"{filename}_{random_string}{extension}"
    new_filename_secure = secure_filename(new_filename)

    # Create the upload folder if it doesn't exist
    os.makedirs(upload_folder, exist_ok=True)

    # Join the upload folder path and the secure file name
    file_path = os.path.join(upload_folder, new_filename_secure)

    # Save the file
    file.save(file_path)
    logging.info("file path: %s", file_path)

    audio_processing(file_path, current_user, deck_id, prompt_options, slug)
    # Return the location of the saved file
    return file_path



""""
    is_valid_audio(file)

    file_type = type(file)
    logging.info(file.filename)
    logging.info("entered send_audio_file %s", file_type)
    if not file:
        logging.info("no file data")
    random_number = ''.join(random.choices('0123456789', k=5))
    filename = file.filename
    extension = os.path.splitext(filename)[1].lower()

    ##file.filename = "file" + str(current_user.id) + random_number + extension
    folder_path = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                                app.config['UPLOAD_FOLDER'])
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    file_loc = os.path.join(folder_path, secure_filename(file.filename))
    file.save(file_loc)
    audio_processing(file_loc, current_user, deck, prompt_options, db)
"""
def is_valid_audio(file_storage):
    try:
        # Attempt to load audio file
        audio = AudioSegment.from_file(file_storage, format=file_storage.filename.split('.')[-1])
        logging.info("Valid audio file")
        return True
    except Exception as e:
        logging.info("Invalid audio file %s", e)
        return False

@app.route("/check_credit", methods=["GET", "POST"])
def check_credit():
    form = UploadFileForm()
    return render_template("check_credit.html", title="Check Credit", form = form)

@app.route("/extract", methods = ["GET", "POST"])
@login_required
def extract():
    user_settings = UserSettings.query.filter_by(user=current_user.id).first()
    if user_settings == None:
        logger.debug("user settings not found")
        user_settings = UserSettings(user=current_user.id)
        db.session.add(user_settings)
        db.session.commit()
    ## plan level requried for genereting images
    form = UploadFileForm()
    if form.validate_on_submit():
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        slug = str(current_user.id) + now
        session['slug'] = slug
        audio_extensions = None
        valid_extensions = [".mp3", ".wav"]
        if form.file.data:
            audio_extensions = os.path.splitext(form.file.data.filename)[1].lower()
        # List of valid extensions
            
        if audio_extensions in valid_extensions:
            duration = check_audio_file(form)
            form.file.data.seek(0)
            if duration:
                prompt_options = process_prompt_options(form)
                if prompt_options['main_opt'] == 'Mix':
                    prompt_options['main_opt'] = 'Definitions'
                logging.info("audio file detected")
                logger.info(f"durationDDDDDDDDDDD: {duration}")
                tokens = convert_time_to_tokens(duration)
                logger.info(f"tokens: {tokens}")
                perform_operation(current_user.id, "extract", tokens)
                if prompt_options['main_opt'] == 'Mix':
                    prompt_options['main_opt'] = 'Definitions'
                deck = get_or_create_deck(form, prompt_options)
                logger.info("form file data %s", form.file.data)
                form.file.data.seek(0)
                deck_id = deck.id
                send_audio_file(form.file.data, deck_id, prompt_options, slug)
                job_notification = JobNotification(user_id=current_user.id,
                 slug = slug, date_created = now, cost = tokens)
                db.session.add(job_notification)
                db.session.commit()
                return redirect('/viewdecks')
        else:
            try:
                now = dt.datetime.now(dt.timezone.utc).isoformat()
                deck, text, prompt_options = handle_form_submission(form)
                logger.debug(text[:100])
                tokens = count_tokens(text)
                texts = None
            
                if text != None and len(text) > 0:      
                    if perform_operation(current_user.id,
                                        prompt_options['main_opt'], tokens) == False:
                        flash('You have reached your monthly usage limit.'
                            'Please upgrade your account to continue.')
                        event_tracker(current_user.id, 'extract_start',
                                    'fail', "limit_reached")
                        return redirect(url_for('upgrade'))
                    else:
                        if prompt_options['save_text_opt'] == True:
                            method = "Source"
                            deck_name = deck.name + " - Source" + " - " + now
                            save_source_text_to_deck(deck_name, deck,
                                                    text, prompt_options, method)

                        texts= split_text(text)
                        if not isinstance(texts, list):
                            texts = [texts]
                        if prompt_options['main_opt'] == 'Mix':
                            prompt_options['main_opt'] = 'Definitions'
                            job_creator(texts, deck, prompt_options, slug)
                            prompt_options['main_opt'] = 'Mcq'
                            job_creator(texts, deck, prompt_options, slug)
                            prompt_options['main_opt'] = 'Cloze'
                            job_creator(texts, deck, prompt_options, slug)
                        else:
                            job_creator(texts, deck, prompt_options, slug)

                        
                        job_notification = JobNotification(user_id=current_user.id,
                            slug = slug, date_created = now, cost = tokens)
                db.session.add(job_notification)
                db.session.commit()
                return redirect('/viewdecks')
            except YoutubeError as e:
                flash('We were unable to extract the text from the link. A small minority of youtube videos do not allow text extraction. Please try another link or contact us for assistance.')
                logger.error(f"Youtube error {e}")
                return redirect(url_for('extract'))
            except FileNotFoundError as e:
                flash("File not found. Please try again.")
                logger.error(f"File not found {e}")
                return redirect(url_for('extract'))
            except Exception as e:
                logger.error(e)
                flash('Something went wrong. Please try again.')
                return redirect('/extract')
    return render_template("extract.html", title="Extract", form=form,
                            settings = user_settings)


def job_creator(texts, deck, prompt_options, slug):
    for text in texts:
        counter = 0
        total_len = len(texts)
        counter = counter + 1
        payload_dict = {'deck': deck.id, 'text': text,
                        'prompt_options': prompt_options}
        payload = json.dumps(payload_dict)
        current_user_id = current_user.id     
        task_type = prompt_options['main_opt']
        data = Job(slug=slug, user = current_user_id,
                    task_type=task_type, payload=payload,
                    item_number = counter, deck_id=deck.id, item_quantity = total_len)
        event_tracker(current_user.id, 'extract_start',
                    'success', payload)
        if counter == total_len:
            session['slug'] = slug
        db.session.add(data)
        db.session.commit()


@app.route("/call_credit_counter", methods = ["POST"])
def call_credit_counter():
    form = UploadFileForm()  # you might need to adjust this part to fit your project
    try:
        credit = credit_counter(form)
        return jsonify(credit)
    except YoutubeError:
        raise YoutubeError
    except FileNotFoundError as e:
        flash("File not found. Please try again.")
        logger.error(f"File not found {e}")
        redirect(url_for('extract'))

    except Exception as e:
        logger.error(e)
    



def credit_counter(form):
    print("Entered credit counter")
    if form.file.data:
        print("Entered data")
        if form.file.data.filename.endswith(".mp3") or form.file.data.filename.endswith(".wav"):
            duration = check_audio_file(form)
            tokens = convert_time_to_tokens(duration)
        else:
            text = get_text_from_file(form.file.data)
            tokens = count_tokens(text)
    elif form.text_input.data: 
            print("Entered text")   
            text = form.text_input.data
            print(text[:50])
            tokens = count_tokens(text)
    elif form.link_input.data:
            print("Entered link")
            try:
                text = get_text_from_link(form.link_input.data)
            except YoutubeError:
                raise YoutubeError
            except Exception as e:
                logger.info(e)
                return "error"
            print(text[:50])
            tokens = count_tokens(text)
    return round(tokens_to_credit(tokens), 1)


def tokens_to_credit(tokens):
    credit = tokens / 682
    return credit

def allowed_file(filename):
    if filename.endswith(".mp3") or filename.endswith(".wav"):
        return True
    
def check_audio_file(form):
    file = form.file.data  # Get the file object from the form
    filename = file.filename
    if filename.endswith(".mp3") or filename.endswith(".wav"):
        file_data = file.read()  # Read the file data
        file_size = len(file_data)  # Calculate the file size
        logging.info(f"File size: {file_size}")
        # Save the file temporarily to be used by FFmpeg
        temp_filename = "temp_audio_file" + filename
        with open(temp_filename, "wb") as temp_file:
            temp_file.write(file_data) 
        info = mediainfo(temp_filename)
        try:
            duration = float(info['duration'])
        except Exception as e:
            logging.info(e)
            time_base = float(info['time_base'].split('/')[1])
            duration = float(info['duration_ts']) / time_base
        logging.info(f"Duration: {duration}")
        os.remove(temp_filename)
        return duration
    else:
        return False
## Functions for extract:
def handle_form_submission(form):
    try:
        prompt_options = process_prompt_options(form)
        deck = get_or_create_deck(form, prompt_options)
        text = get_text_from_form_input(form)
    except YoutubeError:
        raise YoutubeError
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
        time = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
        deck_name = form.name.data or "".join(main_opt + " "+ "deck" +" "+ time)
        deck_description = form.description.data or "".join(main_opt + " " + "deck")
        deck = Deck(name=deck_name, description=deck_description)
        db.session.add(deck)
        db.session.commit()
    deck.user_id = current_user.id
    return deck

def get_text_from_form_input(form):
    if form.file.data:
        try:
            text = get_text_from_file(form.file.data)
        except Exception as e:
            logger.warning("Unable to extract text from file: %s", e)
            flash('We were unable to extract the text from the file. Please try again or use a different format.')
            return redirect('/extract')
    elif form.text_input.data and form.text_input.data.strip():
        text = form.text_input.data
    elif form.link_input.data and form.link_input.data.strip():
        try:
            text = get_text_from_link(form.link_input.data)
        except YoutubeError:
            raise YoutubeError
        except Exception as e:
            logger.warning("Unable to extract text from link: %s", e)
           
    else:
        text = None
    return text

def save_source_text_to_deck(name, deck, text, prompt_options, method="extract"):
    logger.debug("entered save_source_text_to_deck %s", deck)
    try:
        main_opt = prompt_options['main_opt']
        f_name = name
        file_storage = DeckFiles(file_name=f_name,
                                  text_string=text, create_type = "source",
                                    time_created = dt.datetime.now(dt.timezone.utc))
        db.session.add(file_storage)
        deck.deck_files.append(file_storage)
        db.session.commit()
    except Exception as e:
        logger.debug(f"Error while saving source text to deck: {e}")
        db.session.rollback()
    return True

def get_text_from_file(file_data):
    print("entered get_text_from_file")
    try:
        file = file_data
        current_user_id = current_user.id
        now = dt.datetime.now(dt.timezone.utc)
        filename = file.filename
        extension = os.path.splitext(filename)[1].lower()
        file.filename = "file" + str(current_user_id) + str(now) + extension
        folder_path = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                                    app.config['UPLOAD_FOLDER'])
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        file_loc = os.path.join(folder_path, secure_filename(file.filename))
        file.save(file_loc)
        text = text_extractor(file_loc)
        print(len(text))
        return text
    except Exception as e:
        logger.debug(f"Error occurred while processing file: {e}")
        return None
    finally:
        os.remove(file_loc)
    


def get_text_from_link(link_input):
    text = None
    try:
        if "wikipedia" in link_input:
            if check_comma_list(link_input):
                link_input = link_input.split(";")
                for link in link_input:
                    part = extract_from_wiki(link)
                    if text is None:
                        text = part
                    else:
                        text = text + part
            else:
                text = extract_from_wiki(link_input)
        else:
            if check_comma_list(link_input):
                link_input = link_input.split(";")
                for link in link_input:
                    link = get_video_id(link)
                    part = extract_from_youtube(link)
                    if text is None:
                        text = part
                    else:
                        text = text + part
            else:
                print("single link")
                link_input = get_video_id(link_input)
                print(link_input)
               
                text = extract_from_youtube(link_input)
          

        return text
    except YoutubeError as e:
        print("1")
        print("Caught exception type:", type(e))
        raise YoutubeError
    except Exception as e:
        print("Caught exception type:", type(e))
        print("2")
        logger.debug(f"Error occurred while processing link: {e}")
        return None


@app.route("/sea_dox/<int:deck_id>", methods=["GET", "POST"])
@login_required
def sea_dox(deck_id):
    form = UpdateFileNameForm()
    search_and_sort_form = SearchAndSortForm()

    ## GET DECK
    deck = Deck.query.get_or_404(deck_id)
    ## GET source files
    files = deck.deck_files
    if deck.user_id != current_user.id:
        return apology("You do not have permission to view this deck", 403)
    ##files = DeckFiles.query.filter(DeckFiles.decks.any(id=deck_id)).order_by
    # (DeckFiles.file_name.desc()).all()
    if request.method == 'GET':
        logger.debug("entered get request")
        search_query = None
        sort_method = search_and_sort_form.sort.data
        search_query = request.args.get('search', '')

        if sort_method != 'default':
                if sort_method == 'name_asc':
                    files = (
                            DeckFiles.query
                            .filter(DeckFiles.decks.any(id=deck_id))
                            .order_by(DeckFiles.file_name.asc())
                            .all()
                        )
                if sort_method == 'name_desc':
                    files = (
                            DeckFiles.query
                            .filter(DeckFiles.decks.any(id=deck_id))
                            .order_by(DeckFiles.file_name.desc())
                            .all()
                    )
                if sort_method == 'type':
                    files = (
                            DeckFiles.query
                            .filter(DeckFiles.decks.any(id=deck_id))
                            .order_by(DeckFiles.create_type.asc())
                            .all()
                    )
                if sort_method == 'date':
                    files = (
                            DeckFiles.query
                            .filter(DeckFiles.decks.any(id=deck_id))
                            .order_by(DeckFiles.time_created.desc())
                            .all()
                    )
        elif search_query:
                search_query = search_query.strip()
                files = (
                    DeckFiles.query
                    .filter(DeckFiles.decks.any(id=deck_id))
                    .filter(DeckFiles.file_name.contains(search_query))
                    .all()
                )
        return render_template("sea_dox.html", title="Sea Dox",
                                files=files, deck = deck, form = form,
                                search_form = search_and_sort_form)
    if form.validate():
        file_id = form.file_id.data
        new_name = form.new_name.data
        file = DeckFiles.query.get_or_404(file_id)

        if new_name != '':
            file.file_name = new_name
            db.session.commit()
        return render_template("sea_dox.html",
                                title="Sea Dox", files=files, deck = deck,
                                form = form, search_form = search_and_sort_form)
    return render_template("sea_dox.html", title="Sea Dox",
                            files=files, deck = deck, form = form,
                            search_form = search_and_sort_form)

@app.route("/source_file/<int:file_id>", methods=["GET", "POST"])
@login_required
def source_file(file_id):
    c_file_id = file_id
    file = DeckFiles.query.get_or_404(c_file_id)
    return render_template("source_file.html", title="Source File", file=file)

@app.route("/download_source/<int:file_id>", methods=["GET", "POST"])
@login_required
def download_source(file_id):
    ## GET FILE
    c_file_id = file_id
    event_tracker(current_user.id, "download_source", c_file_id)
    file = DeckFiles.query.get_or_404(c_file_id)
    name = file.file_name +".pdf"
    text = file.text_string
    ## turn file.text_string into a pdf
    pdf_buffer = create_pdf(text)
    return send_file(pdf_buffer, download_name = name)

@app.route("/delete_file/<int:deck_id>/<int:file_id>/", methods=["GET", "POST"])
@login_required
def delete_file(deck_id, file_id):
    c_deck_id = deck_id
    c_file_id = file_id
    logger.debug("entered delete file")
    event_tracker(current_user.id, "delete_file", c_file_id)
    file = DeckFiles.query.get_or_404(c_file_id)
    deck = Deck.query.get_or_404(c_deck_id)
    db.session.delete(file)
    db.session.commit()
    return redirect(("/sea_dox/{deck}").format(deck=deck.id)) 

@app.route("/share_deck/<int:deck_id>/", methods=["GET", "POST"])
@login_required
def share_deck(deck_id):
    c_deck_id = deck_id
    share_form = Share()
    sender_id = current_user.id
    deck_to_copy = Deck.query.get_or_404(c_deck_id)
    event_tracker(current_user.id, "share_deck", c_deck_id)

    if share_form.validate_on_submit():
        users_emails = share_form.emails.data.split(",")

        for email in users_emails:
            email = email.strip()
            user = User.query.filter_by(email=email).first()

            if user:
                shared_deck = SharedDecks(name="Copy of " + deck_to_copy.name,
                                           description=deck_to_copy.description,
                                            sender=sender_id,
                                            time_created=dt.datetime.now(dt.timezone.utc),
                                            receiver=user.id)
                db.session.add(shared_deck)

                for card in deck_to_copy.cards:
                    new_card = Card(term=card.term,
                                    content=card.content, boc_2=card.boc_2,
                                    boc_3=card.boc_3, boc_4=card.boc_4, img=card.img,
                                    sound=card.sound, subject=card.subject,
                                    topic=card.topic, category=card.category,
                                    prompt_option=card.prompt_option,
                                    prompt_option2=card.prompt_option2,
                                    trans_option=card.trans_option,
                                    len_option=card.len_option,
                                    qmin_option=card.qmin_option,
                                    qmax_option=card.qmax_option,
                                    diff_lvl=card.diff_lvl)
                    shared_deck.cards.append(new_card)
                db.session.commit()
        return jsonify('success', 'Deck shared successfully')
    else:
        return jsonify('error', 'Deck not shared')
    
@app.route("/approve_shared/<int:deck_id>/", methods=["GET", "POST"])
@login_required
def approve_shared(deck_id):
    c_deck_id = deck_id
    event_tracker(current_user.id, "approve_shared", c_deck_id)
    shared_deck = SharedDecks.query.get_or_404(c_deck_id)
    new_deck = Deck(user_id = current_user.id,
                    name=shared_deck.name,
                    description=shared_deck.description,
                    shared=True, sharer=shared_deck.sender,
                    time_created=dt.datetime.now(dt.timezone.utc))
    db.session.add(new_deck)
    for card in shared_deck.cards:
        new_card = Card(term=card.term,
                         content=card.content, boc_2=card.boc_2, boc_3=card.boc_3,
                        boc_4=card.boc_4,img=card.img, sound=card.sound,
                        subject=card.subject, topic=card.topic,
                        category=card.category,
                        prompt_option=card.prompt_option,
                        prompt_option2=card.prompt_option2,
                        trans_option=card.trans_option, len_option=card.len_option,
                        qmin_option=card.qmin_option,
                        qmax_option=card.qmax_option, diff_lvl=card.diff_lvl)
        new_deck.cards.append(new_card)
    db.session.commit()
    shared_deck.delete()
    db.session.commit()
    success = True
    return jsonify({'success': success})

@app.route("/reject_shared/<int:deck_id>/", methods=["GET", "POST"])
@login_required
def reject_shared(deck_id):
    c_deck_id = deck_id
    event_tracker(current_user.id, "reject_shared", c_deck_id)
    logger.debug("entered reject shared")
    shared_deck = SharedDecks.query.get_or_404(c_deck_id)
    shared_deck.delete()
    db.session.commit()
    success = True
    return jsonify({'success': success})

@app.route("/feedback", methods=["GET", "POST"])
def feedback():
    form = FeedbackForm()
    if form.validate_on_submit():
        entry = Feedback(name=form.name.data,
                        email=form.email.data,
                        message=form.message.data,
                        type_feedback=form.type_feedback.data)
        entry.send_feedback()
        return jsonify(status="success", message="Thank you for your feedback!")
    errors = []
    for field, error_msgs in form.errors.items():
        for msg in error_msgs:
            errors.append(f"{field}: {msg}")
    return jsonify(status="error", errors=errors)

@app.route("/legal", methods = ["GET", "POST"])
def legal():
    return render_template('legal.html', title='Legal')

@app.route("/build_test/<int:deck_id>", methods=["GET", "POST"])
def build_test(deck_id):
    c_deck_id = deck_id
    event_tracker(current_user.id, "build_test", c_deck_id)
    deck = Deck.query.get_or_404(c_deck_id)
    creator = current_user
    if request.method == "POST":
        form_data = request.form.to_dict()
        print(request.form.to_dict())
        test_questions = request.form.getlist('selected_cards[]')
        name = deck.name + " Test" + " " + datetime.now().strftime("%Y-%m-%d %H:%M")
        new_test = Test(creator=current_user.id, deck_id = deck.id)
        db.session.add(new_test)
        new_test.name = name
        jeopardyMode = form_data.get('jeopardyMode')
        print("jeopardyMode: ", jeopardyMode)
        logger.debug(new_test.name)
        for question in test_questions:
            logger.debug("Entering question in test questions")
            logger.debug(question)
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
            elif card.category == "Explain":
                print("card is explain")
                question.question = card.term
                question.q_type = "explain"
            elif card.category == "Formulas":
                print("entered formulas")
                question.question = card.term
                question.term = card.formula
                print(card.formula)
                print(question.term)
                question.q_type = "formulas"
            elif card.category == "Discuss":
                question.question = card.term
                question.q_type = "discuss"
                question.boc_2 = card.boc_2
            elif card.category == "Definitions":
## switching them around so that the test gives them a definition and they have to write the word
                if jeopardyMode == "on":
                    question.question = card.content
                    question.term = card.term
                    question.q_type = "jeopardy"
                else:
                    question.question = card.term
                    question.q_type = "definitions"
            else:
                question.question = card.term
                question.q_type = "other"
            db.session.add(question)
            new_test.questions.append(question)
  
        db.session.commit()
        return redirect('/assign_test/{test.id}'.format(test=new_test))
    return render_template('build_test.html',
                        title='Test Builder', deck=deck, creator=creator)

@app.route("/assign_test/<int:test_id>", methods=["GET", "POST"])
def assign_test(test_id):
    c_test_id = test_id
    update_card_form = UpdateCardForm(request.form)
    form = BuildTest()
    try:
        event_tracker(current_user.id, "assign_test", c_test_id)
        
        test = Test.query.get_or_404(c_test_id)
        logger.debug(request.form)
        if request.method == 'POST' and 'name' in request.form:
            logger.debug("entered post request3")
            test.name = form.name.data
            test.creator = current_user.id
            due_date = request.form['due_date']
            if due_date:
                due_date = dt.datetime.strptime(due_date[:16],'%Y-%m-%dT%H:%M')
                test.due_date = due_date
            test.subject = form.subject.data
            test.topic = form.topic.data
            test.instructions = form.instructions.data
            test.description = form.description.data
            time_limit = form.time_limit.data
            if time_limit != '' and time_limit != None:
                print("entered time limit")
                print(time_limit)
                time_limit = int(time_limit)
                test.time_limit = time_limit
            
            answer_reveal = form.reveal_answers.data
            result_reveal = form.reveal_results.data
            shuffle = form.shuffle.data
            if answer_reveal == 'answer-reveal':
                test.answer_reveal = True
            if result_reveal == 'result-reveal':
                test.result_reveal = True
            if shuffle == 'shuffle':
                test.shuffle = True
            test.count_questions()
            test.sum_points()
            db.session.commit()
            flash(f'Test: "{test.name}" has been updated!', 'success')
        return render_template('assign_test.html', title='Assign test',
                            test=test, form = form, update_card_form = update_card_form)
    except Exception as e:
        logger.info(e)
        flash("At this moment you can only assign tests to other users.  We are working on allowing you to assign tests to non-users")
        return render_template('assign_test.html', title='Assign test',
                            test=test, form = form, update_card_form = update_card_form)


@app.route('/update_card', methods=['POST'])
@login_required
def update_card():
    print("entered update card")
    data = request.get_json()
    print(data)
    form = UpdateCardForm(data=data)
    question_id = data['question-id']
    question = Question.query.filter_by(id=question_id).first_or_404()
    try:
        if data['question'] != '':
            question.question = clean(data['question'])
        if data['answer'] != '':
            question.term = clean(data['answer'])
        if data['answer'] != '':
            question.content = clean(data['answer'])
        logger.debug(data['answer'])
        if data['points'] != '':
            question.points = data['points']
        # Handle multiple choice options
        if question.q_type == 'mcq':
            if data['boc_2'] != '':
                question.boc_2 = clean(data['boc_2'])
            if data['boc_3'] != '':
                question.boc_3 = clean(data['boc_3'])
            if data['boc_4'] != '':
                question.boc_4 = clean(data['boc_4'])
        db.session.flush()
        db.session.commit()
        return jsonify(success=True)
    except Exception as e:
        logger.debug("Error while updating the question:", e)
        return jsonify(success=False, error=str(e))


@app.route("/delete_question/<int:test_id>/<int:question_id>", methods=["POST", "GET"])
@login_required
def delete_question(test_id, question_id):
    c_test_id = test_id
    c_question_id = question_id
    question_to_delete = Question.query.get_or_404(c_question_id)
    # Delthe rows in the questions table that reference the question row you want to del
    db.session.execute(questions.delete()
                       .where(questions.c.question_id == c_question_id))
    # Now you can safely delete the row from the question table
    db.session.delete(question_to_delete)
    db.session.commit()
    return redirect(('/assign_test/{test_id}'.format(test_id=c_test_id)))

@app.route("/delete_test/<int:test_id>/", methods = ["POST", "GET"])
@login_required
def delete_test(test_id):
    c_test_id = test_id
    test_to_delete = Test.query.get_or_404(c_test_id)
    db.session.delete(test_to_delete)
    db.session.commit()
    return redirect('/test_results_overview/')

@app.route("/assign/<int:test_id>/<string:user_email>/", methods=["GET", "POST"])
@login_required
def assign(test_id, user_email):
    c_test_id = test_id
    c_user_email = clean(user_email)
    test = Test.query.filter_by(id=c_test_id).first()
    test.count_questions()
    test.sum_points()
    not_users = []
    if check_comma_list(c_user_email):
        logger.debug(user_email)
        users_emails = user_email.split(",")
        for email in users_emails:
            email = unquote(email).strip()
            taker = User.query.filter_by(email=email).first()
            if taker == None:
                not_users.append(email)
            else:
                test.taker.append(taker)
    else:
        email = unquote(c_user_email)
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
    return redirect('/assign_test/{test_id}'.format(test_id = c_test_id))


@app.route("/take_test/<int:test_id>/<int:user_id>/", methods=["GET", "POST"])
@login_required
def take_test(test_id, user_id):
    c_test_id = test_id
    c_user_id = user_id
    event_tracker(current_user.id, "take_test", c_test_id)
    test_result = TestResult.query.filter_by(test_id = test_id, taker = c_user_id).first()
    test = Test.query.get_or_404(test_id)
    if request.method == 'POST':
            for question in test.questions:
                question_id = question.id
                to_call = "answer"+str(question_id)
                answer = request.form.get(to_call, '')
                answer = answer.strip()
                result = QuestionResult(test_id = test.id,
                                        taker = current_user.id,
                                        question_id = question.id, answer = answer)
                db.session.add(result)
                db.session.commit()
            end_time = request.form.get('end-time')
            end_time = datetime.strptime(end_time, '%Y-%m-%dT%H:%M:%S.%fZ')
            test_result.end_time = end_time
            db.session.commit()
            return redirect('/test_results/{test_id}/{user_id}'.format
                            (test_id = c_test_id, user_id = c_user_id))
       
    else:
        if test_result is None:
            start_time = dt.datetime.now(dt.timezone.utc)
            test_result = TestResult(test_id = test_id,
                                    taker = c_user_id, start_time = start_time,
                                    creator=test.creator)
            taker = User.query.get_or_404(user_id)
            db.session.add(test_result)
            db.session.commit()
            return render_template('take_test.html',
                            test=test, taker=taker, start_time = start_time)
        else:
            test.taker.remove(current_user)
            db.session.commit()
            flash('you have already taken this test', 'danger')
            return redirect('/test_results_overview/')

@app.route('/reject_test/<int:test_id>/<int:user_id>', methods=['DELETE'])
def reject_test(test_id, user_id):
    logger.debug("entered reject test")
    distribution_entry = distribution.delete().where(
        (distribution.c.test_id == test_id) & (distribution.c.taker_id == user_id)
    )
    db.session.execute(distribution_entry)
    db.session.commit()
    return jsonify({'message': 'Test deleted successfully'}), 200

@app.route("/test_results/<int:test_id>/<int:user_id>/", methods=["GET", "POST"])
@login_required
def test_results(test_id, user_id): 
    c_test_id = test_id
    c_user_id = user_id      
    point_counter = 0
    correct_counter = 0
    test = Test.query.get_or_404(c_test_id)
    creator = test.creator
    taker = User.query.get_or_404(c_user_id)
    for question in test.questions:
        answer = QuestionResult.query.filter_by(test_id = c_test_id,
                                taker = c_user_id, question_id = question.id).first()
        answer_given = remove_punctuation(answer.answer).lower().strip()
        if question.q_type == "jeopardy":
            answer_expected = remove_punctuation(question.term).lower().strip()
        elif question.q_type == "cloze":
            answer_expected = remove_punctuation(question.content).lower().strip()
        elif question.q_type == "mcq":
            answer_expected = remove_punctuation(question.content).lower().strip()
        matcher = difflib.SequenceMatcher(None, answer_given.lower(),
                                           answer_expected.lower())
        if matcher.ratio() > 0.9:
            point_counter += question.points
            correct_counter += 1
            answer.points = int(question.points)
        else:
            answer.points = 0
        if not answer.points:
            answer.points = 0
    test = db.session.query(Test).filter_by(id=c_test_id).first()
    test_result = TestResult.query.filter_by(test_id = c_test_id,
                                            taker = c_user_id).first()
    test_result.points = point_counter
    test_result.correct = correct_counter
    test_result.correct = creator
    taker = current_user
    if taker in test.taker:
        test.taker.remove(taker)
    db.session.add(test_result)
    db.session.commit()
    return render_template('test_results.html', test=test,
                            taker=taker, results=test_result)    

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
    return render_template('test_results_overview.html',
                            taken = test_results_taken,
                            given = test_results_given,
                            created = tests_created,tests=tests)

@app.route("/test_result_details/<int:test_id>/", methods=["GET", "POST"])
def test_result_details(test_id):
    c_test_id = test_id
    results = TestResult.query.filter_by(test_id = c_test_id).all()
    test = Test.query.filter_by(id = c_test_id).first()
    # Get the list of taker ids from the TestResult objects
    taker_ids = [result.taker for result in results]
    # Filter the User objects by the taker ids
    
    takers = User.query.filter(User.id.in_(taker_ids)).all()
    return render_template('test_result_details.html',
                        results = results, test = test, takers = takers)

@app.route("/test_created/<int:test_id>/", methods=["GET", "POST"])
def test_created(test_id):
    c_test_id = test_id
    test = Test.query.get_or_404(c_test_id)
    if request.method == 'POST' and 'test-name' in request.form:
        test.name= clean(request.form['test-name'])
        test.creator = current_user.id
        due_date = request.form.get('due-date')
        if due_date:
            due_date = dt.datetime.strptime((due_date),'%Y-%m-%dT%H:%M')
            test.due_date = due_date
        test.subject = clean(request.form['subject'])
        test.topic = clean(request.form['topic'])
        test.instructions = clean(request.form['instructions'])
        test.description = clean(request.form['description'])
        time_limit = request.form.get('time-limit', False)
        if time_limit:
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
    return render_template('test_created.html', test=test)
   
@app.route("/test_result/<int:result_id>/", methods=["GET", "POST"])
def test_result(result_id):
    c_result_id = result_id
    result = TestResult.query.filter_by(id = c_result_id, taker = current_user.id).first()
    test = Test.query.filter_by(id = result.test_id).first()
    return render_template('test_result.html', result=result, test=test)

@app.route("/test_answers/<int:test_id>/<int:taker_id>/", methods=["GET", "POST"])
def test_answers(test_id, taker_id):#
    c_test_id = test_id
    c_taker_id = taker_id
    test = Test.query.filter_by(id = c_test_id).first()
    result = TestResult.query.filter_by(test_id = c_test_id, taker = c_taker_id).first()
    question_results = (
                QuestionResult.query
                .filter_by(test_id = test.id, taker=c_taker_id).all()
    )
    result.sum_points()   
    taker = User.query.filter_by(id = c_taker_id).first()
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
        return render_template('test_answers.html',
                                result=result,
                                question_results=question_results, test=test, taker=taker)
    
@app.route("/answer_key/<int:test_id>/", methods=["GET", "POST"])
@login_required
def test_print(test_id):
    c_test_id = test_id
    test = Test.query.filter_by(id = c_test_id).first()
    return render_template('answer_key.html', test=test)

@app.route("/test_print/<int:test_id>/", methods=["GET", "POST"])
@login_required
def answer_key(test_id):
    c_test_id = test_id
    test = Test.query.filter_by(id = c_test_id).first()
    return render_template('test_print.html', test=test)


@app.route("/sea_source/<int:file_id>/", methods=["GET", "POST"])
@login_required
def sea_source(file_id):
    c_file_id = file_id
    source = DeckFiles.query.filter_by(id = c_file_id).first()
    return render_template('sea_source.html',file=source)

@app.route("/import_deck/", methods=["GET", "POST"])
@login_required
def import_deck():
    return render_template('import_deck.html')



@app.route('/import_anki', methods=['POST'])
@login_required
def import_anki():
    logger.debug("entered import_anki")
    data = request.json
    for card in data:
        deck_name = clean(card['deckName'])
        card_front = clean(card['fields']['Front']['value'])
        card_back = clean(card['fields']['Back']['value'])
        deck = Deck.query.filter_by(name=deck_name, user_id=current_user.id).first()
        if not deck:
            deck = Deck(name=deck_name, description="anki", user_id=current_user.id)
            db.session.add(deck)
            db.session.commit()
        card_O = Card(term=card_front, content=card_back,
                       srs_interval=card['interval']*1440, category="anki")
        db.session.add(card_O)
        deck.cards.append(card_O)
        db.session.commit()
    flash('Anki deck imported', 'success')
    return jsonify({"success": True})

def quote_deck_name_if_needed(deck_name):
    if ' ' in deck_name:
        return '"{}"'.format(deck_name)
    else:
        return deck_name

@app.route("/export_deck/<int:deck_id>/", methods=["GET", "POST"])
@login_required
def export_deck(deck_id):
    c_deck_id = deck_id
    try:
        request_anki_permission()
    except Exception as e:
        logger.debug("anki permission NOT GRANTED %s", e)
        return apology("Anki did not grant permission")
    if check_anki_connect() == True:
        deck = Deck.query.get_or_404(c_deck_id)
        if deck.user != current_user:
            flash('you are not allowed to view this page', 'danger')
            return redirect('/home/')
        cards = deck.cards
        anki_create_deck(deck.name)
        for card in cards:
            query = card.term
            notes = find_notes(query)
            logger.debug(notes)
            if notes == False:
                srs_interval = str(int(card.srs_interval/1440))
                anki_create_card(deck.name, card.term, card.content)
        event_tracker(current_user.id, "export-anki", "success")
        flash("Deck exported", "success")
        return redirect(url_for('viewdecks'))
    else:
        event_tracker(current_user.id, "export-anki", "fail")

        return apology('Please make sure you are on a desktop, have Anki installed' 
                'running, and  have the AnkiConnect plugin installed and enabled.', 400)

#### JAVASCRIPT ANKI CONNECT
@app.route('/get_deck_data/<int:deck_id>', methods=['GET'])
@login_required
def get_deck_data(deck_id):
    c_deck_id = deck_id
    logger.debug("entered get_deck_data")
    deck_name = Deck.query.get_or_404(c_deck_id).name
    cards = Deck.query.get_or_404(c_deck_id).cards
    card_list = []
    for card in cards:
        card_list.append({
            'id': card.id,
            'front': card.term,
            'back': card.content,
            'interval': card.srs_interval
        })
    response = jsonify({
        'name': deck_name,
        'cards': card_list
    })
    return response


@app.route("/about/", methods=['GET', 'POST'])
def about():
    return render_template('about.html')


def job_finisher(user_id):
    if not (incomplete_jobs_notifs := find_non_complete_job_notifs(user_id)):
        return
    print("incomplete jobs notifs", incomplete_jobs_notifs)
    for incomplete_job_notif in incomplete_jobs_notifs:
        jobs = find_jobs_by_slug(incomplete_job_notif.slug)
        print(jobs)
        if check_jobs_complete(jobs):
            print("jobs complete")
            assembly_jobs = []
            audio_transcript = []
            for job in jobs:
                print(job)
                if job.task_type == "audio" and job.save_source is True:
                    audio_transcript.append(job)
                if job.task_type in ["Turn2notes", "Transcribe", "Summarize"]:
                    assembly_jobs.append(job)
                job.result = 1
            if assembly_jobs:
                assemble_file(assembly_jobs)
            if audio_transcript:
                assemble_file(audio_transcript)
            db.session.commit()
            incomplete_job_notif.complete = True
            db.session.commit()

def notify(user_id):
## find unnotified jobs    
    if jobs := find_unnotified_jobs(user_id):
        print("unnotified jobs", jobs)
## send notification
        for job in jobs:
            if current_user.contacted_email is True:
                send_email(current_user.email, current_user.first_name,'deck_ready')
          ## mark job as notified
            job.notified = True
            db.session.commit()
    return True




def find_unnotified_jobs(user_id):
    return JobNotification.query.filter_by(user_id=user_id,complete=True, notified=False).all()

## Look through Job Notification, find items that are not completed for each user
def find_non_complete_job_notifs(user_id):
    return JobNotification.query.filter_by(user_id=user_id, complete=False).all()
## If not complete 

## Look through jobs for that notification and check if jobs are completed
def find_jobs_by_slug(slug):
    return Job.query.filter_by(slug=slug).order_by(Job.id.asc()).all()

def check_jobs_complete(jobs):
    counter = 0
    for job in jobs:
        if job.state == "completed":
            counter = counter + 1
    return counter == len(jobs)

def assemble_file(total_jobs):
    print("entered assemble file route")
    try:
        deck = Deck.query.get_or_404(total_jobs[0].deck_id)
        task_type = total_jobs[0].task_type
        full_text = ""
        for job in total_jobs:
            full_text += job.processed_content
        rand_num = random.randint(1, 1000)
        name = task_type + dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d-%H") + str(rand_num)
        existing_file = DeckFiles.query.filter_by(file_name=name).first()
        print(f"File already exists {existing_file}")
        if not existing_file:
            print("no existing file, creating one")
            file_storage = DeckFiles(file_name=name, text_string=full_text,
                                    create_type = task_type,
                                    time_created = dt.datetime.now(dt.timezone.utc))
            db.session.add(file_storage)
            deck.deck_files.append(file_storage)
            db.session.commit()
    except Exception as e:
        logger.debug("error assembling file %s", e)
        raise e

def job_error_checker(slug):
    print(slug)
    error_ratio = check_for_errors(slug)
    print("error ratio", error_ratio)
    if error_ratio > 0:
        print("Recognized error")
        job_notification = JobNotification.query.filter_by(slug=slug).first()
        credit = current_user.remaining_credit() * 682 + job_notification.cost + 6820
        new_usage_record = UsageRecord(user_id=job_notification.user_id,
            date=dt.datetime.now(dt.timezone.utc), operation_type="credit",
            operation_details="credit for job error", operation_count=0,
            remaining_count = credit, status="active", time_period="month",
            limit_count = credit)
        db.session.add(new_usage_record)
        db.session.commit()
        return True
    else:
        return False


def check_for_errors(slug):
    jobs = find_jobs_by_slug(slug)
    print(f"jobs {jobs}, slug {slug}")
    error_count = 0
    for job in jobs:
        if job.error_type == "error":
            error_count = error_count + 1
            job.error_type = "error_returned"
            
            print("error found")
        db.session.commit()
    return error_count / len(jobs)

## if not wait
## if they are completed check if need to be reassembled and turned into a file
## if not change each jobs result to 1
## if so reassemble and turn into file
## after assembling into a file change job result to 1
## if all jobs are complete and have result of 1, then change notification to complete

def file_assembler(user_id):
    print("entered file assembler route")
    job_finisher(user_id)
    notify(user_id)
    return jsonify({"success": True})

@app.route("/query", methods=["POST"])
@login_required
def query():
    progress = 0
    job_id = request.form["id"]
    print(job_id)
    # Now we can ask database about the state of that request
    data = Job.query.filter_by(slug=job_id).first()
    num_completed = Job.query.filter_by(slug=job_id, state="completed").count()
    num_total = Job.query.filter_by(slug=job_id).count()
    slug = JobNotification.query.filter_by(slug=job_id).first()

    if num_total != 0:
        progress = int(num_completed/num_total*100)
        if progress == 100:
            file_assembler(current_user.id)    
           
    if data is None:
        return jsonify({"state": None, "progress": None, "result": None})
    return jsonify(
        {
            "state": data.state,
            "progress": progress,
            "result": data.result,
        }
    )


@app.route("/notification_complete", methods=["POST"])
@login_required
def notification_complete():
    logger.debug("entered notification")
    slug_id= request.form["id"]
    slug = JobNotification.query.filter_by(slug=slug_id).first()
    if job_error_checker(slug.slug):
            print("entered error checker")
            session.pop('slug', None)
            db.session.commit()
            return jsonify("error")
    if slug.complete is True:
        print("job notification complete is true")
        session.pop('slug', None)
        db.session.commit()
        return jsonify("success")
 
@app.route("/latest_deck", methods=["POST", "GET"])
@login_required
def latest_deck():
    if current_user.is_authenticated:
        deck = (
                Deck.query
                .filter_by(user_id=current_user.id)
                .order_by(Deck.id.desc()).first()
        )
        if deck is not None:
            return redirect('/deck_manager/{deck_id}'.format(deck_id=deck.id))
        else:
            # Handle the case when the user has no decks, e.g.,
            #  show an error message or redirect to a create deck page
            return redirect('/viewdecks')
    else:
        # Handle the case when the user is not authenticated, e.g., 
        # redirect to login page or show an error message
        return "User is not authenticated. Please log in to continue."

@app.route("/documentation/", methods=['GET', 'POST'])
def documentation():
    return render_template('documentation.html')
#################  USAGE CHECKS  #######################################################

def convert_time_to_tokens(time):
    logger.info("converting time to tokens")
    tokens = ((time / 60)/PAGES_PER_MIN) * TOKENS_PER_PAGE
    logger.info("tokens %s", tokens)
    return tokens

def perform_operation(user_id, operation_type, n):
    # Check the user's remaining count for this time period
    user = User.query.filter_by(id=user_id).first()
    logger.debug("checking operation %s, %s", operation_type, n)
    usage_record = (
            UsageRecord.query
            .filter_by(user_id=user.id)
            .order_by(UsageRecord.date.desc()).first()
    )
    subscription_plan = (
            SubscriptionPlan.query
            .filter_by(id=user.subscription_plan).first() 
    ) 
    if usage_record is None:
        remaining_count = subscription_plan.limit_count
    else:
        remaining_count = usage_record.remaining_count
    if remaining_count - n <= 0:
        return False
    # Perform the operation and update the usage record
    # Update the usage reco
    new_record = UsageRecord(user_id=user.id, operation_type=operation_type,
                              time_period='month',
                                limit_count=subscription_plan.limit_count)
    new_record.operation_count = n
    if usage_record is None:

        new_record.remaining_count = subscription_plan.limit_count - n
    else:
        new_record.remaining_count = usage_record.remaining_count - n
    db.session.add(new_record)

def check_subscription_plan(user):
    subscription_plan = (
        SubscriptionPlan.query
        .filter_by(id=user.subscription_plan).first()
    )
    return subscription_plan

####################  MORE INFO ABOUT CARDS ###########################################

@app.route("/explain_further/<int:card_id>/", methods=['GET', 'POST'])
@login_required
def explain_further(card_id):
    c_card_id = card_id
    card = Card.query.filter_by(id=c_card_id).first()
    if card is None:
        return render_template('404.html')
    term = card.term
    subject = card.subject
    content = card.content
    response = explain_more(term, subject, content)
    json_response = {"response": response}
    return json_response

@app.route("/why_wrong/<int:card_id>/", methods=['GET', 'POST'])
@login_required
def why_wrong(card_id):
    c_card_id = card_id
    card = Card.query.filter_by(id=c_card_id).first()
    if card is None:
        return render_template('404.html')
    ww_prompt = why_wrong_builder(c_card_id)
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
@login_required
def send_question(card_id):
    c_card_id = card_id
    logger.debug("send question")
    card = Card.query.filter_by(id=c_card_id).first()
    latest_paragraph = clean(request.form.get('latest_paragraph'))
    question = clean(request.form.get('question'))
    term = clean(card.term)
    content = clean(card.content)
    response = send_question_generator(term, content, latest_paragraph, question)
    json_response = {"response": response}
    return json_response   

@app.route("/news/", methods=['GET', 'POST'])
def news():
    return render_template('news.html')

@app.route("/public_cards/<int:deck_id>/", methods=['GET', 'POST'])
@login_required
def public_cards(deck_id):
    c_deck_id = deck_id
    deck = Deck.query.filter_by(id=c_deck_id).first()
    if deck.public == False:
        return apology("Sorry, this deck is not public")
    cards = (
            Card.query.filter(Card.decks_backref.any(id=deck_id))
            .order_by(Card.term.desc()).all()
    )
    return render_template('public_cards.html', cards=cards, deck=deck)


@app.route("/public_decks", methods = ['GET', 'POST'])
@login_required
def public_decks():
    form = SearchAndSortForm()
    decks = Deck.query.filter_by(public=True).all()
    search_query= form.search.data
    sort_method = form.sort.data
    # Start building the query
    query = Deck.query.filter(Deck.public == True)
    # Apply search filters if search_query is present
    if search_query:
        query = query.filter(
            or_(
                Deck.name.ilike(f'%{search_query}%'),
                Deck.description.ilike(f'%{search_query}%'),
                Deck.category.ilike(f'%{search_query}%')
            )
        )
    # Apply sorting if sort_method is not 'default'
    if sort_method != 'default':
        if sort_method == 'name_asc':
            query = query.order_by(Deck.name.asc())
        elif sort_method == 'name_desc':
            query = query.order_by(Deck.name.desc())
        elif sort_method == "category_asc":
            query = query.order_by(Deck.category.asc())
        elif sort_method == "category_desc":
            query = query.order_by(Deck.category.desc())

    # Execute the query and fetch all the decks
    decks = query.all()
    return render_template('public_decks.html', decks=decks, form = form)

@app.route("/deck_manager/<int:deck_id>", methods=['GET', 'POST'])
@login_required
def deck_manager(deck_id):
    form = DeckOrg()
    share_form = Share()
    deck = Deck.query.filter_by(id=deck_id).first()
    tests = Test.query.filter_by(deck_id=deck_id).all()
    if current_user.id != deck.user_id:
        return apology("Sorry, this is not your deck")
    files = deck.deck_files
    if form.validate_on_submit():
        if form.new_deck_name.data:
            deck.name = form.new_deck_name.data
            deck.description = form.new_deck_description.data
            deck.subject = form.new_deck_subject.data
            deck.topic = form.new_deck_topic.data
            parent = form.deck_list.data
            public = bool(request.form.get('public'))
            if public:
                deck.public = True
            else:
                deck.public = False

            if parent:
                db.session.execute(deck_relationships.insert().values(parent_deck=parent.id,
                                    child_deck=deck.id))

            db.session.commit()


    return render_template('deck_manager.html', deck=deck, files=files,
                            share_form = share_form, tests = tests, form=form)

##@app.route("/team", methods=['GET', 'POST'])
##def team():
    ##return render_template('team.html')

########################  STRIPE ###################################
##################################################################
################################
@app.route('/pricing', methods=['GET', 'POST'])
def pricing():
    return render_template('pricing.html')


@app.route('/upgrade', methods=['GET', 'POST'])
def upgrade():
    if not current_user.is_authenticated:
        flash('You must first have an account and be logged in'
            'before upgrading your account', 'warning')
        return redirect(url_for('index'))
    return render_template('upgrade.html')



counter = 0

@app.route("/stripe_webhook", methods=['POST'])
def stripe_webhook():
    logger.debug("entered webhook")
    valid_events = ['checkout.session.completed','customer.updated']
    global counter
    counter += 1
    logger.debug(f"Webhook call #{counter}")
    payload = request.data.decode('utf-8')
    sig_header = request.headers.get('stripe-signature')
    event = None
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        # Invalid payload
        logger.exception("An exception occurred in stribe_webhook() route): %s", e)
        return 'Invalid payload', 401
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        logger.debug(f"Signature verification error: {str(e)}")
        logger.error("An exception occurred in stribe_webhook() route): %s", e)

        return 'Invalid signature', 402
    # Handle the checkout.session.completed event
    if event['type'] in valid_events:
        # Fulfill the purchase...
        process_event_in_background(event)
    else:
        # Unknown event type
        logger.debug("unused event type %s", event['type'])
        return 'Unused event type', 200
    return 'Success', 200

def process_event_in_background(event):
    try:
        logger.debug('entered process_event_in_background')
        logger.debug("event type: %s", event['type'])
        stripe_event_id = event['id']
        event_type = event['type']
        event_data = json.dumps(event)
        created_at = dt.datetime.now(dt.timezone.utc)
        if event['type'] == 'checkout.session.completed':
            user_id = event['data']['object']['client_reference_id']
        else:
            user_id = None
        if event['type'] != 'customer.updated':
            stripe_customer_id = event['data']['object']['customer']
            logger.debug("CUSTOMER ID %s", event['data']['object']['customer'])
        else:
            stripe_customer_id = None
        stripe_event = StripeEvents(
            stripe_event_id=stripe_event_id,
            event_type=event_type,
            event_data=event_data,
            event_created=created_at,
            user_id=user_id,
            stripe_customer_id=stripe_customer_id,
        )
        db.session.add(stripe_event)
        db.session.commit()
    except Exception as e:
        logger.error("Exception in process_event_background function):%s", e)
        pass
    if event['type'] == 'checkout.session.completed':
        associate_stripe_customer_with_user(event)
        # Add a small delay to give the webhook function enough time to return a response
        time.sleep(1)
        # Store the event data in the StripeEvents table
        logger.debug("unused event type: %s", event['type'])
        stripe_event_id = event['id']
        event_type = event['type']
        event_data = json.dumps(event)
        created_at = dt.datetime.now(dt.timezone.utc)
        user_id = event['data']['object']['client_reference_id']
        stripe_customer_id = event['data']['object']['customer']
        logger.debug("CLIENT REF ID %s", event['data']['object']['client_reference_id'])
        logger.debug("CUSTOMER ID %s", event['data']['object']['customer'])
        stripe_event = StripeEvents(
            stripe_event_id=stripe_event_id,
            event_type=event_type,
            event_data=event_data,
            event_created=created_at,
            user_id=user_id,
            stripe_customer_id=stripe_customer_id,
        )
        db.session.add(stripe_event)
        db.session.commit()
        try:
            # Your event processing logic
            handle_checkout_session(event)
            # Update the event as processed in the StripeEvents table
            stripe_event.processed = True
            stripe_event.processed_at = dt.datetime.now(dt.timezone.utc)

        except Exception as e:
            # Update the StripeEvents table with the error message if processing fails
            stripe_event.error_message = str(e)
            current_app.logger.error('Exception in process_event_background'
                                    'function):%s', e)

        finally:
            db.session.commit()
    else:
        ## handle other event types
        pass

def associate_stripe_customer_with_user(event):
    try:
        idempo = str(uuid.uuid4())
        logger.debug("associating stripe customer with user")
        user_id = event['data']['object']['client_reference_id']
        stripe_customer_id = event['data']['object']['customer']
        ## modify user entry in DB
        user = User.query.filter_by(id=user_id).first()
        user.stripe_customer_id = stripe_customer_id
        ## modify stripe customer entry
        stripe.Customer.modify(
            stripe_customer_id,
            metadata={'user_id': user_id},
            idempotency_key=idempo, 
            )
        db.session.commit()
    except Exception as e:
        logger.debug("error associating stripe customer with user %s", e)
        raise

def handle_checkout_session(event):
    logger.debug('entered handle_checkout_session')
    plans_dict = {
    'price_1NAp58GXWJkeH44y1XCry43l':'premium_yearly',
    'price_1NAp4FGXWJkeH44yaeBrflCN': 'premium_monthly', 
    'price_1N8LUuGXWJkeH44yZcPvdyIk': 'standard_yearly', 
    'price_1N8LSNGXWJkeH44yRgflWxVx': 'standard_monthly',
    'price_1NAp2WGXWJkeH44yPZ7Lfh2I': 'basic_yearly',
    'price_1NAoyjGXWJkeH44y6apbQdjH': 'basic_monthly',
    }
    # Extract customer ID and subscription ID from the invoice object
    customer_id = event['data']['object']['customer']
    logger.debug("recognized customer id as %s", customer_id)
    ##subscription_id = event['data']['object']['subscription']
    checkout_session_id = event['data']['object']['id']
    line_items = stripe.checkout.Session.list_line_items(checkout_session_id)
    # Look up the user in your database using the customer ID
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    logger.debug('user is:  %s', user)
    if line_items.data:
        logger.debug("entered line_items.data")
        # Assuming there is only one line item
        item = line_items.data[0]
        product_id = item['price']['product']        
        price_id = item['price']['id']
        logger.debug(price_id)
        logger.debug("product_id %s",product_id)
        # Retrieve the product details from Stripe API
        product = stripe.Product.retrieve(product_id)
        product_name = product['name']
        logger.debug("product_name %s",product_name)
        plan = plans_dict[price_id]
        logger.debug(plan)
    try:
        if user:
            update_plan(user, plan)
    except Exception as e:
            ## log user not found error
            logger.debug("user not found")
            logger.error(f"Exception occurred in handle_checkout_session: {str(e)}") 
            raise e

def update_plan(user,plan):
    logger.debug('entered update_plan')
    try:
        if plan == 'standard_yearly':
            user.subscription_plan = 6
            user.subscription_start_date = dt.datetime.now(dt.timezone.utc)
            user.subscription_latest_roll_over = dt.datetime.now(dt.timezone.utc)
            set_usage_limit(user, 682700)
            if user.contacted_email == True:
                send_email(user.email, user.first_name, 'upgrade')
        elif plan == 'standard_monthly':
            user.subscription_plan = 4
            user.subscription_start_date = dt.datetime.now(dt.timezone.utc)
            user.subscription_latest_roll_over = dt.datetime.now(dt.timezone.utc)
            set_usage_limit(user, 682700)
            if user.contacted_email == True:
                send_email(user.email, user.first_name, 'upgrade')
        elif plan == 'premium_yearly':
            user.subscription_plan = 7
            user.subscription_start_date = dt.datetime.now(dt.timezone.utc)
            user.subscription_latest_roll_over = dt.datetime.now(dt.timezone.utc)
            set_usage_limit(user, 2048000)
            if user.contacted_email == True:
                send_email(user.email, user.first_name, 'upgrade')
        elif plan == 'premium_monthly':
            user.subscription_plan = 5
            user.subscription_start_date = dt.datetime.now(dt.timezone.utc)
            user.subscription_latest_roll_over = dt.datetime.now(dt.timezone.utc)
            set_usage_limit(user, 2048000)
            if user.contacted_email == True:
                send_email(user.email, user.first_name, 'upgrade')
        elif plan == 'basic_monthly':
            user.subscription_plan = 2
            user.subscription_start_date = dt.datetime.now(dt.timezone.utc)
            user.subscription_latest_roll_over = dt.datetime.now(dt.timezone.utc)
            set_usage_limit(user, 204800)
            if user.contacted_email == True:
                send_email(user.email, user.first_name, 'upgrade')
        elif plan == 'basic_yearly':
            user.subscription_plan = 3
            user.subscription_start_date = dt.datetime.now(dt.timezone.utc)
            user.subscription_latest_roll_over = dt.datetime.now(dt.timezone.utc)
            set_usage_limit(user, 204800)
            if user.contacted_email == True:
                send_email(user.email, user.first_name, 'upgrade')
        else:
            logger.debug("plan not found")
        logger.debug("%s, %s", user.id, user.subscription_plan)
        db.session.commit()
    except Exception as e:
        logger.debug(e)
        logger.debug("error updating plan")
        raise e

def set_usage_limit(user, n):
    new_record = UsageRecord(
        user_id=user.id,
        operation_type="Change plan",
        limit_count=n,
        operation_count=0,
        remaining_count=n,
        date=dt.datetime.now(dt.timezone.utc),
        time_period = "month",
    )
    db.session.add(new_record)
    db.session.commit()
                        
####################### GROUPS #####################################################
####################################################################################
####################################################################################
@app.route('/remove_deck_from_group/<group_id>/<deck_id>', methods=['GET','POST'])
@login_required
def remove_deck_from_group(group_id, deck_id):
    logger.debug("remove deck from group")
    group = Group.query.filter_by(id=group_id).first()
    deck = Deck.query.filter_by(id=deck_id).first()
    group.decks.remove(deck)
    db.session.commit()
    return redirect(("/group/{group}").format(group=group.id)) 


@app.route('/my_groups')
@login_required
def my_groups():
    group_form = GroupForm()
    user_id = current_user.id
    created_groups = Group.query.filter_by(creator_id=user_id).all()
    user_groups = current_user.groups
    group_invites = get_invited_users_info(user_id)
    invitations = GroupInvite.query.filter_by(user_id=user_id).all()
    all_groups_member_roles = get_all_groups_member_roles(user_id)
    return render_template('my_groups.html', invitations = invitations,
                            groups=user_groups, created_groups = created_groups,
                            group_invites = group_invites,
                            user_roles = all_groups_member_roles,
                            form = group_form)

@app.route('/create_group', methods=['POST'])
@login_required
def create_group():
    logger.debug("create group")
    form = GroupForm(request.form)
    if form.validate():
        logger.debug("form validated")
        name = form.name.data
        description = form.description.data
        group_type = form.group_type.data
        private = form.is_private.data
        user_id = current_user.id
        new_group = Group(name=name, description=description,
                        group_type=group_type, is_private=private, creator_id=user_id)
        db.session.add(new_group)
        new_group.users.append(current_user)
        db.session.commit()
        update_member_permissions(new_group.id, user_id, "write")
        logger.debug("where")
        db.session.commit()
        success_response = jsonify({'message': 'Group created successfully'}), 201
        
        logger.debug("Success response: %s", success_response)# Log the success response
        return success_response
    else:
        logger.debug("form not validated")
        logger.debug("Form errors: %s", form.errors)  # Log the form errors
        errors = form.errors
        return jsonify(errors), 400

@app.route("/invite_group/", methods=["GET", "POST"])
@login_required
def invite_group():
    group_id = request.args.get('groupId', type=int)
    user_email = request.args.get('email', type=str)
    not_users = []
    group = Group.query.filter_by(id=group_id).first()
    if check_comma_list(user_email):
        users_emails = user_email.split(",")
        for email in users_emails:
            logger.debug("user email %s", email)
            email = unquote(email).strip()
            user = User.query.filter_by(email=email).first()
            already_invited = GroupInvite().query.filter_by(user_id=user.id,
                                                            group_id=group_id).first()
            if user is None:
                not_users.append(email)
            elif already_invited is None:
                if user not in group.users:
                    new_invite = GroupInvite(name = group.name,
                        invited_by_email=current_user.email,
                        invited_by_id=current_user.id, user_id=user.id,
                        group_id=group_id, created_at = dt.datetime.now(dt.timezone.utc))
                    db.session.add(new_invite)
                    db.session.commit()
                if len(not_users) > 0:
                    flash('The following users are not registered:' + str(not_users),
                           'warning')
        return jsonify('success', 'User invited successfully')
    else:
        user = User.query.filter_by(email=user_email).first()
        if user is None:
            not_users.append(user_email)
        else:
            new_invite = GroupInvite(name = group.name,
                        invited_by_email=current_user.email,
                        invited_by_id=current_user.id, user_id=user.id,
                        group_id=group_id, created_at = dt.datetime.now(dt.timezone.utc))
            db.session.add(new_invite)
            db.session.commit()
        if len(not_users) > 0:
            flash('The following users are not registered: ' + str(not_users), 'warning')
        return jsonify('success', 'User invited successfully')


@app.route("/approve_group/<int:group_id>/", methods=["GET", "POST"])
@login_required
def approve_group(group_id):
    c_group_id = group_id
    group_invite = GroupInvite.query.filter_by(id=c_group_id,
                                            user_id=current_user.id).first()
    if group_invite:
        group = Group.query.get_or_404(group_invite.group_id)
        db.session.execute(user_group_association.insert().values(
            user_id=current_user.id, 
            group_id=group.id, 
            role="member", 
            permissions="read",
            ))
        db.session.delete(group_invite)
        db.session.commit()
        return jsonify('success', 'User added to group successfully')
    
@app.route("/reject_group/<int:group_id>/", methods=["GET", "POST"])
@login_required
def reject_group(group_id):
    c_group_id = group_id
    group_invite = GroupInvite.query.filter_by(id=c_group_id,
                                            user_id=current_user.id).first()
    if group_invite:
        db.session.delete(group_invite)
        db.session.commit()
        return jsonify('success', 'User rejected successfully')
    else:
        return jsonify('error', 'User not invited to group')

def get_group_member_roles(group_id):
    c_group_id = group_id
    results = db.session.query(User.id, User.username,
                        User.email,
                        user_group_association.c.role).join(user_group_association).filter(
        user_group_association.c.group_id == c_group_id
    ).all()
    group_member_roles = {}
    for result in results:
        if result.username is not None:
            username_or_email = result.username
        else:
            username_or_email = result.email
        group_member_roles[result.id] = {
            'username': username_or_email,
            'role': result.role
        }
    return group_member_roles

def get_all_groups_member_roles(user_id):
    c_user_id = user_id
    user_groups = db.session.query(Group).join(user_group_association).filter(
        user_group_association.c.user_id == c_user_id
    ).all()
    all_groups_member_roles = {}
    for group in user_groups:
        group_member_roles = get_group_member_roles(group.id)
        all_groups_member_roles[group.id] = group_member_roles
    return all_groups_member_roles

def get_group_member_permissions(group_id):
    c_group_id = group_id
    results = db.session.query(User.id,
                    User.username, User.email,
                    user_group_association.c.permissions).join(user_group_association).filter(
        user_group_association.c.group_id == c_group_id
    ).all()
    group_member_permissions = {}
    for result in results:
        if result.username is not None:
            username_or_email = result.username
        else:
            username_or_email = result.email
        group_member_permissions[result.id] = {
            'username': username_or_email,
            'permissions': result.permissions
        }
    return group_member_permissions

def get_all_groups_member_permissions(user_id):
    c_user_id = user_id
    user_groups = db.session.query(Group).join(user_group_association).filter(
        user_group_association.c.user_id == c_user_id
    ).all()
    all_groups_member_permissions = {}
    for group in user_groups:
        group_member_permissions = get_group_member_permissions(group.id)
        all_groups_member_permissions[group.id] = group_member_permissions
    return all_groups_member_permissions

def get_invited_users_info(user_id):
    c_user_id = user_id
    # Get all the groups the user is a part of
    user_groups_query = db.session.query(Group.id).join(user_group_association).filter(
        user_group_association.c.user_id == c_user_id
    ).all()
    # Extract the group IDs from the Row objects
    user_groups = [row[0] for row in user_groups_query]
    # Get the user IDs from the invite_group table for those groups
    invited_users = (
            db.session.query(User.id, User.username, User.email)
            .join(GroupInvite, GroupInvite.user_id == User.id)
            .filter(GroupInvite.group_id.in_(user_groups)).all()
    )
    return invited_users

@app.route("/group/<int:group_id>/", methods=["GET", "POST"])
@login_required
def group(group_id):
    c_group_id = group_id
    mydecks = Deck.query.filter_by(user_id = current_user.id).all()
    group = Group.query.get_or_404(c_group_id)
    ## get group members and their roles
    group_member_roles = get_group_member_roles(c_group_id)
    ## get invited group members
    invited_users = get_invited_users_info(current_user.id)
    decks = Deck.query.filter_by(group_id=c_group_id).all()
    permissions = get_group_member_permissions(group_id)
    return render_template('group.html', mydecks = mydecks,
                group=group, group_member_roles=group_member_roles,
                invited_users=invited_users, decks = decks, permissions = permissions)

@app.route('/group/<int:group_id>/update_member_permissions', methods=['POST'])
@login_required
def update_member_permissions(group_id, user_id = None, permission = None):
    logger.debug("entered member permissions update")
    c_group_id = group_id
    if user_id:
        logger.debug("user id is %s", user_id)
        target_user_id = user_id
    else:
        data = request.json
        target_user_id = int(data['target_user_id'])
    if permission:
        logger.debug("permission is %s", permission)
        new_permissions = permission
    else:
        new_permissions = data['new_permissions']
    # Check if the current user is the creator of the group
    group = Group.query.get(c_group_id)
    logger.debug("group is %s", group)
    user_id = current_user.id
    if group.creator_id == user_id:
        # Update the target user's permissions
        db.session.query(user_group_association).filter(
            user_group_association.c.group_id == c_group_id,
            user_group_association.c.user_id == target_user_id
        ).update({user_group_association.c.permissions: new_permissions})
        db.session.commit()
        response = {
            "status": "success",
            "message": "Member permissions updated successfully"
        }
    else:
        response = {
            "status": "error",
            "message": "You do not have permission to update member permissions"
        }
    logger.debug(response)
    return jsonify(response)

@app.route('/search_public_decks', methods=['POST'])
@login_required
def search_public_decks():
    data = request.json
    search_term = clean(data['search'])
    decks = Deck.query.filter(Deck.public == True, Deck.name.contains(search_term)).all()
    return jsonify([deck.serialize() for deck in decks])

@app.route('/add_deck_to_group', methods=['POST'])
@login_required
def add_deck_to_group():
    data = request.json
    group_id = clean(data['group_id'])
    if check_group_write_permission(group_id) == False:
        return jsonify({"status": "error",
                    "message": "You do not have permission to add decks to this group"})
    else:
        deck_id = data['deck_id']
        group = Group.query.get(group_id)
        existing_deck = Deck.query.get(deck_id)
        new_deck = Deck(user_id = current_user.id,
                name=existing_deck.name, description=existing_deck.description,
                group_id = group_id, time_created=dt.datetime.now(dt.timezone.utc))
        db.session.add(new_deck)
        for card in existing_deck.cards:
            new_card = Card(term=card.term,
                content=card.content, boc_2=card.boc_2, boc_3=card.boc_3,
                boc_4=card.boc_4, img=card.img, sound=card.sound,
                subject=card.subject, topic=card.topic, category=card.category,
                prompt_option=card.prompt_option, prompt_option2=card.prompt_option2,
                trans_option=card.trans_option, len_option=card.len_option,
                qmin_option=card.qmin_option, qmax_option=card.qmax_option,
                diff_lvl=card.diff_lvl)
            new_deck.cards.append(new_card)
        db.session.commit()
        return jsonify({"status": "success"})

def check_group_write_permission(group_id):
    c_group_id = group_id
    user_id = current_user.id
    association = db.session.query(user_group_association).filter_by(user_id=user_id,
                                                                      group_id=c_group_id).first()
    if association and association.permissions and 'write' in association.permissions:
        return True
    else:
        logger.debug("no permission to edit")
        return False

@app.route("/delete_group/<int:group_id>/", methods=["GET", "POST"])
@login_required
def delete_group(group_id):
    c_group_id = group_id
    group = Group.query.get(c_group_id)
    if group.creator_id == current_user.id:
        GroupInvite.query.filter_by(group_id=c_group_id).delete()
        db.session.delete(group)
        db.session.commit()
        return redirect(url_for('my_groups'))
    else:
        return jsonify({"message": "You do not have permission to delete this group",
                         "status": "error"})


@app.route("/import_from_group/<int:deck_id>/<int:group_id>", methods=["GET", "POST"])
@login_required
def import_from_group(deck_id, group_id):
    c_group_id = group_id
    c_deck_id = deck_id
    group = Group.query.get(c_group_id)
    existing_deck = Deck.query.get(c_deck_id)
    group = Group.query.filter_by(id=c_group_id).first()
    user_ids = [user.id for user in group.users]
    if current_user.id in user_ids:
        new_deck = Deck(user_id = current_user.id,
                name=existing_deck.name, description=existing_deck.description,
                group_id = group_id, time_created=dt.datetime.now(dt.timezone.utc))
        for card in existing_deck.cards:
            new_card = Card(term=card.term, content=card.content,
                boc_2=card.boc_2, boc_3=card.boc_3, boc_4=card.boc_4, img=card.img,
                sound=card.sound, subject=card.subject, topic=card.topic,
                category=card.category, prompt_option=card.prompt_option,
                prompt_option2=card.prompt_option2, trans_option=card.trans_option,
                len_option=card.len_option, qmin_option=card.qmin_option,
                qmax_option=card.qmax_option, diff_lvl=card.diff_lvl)
            new_deck.cards.append(new_card)
        db.session.add(new_deck)
        return jsonify({"message": "Deck imported successfully", "status": "success"})
    else:
        return jsonify({"message":"You don't have permission to import from this group",
                         "status": "error"})

@app.route("/remove_user_group/<int:group_id>/<int:user_id>", methods=["GET", "POST"])
@login_required
def remove_user_group(group_id, user_id):
    logger.debug("remove user group")
    c_group_id = group_id
    c_user_id = user_id
    group = Group.query.get(c_group_id)
    if group.creator_id == current_user.id:
        association = db.session.query(user_group_association).filter(
            and_(user_group_association.c.user_id == c_user_id,
                user_group_association.c.group_id == c_group_id)
        ).first()
        if association:
            db.session.execute(
                user_group_association.delete().where(
                    and_(user_group_association.c.user_id == c_user_id,
                        user_group_association.c.group_id == c_group_id)
                )
            )
            db.session.commit()
        return jsonify({"message": "User removed successfully", "status": "success"})
    else:
        return jsonify({"message": "You do not have permission"
                    "to remove users from this group", "status": "error"})
    


##################### EMAIL ###########################################################







###################### TO BE REORGANIZED ###############################################

def split_string(string):
    items = string.split("&-&-&")
    return items
################## CURRENTLY UNUSED ####################################################


if __name__ == "__main__":
    app.run(debug=DEBUG)
    
else:
    # For Alembic
    from models import db
    db.init_app(app)