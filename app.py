import openai 
import os
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from tempfile import mkdtemp
from sqlalchemy_utils import database_exists, create_database
from helpers import apology, login_required
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from wtforms import StringField, PasswordField, SubmitField
from flask_wtf.file import FileField, FileRequired
from wtforms.validators import InputRequired, Length, ValidationError, EqualTo
from flask_wtf import FlaskForm
from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename
from cardcreator import card_creator, write_to_csv
import sys

openai.api_key = os.environ.get("OPENAI_API_KEY")

# Configure application
app = Flask(__name__)
bcrypt = Bcrypt(app)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database1.db'
app.config['SECRET_KEY'] = 'whynot'
app.config['UPLOAD_FOLDER'] = 'static\\files'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1000 * 1000

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

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False, unique=True)
    password = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    email_confirmed_at = db.Column(db.DateTime())
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    
class Cards(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False) 
    description = db.Column(db.String(255), nullable=False)
    decks = relationship("Decks", back_populates="cards")


class Decks(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(255), nullable=False) 
    cards = db.relationship('Cards', back_populates="decks")
    user_id = db.Column(db.Integer, db.ForeignKey('user.id')) 




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
    file = FileField("File", validators=[InputRequired()])
    submit = SubmitField("Upload File")

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
def view_decks():
    return render_template("viewdecks.html", title="View Decks")

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

    form = UploadFileForm()
    if form.validate_on_submit():
        file = form.file.data
        filename = secure_filename(file.filename)
        file_loc = (os.path.join(os.path.abspath(os.path.dirname(__file__)),app.config['UPLOAD_FOLDER'],secure_filename(file.filename)))
        file.save(file_loc)
       
        terms = card_creator(file_loc)
        #terms = ({'key1': 'value1'}, {'key2': 'value2'})
    
    
        return render_template("cards.html", title="Cards", terms=terms)
    
    return render_template("extract.html", title="Extract", form=form)

@app.route("/account", methods = ["POST", "GET"])
@login_required
def account():
    return render_template("account.html", title="Account")

if __name__ == "__main__":
    app.run(debug=False)