import openai 
import os
from bs4 import BeautifulSoup
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import or_, and_, insert
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
from urllib.parse import unquote
from helpers import remove_punctuation, apology
from anki import request_anki_permission, anki_import_all, anki_import_deck, anki_create_deck, anki_create_card, find_notes, check_anki_connect
from flask import abort
from celery import Celery
from beta import BetaKeys
from config import UPLOAD_FOLDER, SECRET_KEY, DEBUG, BROKER, SQLALCHEMY_DATABASE_URI, MAX_CONTENT, SQLALCHEMY_TRACK_MODIFICATIONS, ALLOWED_EXTENSIONS
from models import db, Job, TestResult, QuestionResult, Question, Test, Feedback, ResponseData, DeckFiles, Subscriber, Deck, SharedDecks, Card
from models import StripeEvents, GroupInvite, Group, user_group_association, UsageRecord, SubscriptionPlan, User, cards, source_files, cards_shared, questions, distribution, UserSettings, deck_relationships
import logging.config
from events import event_tracker
from flask_talisman import Talisman
from logging.config import dictConfig
from logging_config import LOGGING_CONFIG
from Crypto.Cipher import AES
from bleach import clean
from json import JSONEncoder
from flask_wtf.csrf import generate_csrf
from threading import Thread



class Unsubscribe(FlaskForm):
    email = StringField(validators=[InputRequired(), Length(min=5, max=100)], render_kw={"placeholder": "Email"})
    newsletter = BooleanField('Newsletter')
    contacted = BooleanField('Contacted')
    submit = SubmitField('Unsubscribe')


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
    term = TextAreaField('Term', render_kw={"placeholder": "Term"})
    content = TextAreaField('Content', render_kw={"placeholder": "Content"})
    boc_2 = TextAreaField('boc_2')
    boc_3 = TextAreaField('boc_3')
    boc_4 = TextAreaField('boc_4')
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
    new_category = SelectField('Category', choices=[('Mix', 'Mix'), ('Definitions', 'Definitions'), ('Mcq', 'Multiple choice'), ('Translate', 'Translate'), ('Cloze', 'Fill in the blank'),
                                           ('Formulas', 'Formulas'), ('Theories', 'Theories'), ('Rhyme', 'Rhyme'), ('Comprehension', 'Comprehension'),
                                           ('People', 'People'), ('Vocab_builder', 'Vocabulary builder'), ('Transcribe', 'Transcribe'),  ('Summarize', 'Summarize'),
                                           ('Turn2notes', 'Turn to notes'), ('Custom', 'Custom')], default='Mix')
    edit_deck = SubmitField("Edit deck", render_kw={"id": "edit-deck"})

class UpdateCardForm(FlaskForm):
    question = TextAreaField('Question', validators=[DataRequired()])
    points = IntegerField('Points', validators=[DataRequired()])
    category = SelectField('Category', choices=[('Definitions', 'Definitions'), ('Mcq', 'Multiple choice'), ('Translate', 'Translate'), ('Cloze', 'Fill in the blank'),
                                           ('Formulas', 'Formulas'), ('Theories', 'Theories'), ('Rhyme', 'Rhyme'), ('Comprehension', 'Comprehension'),
                                           ('People', 'People'), ('Vocab_builder', 'Vocabulary builder'), ('Transcribe', 'Transcribe'),  ('Summarize', 'Summarize'),
                                           ('Turn2notes', 'Turn to notes'), ('Custom', 'Custom')], default='Definitions')
    answer = TextAreaField('Answer', validators=[DataRequired()])
    boc_2 = TextAreaField('Option 2')
    boc_3 = TextAreaField('Option 3')
    boc_4 = TextAreaField('Option 4')

        
class UploadFileForm(FlaskForm):
    file = FileField("File")
    name = StringField("Deck name", render_kw={"placeholder": "Name your deck"})
    description = StringField("Description", render_kw={"placeholder": "Describe your deck"})
    submit = SubmitField("Generate", render_kw={"id": "extract-submit"})
    deck_list = QuerySelectField("Choose a deck", query_factory=lambda: Deck.query.filter(Deck.user_id == current_user.id), allow_blank=True, get_label='name', render_kw={"placeholder": "Choose an existing deck"})
    prompt = RadioField('Prompt', choices=[('Mix', 'Mix'), ('Definitions', 'Definitions'), ('Mcq', 'Multiple choice'), ('Cloze', 'Fill in the blank'), ('Translate', 'Translate'), 
                                           ('Formulas', 'Formulas'), ('Theories', 'Theories'), ('Rhyme', 'Rhyme'), ('Comprehension', 'Comprehension'),
                                           ('People', 'People'), ('Vocab_builder', 'Vocabulary builder'), ('Explain', 'Explain'), ('Discuss', 'Discuss'), ('Transcribe', 'Transcribe'),  ('Summarize', 'Summarize'),
                                           ('Turn2notes', 'Turn to notes'), ('Custom', 'Custom')], default='Mix')
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
    length = SelectField('Length', choices=[('', ''), ('long', 'Detailed'), ('short', 'Brief')], default = None,  render_kw={"placeholder": ""})
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
    timezone = SelectField(
    "Timezone:",
    choices=[('', 'Select a timezone')] + [(tz, tz) for tz in pytz.all_timezones],
    validate_choice=False)
    contacted_email = BooleanField("Enable notifications")
    subscribe = BooleanField("Sign up to our mailing list")

class DeleteAccountForm(FlaskForm):
    del_email = StringField('Email')
    reason = SelectField('Reason for leaving', choices=[('', ''),
     ('too-expensive', 'Too expensive'), ('not-enough-features', 'Not enough features'),
       ('too-complicated', 'Too complicated'),
         ('not-enough-content', 'Not enough content'), 
         ('bad-content', "The content didn't suit my needs"),
            ('other', 'Other')])
    other_reason = StringField('Reason:') # Shown if 'other' is selected
    more = StringField('Can you tell us more?')
    del_submit = SubmitField('Delete account')

class UpdateProfilePicForm(FlaskForm):
    profile_pic = FileField('Profile Picture', validators=[FileAllowed(['jpg', 'jpeg', 'png']), FileSize(max_size=1 * 1024 * 1024, message='File size must be less than 1 MB.')])
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
