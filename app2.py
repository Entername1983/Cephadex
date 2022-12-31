import os
import time

from sqlalchemy import create_engine, Column, Integer, String, Date
from sqlalchemy.ext.declarative import declarative_base
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy_utils import database_exists, create_database
from helpers import apology, login_required

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)



engine = create_engine('sqlite+pysqlite:///flashcards.db')
if not database_exists(engine.url):
    create_database(engine.url)

Base = declarative_base()


class Users(Base):
    __tablename__ = 'Users'

    user_id = Column(Integer, primary_key=True)
    user_name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    password = Column(String, nullable=False)

Base.metadata.create_all(engine)




@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response




@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?",
                          request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":

        # Require that a user input a username (text, name should be username?)  apology if the user’s input is blank or the username already exists.
        if not request.form.get("username"):
            return apology("must enter username", 400)

        # Require that a user input a password, text field whose name is password?, and then that same password again, confirmation. apology if either input is blank or the passwords do not match.
        elif not request.form.get("password"):
            return apology("must enter password", 400)

        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("unlike socks passwords must match", 400)
        
        elif not request.form.get("email"):
            return apology("must enter email", 400)
        
        elif request.form.get("email") != request.form.get("email_conf"):
            return apology("unlike socks emails must match", 400)

        ## check if username already exists
        rows = db.execute("SELECT * FROM users WHERE username = ?",
                          request.form.get("username"))
        if len(rows) > 0:
            return apology("username already taken", 400)
        
        ##check if email already used
        rows = db.execute("SELECT * FROM users WHERE email = ?",
                          request.form.get("email"))
        if len(rows) > 0:
            return apology("An account is already associated with this e-mail address", 400)
        
        # Insert the new user's info into the database.
        db.execute("INSERT INTO users (username, hash, email) VALUES (?, ?, ?)", request.form.get(
            "username"), generate_password_hash(request.form.get("password")), request.form.get("email"))

        return redirect("/login")

    else:
        return render_template("register.html")


@app.route("/change_pass", methods=["GET", "POST"])
def change_pass():
    """Change password"""
    if request.method == "POST":

        # Require that a user input a username (text, name should be username?)  apology if the user’s input is blank or the username already exists.
        if not request.form.get("username"):
            return apology("must enter username", 403)

        # Require that a user input a password, text field whose name is password?, and then that same password again, confirmation. apology if either input is blank or the passwords do not match.
        elif not request.form.get("password"):
            return apology("must enter password", 403)

        elif request.form.get("new_pass") != request.form.get("conf_new_pass"):
            return apology("unlike socks passwords must match", 403)

        else:
            rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
            if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
                return apology("invalid username and/or password", 403)
            print((request.form.get("new_pass")))
            print(generate_password_hash(request.form.get("new_pass")))
            print(request.form.get("username"))
            db.execute("UPDATE users  SET hash = (?) WHERE username IS (?)", generate_password_hash(request.form.get("new_pass")), request.form.get("username"))

        return redirect("/login")

    else:
        return render_template("change_pass.html")





def apology(message, code=400):
    """Render message as an apology to user."""
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=code, bottom=escape(message)), code