from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import secrets
from functools import wraps
import re

from flask_session import Session
from flask_wtf import CSRFProtect

import os

app = Flask(__name__)

debug_mode = os.environ.get("FLASK_DEBUG") == "1"
app.config["DEBUG"] = debug_mode

app.secret_key = secrets.token_hex(32)
csrf = CSRFProtect(app)

# Secure Flask Session Configuration
app.config.update(
    SESSION_COOKIE_HTTPONLY=True, # JS cannot access cookies
    SESSION_COOKIE_SECURE=False, # only sends cookies over https
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=1800
)

app.config["SESSION_TYPE"] = "filesystem" # Store sessions on server side
app.config["SESIION_PERMANENT"] = True
Session(app) #Initialize server side sessions

# HTTP Security Policies
csp = {
    "default-src": "'self'", 
    "script-src": "'self'",
    "style-src": "'self'"
}

Talisman(app, content_security_policy=csp)

# RATE Limiting
limiter = Limiter(
    get_remote_address,
    app = app,
    default_limits=["200 per day", "50 per hour"]
)


# ROUTES 
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("app.db")
        cursor = conn.cursor() # tells it what to add to the database

        cursor.execute("SELECT user_id, password, parent_name, child_name FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()

        conn.close()

        if not user:
            return render_template("login.html", error="* Incorrect email or password")
        
        stored_hash = user[1]

        if check_password_hash(stored_hash, password):
            session.clear() # Resets old session
            session["user_id"] = user[0]
            session["parent_name"] = user[2]
            session["child_name"] = user[3]
            session.permanent = True

            return redirect("/dashboard")
        else:
            return render_template("login.html", error="* Incorrect email or password")
    

    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
        
    # If a post method, get data from form
    if request.method == "POST":
        email = request.form["email"]
        parent_name = request.form["parent_name"]
        child_name = request.form["child_name"]
        child_dob = request.form["child_dob"]
        password = request.form["password"]
        terms_check = 1 if request.form.get("terms_check") else 0
        error = validate_password(password)
        if error:
            return render_template("signup.html", error=error)

        hashed_password = generate_password_hash(password)

        # Connect to the database
        conn = sqlite3.connect("app.db")
        cursor = conn.cursor() # tells it what to add to the database

        # Check if the email exists already
        cursor.execute("SELECT email FROM users WHERE email = ?", (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            conn.close()
            return render_template("signup.html", error="* Email already registered")
        
        conn = sqlite3.connect("app.db")
        cursor = conn.cursor() # tells it what to add to the database

        # Sqlite Injections/Execute database code
        cursor.execute(
            """
            INSERT INTO users (email, password, parent_name, child_name, child_dob, terms_check) VALUES (?, ?, ?, ?, ?, ?)
            """, 
            (email, hashed_password, parent_name, child_name, child_dob, terms_check)
        ) 

        # Commit the changes to db and close
        conn.commit()
        conn.close()

        return redirect("/login")

    return render_template("signup.html")

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/login")
        return f(*args, **kwargs)
    return wrapper

def validate_password(password):
    if len(password) < 8:
        return "The password must be at least 8 characters"
    if not re.search(r"[A-Z]", password):
        return "Must have an uppercase letter"
    if not re.search(r"[a-z]", password):
        return "Must have a lowercase letter"
    if not re.search(r"[!@#$%^&*(),.?/<>|=+\-_^~`]", password):
        return "Must have a special character"
    

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html",
                           parent=session["parent_name"],
                           child=session["child_name"])

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/terms-of-use")
def terms():
    return render_template("terms.html")

@app.route("/privacy-policy")
def privacy():
    return render_template("privacy.html")

@app.route("/welcome-activity")
@login_required
def welcomeActivity():
    return render_template("activity1.html",
                           parent=session["parent_name"],
                           child=session["child_name"])

if __name__ == "__main__":
    app.run(debug=True)