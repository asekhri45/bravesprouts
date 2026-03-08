from flask import Flask, render_template, request, redirect
import sqlite3

app = Flask(__name__)

@app.route("/")
def login():
    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():

    # If a post method, get data from form
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        parent_name = request.form["parent_name"]
        child_name = request.form["child_name"]
        child_dob = request.form["child_dob"]
        password = request.form["password"]

        # Connect to the database
        conn = sqlite3.connect("app.db")
        cursor = conn.cursor() # tells it what to add to the database

        # Sqlite Injections/Execute database code
        cursor.execute(
            """
            INSERT INTO users (email, username, password, parent_name, child_name, child_dob) VALUES (?, ?, ?, ?, ?, ?)
            """, 
            (email, username, parent_name, child_name, child_dob, password)
        ) 

        # Commit the changes to db and close
        conn.commit()
        conn.close()

        return redirect("/")

    return render_template("signup.html")


if __name__ == "__main__":
    app.run(debug=True)