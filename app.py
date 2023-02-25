import openai 
import os
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
from cardcreator import card_creator, write_to_csv, create_image
from extractors import Regenerate_def, add_period, large_extract_terms, small_extract_terms
import sys
from sqlalchemy.sql import func
import logging
import logging.handlers
from datetime import datetime, timedelta

openai.api_key = os.environ.get("OPENAI_API_KEY")

# Configure application
app = Flask(__name__)

bcrypt = Bcrypt(app)



app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database1.db'
app.config['SECRET_KEY'] = 'whynot'
app.config['UPLOAD_FOLDER'] = 'static\\files'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1000 * 1000

werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.INFO)



ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx', 'pptx'}

db = SQLAlchemy(app)

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
## external auth + external type + external
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False, unique=True)
    password = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    email_confirmed_at = db.Column(db.DateTime())
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    decks = db.relationship("Deck", backref=db.backref("user", lazy="joined"), lazy="select")


class Card(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    term = db.Column(db.String(50), nullable=False) 
    # content == Back of card 1
    content = db.Column(db.String(255), nullable=False)
    ## used for MCQ wrong answers
    boc_2 = db.Column(db.String(255), nullable=True) 
    boc_3 = db.Column(db.String(255), nullable=True) 
    boc_4 = db.Column(db.String(255), nullable=True)
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
    # unused
    #data_1 = db.Column(db.float(100), nullable = True)
    #data_2 = db.Column(db.float(100), nullable = True)
    #data_3 = db.Column(db.float(100), nullable = True)
    #data_time = db.Column(db.Interval, nullable = True)
    
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
        self.content = Regenerate_def(self.term)
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
        if self.times_correct_row > 4:
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
        db.session.commit()
        
    def decrement(self):
        self.times_asked = self.times_asked + 1
        self.times_correct_row = 0
        if self.box_id == 0:
            self.interval = 1
        if self.box_id == 2:
            self.box_id = 1
        if self.box_id == 3:
            self.box_id == 2
        if self.box_id == 1:
            self.interval = self.interval / 2
        if self.box_id == 2:
            self.interval - self.interval * 0.8
        if self.box_id == 3:
            self.interval - self.interval * 0.9
        if not self.box_id == 1 and self.interval < 5:
            self.interval = 5
        db.session.commit()
    
    def reset_interval(self):
        self.interval = 10
        db.session.commit()
        
    def update_time(self):
        self.time_updated = datetime.utcnow()
        db.session.commit()
    

class Deck(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(255), nullable=False) 
    ## make relational table instead of using user_id?
    user_id = db.Column(db.Integer, db.ForeignKey('user.id')) 
    cards = db.relationship('Card', secondary=cards, backref="decks", lazy="select")
    time_created = db.Column(db.DateTime, default=datetime.utcnow)   
    time_updated = db.Column(db.DateTime, default=datetime.utcnow)

    creator = db.Column(db.Integer) 
    public = db.Column(db.Integer, default=0) 
    edited = db.Column(db.Integer, default=0)
    create_method = db.Column(db.String(255), nullable=True)
    category = db.Column(db.String(255), nullable=True)
    times_accessed = db.Column(db.Integer, default=0)
    access_date = db.Column(db.DateTime, default=datetime.utcnow)
 
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
            if time_diff >= card.interval:
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
                })
        if not due_cards:
            return jsonify({'info': 'No due cards found'}), 204
        return jsonify(due_cards)
    
    def cards_due(self):
        due_cards = 0
        current_time = datetime.now()
        for card in self.cards:
            time_diff = (current_time - card.time_updated).total_seconds() / 60
            if time_diff >= card.interval:
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
    submit = SubmitField("Extract", render_kw={"id": "extract-submit"})
    deck_list = QuerySelectField("Choose a deck", query_factory=lambda: Deck.query.filter(Deck.user_id == current_user.id), allow_blank=True, get_label='name', render_kw={"placeholder": "Choose an existing deck"})
    prompt = RadioField('Prompt', choices=[('Definitions', 'Definitions'), ('Translate', 'Translate'), ('Rhyme', 'Rhyme'), ('People', 'People'), ('Theories', 'Theories'), ('Cloze', 'Cloze'), ('Mcq', 'MCQ'), ('Comprehension', 'Comprehension')], default='Definitions')
    generate_images = BooleanField('Generate_images')
    languages = SelectField('Languages', choices=[('French', 'French'), ('English', 'English'), ('Spanish', 'Spanish'), ('Chinese', 'Chinese'), ('German', 'German'), ('Portuguese', 'Portuguese'), ('Japanese', 'Japanese'), ('Swahili', 'Swahili'), ('Dutch', 'Dutch'), ('Russian', 'Russian'), ('Klingon', 'Klingon'), ('Dothraki', 'Dothraki')], default = None)
    text_input = StringField('Text Input', render_kw={"placeholder": "Paste your text here"})
    link_input = StringField('Link Input', render_kw={"placeholder": "Paste your link here"}, validators=[Optional(), URL()])
    
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
    
    
@app.route("/", methods=["GET", "POST"])
def index():
    return render_template('index.html')

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data)
        user = User(username=form.username.data, email=form.email.data, password=hashed_password, first_name=form.first_name.data, last_name=form.last_name.data)
        db.session.add(user)
        db.session.commit()
        flash("Your account has been created! You are now able to log in", "info")
        return redirect(url_for("login"))
    return render_template("register.html", title="Register", form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    app.logger.info('0')
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user:
            if bcrypt.check_password_hash(user.password, form.password.data):
                login_user(user)
                return redirect(url_for('study'))
        else:
            flash('Login Unsuccessful. Please check username and password')
    return render_template('login.html', title='Login', form=form)

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
    
    print("page reloaded")
    decks = Deck.query.filter(Deck.user_id == current_user.id).all()
   
    
    if request.method == 'GET':
        print("entered get request")
        sort_method =request.args.get('sort')
        search_query = None
        search_query = request.args.get('search', '').strip()
        print(search_query)
        print(sort_method)
        
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
            print(decks)

        
            
        return render_template('viewdecks.html', decks=decks)
            
        
        
        
        
        
    if request.method == 'POST':
        deck_id = request.form['deck_id']
        deck = Deck.query.filter(Deck.id == deck_id).first()
        new_name = request.form['new_name']
        if new_name != '':
            deck.name = new_name
            db.session.commit()

        return render_template('viewdecks.html', decks=decks)
    
    return render_template('viewdecks.html', decks=decks)



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


@app.route("/extract", methods = ["GET", "POST"])
@login_required
def extract_page():
    mapping = {
    "Definitions": ("T", "D"),
    "Translate": ("T", "CH"),
    "Rhyme": ("T", "R"),
    "People": ("P", "B"),
    "Theories": ("TC", "E"),
    }
    form = UploadFileForm()
    if form.validate_on_submit():
        if form.deck_list.data != None:
            deck = form.deck_list.data
        else:
            deck_name = form.name.data
            deck_description = form.description.data
            deck = Deck(name=deck_name, description=deck_description)
            db.session.add(deck)   
        file = form.file.data
        file_loc = (os.path.join(os.path.abspath(os.path.dirname(__file__)),app.config['UPLOAD_FOLDER'],secure_filename(file.filename)))
        file.save(file_loc)
        prompt_option = form.prompt.data
        terms = card_creator(file_loc, prompt_option)
        deck.user_id = current_user.id
        x, y = mapping.get(prompt_option, ("T", "D"))
        for item in terms:
            entry = Card(term=item[x].capitalize(), content=add_period(item[y]))
            db.session.add(entry)
            deck.cards.append(entry)
        db.session.commit()
        return redirect('/currentdeck/{deck.id}'.format(deck = deck))
    return render_template("extract.html", title="Extract", form=form)

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
    db.session.delete(deck_to_delete)
    db.session.commit()
    return redirect(url_for('viewdecks'))

@app.route("/rename_deck/<int:id>/<string:new_name>", methods = ["POST", "GET"])
@login_required
def rename_deck(id, new_name):
    deck = Deck.query.get_or_404(id)
    deck.rename(new_name)
    db.session.commit()
    return redirect(url_for('viewdecks'))
    
@app.route("/account", methods = ["POST", "GET"])
@login_required
def account():
    return render_template("account.html", title="Account")

@app.route("/deletecard/<int:deck_id>/<int:card_id>", methods = ["POST", "GET"])
@login_required
def deletecard(card_id, deck_id):
    card_to_delete = Card.query.get_or_404(card_id)
    db.session.delete(card_to_delete)
    db.session.commit()
    return redirect(("/carousel/{deck}").format(deck=deck_id))  

@app.route("/addterms/<int:deck_id>", methods = ["POST", "GET"])
@login_required
def addterms(deck_id):
    form = AddTermForm()
    deck = Deck.query.filter_by(id=deck_id, user_id=current_user.id).first()
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
    cards = Card.query.filter(Card.decks.any(id=deck_id)).all()
    termsstrings = []
    for card in cards:
        string = card.term + "," + card.content + "\n"
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
    if deck is None:
        return jsonify({'error': 'Deck not found'}), 404
    return deck.get_due_cards()


@app.route("/study_deck/<int:deck_id>", methods = ["POST", "GET"])
def study_deck(deck_id):
    deck = Deck.query.get(deck_id)
    return render_template("study_deck.html", title="Study deck", deck=deck_id, deck0 = deck)       


@app.route("/increment/<card_id>", methods = ["POST", "GET"])
def increment(card_id):
    card = Card.query.get(card_id)
    if card is None:
        return jsonify({'error': 'Card not found'}), 404
    card.increment()
    card.update_time()
    return jsonify({'success': 'Card incremented'}), 200
    

@app.route("/decrement/<card_id>", methods = ["POST"])
def decrement(card_id):
    card = Card.query.get(card_id)
    if card is None:
        return jsonify({'error': 'Card not found'}), 404
    card.decrement()
    card.update_time()
    return jsonify({'success': 'Card decremented'}), 200

@app.route("/forcestudy/<deck_id>")
def force_study(deck_id):
    deck = Deck.query.get(deck_id)
    if deck is None:
        return jsonify({'error': 'Deck not found'}), 404
    return deck.force_study()
    
@app.route("/casualmode/<int:deck_id>")
def casual_mode(deck_id):
    return render_template("casualmode.html", title="Casual Mode", deck=deck_id)   

@app.route('/subscribe', methods=['GET', 'POST'])
def subrscribe():
    form = RegSub()
    if form.validate_on_submit():
        subscriber = Subscriber(email=form.email.data, first_name=form.first_name.data, last_name=form.last_name.data, timestamp = datetime.now())
        db.session.add(subscriber)
        db.session.commit()
        flash('You are now subscribed to our newsletter!')

    return render_template('subscribe.html', title='Login', form=form)
 
 
@app.route('/generate_img/<int:deck_id>', methods=['GET', 'POST'])
def generate_img(deck_id):
    deck = Deck.query.get(deck_id)
    if deck is None:
        return jsonify({'error': 'Deck not found'}), 404
    for card in deck.cards:
        try:
            card.img = create_image(card.term)
            db.session.commit()
        except:
            pass

    return redirect(("/currentdeck/{deck}").format(deck=deck_id))
    
    
@app.route("/extract2", methods = ["GET", "POST"])
@login_required
def extract2():

    mapping = {
    "Definitions": ("T", "D"),
    "Translate": ("T", "TR"),
    "Rhyme": ("T", "R"),
    "People": ("P", "B"),
    "Theories": ("TC", "E"),
    "Cloze": ("C", "F"),
    "Mcq": ("Q", "A", "W1", "W2", "W3"),
    "Comprehension": ("QC", "AC"),
    }
    form = UploadFileForm()
    if form.validate_on_submit():
        print("form submitted")
        ## load type of card to be made to prompt_option
        if form.prompt.data != None:       
            prompt_option = form.prompt.data
        ## load optional secondary option, currently only useful for languages    
        if form.languages.data != None:    
            prompt_option2 = form.languages.data    
             
        if form.prompt.data != "Translate":
            prompt_option2 = None         
        
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
   
        ## create card content, gets outputed as a list of dicts    
        if form.file.data != None:  
            print("file inputted")
            method = "file upload"
            file = form.file.data
            file_loc = (os.path.join(os.path.abspath(os.path.dirname(__file__)),app.config['UPLOAD_FOLDER'],secure_filename(file.filename)))
            file.save(file_loc)
            terms = card_creator(file_loc, prompt_option, prompt_option2)
            
        elif form.text_input.data != None:
            print("text inputted")
            method = "text input"
            text = form.text_input.data
            print(text)
            terms = small_extract_terms(text, prompt_option, prompt_option2)

        if prompt_option == "Translate":
            cat = prompt_option2
        else:
            cat = prompt_option
            
        deck.user_id = current_user.id
        ## need to modify db accordingly
        if prompt_option == "Mcq":
            v, w, x, y, z = mapping.get(prompt_option, ("Q", "A", "W1", "W2", "W3"))
            for item in terms:
                entry = Card(category = cat, term=item[v].capitalize(), content=(add_period(item[w])), boc_2=(add_period(item[x])), boc_3=(add_period(item[y])), boc_4=(add_period(item[z])), create_method = method)
                db.session.add(entry)
                deck.cards.append(entry)
            db.session.commit()
        elif prompt_option != "Mcq":
            x, y = mapping.get(prompt_option, ("T", "D"))
            for item in terms:
                entry = Card(category = cat, term=item[x].capitalize(), content=add_period(item[y]), create_method=method)
                db.session.add(entry)
                deck.cards.append(entry)
            db.session.commit()                
        if form.generate_images.data == True: 
            for card in deck.cards:
                try:
                    card.img = create_image(card.term)
                    db.session.commit()
                except:
                    pass
        
        return redirect('/carousel/{deck.id}'.format(deck = deck))
    else:
        print("form not valid")
        print("name", form.name.data, "/n", "description" ,form.description.data, "/n", "deck_list", form.deck_list.data, "/n", "prompt", form.prompt.data, "/n", "text_input", form.text_input.data, "/n", "file", form.file.data)

    return render_template("extract2.html", title="Extract2", form=form)


@app.route("/carousel/<int:deck_id>", methods = ["GET", "POST"])
def carousel(deck_id):
    
    deck = Deck.query.filter_by(id=deck_id, user_id=current_user.id).first()
    cards = Card.query.filter(Card.decks.any(id=deck_id)).order_by(Card.id.desc()).all()

    if request.method == 'POST' and 'term' in request.form:
        print("entered post request3")
        term = request.form['term'] ## new term for card
        content = request.form['content'] ## new content for card
        id = request.form['id'] ## id of card to be edited
        print(id)
        card = Card.query.filter_by(id=id).first()
        if term != "":
            card.term = term
        if content != "":
            card.content = content
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
        
    
    
    return render_template("carousel.html", title="Carousel", deck=deck, cards=cards) 

@app.route("/add_new_card/<int:deck_id>", methods = ["GET", "POST"])
def add_new_card(deck_id):
    deck = Deck.query.filter_by(id=deck_id, user_id=current_user.id).first()
    if request.method == 'POST':
        term = request.form['term'] 
        content = request.form['content']
        boc_2 = request.form['boc_2']
        boc_3 = request.form['boc_3']
        boc_4 = request.form['boc_4']
        category = request.form['category']
        create_date = datetime.now()
        entry = Card(term=term, content=content, boc_2=boc_2, boc_3=boc_3, boc_4=boc_4, category=category, create_date=create_date)
        db.session().add(entry)
        deck.cards.append(entry)
        db.session.commit()
    if request.method == 'POST' and "new-card" in request.form:
        id = request.form['id']
        card = Card.query.filter_by(id=id).first()
        db.session.delete(card)
        db.session.commit()

    return render_template("add_new_card.html", title="Add New Card", deck=deck)


if __name__ == "__main__":
    app.run(debug=True)