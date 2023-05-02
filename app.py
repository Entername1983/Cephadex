import openai 
import os
from bs4 import BeautifulSoup
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import or_, and_, insert
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Mapped
from flask import g, Flask, flash, redirect, render_template, request, session, url_for, Response, send_file, jsonify
from flask_session import Session
from tempfile import mkdtemp
import pytz
from pytz import common_timezones
from sqlalchemy_utils import database_exists, create_database
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from wtforms import DateField, IntegerField, StringField, PasswordField, SubmitField, RadioField, SelectField, BooleanField, TextAreaField
from email_validator import validate_email, EmailNotValidError
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms_sqlalchemy.fields import QuerySelectField
from wtforms.validators import InputRequired, Length, ValidationError, EqualTo, Optional, URL, DataRequired, Email
from flask_wtf import FlaskForm
from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename
from werkzeug.datastructures import ImmutableDict
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
from anki import request_anki_permission, anki_import_all, anki_import_deck, anki_create_deck, anki_create_card, find_notes, check_anki_connect
from flask import abort
from celery import Celery
import time
import schedule
from beta import BetaKeys
from config import UPLOAD_FOLDER, SECRET_KEY, DEBUG, BROKER, SQLALCHEMY_DATABASE_URI, MAX_CONTENT, SQLALCHEMY_TRACK_MODIFICATIONS, ALLOWED_EXTENSIONS
from models import db, Job, TestResult, QuestionResult, Question, Test, Feedback, ResponseData, DeckFiles, Subscriber, Deck, SharedDecks, Card
from models import GroupInvite, Group, user_group_association, UsageRecord, SubscriptionPlan, User, cards, source_files, cards_shared, questions, distribution, UserSettings, deck_relationships
import configparser
import logging.config
from events import event_tracker
from flask_talisman import Talisman
from logging.config import dictConfig
from logging_config import LOGGING_CONFIG

dictConfig(LOGGING_CONFIG)

openai.api_key = os.environ.get("OPENAI_API_KEY")
os.environ["FLASK_DEBUG"] = "1"
# Configure application
app = Flask(__name__)
app.config.from_object('config')


### AUTO ESCAPE

jinja_options = ImmutableDict(
 extensions=[
  'jinja2.ext.autoescape', 'jinja2.ext.with_' 
 ])

app.jinja_env.autoescape = True




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
    select_text = SelectField('Select Text', choices=[('', 'Select a passage on one of the following topics'), ('A cephalopod  is any member of the molluscan class Cephalopoda  (Greek plural "head-feet") such as a squid, octopus, cuttlefish, or nautilus. These exclusively marine animals are characterized by bilateral body symmetry, a prominent head, and a set of arms or tentacles (muscular hydrostats) modified from the primitive molluscan foot. Fishers sometimes call cephalopods "inkfish", referring to their common ability to squirt ink. The study of cephalopods is a branch of malacology known as teuthology.', 'Cephalopods'),
                                                      ('A deck is a permanent covering over a compartment or a hull of a ship. On a boat or ship, the primary or upper deck is the horizontal structure that forms the "roof" of the hull, strengthening it and serving as the primary working surface. Vessels often have more than one level both within the hull and in the superstructure above the primary deck, similar to the floors of a multi-storey building, that are also referred to as decks, as are certain compartments and decks built over specific areas of the superstructure. Decks for some purposes have specific names.', 'Ship decks'), 
                                                      ('The Great Library of Alexandria in Alexandria, Egypt, was one of the largest and most significant libraries of the ancient world. The Library was part of a larger research institution called the Mouseion, which was dedicated to the Muses, the nine goddesses of the arts. The idea of a universal library in Alexandria may have been proposed by Demetrius of Phalerum, an exiled Athenian statesman living in Alexandria, to Ptolemy I Soter, who may have established plans for the Library, but the Library itself was probably not built until the reign of his son Ptolemy II Philadelphus. The Library quickly acquired many papyrus scrolls, owing largely to the Ptolemaic kings aggressive and well-funded policies for procuring texts. It is unknown precisely how many such scrolls were housed at any given time, but estimates range from 40,000 to 400,000 at its height.', 'The Great Library of Alexandria'), 
                                                      ('Spaced repetition is an evidence-based learning technique that is usually performed with flashcards. Newly introduced and more difficult flashcards are shown more frequently, while older and less difficult flashcards are shown less frequently in order to exploit the psychological spacing effect. The use of spaced repetition has been proven to increase the rate of learning. Although the principle is useful in many contexts, spaced repetition is commonly applied in contexts in which a learner must acquire many items and retain them indefinitely in memory. It is, therefore, well suited for the problem of vocabulary acquisition in the course of second-language learning. A number of spaced repetition software programs have been developed to aid the learning process. It is also possible to perform spaced repetition with physical flashcards using the Leitner system.', 'Spaced Repetition and Flashcards'), 
                                                      ], default='Choose a text')
    prompt = RadioField('Prompt', choices=[('Definitions', 'Definitions'), ('Mcq', 'Multiple choice'), ('Translate', 'Translate'), ('Cloze', 'Fill in the blank'),
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
    
    
class DeckOrg(FlaskForm):    
    deck_list = QuerySelectField("Choose a deck", query_factory=lambda: Deck.query.filter(Deck.user_id == current_user.id), allow_blank=True, get_label='name', render_kw={"placeholder": "Choose an existing deck"})
    term = StringField('Term', render_kw={"placeholder": "Term"})
    content = TextAreaField('Content', render_kw={"placeholder": "Content"})
    boc_2 = StringField('boc_2')
    boc_3 = StringField('boc_3')
    boc_4 = StringField('boc_4')
    id = StringField('id')
    formula = StringField('formula')
    new_deck_name = StringField('deck_name')
    new_deck_description = StringField('deck_description')
    new_deck_subject = StringField('deck_subject')
    new_deck_topic = StringField('deck_topic')
    is_public = BooleanField('is_public')
    new_term = StringField('new_term')
    new_content = TextAreaField('new_content')
    new_boc_2 = StringField('new_boc_2')
    new_boc_3 = StringField('new_boc_3')
    new_boc_4 = StringField('new_boc_4')
    new_category = StringField('new_category')
    edit_deck = SubmitField("Edit deck", render_kw={"id": "edit-deck"})

        
class UploadFileForm(FlaskForm):
    file = FileField("File")
    name = StringField("Deck name", render_kw={"placeholder": "Name your deck"})
    description = StringField("Description", render_kw={"placeholder": "Describe your deck"})
    submit = SubmitField("Generate", render_kw={"id": "extract-submit"})
    deck_list = QuerySelectField("Choose a deck", query_factory=lambda: Deck.query.filter(Deck.user_id == current_user.id), allow_blank=True, get_label='name', render_kw={"placeholder": "Choose an existing deck"})
    prompt = RadioField('Prompt', choices=[('Definitions', 'Definitions'), ('Mcq', 'MCQ'), ('Translate', 'Translate'), ('Cloze', 'Fill in the blank'),
                                           ('Formulas', 'Formulas'), ('Theories', 'Theories'), ('Rhyme', 'Rhyme'), ('Comprehension', 'Comprehension'),
                                           ('People', 'People'), ('Vocab_builder', 'Vocabulary builder'), ('Transcribe', 'Transcribe'),  ('Summarize', 'Summarize'),
                                           ('Turn2notes', 'Turn to notes'), ('Custom', 'Custom')], default='Definitions')
    generate_images = BooleanField('Generate_images')
    save_text = BooleanField('Save_text')
    languages = SelectField('Languages', choices=[("", "Choose a language"), ("English",  "English"), ("Arabic", "Arabic"), ("Bulgarian", "Bulgarian"), ("Chinese", "Chinese"), ("Croatian",  "Croatian"), 
                                                  ("Czech",  "Czech"), ("Dutch", "Dutch"), ("Dothraki",  "Dothraki"), ("Elvish", "Elvish"), ("English",  "English"), 
                                                  ("Estonian", "Estonian"), ("Farsi", "Farsi"), ("French",  "French"), ("German", "German"), ("Greek",  "Greek"),
                                                  ("Hebrew", "Hebrew"), ("Hindi", "Hindi"), ("Hungarian", "Hungarian"), ("Indonesian", "Indonesian"),
                                                  ("Italian", "Italian"), ("Japanese", "Japanese"), ("Korean", "Korean"), ("Klingon", "Klingon"),
                                                  ("Latvian", "Latvian"), ("Lithuanian", "Lithuanian"), ("Malay", "Malay"), ("Norwegian", "Norwegian"),
                                                  ("Polish", "Polish"), ("Portuguese", "Portuguese"), ("Romanian", "Romanian"), ("Russian",  "Russian"),
                                                  ("Spanish", "Spanish"), ("Serbian", "Serbian"), ("Swahili", "Swahili"), ("Swedish", "Swedish"),
                                                  ("Tagalog", "Tagalog"), ("Thai", "Thai"), ("Turkish", "Turkish"), ("Urdu",  "Urdu"),
                                                  ( "Vietnamese", "Vietnamese")], default = None)
    
    text_input = TextAreaField('Text Input', render_kw={"placeholder": "Paste your text here"})
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
    
class AccountForm(FlaskForm):
    first_name = StringField("First Name:")
    last_name = StringField("Last Name:")
    username = StringField("Username:")
    email = StringField("Email:")
    gender = SelectField("Gender:", choices=[('', 'Select your gender'), ('Female', 'Female'), ('Male', 'Male'), ('Other', 'Other'), ('Prefer not to say', 'Prefer not to say')])
    role = SelectField("Role:", choices=[('', 'Select your role'), ('school-administrator', 'School Administrator'), ('teacher', 'Teacher'), ('student', 'Student'), ('part-time-student', 'Part-Time Student'), ('lifelong-learner', 'Lifelong Learner'), ('parent-guardian', 'Parent/Guardian'), ('homeschooling-parent', 'Homeschooling Parent'), ('tutor', 'Tutor'), ('curriculum-developer', 'Curriculum Developer'), ('educational-researcher', 'Educational Researcher'), ('educational-consultant', 'Educational Consultant'), ('instructional-designer', 'Instructional Designer'), ('academic-advisor', 'Academic Advisor'), ('admissions-counselor', 'Admissions Counselor'), ('school-counselor', 'School Counselor'), ('librarian', 'Librarian'), ('it-administrator', 'IT Administrator'), ('education-technology-specialist', 'Education Technology Specialist'), ('education-policy-maker', 'Education Policy Maker'), ('education-advocate-activist', 'Education Advocate/Activist'), ('other', 'Other')])
    timezone = SelectField("Timezone:", choices=[(tz, tz) for tz in pytz.all_timezones]) # Don't forget to import pytz
    contacted_email = BooleanField("Agree to be contacted by email")
    subscribe = BooleanField("Sign up to our mailing list")

class DeleteAccountForm(FlaskForm):
    del_email = StringField('Email')
    del_submit = SubmitField('Delete account')

class UpdateProfilePicForm(FlaskForm):
    profile_pic = FileField('Profile Picture', validators=[FileAllowed(['jpg', 'jpeg', 'png'])])
    submit = SubmitField('Update Profile Picture')

class FeedbackForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    type_feedback = SelectField('Feedback Type', choices=[('', ''),('general', 'General Feedback'), ('bug', 'Bug Report'), ('feature', 'Feature Request')])
    message = TextAreaField('Message', validators=[DataRequired()])
    submit = SubmitField('Submit')

class UpdateFileNameForm(FlaskForm):
    new_name = StringField('New Name', [DataRequired()])
    file_id = IntegerField('File ID', [InputRequired()])

class SearchAndSortForm(FlaskForm):
    name = StringField('Name')
    search = StringField('Search')
    sort = SelectField('Sort', choices=[
        ('default', 'Default'),
        ('name_asc', 'Name Ascending'),
        ('name_desc', 'Name Descending'),
        ('type', 'Type'),
        ('date', 'Date')
    ])


class Share(FlaskForm):
    emails = StringField('Emails', validators=[DataRequired()])
    submit = SubmitField('Share')


class BuildTest(FlaskForm):
    name = StringField('Test Name', validators=[DataRequired()])
    due_date = DateField('Due Date')
    subject = StringField('Subject')
    topic = StringField('Topic')
    instructions = StringField('Instructions')
    description = StringField('Description')
    time_limit = StringField('Time Limit')
    shuffle = BooleanField('Shuffle')
    reveal_answers = BooleanField('Reveal Answers')
    reveal_results = BooleanField('Reveal Results')


class UpdateCardForm(FlaskForm):
    question = StringField('Question', validators=[DataRequired()])
    points = IntegerField('Points', validators=[DataRequired()])
    category = SelectField('Category', choices=[('mcq', 'Multiple Choice'), ('saq', 'Short Answer')], validators=[DataRequired()])
    answer = StringField('Answer', validators=[DataRequired()])
    boc_2 = StringField('Option 2')
    boc_3 = StringField('Option 3')
    boc_4 = StringField('Option 4')

class GroupForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(min=1, max=100)])
    description = TextAreaField('Description', validators=[DataRequired(), Length(min=1, max=500)])
    group_type = SelectField('Group Type', validators=[DataRequired()], choices=[
        ('', 'Select a group type'),
        ('school', 'School'),
        ('class', 'Class'),
        ('department', 'Department'),
        ('club', 'Club'),
        ('other', 'Other')
    ], default='')
    is_private = BooleanField('Is Private')
    submit = SubmitField('Create Group')

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

@app.before_request
def before_request():
    g.feedback_form = FeedbackForm()


@app.route("/", methods=["GET", "POST"])
def index():
    form = TryOut()
    terms = []
    if not current_user.is_authenticated:
        
        if form.validate_on_submit():
            print("form validated")
            text = form.select_text.data
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
            print(prompt_options)
            
            response = creator(text, prompt_options)
            terms = response[0]
            for item in terms:
                print(item['A'])
                print(item['B'])
            
            event_tracker(None, "tryout", json.dumps(prompt_options), json.dumps(terms))
            return render_template('index.html', form = form, terms = terms, option = prompt_options['main_opt'])
  
    return redirect(url_for("viewdecks")) 
  




@app.route("/tryout", methods=["GET", "POST"])
def tryout():
    form = TryOut()
    terms = []
    try:
        if form.validate_on_submit():
            print("form validated")
            text = form.select_text.data
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
            response = creator(text, prompt_options)
            terms = response[0]
            json_terms = []
            count = 0
            for item in terms:
                print(item)
            if prompt_options['main_opt'] == 'Mcq':
                for item in terms:
                    if count >= 8:
                        break
                    json_terms.append({'A': item['A'], 'B': item['B'], 'C': item['C'], 'D': item['D'], 'E': item['E']})
                    count += 1
            else:
                for item in terms:
                    if count >= 8:
                        break
                    json_terms.append({'A': item['A'], 'B': item['B']})
                    count += 1
            print(json_terms)
            
            event_tracker(None, "tryout", json.dumps(prompt_options), json.dumps(terms))
            return jsonify({'terms': json_terms, 'option': prompt_options['main_opt'], 'text': text})
    except Exception as e: 
        logging.error(f"Exception occurred in tryout(): {str(e)}")
        return jsonify({"error": "An error occurred while processing your request."}), 500
    
@app.route("/googleSignIn", methods=["POST"])
def googleSignIn():
    #Security validation
    form = TryOut()
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
            return redirect(url_for('viewdecks'))
        
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
    return render_template('index.html', title='Index', form = form)

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
        role = request.form.get('role')
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
                    timezone = timezone, subscription_start_date = datetime.utcnow(), role = role)
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
        return redirect(url_for('viewdecks'))
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
                return redirect(url_for('viewdecks'))
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


@app.route('/subscribe2', methods=['GET', 'POST'])
def subscribe2():
    data = request.json
    first_name = data['first-name']
    last_name = data['last-name']
    email = data['email']
    print(last_name)
    existing_subscriber = Subscriber.query.filter_by(email=email).first()
    print(existing_subscriber)
    if existing_subscriber and existing_subscriber != None:
        print("already subscribed")
        flash("You are already subscribed!")
        return jsonify({'status': 'failure', 'message': 'You are already subscribed!'})
    else:
        print(email)
        print("not subscribed, subscribing")
        subscriber = Subscriber(email=email, first_name=first_name, last_name=last_name, timestamp = datetime.utcnow())
        db.session.add(subscriber)
        db.session.commit()
        flash("Thanks for subscribing!")
        return jsonify({'status': 'success', 'message': 'Subscription successful!'})


@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    flash('You have been logged out!')
    return redirect(url_for('index'))




@app.route("/viewdecks", methods = ["GET", "POST"])
@login_required
def viewdecks():
    share_form = Share()

    user_settings = UserSettings.query.filter_by(user=current_user.id).first()
    if user_settings == None:
        print("user settings not found")
        user_settings = UserSettings(user=current_user.id)
        db.session.add(user_settings)
        db.session.commit()
    
    
   ## check if user has any pending tests
    tests = Test.query.filter(Test.taker.contains(current_user)).all()
    user = current_user
    email = current_user.email
    shared_decks = SharedDecks.query.filter(SharedDecks.receiver == current_user.id).all()


    decks = Deck.query.filter(Deck.user_id == current_user.id).all()
    if request.method == 'GET':
        sort_method = request.args.get('sort')
        search_query = request.args.get('search', '').strip()
        if sort_method:
            column, order = sort_method.split('_')
            order_by = getattr(getattr(Deck, column), order)() if column in ['name', 'category', 'time_created'] else None

            if order_by:
                decks = Deck.query.filter(Deck.user_id == current_user.id).order_by(order_by).all()
            elif column == "cards_due":
                decks = sorted(decks, key=lambda deck: deck.qty_cards_due(), reverse=order == 'desc')

    if search_query:
        decks = Deck.query.filter(Deck.name.ilike(f'%{search_query}%')).all()


    return render_template('viewdecks.html', decks=decks, shared_decks = shared_decks, tests=tests, user = user, settings = user_settings, share_form = share_form)


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
    form = AccountForm()
    user = User.query.filter_by(id=current_user.id).first()
    subscriber = Subscriber.query.filter_by(email=user.email).first()
    form_del = DeleteAccountForm()

    if form.validate_on_submit():
        user.first_name = form.first_name.data
        user.last_name = form.last_name.data
        user.username = form.username.data
        user.gender = form.gender.data
        user.role = form.role.data
        user.timezone = form.timezone.data
        user.contacted_email = form.contacted_email.data

        if form.subscribe.data:
            if not subscriber:
                subscriber = Subscriber(email=user.email, first_name=user.first_name, last_name=user.last_name, timestamp=datetime.utcnow())
                db.session.add(subscriber)
                db.session.commit()
                flash("You have been subscribed to our mailing list")
        else:
            if subscriber:
                db.session.delete(subscriber)
                db.session.commit()
                flash("You have been unsubscribed from our mailing list")

        db.session.commit
        flash("Your account has been updated")
    return render_template("account.html", title="Account", form_del = form_del, form = form, user = user, subscriber = subscriber)

@app.route('/update_profile_pic', methods=['POST'])
def update_profile_pic():
    form = UpdateProfilePicForm()

    if form.validate_on_submit():
        profile_picture = form.profile_pic.data

        if profile_picture:
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
        return jsonify({"status": "success", "message": "Card deleted"})
    else:
        return jsonify({"status": "error", "message": "Card not found"})
    ##cards = deck.cards
 ##   return render_template('carousel.html', title="Deck", deck=deck, cards=cards)



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
@login_required
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
@login_required
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


@app.route("/update_study_data/<int:deck_id>", methods = ["POST", "GET"])
@login_required
def update_study_data(deck_id):
    deck0 = Deck.query.get(deck_id)
    total_answered = deck0.total_answered()
    percentage = ((deck0.correct_incorrect()[0] / total_answered) * 100) if total_answered > 0 else 0
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
    return render_template('study_deck_all.html', title='Study all decks', decks_json=decks_json, decks=decks, settings = user_settings)

@app.route("/increment/<card_id>", methods = ["POST", "GET"])
@login_required
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
@login_required
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
@login_required
def casual_mode(deck_id):
    return render_template("casualmode.html", title="Casual Mode", deck=deck_id)   

@app.route('/generate_img/<int:deck_id>', methods=['GET', 'POST'])
@login_required
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
    
    
def create_parent_child_relationship(parent_deck_id, child_deck_id):
    new_relationship = insert(deck_relationships).values(parent_deck=parent_deck_id, child_deck=child_deck_id)
    session.execute(new_relationship)
    session.commit()



@app.route("/carousel/<int:deck_id>", methods = ["GET", "POST"])
@login_required
def carousel(deck_id):
    deck = Deck.query.filter_by(id=deck_id, user_id=current_user.id).first()

    form = DeckOrg(obj=deck)
    cards = Card.query.filter(Card.decks_backref.any(id=deck_id)).order_by(Card.id.desc()).all()
    if(current_user.id != deck.user_id):
         return apology('Deck not assigned to user', 403)
    if form.validate_on_submit():
        if form.term.data:
            term = form.term.data
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
        elif form.new_term.data:
            entry = Card(term=form.new_term.data, content=form.new_content.data, boc_2=form.new_boc_2.data,
                boc_3=form.new_boc_3.data, boc_4=form.new_boc_4.data, category=form.new_category.data,
                time_created=datetime.utcnow())
            deck.cards.append(entry)
            db.session.commit()
        elif form.new_deck_name.data:
            deck.name = form.new_deck_name.data
            deck.description = form.new_deck_description.data
            deck.subject = form.new_deck_subject.data
            deck.topic = form.new_deck_topic.data
            parent = form.deck_list.data
            public = form.is_public.data
            if public:
                deck.public = True
            else:
                deck.public = False

            if parent:
                db.session.execute(deck_relationships.insert().values(parent_deck=parent.id, child_deck=deck.id))

            db.session.commit()
    return render_template("carousel.html", title="Carousel", deck=deck, cards=cards, form=form)



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
            user.expiration = datetime.utcnow()
            user.account_expiration_reason = "Deleted"
            db.session.commit()
            flash("We're sorry to see you go. Your account is now inactive and will be permanently deleted within 48 hours.")
            return redirect(url_for('logout'))

    return render_template('delete_account.html', form_del=form)

@app.route("/import_public_deck/<int:deck_id>", methods = ["GET", "POST"])
@login_required
def import_public_deck(deck_id):
    print("entered public decks")
    deck = Deck.query.filter_by(id=deck_id, public=True).first()
    if deck is None:
        return apology("Deck not found", 404)
    else:
        shared_deck = SharedDecks(name="Copy of " + deck.name, description=deck.description, time_created=datetime.utcnow(), receiver=current_user.id)
        db.session.add(shared_deck)
        for card in deck.cards:
            new_card = Card(term=card.term, content=card.content, boc_2=card.boc_2, boc_3=card.boc_3, boc_4=card.boc_4, img=card.img, sound=card.sound, subject=card.subject, topic=card.topic, category=card.category, prompt_option=card.prompt_option, prompt_option2=card.prompt_option2, trans_option=card.trans_option, len_option=card.len_option, qmin_option=card.qmin_option, qmax_option=card.qmax_option, diff_lvl=card.diff_lvl)
            shared_deck.cards.append(new_card)
        db.session.commit()
        print(shared_deck)
    return jsonify({"success": True})

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
                return redirect(url_for('upgrade'))
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
                flash('Your cards are being created, once finished they will appear in your decks.  In the meantime feel free to create more decks or start studying!')
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
        deck_name = form.name.data or "".join(main_opt + " "+ "deck" +" "+ time)
        deck_description = form.description.data or "".join(main_opt + " " + "deck")
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
    os.remove(file_loc)
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
    ##files = DeckFiles.query.filter(DeckFiles.decks.any(id=deck_id)).order_by(DeckFiles.file_name.desc()).all()
    if request.method == 'GET':
        print("entered get request")
        search_query = None
        sort_method = search_and_sort_form.sort.data
        search_query = request.args.get('search', '')

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
                search_query = search_query.strip()
                files = DeckFiles.query.filter(DeckFiles.decks.any(id=deck_id)).filter(DeckFiles.file_name.contains(search_query)).all()
        return render_template("sea_dox.html", title="Sea Dox", files=files, deck = deck, form = form, search_form = search_and_sort_form)
    if form.validate():
        file_id = form.file_id.data
        new_name = form.new_name.data
        file = DeckFiles.query.get_or_404(file_id)

        if new_name != '':
            file.file_name = new_name
            db.session.commit()
        return render_template("sea_dox.html", title="Sea Dox", files=files, deck = deck, form = form, search_form = search_and_sort_form)
    return render_template("sea_dox.html", title="Sea Dox", files=files, deck = deck, form = form, search_form = search_and_sort_form)

@app.route("/source_file/<int:file_id>", methods=["GET", "POST"])
@login_required
def source_file(file_id):
    ## GET FILE
    file = DeckFiles.query.get_or_404(file_id)
    return render_template("source_file.html", title="Source File", file=file)

@app.route("/download_source/<int:file_id>", methods=["GET", "POST"])
@login_required
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
@login_required
def delete_file(deck_id, file_id):
    print("entered delete file")
    event_tracker(current_user.id, "delete_file", file_id)
    file = DeckFiles.query.get_or_404(file_id)
    deck = Deck.query.get_or_404(deck_id)
    db.session.delete(file)
    db.session.commit()
    return redirect(("/sea_dox/{deck}").format(deck=deck.id)) 

class Share(FlaskForm):
    emails = StringField('Emails', validators=[DataRequired()])
    submit = SubmitField('Share')
@app.route("/share_deck/<int:deck_id>/", methods=["GET", "POST"])
@login_required
def share_deck(deck_id):
    share_form = Share()
    sender_id = current_user.id
    deck_to_copy = Deck.query.get_or_404(deck_id)
    event_tracker(current_user.id, "share_deck", deck_id)

    if share_form.validate_on_submit():
        users_emails = share_form.emails.data.split(",")

        for email in users_emails:
            email = email.strip()
            user = User.query.filter_by(email=email).first()

            if user:
                shared_deck = SharedDecks(name="Copy of " + deck_to_copy.name, description=deck_to_copy.description, sender=sender_id, time_created=datetime.utcnow(), receiver=user.id)
                db.session.add(shared_deck)

                for card in deck_to_copy.cards:
                    new_card = Card(term=card.term, content=card.content, boc_2=card.boc_2, boc_3=card.boc_3, boc_4=card.boc_4, img=card.img, sound=card.sound, subject=card.subject, topic=card.topic, category=card.category, prompt_option=card.prompt_option, prompt_option2=card.prompt_option2, trans_option=card.trans_option, len_option=card.len_option, qmin_option=card.qmin_option, qmax_option=card.qmax_option, diff_lvl=card.diff_lvl)
                    shared_deck.cards.append(new_card)

                db.session.commit()

        return jsonify('success', 'Deck shared successfully')

    else:
        return jsonify('error', 'Deck not shared')
    

@app.route("/approve_shared/<int:deck_id>/", methods=["GET", "POST"])
@login_required
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
@login_required
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
    form = FeedbackForm()
    if form.validate_on_submit():
        entry = Feedback(name=form.name.data, email=form.email.data, message=form.message.data, type_feedback=form.type_feedback.data)
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
    event_tracker(current_user.id, "build_test", deck_id)
    deck = Deck.query.get_or_404(deck_id)
    creator = current_user
    if request.method == "POST":
        test_questions = request.form.getlist('selected_cards[]')
        
        name = deck.name + " Test" + " " + datetime.now().strftime("%Y-%m-%d %H:%M")
        new_test = Test(creator=current_user.id)
        db.session.add(new_test)
        new_test.name = name
        print(new_test.name)
        for question in test_questions:
            print("Entering question in test questions")
            print(question)
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
    update_card_form = UpdateCardForm(request.form)
    form = BuildTest()
    event_tracker(current_user.id, "assign_test", test_id)
    test = Test.query.get_or_404(test_id)
    print(request.form)
    if request.method == 'POST' and 'name' in request.form:
        print("entered post request3")
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
    return render_template('assign_test.html', title='Assign test', test=test, form = form, update_card_form = update_card_form)
    
@app.route('/update_card', methods=['POST'])
@login_required
def update_card():
    print("entered update card")
    data = request.get_json()
    form = UpdateCardForm(data=data)
    print(data)
    
    question_id = data['question-id']
    print(question_id)
    question = Question.query.filter_by(id = question_id).first_or_404()
    print(question)
    print(data['question'])
    try:
        question.question = data['question']
        question.content = data['answer']
        question.points = data['points']
        db.session.flush()
        db.session.commit()
        return jsonify(success=True)
    except Exception as e:
        print("Error while updating the question:", e)
        return jsonify(success=False, error=str(e))



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
@login_required
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
@login_required
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
    return render_template('import_deck.html')


@app.route('/import_anki', methods=['POST'])
@login_required
def import_anki():
    print("entered import_anki")
    data = request.json
    for card in data:
        deck_name = card['deckName']
        print(deck_name)
        card_front = card['fields']['Front']['value']
        print(card_front)
        card_back = card['fields']['Back']['value']
        print(card_back)
        deck = Deck.query.filter_by(name=deck_name, user_id=current_user.id).first()
        if not deck:
            deck = Deck(name=deck_name, description="anki", user_id=current_user.id)
            db.session.add(deck)
            db.session.commit()

        print("creating new card")
        card_O = Card(term=card_front, content=card_back, srs_interval=card['interval']*1440, category="anki")
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


@app.route('/upgrade', methods=['GET', 'POST'])
def upgrade():
    return render_template('upgrade.html')

@app.route("/export_deck/<int:deck_id>/", methods=["GET", "POST"])
@login_required
def export_deck(deck_id):
    try:
        request_anki_permission()
    except:
        print("anki permission NOT GRANTED")
        return apology("Anki did not grant permission")
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


#### JAVASCRIPT ANKI CONNECT
@app.route('/get_deck_data/<int:deck_id>', methods=['GET'])
@login_required
def get_deck_data(deck_id):
    print("entered get_deck_data")
    deck_name = Deck.query.get_or_404(deck_id).name
    cards = Deck.query.get_or_404(deck_id).cards
    print(deck_name, cards)
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


@app.route("/query", methods=["POST"])
def query():
    progress = 0
    print("entered query")
    
    # The id of the queried request comes in with a new request
    # sent from the frontend JS code
    job_id = request.form["id"]
    # Now we can ask database about the state of that request
    data = Job.query.filter_by(slug=job_id).first()
    # And return a response containing the state and the result
    print(data)
    num_completed = Job.query.filter_by(slug=job_id, state="completed").count()
    num_total = Job.query.filter_by(slug=job_id).count()
    if num_total != 0:
        progress = int(num_completed/num_total*100)
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
    session.pop('slug', None)

    return jsonify("success")
 
@app.route("/latest_deck", methods=["POST", "GET"])
@login_required
def latest_deck():
    if current_user.is_authenticated:
        deck = Deck.query.filter_by(user_id=current_user.id).order_by(Deck.id.desc()).first()

        if deck is not None:
            return redirect('/carousel/{deck_id}'.format(deck_id=deck.id))
        else:
            # Handle the case when the user has no decks, e.g., show an error message or redirect to a create deck page
            return "No decks found for this user. Please create a deck."
    else:
        # Handle the case when the user is not authenticated, e.g., redirect to login page or show an error message
        return "User is not authenticated. Please log in to continue."

 
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
        new_record.operation_count =  n
        new_record.remaining_count = usage_record.remaining_count - n
    db.session.add(new_record)

def check_subscription_plan(user):
    subscription_plan = SubscriptionPlan.query.filter_by(id=user.subscription_plan).first()
    return subscription_plan


####################  MORE INFO ABOUT CARDS ################################################

@app.route("/explain_further/<int:card_id>/", methods=['GET', 'POST'])
@login_required
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
@login_required
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
@login_required
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

@app.route("/public_cards/<int:deck_id>/", methods=['GET', 'POST'])
@login_required
def public_cards(deck_id):
    deck = Deck.query.filter_by(id=deck_id).first()
    if deck.public == False:
        return apology("Sorry, this deck is not public")
    cards = Card.query.filter(Card.decks_backref.any(id=deck_id)).order_by(Card.term.desc()).all()
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




####################### GROUPS #####################################################
####################################################################################
####################################################################################

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
    return render_template('my_groups.html', invitations = invitations, groups=user_groups, created_groups = created_groups,
                            group_invites = group_invites, user_roles = all_groups_member_roles,
                            form = group_form)

@app.route('/create_group', methods=['POST'])
@login_required
def create_group():
    print("create group")
    form = GroupForm(request.form)
    if form.validate():
        print("form validated")
        name = form.name.data
        description = form.description.data
        group_type = form.group_type.data
        private = form.is_private.data
        user_id = current_user.id
        
        new_group = Group(name=name, description=description, group_type=group_type, is_private=private, creator_id=user_id)
        db.session.add(new_group)
        new_group.users.append(current_user)
        db.session.commit()
        
        update_member_permissions(new_group.id, user_id, "write")
        print("where")
        db.session.commit()
        success_response = jsonify({'message': 'Group created successfully'}), 201
        
        print("Success response:", success_response)  # Log the success response
        return success_response
    else:
        print("form not validated")
        print("Form errors:", form.errors)  # Log the form errors
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
            print("user email", email)
            email = unquote(email).strip()
            user = User.query.filter_by(email=email).first()
            already_invited = GroupInvite().query.filter_by(user_id=user.id, group_id=group_id).first()
            if user is None:
                not_users.append(email)
            elif already_invited is None:
                if user not in group.users:
                    new_invite = GroupInvite(name = group.name, invited_by_email=current_user.email, invited_by_id=current_user.id, user_id=user.id, group_id=group_id, created_at = datetime.utcnow())
                    db.session.add(new_invite)
                    db.session.commit()
                if len(not_users) > 0:
                    flash('The following users are not registered: ' + str(not_users), 'warning')
        return jsonify('success', 'User invited successfully')
    else:
        user = User.query.filter_by(email=user_email).first()
        if user is None:
            not_users.append(user_email)
        else:
            new_invite = GroupInvite(name = group.name, invited_by_email=current_user.email, invited_by_id=current_user.id, user_id=user.id, group_id=group_id, created_at = datetime.utcnow())
            db.session.add(new_invite)
            db.session.commit()
        if len(not_users) > 0:
            flash('The following users are not registered: ' + str(not_users), 'warning')
        return jsonify('success', 'User invited successfully')


@app.route("/approve_group/<int:group_id>/", methods=["GET", "POST"])
@login_required
def approve_group(group_id):
    group_invite = GroupInvite.query.filter_by(id=group_id, user_id=current_user.id).first()
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
    print(group_id)
    group_invite = GroupInvite.query.filter_by(id=group_id, user_id=current_user.id).first()
    print(group_invite)
    if group_invite:
        db.session.delete(group_invite)
        db.session.commit()
        return jsonify('success', 'User rejected successfully')
    else:
        return jsonify('error', 'User not invited to group')


def get_group_member_roles(group_id):
    results = db.session.query(User.id, User.username, User.email, user_group_association.c.role).join(user_group_association).filter(
        user_group_association.c.group_id == group_id
    ).all()
    group_member_roles = {}
    for result in results:
        username_or_email = result.username if result.username is not None else result.email
        group_member_roles[result.id] = {
            'username': username_or_email,
            'role': result.role
        }
    return group_member_roles

def get_all_groups_member_roles(user_id):
    user_groups = db.session.query(Group).join(user_group_association).filter(
        user_group_association.c.user_id == user_id
    ).all()
    all_groups_member_roles = {}
    for group in user_groups:
        group_member_roles = get_group_member_roles(group.id)
        all_groups_member_roles[group.id] = group_member_roles

    return all_groups_member_roles



def get_group_member_permissions(group_id):
    results = db.session.query(User.id, User.username, User.email, user_group_association.c.permissions).join(user_group_association).filter(
        user_group_association.c.group_id == group_id
    ).all()

    group_member_permissions = {}
    for result in results:
        username_or_email = result.username if result.username is not None else result.email
        group_member_permissions[result.id] = {
            'username': username_or_email,
            'permissions': result.permissions
        }
    return group_member_permissions

def get_all_groups_member_permissions(user_id):
    user_groups = db.session.query(Group).join(user_group_association).filter(
        user_group_association.c.user_id == user_id
    ).all()
    all_groups_member_permissions = {}
    for group in user_groups:
        group_member_permissions = get_group_member_permissions(group.id)
        all_groups_member_permissions[group.id] = group_member_permissions
    return all_groups_member_permissions


def get_invited_users_info(user_id):
    # Get all the groups the user is a part of
    user_groups_query = db.session.query(Group.id).join(user_group_association).filter(
        user_group_association.c.user_id == user_id
    ).all()
    # Extract the group IDs from the Row objects
    user_groups = [row[0] for row in user_groups_query]
    # Get the user IDs from the invite_group table for those groups
    invited_users = db.session.query(User.id, User.username, User.email).join(GroupInvite, GroupInvite.user_id == User.id).filter(
        GroupInvite.group_id.in_(user_groups)
    ).all()
    return invited_users


@app.route("/group/<int:group_id>/", methods=["GET", "POST"])
@login_required
def group(group_id):
    mydecks = Deck.query.filter_by(user_id = current_user.id).all()
    group = Group.query.get_or_404(group_id)
    ## get group members and their roles
    group_member_roles = get_group_member_roles(group_id)
    ## get invited group members
    invited_users = get_invited_users_info(current_user.id)
    decks = Deck.query.filter_by(group_id=group_id).all()
    permissions = get_group_member_permissions(group_id)
    return render_template('group.html', mydecks = mydecks, group=group, group_member_roles=group_member_roles, invited_users=invited_users, decks = decks, permissions = permissions)


@app.route('/group/<int:group_id>/update_member_permissions', methods=['POST'])
@login_required
def update_member_permissions(group_id, user_id = None, permission = None):
    print("entered member permissions update")
    if user_id:
        print("user id is", user_id)
        target_user_id = user_id
    else:
        data = request.json

        target_user_id = int(data['target_user_id'])
    if permission:
        print("permission is", permission)
        new_permissions = permission
    else:
        new_permissions = data['new_permissions']
    # Check if the current user is the creator of the group
    group = Group.query.get(group_id)
    print("group is", group)
    if group.creator_id == user_id:
        # Update the target user's permissions
        db.session.query(user_group_association).filter(
            user_group_association.c.group_id == group_id,
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
    print(response)
    return jsonify(response)

@app.route('/search_public_decks', methods=['POST'])
@login_required
def search_public_decks():
    data = request.json
    search_term = data['search']
    decks = Deck.query.filter(Deck.public == True, Deck.name.contains(search_term)).all()
    return jsonify([deck.serialize() for deck in decks])

@app.route('/add_deck_to_group', methods=['POST'])
@login_required
def add_deck_to_group():
    data = request.json
    group_id = data['group_id']
    if check_group_write_permission(group_id) == False:
        return jsonify({"status": "error", "message": "You do not have permission to add decks to this group"})
    else:
        deck_id = data['deck_id']
        group = Group.query.get(group_id)
        existing_deck = Deck.query.get(deck_id)
        new_deck = Deck(user_id = current_user.id, name=existing_deck.name, description=existing_deck.description, group_id = group_id, time_created=datetime.utcnow())
        db.session.add(new_deck)
        for card in existing_deck.cards:
            new_card = Card(term=card.term, content=card.content, boc_2=card.boc_2, boc_3=card.boc_3, boc_4=card.boc_4, img=card.img, sound=card.sound, subject=card.subject, topic=card.topic, category=card.category, prompt_option=card.prompt_option, prompt_option2=card.prompt_option2, trans_option=card.trans_option, len_option=card.len_option, qmin_option=card.qmin_option, qmax_option=card.qmax_option, diff_lvl=card.diff_lvl)
            new_deck.cards.append(new_card)
        db.session.commit()
        return jsonify({"status": "success"})

def check_group_write_permission(group_id):
    user_id = current_user.id
    association = db.session.query(user_group_association).filter_by(user_id=user_id, group_id=group_id).first()
    if association and association.permissions and 'write' in association.permissions:
        return True
    else:
        print("no permission to edit")
        return False

@app.route("/delete_group/<int:group_id>/", methods=["GET", "POST"])
@login_required
def delete_group(group_id):
    group = Group.query.get(group_id)
    if group.creator_id == current_user.id:
        db.session.delete(group)
        db.session.commit()
        return redirect(url_for('my_groups'))
    else:
        return jsonify({"message": "You do not have permission to delete this group", "status": "error"})


@app.route("/import_from_group/<int:deck_id>/<int:group_id>", methods=["GET", "POST"])
@login_required
def import_from_group(deck_id, group_id):
    group = Group.query.get(group_id)
    existing_deck = Deck.query.get(deck_id)
    group = Group.query.filter_by(id=group_id).first()
    user_ids = [user.id for user in group.users]
    if current_user.id in user_ids:
        new_deck = Deck(user_id = current_user.id, name=existing_deck.name, description=existing_deck.description, group_id = group_id, time_created=datetime.utcnow())
        for card in existing_deck.cards:
            new_card = Card(term=card.term, content=card.content, boc_2=card.boc_2, boc_3=card.boc_3, boc_4=card.boc_4, img=card.img, sound=card.sound, subject=card.subject, topic=card.topic, category=card.category, prompt_option=card.prompt_option, prompt_option2=card.prompt_option2, trans_option=card.trans_option, len_option=card.len_option, qmin_option=card.qmin_option, qmax_option=card.qmax_option, diff_lvl=card.diff_lvl)
            new_deck.cards.append(new_card)
        db.session.add(new_deck)
        return jsonify({"message": "Deck imported successfully", "status": "success"})
    else:
        return jsonify({"message": "You do not have permission to import from this group", "status": "error"})

@app.route("/remove_user_group/<int:group_id>/<int:user_id>", methods=["GET", "POST"])
@login_required
def remove_user_group(group_id, user_id):
    group = Group.query.get(group_id)
    if group.creator_id == current_user.id:
        association = db.session.query(user_group_association).filter(
            and_(user_group_association.c.user_id == user_id, user_group_association.c.group_id == group_id)
        ).first()
        if association:
            db.session.execute(
                user_group_association.delete().where(
                    and_(user_group_association.c.user_id == user_id, user_group_association.c.group_id == group_id)
                )
            )
            db.session.commit()
        return jsonify({"message": "User removed successfully", "status": "success"})
    else:
        return jsonify({"message": "You do not have permission to remove users from this group", "status": "error"})
###################### TO BE REORGANIZED ###############################################################################################


def split_string(string):
    items = string.split("&-&-&")
    return items
################## CURRENTLY UNUSED ###############################################################################################

@app.route("/change_password", methods=["GET", "POST"])
@login_required
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
  ## OBSOLETE CODE BELOW ###############################################################################################  
############################################################################################################    





if __name__ == "__main__":
    app.run(debug=False)
else:
    # For Alembic
    from models import db
    db.init_app(app)