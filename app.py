from flask import Flask, render_template, request, redirect
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)

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

@app.route("/login")
def login():
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

        hashed_password = generate_password_hash(password)

        # Connect to the database
        conn = sqlite3.connect("app.db")
        cursor = conn.cursor() # tells it what to add to the database

        # Sqlite Injections/Execute database code
        cursor.execute(
            """
            INSERT INTO users (email, password, parent_name, child_name, child_dob) VALUES (?, ?, ?, ?, ?)
            """, 
            (email, hashed_password, parent_name, child_name, child_dob)
        ) 

        # Commit the changes to db and close
        conn.commit()
        conn.close()

        return redirect("/login")

    return render_template("signup.html")


if __name__ == "__main__":
    app.run(debug=True)