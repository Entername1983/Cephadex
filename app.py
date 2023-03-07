import openai 
import os
from bs4 import BeautifulSoup
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from flask import Flask, flash, redirect, render_template, request, session, url_for, Response, send_file, jsonify
from flask_session import Session
from tempfile import mkdtemp
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
from extractors import regenerate_def, add_period, extract_from_wiki, extract_from_youtube, text_extractor, create_pdf, check_comma_list, get_video_id, text_extractor
from google.oauth2 import id_token
from google.auth.transport import requests
import sys
from sqlalchemy.sql import func
import logging
import logging.handlers
import json
from datetime import datetime, timedelta
from flask_migrate import Migrate
import urllib.parse
from urllib.parse import unquote

openai.api_key = os.environ.get("OPENAI_API_KEY")

# Configure application
app = Flask(__name__)

bcrypt = Bcrypt(app)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max limi
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database1.db'
app.config['SECRET_KEY'] = 'whynot'
app.config['UPLOAD_FOLDER'] = 'static\\files'

werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.INFO)


ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx', 'pptx'}

db = SQLAlchemy(app)
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"



login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create database

# relational database cards & decks
cards = db.Table("cards", 
                 db.Column("card_id", db.Integer, db.ForeignKey("card.id")), 
                 db.Column("deck_id", db.Integer, db.ForeignKey("deck.id")),
                 )

source_files = db.Table("source_files",
                        db.Column("deck_file_id", db.Integer, db.ForeignKey("deck_files.id")), 
                        db.Column("deck_id", db.Integer, db.ForeignKey("deck.id")),  # 
                        )

cards_shared = db.Table("cards_shared", 
                 db.Column("card_id", db.Integer, db.ForeignKey("card.id")), 
                 db.Column("shared_decks_id", db.Integer, db.ForeignKey("shared_decks.id")),
                 )
                      
## external auth + external type + external
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=True, unique=True)
    password = db.Column(db.String(80), nullable=True)
    email = db.Column(db.String(255), nullable=False)
    email_confirmed_at = db.Column(db.DateTime())
    first_name = db.Column(db.String(50), nullable=True)
    last_name = db.Column(db.String(50), nullable=True)
    decks = db.relationship("Deck", backref=db.backref("user", lazy="joined"), lazy="select")
    ## external auth + external type
    external_id = db.Column(db.String(255), nullable=True) 
    external_type = db.Column(db.String(255), nullable=True)
    
    time_created = db.Column(db.DateTime, default=datetime.utcnow)
    time_accessed= db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    account_type = db.Column(db.String(255), nullable=True, default="free")
    account_status = db.Column(db.String(255), nullable=True, default="active")
    account_expiration = db.Column(db.DateTime, nullable=True)
    account_expiration_reason = db.Column(db.String(255), nullable=True)
    gender = db.Column(db.String(255), nullable=True)
    pic = db.Column(db.String(255), nullable=True)
    contacted_email = db.Column(db.Boolean, default=False)
    dob = db.Column(db.DateTime, nullable=True)

    
    def member_since(self):
        return self.time_created.strftime('%b %Y')
    
    def quantity_decks(self):
        return len(self.decks)
    
    def quantity_cards(self):
        return sum([len(deck.cards) for deck in self.decks])
    
    def quantity_cards_mastered(self):
        counter = 0
        for deck in self.decks:
            for card in deck.cards:
                if card.box_id == 3:
                    counter += 1
        return counter

    def quantity_cards_learning(self):
        counter = 0
        for deck in self.decks:
            for card in deck.cards:
                if card.box_id != 3 and card.times_asked != 0:
                    counter += 1
        return counter
    
    def quantity_cards_new(self):
        counter = 0
        for deck in self.decks:
            for card in deck.cards:
                if card.times_asked == 0:
                    counter += 1
        return counter
        

#class GoogleUser(db.Model, UserMixin):
#    email = db.Column(db.String(255), nullable=False)
#    external_id = db.Column(db.String(64), nullable=False,  primary_key=True)
#    given_name = db.Column(db.String(50), nullable=False)
#    family_name = db.Column(db.String(50), nullable=False)
#    enabled = db.Column(db.Boolean, default=True)

class Card(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    term = db.Column(db.String(50), nullable=False) 
    # content == Back of card 1
    content = db.Column(db.String(255), nullable=False)
    ## used for MCQ wrong answers
    boc_2 = db.Column(db.String(255), nullable=True) 
    boc_3 = db.Column(db.String(255), nullable=True) 
    boc_4 = db.Column(db.String(255), nullable=True)
    formula = db.Column(db.String(255), nullable=True)
    img = db.Column(db.String(255), nullable=True) 
    sound = db.Column(db.String(255), nullable=True) 
    boc_id = db.Column(db.Float(10), nullable=True)
    box_id = db.Column(db.Float(10), nullable=True, default=0)
    interval = db.Column(db.Integer, default=1)
    time_updated = db.Column(db.DateTime, default=datetime.utcnow)
    times_asked = db.Column(db.Integer, default=0)
    times_correct = db.Column(db.Integer, default=0)
    times_correct_row = db.Column(db.Integer, default=0)
    create_method = db.Column(db.String(255), nullable=True)
    time_created = db.Column(db.DateTime, default=datetime.utcnow) 
    category = db.Column(db.String(255), nullable=True)
    edited = db.Column(db.Integer, default=0)
    diff_lvl = db.Column(db.Float(100), default=1)
    subject = db.Column(db.String(255), nullable=True)
    topic = db.Column(db.String(255), nullable=True)
    prompt_option = db.Column(db.String(255), nullable=True)
    prompt_option2 = db.Column(db.String(255), nullable=True)
    trans_option = db.Column(db.String(255), nullable=True)
    len_option = db.Column(db.String(255), nullable=True)
    qmin_option = db.Column(db.String(255), nullable=True)
    qmax_option = db.Column(db.String(255), nullable=True)
    
    # unused
    #data_1 = db.Column(db.float(100), nullable = True)
    #data_2 = db.Column(db.float(100), nullable = True)
    #data_3 = db.Column(db.float(100), nullable = True)
    #data_time = db.Column(db.Interval, nullable = True)
    ## consider including a field for explanation of answer
    ## how can we keep track of time studied deck?  
    
    def to_json(self):
        return {
            "id": self.id,
            "term": self.term,
            "content": self.content,               
        }
        
    def update_interval(self, value):
        self.interval = self.interval * value
        db.session.commit()
        
        
    def edit_card(self, term, content):
        self.term = term
        self.content = content
        db.session.commit()
    
    def delete_card(self):
        db.session.delete(self)
        db.session.commit()
        
    def regen_def(self):
        self.content = regenerate_def(self.term)
        db.session.commit()
    
    def copy_card(self, deck):
        new_card = Card(term=self.term, content=self.content)
        deck.cards.append(new_card)
        db.session.add(new_card)            
        db.session.commit()
        
    def increment(self):
        self.times_correct = self.times_correct + 1
        self.times_asked = self.times_asked + 1
        self.times_correct_row = self.times_correct_row + 1
        if self.times_correct_row > 3:
            self.box_id = self.box_id + 1
            if self.box_id > 3:
                self.box_id = 3
        if self.box_id == 0:
            self.interval = self.interval * 1.2    
        if self.box_id == 1:
            self.interval = self.interval * 2
        if self.box_id == 2:
            self.interval = self.interval * 5
        if self.box_id == 3:
            self.interval = self.interval * 10
        if self.interval > 525600:
            self.interval = 525600
        ## ensure that at minimum if someone answer 3 questions in a row correctly, they will be asked again in 24 hours
        if self.times_correct_row > 3:
            self.interval += 1440
        db.session.commit()
        
    def decrement(self):
        self.times_asked = self.times_asked + 1
        self.times_correct_row = 0
        if self.box_id == 1:
            self.interval = self.interval * 0.5
        if self.box_id == 2:
            self.interval - self.interval * 0.8
        if self.box_id == 3:
            self.interval - self.interval * 0.9
            
        if not self.box_id == 1 and self.interval < 5:
            self.interval = 5
            
        if self.box_id > 0:
            self.box_id = self.box_id-1; 
             
        db.session.commit()
    
    def reset_interval(self):
        self.interval = 10
        db.session.commit()
        
    def update_time(self):
        self.time_updated = datetime.utcnow()
        db.session.commit()
    
class SharedDecks(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(255), nullable=False) 
    sender = db.Column(db.Integer, db.ForeignKey('user.id'))
    receiver = db.Column(db.Integer, db.ForeignKey('user.id'))
    time_created = db.Column(db.DateTime, default=datetime.utcnow)
    creator = db.Column(db.Integer) 
    public = db.Column(db.Integer, default=0) 
    edited = db.Column(db.Integer, default=0)
    cards = db.relationship('Card', secondary=cards_shared, backref="decks", lazy="select")
    
    def delete(self):
        db.session.delete(self)
        db.session.commit()

    
class Deck(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(255), nullable=False) 
    ## make relational table instead of using user_id?
    user_id = db.Column(db.Integer, db.ForeignKey('user.id')) 
    cards = db.relationship('Card', secondary=cards, backref="decks_backref", lazy="select")
    deck_files = db.relationship('DeckFiles', secondary=source_files, backref="decks", lazy="select")
    time_created = db.Column(db.DateTime, default=datetime.utcnow)   
    time_updated = db.Column(db.DateTime, default=datetime.utcnow)
    creator = db.Column(db.Integer) 
    public = db.Column(db.Integer, default=0) 
    edited = db.Column(db.Integer, default=0)
    create_method = db.Column(db.String(255), nullable=True)
    category = db.Column(db.String(255), nullable=True)
    times_accessed = db.Column(db.Integer, default=0)
    access_date = db.Column(db.DateTime, default=datetime.utcnow)
    subject = db.Column(db.String(255), nullable=True)
    topic = db.Column(db.String(255), nullable=True)
    shared = db.Column(db.Boolean, default=False)
    accepted = db.Column(db.Boolean, default=False)
    sharer = db.Column(db.Integer) 
    share_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    def force_study(self):
        due_cards = []
        current_time = datetime.now()
        for card in self.cards:
            time_diff = (current_time - card.time_updated).total_seconds() / 60
            due_cards.append({
                'term': card.term,
                'content': card.content,
                'boc_2': card.boc_2,
                'boc_3': card.boc_3,
                'boc_4': card.boc_4,
                'category': card.category,
                'id': card.id,
                'img': card.img,
                'sound': card.sound,
                'time_remain': card.interval - time_diff,
            })
        due_cards.sort(key=lambda x: x['time_remain'])
        return jsonify(due_cards)
     
        
    def get_due_cards(self):
        due_cards = []
        current_time = datetime.now()
        for card in self.cards:
            time_diff = (current_time - card.time_updated).total_seconds() / 60
            if (time_diff + 1440)>= card.interval:
                due_cards.append({
                    'term': card.term,
                    'content': card.content,
                    'boc_2': card.boc_2,
                    'boc_3': card.boc_3,
                    'boc_4': card.boc_4,
                    'formula': card.formula,
                    'category': card.category,
                    'id': card.id,
                    'img': card.img,
                    'sound': card.sound,
                })
        if not due_cards:
            return jsonify({'info': 'No due cards found'}), 204
        return jsonify(due_cards)
    
    def cards_due(self):
        due_cards = 0
        current_time = datetime.now()
        for card in self.cards:
            time_diff = (current_time - card.time_updated).total_seconds() / 60
            if (time_diff + 1440) >= card.interval:
                due_cards = due_cards + 1
        return due_cards
    
    def qty_cards_due(self):
        current_time = datetime.now()
        qty = 0
        for card in self.cards:
            if card.time_updated == None:
                card.time_updated = current_time
            else:
                time_diff = (current_time - card.time_updated).total_seconds() / 60
                if time_diff >= card.interval:
                    qty = qty + 1
        return qty

    def check_cat(self):
        Mcq = 0
        Cloze = 0
        Definitions = 0
        Comprehension = 0
        Vocab_builder = 0
        Theories = 0
        Rhyme = 0
        Translate = 0
        counter = 0
        People = 0
        ## check if all cards have same category
        for card in self.cards:
            if card.category == "Mcq":
                Mcq += 1
            elif card.category == "Cloze":
                Cloze += 1
            elif card.category == "Definitions":
                Definitions += 1
            elif card.category == "Comprehension":
                Comprehension += 1
            elif card.category == "Vocab_builder":
                Vocab_builder += 1
            elif card.category == "Theories":
                Theories += 1
            elif card.category == "Rhyme":
                Rhyme += 1
            elif card.category == "Translate":
                Translate += 1
            elif card.category == "People":
                People += 1
        ## loop through each category and check if it is the highest count
        categories = {'Mcq': Mcq, 'Cloze': Cloze, 'Definitions': Definitions,
                  'Comprehension': Comprehension, 'Vocab_builder': Vocab_builder,
                  'Theories': Theories, 'Rhyme': Rhyme, 'Translate': Translate,
                  'People': People}
        max_category, max_count = max(categories.items(), key=lambda x: x[1])
        if max_count > len(self.cards) / 2:
            self.category = max_category
            db.session.commit()
            return max_category
        else:
            self.category = "Mixed"
            db.session.commit()
            return "Mixed"
        
    def to_json(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "user_id": self.user_id,
            "cards": [card.to_json() for card in self.cards]
        }
        
    def quantity_cards(self):
        return len(self.cards)
    
    def add_card(self, card):
        self.cards.append(card)            
        db.session.commit()
        
    def remove_card(self, card):
        self.cards.remove(card)            
        db.session.commit()
        
    def rename_deck(self, new_name):
        Deck.name = new_name
        db.session.commit()            
        
    def delete_deck(self):
        db.session.delete(self)            
        db.session.commit()
    
    def rename(self, new_name):
        self.name = new_name
        db.session.commit()            
        
        
    def copy_deck(self, new_deck_name):
        new_deck = Deck(name=self.name, description=self.description, user_id=self.user_id)  
        new_deck.name = new_deck_name                      
        db.session.add(new_deck)            
        db.session.commit()
        
    
    def assign_deck(self, user):
        pass
    
    def export_deck_csv(self):
        pass
    
    def import_deck_csv(self):
        pass
    
    
    
class Subscriber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), unique=True)
    last_name = db.Column(db.String(50), unique=True)
    email = db.Column(db.String(120), unique=True)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    def __repr__(self):
        return '<Newsletter {}>'.format(self.email)
    
    def subscribe(self):
        db.session.add(self)            	
        db.session.commit()
        
    def unsubscribe(self):
        db.session.delete(self)            	
        db.session.commit()
 
class DeckFiles(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    file_name = db.Column(db.String(100))
    file_path = db.Column(db.String(50))
    file_type = db.Column(db.String(500))	
    file_size = db.Column(db.String(50))
    text_string = db.Column(db.String())
    create_type = db.Column(db.String(50))
    time_created = db.Column(db.DateTime, default=datetime.utcnow)
    
       
class ResponseData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prompt = db.Column(db.String())	
    response = db.Column(db.String())
    content = db.Column(db.String())	
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    success = db.Column(db.Boolean)
          
class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    email = db.Column(db.String(120))
    message = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    type_feedback = db.Column(db.String(50))
    def __repr__(self):
        return '<Feedback {}>'.format(self.email)
    
    def send_feedback(self):
        db.session.add(self)            	
        db.session.commit()
        
    def delete_feedback(self):
        db.session.delete(self)            	
        db.session.commit() 
                 
#########################TEST TABLES#######################



          
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
class UploadFileForm(FlaskForm):
    file = FileField("File")
    name = StringField("Deck name", render_kw={"placeholder": "Name your deck"})
    description = StringField("Description", render_kw={"placeholder": "Describe your deck!"})
    submit = SubmitField("Generate", render_kw={"id": "extract-submit"})
    deck_list = QuerySelectField("Choose a deck", query_factory=lambda: Deck.query.filter(Deck.user_id == current_user.id), allow_blank=True, get_label='name', render_kw={"placeholder": "Choose an existing deck"})
    prompt = RadioField('Prompt', choices=[('Definitions', 'Definitions'), ('Translate', 'Translate'), ('Rhyme', 'Rhyme'), ('People', 'People'), ('Theories', 'Theories'), ('Cloze', 'Cloze'), ('Mcq', 'MCQ'), ('Comprehension', 'Comprehension'), ('Vocab_builder', 'Vocabulary builder'), ('Transcribe', 'Transcribe'), ('Formulas', 'Formulas')], default='Definitions')
    generate_images = BooleanField('Generate_images')
    languages = SelectField('Languages', choices=[("English",  "English"), ("Arabic", "Arabic"), ("Bulgarian", "Bulgarian"), ("Chinese", "Chinese"), ("Croatian",  "Croatian"), 
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
    qmin_option = StringField("Minimum number of items", render_kw={"placeholder": "Min. items per page"})
    qmax_option = StringField("Maximum number of items", render_kw={"placeholder": "Max. items per page"})
    subject = SelectField('Subject', choices=[("", 'Select subject'),('Art', 'Art'), ('Anatomy', 'Anatomy'), ('Astron', 'Astronomy'), ('Bus', 'Business'), 
                                              ('Bio', 'Biology'), ('Chem', 'Chemistry'), ('CS', 'Computer Science'), ('Econ', 'Economics'), 
                                              ('Eng', 'Engineering'), ('Film', 'Film'), ('Geo', 'Geography'), ('Hist', 'History'), 
                                              ('Lit', 'Literature'), ('Law', 'Law'),
                                              ('Math', 'Math'), ('Music', 'Music'), ('Med', 'Medecine'), 
                                              ('Politics', 'Politics'), ('Physics', 'Physics'), ('Psych', 'Psychology'), ('Phil', 'Philosophy'), ('Phys', 'Physiology'),
                                              ('Science', 'Science'), ('Soc', 'Sociology'),], default = None)
    length = SelectField('Length', choices=[("", "Content length"), ('long', 'Long'), ('short', 'Short')], default = None)
    main_lang = SelectField('Main Language', choices=[("", "Select output language"), ("Arabic", "Arabic"), ("Bulgarian", "Bulgarian"), ("Chinese", "Chinese"), ("Croatian",  "Croatian"), 
                                                  ("Czech",  "Czech"), ("Dutch", "Dutch"), ("Dothraki",  "Dothraki"), ("Elvish", "Elvish"), ("English",  "English"), 
                                                  ("Estonian", "Estonian"), ("Farsi", "Farsi"), ("French",  "French"), ("German", "German"), ("Greek",  "Greek"),
                                                  ("Hebrew", "Hebrew"), ("Hindi", "Hindi"), ("Hungarian", "Hungarian"), ("Indonesian", "Indonesian"),
                                                  ("Italian", "Italian"), ("Japanese", "Japanese"), ("Korean", "Korean"), ("Klingon", "Klingon"),
                                                  ("Latvian", "Latvian"), ("Lithuanian", "Lithuanian"), ("Malay", "Malay"), ("Norwegian", "Norwegian"),
                                                  ("Polish", "Polish"), ("Portuguese", "Portuguese"), ("Romanian", "Romanian"), ("Russian",  "Russian"),
                                                  ("Spanish", "Spanish"), ("Serbian", "Serbian"), ("Swahili", "Swahili"), ("Swedish", "Swedish"),
                                                  ("Tagalog", "Tagalog"), ("Thai", "Thai"), ("Turkish", "Turkish"), ("Urdu",  "Urdu"),
                                                  ( "Vietnamese", "Vietnamese")], default = None)
    
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
    
@app.route("/", methods=["GET", "POST"])
def index():

    return render_template('index.html')


@app.route("/register", methods=["GET", "POST"])
def register():
    
    username = request.form.get('username')
    email = request.form.get('email')
    email_conf = request.form.get('email_conf')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')
    agree_terms = request.form.get('terms-cond')
    agree_contact = request.form.get('contacted')
    if agree_terms == "agree-terms":
        if agree_contact == "agree-contacted":
            subscriber = Subscriber(email=email)
            db.session.add(subscriber)
            db.session.commit()
        if password != confirm_password:
            return 'Passwords do not match'
        elif email != email_conf:
            return 'Emails do not match'
        elif User.query.filter_by(username=username).first():
            return 'Username already exists'
        elif User.query.filter_by(email=email).first():
            return 'Email already exists'
        elif User.query.filter_by(email=email_conf).first():
            return 'Email already exists'
        else:
            password = bcrypt.generate_password_hash(request.form.get('password'))
            user = User(username=username, email=email, password=password)
            db.session.add(user)
            db.session.commit()
            flash('You have been registered succesfully!', 'success')

    return render_template('index.html', title='Index')

    
    
@app.route("/googleSignIn", methods=["POST"])
def googleSignIn():
    #Security validation
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
        idinfo = id_token.verify_oauth2_token(credential, requests.Request(),'561849198746-i5jlgmh2jgdti2sh9rhbvotjtv1r81bs.apps.googleusercontent.com')
        print(idinfo);
        # ID token is valid. Get the user's Google Account ID from the decoded token. (UniqueID to use for login)
        userid = idinfo['sub']
        
        user = User.query.filter_by(external_id=userid).first()
        
        if (user):
            login_user(user)
            flash('You have been logged in!', 'success')
            return redirect(url_for('index'))
        
        email = idinfo['email']
        given_name = idinfo['given_name']
        family_name = idinfo['family_name']
        
        
        user = User(email=email, first_name=given_name, last_name=family_name,external_id=userid)
        
        #user = User(email = email, external_id = userid, given_name = given_name, family_name = family_name, enabled = True)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for('index'))
    
    except ValueError:
        # Invalid token
        pass
    return render_template('index.html', title='Index')
    
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
    return render_template('index.html', title='Index')


@app.route('/subscribe', methods=['GET', 'POST'])
def subscribe():
    subscribe_form = RegSub()
    if subscribe_form.validate_on_submit():
        subscriber = Subscriber(email=subscribe_form.email.data, first_name=subscribe_form.first_name.data, last_name=subscribe_form.last_name.data, timestamp = datetime.now())
        db.session.add(subscriber)
        db.session.commit()
        flash('You are now subscribed to our newsletter!')

    return render_template('subscribe.html', title='Login', subscribe_form=subscribe_form)



@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    flash('You have been logged out!')
    return redirect(url_for('login'))

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


@app.route("/viewdecks", methods = ["GET", "POST"])
@login_required
def viewdecks():
    shared_decks = SharedDecks.query.all()
    
    email = current_user.email
    print("current user email: " + current_user.email)
    
    shared_decks = SharedDecks.query.filter(SharedDecks.receiver.ilike(f"%{email}%")).all()

    decks = Deck.query.filter(Deck.user_id == current_user.id).all()
    print("SHARED DECKS")
    for deck in shared_decks:
        print(deck.sender)
    
    if request.method == 'GET':
        print("entered get request")
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
            
        return render_template('viewdecks.html', decks=decks, shared_decks = shared_decks)
        
    if request.method == 'POST':
        deck_id = request.form['deck_id']
        deck = Deck.query.filter(Deck.id == deck_id).first()
        new_name = request.form['new_name']
        if new_name != '':
            deck.name = new_name
            db.session.commit()

        return render_template('viewdecks.html', decks=decks, shared_decks = shared_decks)
    print(shared_decks)
    return render_template('viewdecks.html', decks=decks, shared_decks = shared_decks)



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
    user = User.query.filter_by(id=current_user.id).first()
    
    
    if request.method == 'POST':
        print(request.form)
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        username = request.form.get('username')
        gender = request.form.get('gender')
        email_checkbox = request.form.get('email-checkbox')
        print(user, first_name, last_name, username, gender, email_checkbox)
        print("Entered account post request")
        if first_name != "":
            user.first_name = first_name
        if last_name != "":
            user.last_name = last_name
        if username != "":
            if User.query.filter_by(username=username).first() is not None and username != user.username:
                flash("Username already taken")
            else:
                user.username = username
        if gender != "":
            user.gender = gender
        if email_checkbox == "on":
            user.email_checkbox = True
            if not Subscriber.query.filter_by(email=user.email).first():
                subscriber = Subscriber(email=user.email, first_name=user.first_name, last_name=user.last_name, timestamp = datetime.now())
                db.session.add(subscriber)
                db.session.commit()


    return render_template("account.html", title="Account", user = user)

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
    print(pic)
    db.session.commit()
    print(user.pic)
    
  else:
      flash('No file selected')
  # update the user's profile picture in the database
  # (replace this with your own code to update the database)
  
  # redirect back to the user's profile page
  return redirect(url_for('account'))



@app.route("/deletecard/<int:deck_id>/<int:card_id>", methods = ["POST", "GET"])
@login_required
def deletecard(card_id, deck_id):
    print("card to delete")
    print(card_id)
    print("from deck")
    print(deck_id)
    deck = Deck.query.get_or_404(deck_id)
    if(current_user.id != deck.user_id):
       return jsonify({'error': 'Deck not assigned to user'}), 403
      
    card_to_delete = Card.query.get_or_404(card_id)
    if card_to_delete != None:
        db.session.delete(card_to_delete)
        db.session.commit()

    return redirect(("/carousel/{deck}").format(deck=deck_id))  

@app.route("/addterms/<int:deck_id>", methods = ["POST", "GET"])
@login_required
def addterms(deck_id):
    form = AddTermForm()
    deck = Deck.query.filter_by(id=deck_id, user_id=current_user.id).first()
    if(current_user.id != deck.user_id):
       return jsonify({'error': 'Deck not assigned to user'}), 403
    
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
    deck = Deck.query.filter_by(id=deck_id).first()
    if(current_user.id != deck.user_id):
       return jsonify({'error': 'Deck not assigned to user'}), 403
    cards = Card.query.filter(Card.decks.any(id=deck_id)).all()
    termsstrings = []

    for card in cards:
        if card.boc_2 == None:
            card.boc_2 = "null"
        if card.boc_3 == None:
            card.boc_3 = "null"
        if card.boc_4 == None:
            card.boc_4 = "null"    
        
        
        string = card.term + "," + card.content + "," + card.boc_2 + "," + card.boc_3 + "," + card.boc_4 + "," + card.category + "\n"
        termsstrings.append(string)            
    csvstring = "".join(termsstrings)            
    return Response(csvstring, mimetype="text/csv")

@app.route("/regen_def/<int:deck_id>/<int:card_id>", methods = ["POST", "GET"])
@login_required
def regenerate_def(deck_id, card_id):
    card = Card.query.filter(Card.id==card_id).first()
    card.regen_def()           
    return redirect(("/currentdeck/{deck}").format(deck=deck_id))



@app.route("/get-due-cards/<deck_id>")
def get_due_cards(deck_id):
    deck = Deck.query.get(deck_id)
    if(current_user.id != deck.user_id):
        return jsonify({'error': 'Deck not assigned to user'}), 403
    if deck is None:
        return jsonify({'error': 'Deck not found'}), 404
    return deck.get_due_cards()


@app.route("/study_deck/<int:deck_id>", methods = ["POST", "GET"])
def study_deck(deck_id):
    deck = Deck.query.get(deck_id)
    if(current_user.id != deck.user_id):
        return jsonify({'error': 'Deck not assigned to user'}), 403
    return render_template("study_deck.html", title="Study deck", deck=deck_id, deck0 = deck) 

@app.route("/study_deck_all", methods = ["POST", "GET"])   
@login_required   
def study_deck_all():
    ## loads all decks for a user
    
    ## get list of decks for user with id user id
    decks = Deck.query.filter(Deck.user_id == current_user.id).all()
    print(decks)
    decks_data = [{'id': deck.id} for deck in decks]
    decks_json = json.dumps(decks_data)
    print(decks_json)
    return render_template('study_deck_all.html', title='Study all decks', decks_json=decks_json, decks=decks)

@app.route("/increment/<card_id>", methods = ["POST", "GET"])
def increment(card_id):
    card = Card.query.get(card_id)
    
    deck = Deck.query.filter(Deck.cards.any(id=card_id)).first()
    if(current_user.id != deck.user_id):
        return jsonify({'error': 'Card not assigned to user'}), 403
    
    if card is None:
        return jsonify({'error': 'Card not found'}), 404
    card.increment()
    card.update_time()
    return jsonify({'success': 'Card incremented'}), 200
    

@app.route("/decrement/<card_id>", methods = ["POST"])
def decrement(card_id):
    card = Card.query.get(card_id)
    
    deck = Deck.query.filter(Deck.cards.any(id=card_id)).first()
    if(current_user.id != deck.user_id):
        return jsonify({'error': 'Deck not assigned to user'}), 403
    
    if card is None:
        return jsonify({'error': 'Card not found'}), 404
    card.decrement()
    card.update_time()
    return jsonify({'success': 'Card decremented'}), 200

@app.route("/forcestudy/<deck_id>")
def force_study(deck_id):
    deck = Deck.query.get(deck_id)
    
    if(current_user.id != deck.user_id):
         return jsonify({'error': 'Deck not assigned to user'}), 403
    
    if deck is None:
        return jsonify({'error': 'Deck not found'}), 404
    return deck.force_study()
    
@app.route("/casualmode/<int:deck_id>")
def casual_mode(deck_id):
    return render_template("casualmode.html", title="Casual Mode", deck=deck_id)   


 
 
@app.route('/generate_img/<int:deck_id>', methods=['GET', 'POST'])
def generate_img(deck_id):
    deck = Deck.query.get(deck_id)
    if(current_user.id != deck.user_id):
         return jsonify({'error': 'Deck not assigned to user'}), 403
        
    if deck is None:
        return jsonify({'error': 'Deck not found'}), 404
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
         return jsonify({'error': 'Deck not assigned to user'}), 403
        
    if request.method == 'POST' and 'term' in request.form:
        print("entered post request3")
        term = request.form['term'] ## new term for card
        content = request.form['content']
        
        
        boc_2 = request.form.get('boc_2')
        boc_3 = request.form.get('boc_3')
        boc_4 = request.form.get('boc_4')
        id = request.form['id'] ## id of card to be edited
        formula = request.form['formula']
        print(id)
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
        print(boc_2, boc_3, boc_4)
        db.session.commit()
    
    if request.method == 'POST' and 'new_term' in request.form:
        print("entered post request for adding new card")
        term = request.form['new_term']
        content = request.form['new_content']
        boc_2 = request.form['new_boc_2']
        boc_3 = request.form['new_boc_3']
        boc_4 = request.form['new_boc_4']
        category = request.form['new_category']
        time_created = datetime.now()
        entry = Card(term=term, content=content, boc_2=boc_2, boc_3=boc_3, boc_4=boc_4, category=category, time_created=time_created)
        deck.cards.append(entry)
        db.session.commit()
    
    if request.method == 'POST' and 'new_deck_name' in request.form:
        print("entered post request for editing deck")
        name = request.form['new_deck_name']
        description = request.form['new_deck_description']
        subject = request.form['new_deck_subject']
        topic = request.form['new_deck_topic']
        deck.name = name
        deck.description = description
        deck.subject = subject
        deck.topic = topic
        db.session.commit()   
    
    return render_template("carousel.html", title="Carousel", deck=deck, cards=cards) 

@app.route("/add_new_card/<int:deck_id>", methods = ["GET", "POST"])
def add_new_card(deck_id):
    print("entered add new card")
    deck = Deck.query.filter_by(id=deck_id, user_id=current_user.id).first()
    if(current_user.id != deck.user_id):
         return jsonify({'error': 'Deck not assigned to user'}), 403
        
    term = request.form['new_term'] 
    content = request.form['new_content']
    boc_2 = request.form['new_boc_2']
    boc_3 = request.form['new_boc_3']
    boc_4 = request.form['new_boc_4']
    category = request.form['new_category']
    entry = Card(term=term, content=content, boc_2=boc_2, boc_3=boc_3, boc_4=boc_4, category=category)
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
    del_email = request.form['del_email']
    del_password = request.form['del_password']
    if user.email == del_email and bcrypt.check_password_hash(user.password, del_password):
        db.session.delete(user)
        db.session.commit()
        flash("We'are sorry to see you go. Your account has been deleted.")
    return redirect(url_for('logout'))


## USING FOR EXPERIMENTATION
@app.route("/extract", methods = ["GET", "POST"])
@login_required
def extract():
    form = UploadFileForm()
    mapping = {
    "Definitions": ("A", "B"),
    "Translate": ("A", "B"),
    "Rhyme": ("A", "B"),
    "People": ("A", "B"),
    "Theories": ("A", "B"),
    "Cloze": ("A", "B"),
    "Mcq": ("A", "B", "C", "D", "E"),
    "Comprehension": ("A", "B"),
    "Vocab_builder": ("A", "B"),
    "Formulas": ("A", "B", "C"),
    }
    
    prompt_option2 = None
    lang_option = None
    trans_option = None
    len_option = None
    qmin_option = None
    qmax_option = None
    if form.validate_on_submit():
        print("form submitted")
        ## load type of card to be made to prompt_option
        if form.prompt.data != None:       
            prompt_option = form.prompt.data
            print(prompt_option)
        ## load translate option  
        if form.languages.data != None:    
            trans_option = form.languages.data
            print("------------------TRANS OPTION------------------")
            print(trans_option)    
        ## load secondary prompt option
        if form.subject.data:
            prompt_option2 = form.subject.data
        ## load language output option (defaults to English)
        if form.main_lang.data:
            lang_option = form.main_lang.data
        if form.length.data:
            len_option = form.length.data
        if form.qmin_option.data:
            qmin_option = form.qmin_option.data
        if form.qmax_option.data:
            qmax_option = form.qmax_option.data
                
        ## use existing deck or create a new one
        if form.deck_list.data != None:
            deck = form.deck_list.data
        else:
            deck_name = form.name.data
            if form.description.data != None:
                deck_description = form.description.data
            else:
                deck_description = " ".join(prompt_option + "deck")
            deck = Deck(name=deck_name, description=deck_description)
            db.session.add(deck) 
        print("type of data received, file, text, link")
        ## GET TEXT FROM INPUT 
        if form.file.data != None:
            f_type = form.file.data.content_type  
            print("file inputted3")
            method = "file upload"
            file = form.file.data
            file_loc = (os.path.join(os.path.abspath(os.path.dirname(__file__)),app.config['UPLOAD_FOLDER'],secure_filename(file.filename)))
            file.save(file_loc)
            text = text_extractor(file_loc)
        elif form.text_input.data is not None and form.text_input.data.strip() != '':
            f_type = "text"
            print("text inputted")
            method = "text input"
            text = form.text_input.data  
        elif form.link_input.data != None and form.link_input.data.strip() != '':
            f_type = "link"
            method = "link input"
            text = None
            link_input = form.link_input.data
            if "wikipedia" in form.link_input.data:
                if check_comma_list(link_input):
                    link_input = link_input.split(",")
                    print(link_input)
                    for link in link_input:
                        part = extract_from_wiki(link_input)
                    if text == None:
                        text = part
                    text = text + part
                print(link_input)
                text = extract_from_wiki(link_input)   
                    
            else:
                if check_comma_list(link_input):
                    link_input = link_input.split(",")
                    print(link_input)
                    for link in link_input:
                        print(link)
                        print(type(link))
                        link = get_video_id(link)
                        part = extract_from_youtube(link)
                        if text == None:
                            text = part
                        text = text + part
                print("youtube link inputted")
                link_input = get_video_id(link_input)
                text = extract_from_youtube(link_input)
         ## RETURN OUTPUT    
        terms = creator(text, prompt_option, prompt_option2, trans_option, lang_option, len_option, qmin_option, qmax_option)
        ## IF CHOSING TRANSSLATE SET CATEGORY TO LANGUAGE OTHERWISE TAKES ON TYPE OF CARD
        if prompt_option == "Translate":
            cat = prompt_option2
        else:
            cat = prompt_option
            
        ## DATA LOGGING
        prompt = str(terms[1])
        response = str(terms[2])
        content = str(terms[3])
        terms = terms[0]
        response_entry = ResponseData(prompt=prompt, response=response, content=content, timestamp = datetime.now())
        db.session.add(response_entry)
        db.session.commit()
        ## SET USER TO CURRENT USER
        deck.user_id = current_user.id
        ## ADD CARDS TO DECK
        
        
        if prompt_option == "Mcq":
            v, w, x, y, z = mapping.get(prompt_option, ("A", "B", "C", "D", "E"))
            for item in terms:
                entry = Card(category = cat, term=item[v].capitalize(), content=(add_period(item[w].capitalize())), boc_2=(add_period(item[x].capitalize())), boc_3=(add_period(item[y].capitalize())), boc_4=(add_period(item[z].capitalize())), create_method = method)
                db.session.add(entry)
                deck.cards.append(entry)
            db.session.commit()
        elif prompt_option != "Mcq" and prompt_option != "Transcribe" and prompt_option != "Formulas":
            x, y = mapping.get(prompt_option, ("A", "B"))
            for item in terms:
                entry = Card(category = cat, term=item[x].capitalize(), content=add_period(item[y].capitalize()), create_method=method)
                db.session.add(entry)
                deck.cards.append(entry)
            db.session.commit()
        elif prompt_option == "Formulas":
            x, y, z = mapping.get(prompt_option, ("A", "B", "C"))
            for item in terms:
                entry = Card(category = cat, term=item[x].capitalize(), formula="\["+(item[y])+"\]", content=add_period(item[z].capitalize()), create_method=method)
                db.session.add(entry)
                deck.cards.append(entry)
            db.session.commit()
        elif prompt_option == "Transcribe":
            if trans_option != None:
                name = deck.name + "_" + method + "_" + prompt_option + trans_option + "_" + str(datetime.now())
                create_type = trans_option + " translation"
                transcript_trans = DeckFiles(file_name = name, text_string = terms, time_created = datetime.now(), create_type = create_type)
                db.session.add(transcript_trans)
                deck.deck_files.append(transcript_trans)
                db.session.commit()
                return redirect("sea_dox/{deck.id}".format(deck = deck))
        ## ADD DECK)        
        if form.generate_images.data == True: 
            for card in deck.cards:
                try:
                    card.img = create_image(card.term)
                    db.session.commit()
                except:
                    pass
                
        ## SAVE TEXT TO DB
        f_name = deck.name + "_" + method + "_" + prompt_option + "_" + str(datetime.now())
        file_storage = DeckFiles(file_name=f_name, text_string=text, create_type = "source", time_created = datetime.now())
        db.session.add(file_storage) 
        deck.deck_files.append(file_storage)
        db.session.commit()
        
        return redirect('/carousel/{deck.id}'.format(deck = deck))
    else:
        print("form not valid")
        print("name", form.name.data, "/n", "description" ,form.description.data, "/n", "deck_list", form.deck_list.data, "/n", "prompt", form.prompt.data, "/n", "text_input", form.text_input.data, "/n", "file", form.file.data)

    return render_template("extract.html", title="Extract", form=form)


@app.route("/sea_dox/<int:deck_id>", methods=["GET", "POST"])
def sea_dox(deck_id):
    ## GET DECK
    deck = Deck.query.get_or_404(deck_id)
    ## GET source files
    files = deck.deck_files
    files = DeckFiles.query.filter(DeckFiles.decks.any(id=deck_id)).order_by(DeckFiles.file_name.desc()).all()
    
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
    file = DeckFiles.query.get_or_404(file_id)
    name = file.file_name +".pdf"
    text = file.text_string
    ## turn file.text_string into a pdf
    pdf_buffer = create_pdf(text)
    return send_file(pdf_buffer, download_name = name)



@app.route("/delete_file/<int:deck_id>/<int:file_id>/", methods=["GET", "POST"])
def delete_file(deck_id, file_id):
    print("entered delete file")
    file = DeckFiles.query.get_or_404(file_id)
    deck = Deck.query.get_or_404(deck_id)
    db.session.delete(file)
    db.session.commit()
    return redirect(("/sea_dox/{deck}").format(deck=deck.id)) 

@app.route("/share_deck/<int:deck_id>/<string:user_email>/", methods=["GET", "POST"])
def share_deck(deck_id, user_email):
    decks = Deck.query.filter(Deck.user_id == current_user.id).all()
    sender_id = current_user.email
    deck_to_copy = Deck.query.get_or_404(deck_id)
    
    if check_comma_list(user_email):
        print(user_email)
        users_emails = user_email.split(",")
        print(users_emails)
        for email in users_emails:
            email = unquote(email).strip()
            print(email)
            shared_deck = SharedDecks(name="Copy of " + deck_to_copy.name, description=deck_to_copy.description, sender = sender_id, time_created=datetime.now(), receiver=email)
            db.session.add(shared_deck)
            for card in deck_to_copy.cards:
                new_card = Card(term=card.term, content=card.content, boc_2=card.boc_2, boc_3=card.boc_3, boc_4=card.boc_4, img=card.img, sound=card.sound, subject=card.subject, topic=card.topic, category=card.category, prompt_option=card.prompt_option, prompt_option2=card.prompt_option2, trans_option=card.trans_option, len_option=card.len_option, qmin_option=card.qmin_option, qmax_option=card.qmax_option, diff_lvl=card.diff_lvl)
                shared_deck.cards.append(new_card)
            db.session.commit()
        return redirect(url_for('viewdecks'))
    else:
        email = unquote(user_email)
        shared_deck = SharedDecks(name="Copy of " + deck_to_copy.name, description=deck_to_copy.description, sender = sender_id, time_created=datetime.now(), receiver=email)
        db.session.add(shared_deck)
        for card in deck_to_copy.cards:
            new_card = Card(term=card.term, content=card.content, boc_2=card.boc_2, boc_3=card.boc_3, boc_4=card.boc_4, img=card.img, sound=card.sound, subject=card.subject, topic=card.topic, category=card.category, prompt_option=card.prompt_option, prompt_option2=card.prompt_option2, trans_option=card.trans_option, len_option=card.len_option, qmin_option=card.qmin_option, qmax_option=card.qmax_option, diff_lvl=card.diff_lvl)
            shared_deck.cards.append(new_card)
        db.session.commit()
        return redirect(url_for('viewdecks'))

@app.route("/approve_shared/<int:deck_id>/", methods=["GET", "POST"])
def approve_shared(deck_id):
    print("entered approve shared")
    shared_deck = SharedDecks.query.get_or_404(deck_id)
    new_deck = Deck(user_id = current_user.id, name=shared_deck.name, description=shared_deck.description, shared=True, sharer=shared_deck.sender, time_created=datetime.now())
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
    print("entered reject shared")
    shared_deck = SharedDecks.query.get_or_404(deck_id)
    shared_deck.delete()
    db.session.commit()
    success = True
    return jsonify({'success': success})
if __name__ == "__main__":
    app.run(debug=True)
    
@app.route("/feedback", methods=["GET", "POST"])
def feedback():
    if request.method == 'POST' and 'message_feedback' in request.form:
        name = request.form['name_feedback']
        email = request.form['email_feedback']
        feedback = request.form['message_feedback']
        type_feedback = request.form['type_feedback']
        entry = Feedback(name=name, email=email, message=feedback, type_feedback=type_feedback)
        entry.send_feedback()
        flash("Thank you for your feedback!", "success")

    return render_template('index.html', title='Index')



  ## OBSOLETE CODE BELOW ###############################################################################################  
############################################################################################################    
    
    