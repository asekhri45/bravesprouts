from flask import Flask, render_template, request, redirect, session, url_for, abort, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

import json

import hashlib

from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from werkzeug.security import generate_password_hash

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from datetime import date, datetime

from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import secrets
from functools import wraps
import re

from flask_session import Session
from flask_wtf import CSRFProtect

from flask import jsonify
from dotenv import load_dotenv
from openai import OpenAI
import base64

from elevenlabs.client import ElevenLabs

import requests

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "app.db")

RESEARCH_LIBRARY_PATH = os.path.join(BASE_DIR, "research_library.json")

try:
    with open(RESEARCH_LIBRARY_PATH, "r", encoding="utf-8") as f:
        RESEARCH_LIBRARY = json.load(f)
except Exception as e:
    print("Could not load research_library.json:", e)
    RESEARCH_LIBRARY = []

app = Flask(__name__)


load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
eleven_client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

debug_mode = os.environ.get("FLASK_DEBUG") == "1"
app.config["DEBUG"] = debug_mode
is_development = os.environ.get("FLASK_ENV") == "development"

#app.secret_key = secrets.token_hex(32)
csrf = CSRFProtect(app)

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key-change-later")

serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])

# Secure Flask Session Configuration
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=False,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=1800
)

app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_PERMANENT"] = True
Session(app)

# HTTP Security Policies
csp = {
    "default-src": "'self'",
    "script-src": "'self'",
    "style-src": "'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src": "'self' https://fonts.gstatic.com data:",
    "img-src": "'self' data:",
    "media-src": "'self' data: blob:"
}

Talisman(app, content_security_policy=csp, force_https=False)
# Talisman(app, content_security_policy=csp, force_https=os.environ.get("FLASK_ENV") == "production")

# RATE Limiting
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"]
)

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

MATCHING_GAME_TARGET_ROUNDS = 12


def ensure_matching_game_progress_columns():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(progress)")
    existing_columns = {row["name"] for row in cursor.fetchall()}

    columns_to_add = {
        "matching_rounds_completed": "ALTER TABLE progress ADD COLUMN matching_rounds_completed INTEGER DEFAULT 0",
        "matching_spoken_responses": "ALTER TABLE progress ADD COLUMN matching_spoken_responses INTEGER DEFAULT 0",
        "matching_silent_windows": "ALTER TABLE progress ADD COLUMN matching_silent_windows INTEGER DEFAULT 0",
        "matching_wonder_prompts_asked": "ALTER TABLE progress ADD COLUMN matching_wonder_prompts_asked INTEGER DEFAULT 0",
        "matching_help_prompts_asked": "ALTER TABLE progress ADD COLUMN matching_help_prompts_asked INTEGER DEFAULT 0",
        "matching_clear_prompts_asked": "ALTER TABLE progress ADD COLUMN matching_clear_prompts_asked INTEGER DEFAULT 0",
        "matching_child_choice_responses": "ALTER TABLE progress ADD COLUMN matching_child_choice_responses INTEGER DEFAULT 0",
        "matching_child_opinion_responses": "ALTER TABLE progress ADD COLUMN matching_child_opinion_responses INTEGER DEFAULT 0",
        "matching_clear_child_responses": "ALTER TABLE progress ADD COLUMN matching_clear_child_responses INTEGER DEFAULT 0",
        "matching_direct_child_question_silences": "ALTER TABLE progress ADD COLUMN matching_direct_child_question_silences INTEGER DEFAULT 0",
        "matching_last_stage": "ALTER TABLE progress ADD COLUMN matching_last_stage INTEGER DEFAULT 0",
        "matching_last_played_at": "ALTER TABLE progress ADD COLUMN matching_last_played_at TEXT"
    }

    for column_name, alter_sql in columns_to_add.items():
        if column_name not in existing_columns:
            cursor.execute(alter_sql)

    conn.commit()
    conn.close()


def safe_matching_int(value, default=0):
    try:
        return max(0, int(float(value or default)))
    except (TypeError, ValueError):
        return default


def safe_matching_float(value, default=0.0):
    try:
        return max(0.0, float(value or default))
    except (TypeError, ValueError):
        return default

def initialize_user_progress(cursor, user_id):
    cursor.execute("""
        SELECT activity_id, activity_name
        FROM activity
        WHERE is_active = 1
        ORDER BY level_of_realism, activity_order
    """)
    activities = cursor.fetchall()

    first_activity_id = None

    for activity in activities:
        activity_id = activity["activity_id"]
        activity_name = activity["activity_name"]

        is_unlocked = 1 if activity_name == "match_cards" else 0

        if activity_name == "match_cards":
            first_activity_id = activity_id

        cursor.execute("""
            INSERT INTO progress (
                user_id,
                activity_id,
                is_unlocked,
                is_completed,
                words_spoken,
                minutes_spoken,
                active_minutes
            )
            VALUES (?, ?, ?, 0, 0, 0, 0)
        """, (user_id, activity_id, is_unlocked))

    return first_activity_id

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

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT user_id, password, parent_name, child_name, profile_icon FROM users WHERE email = ?",
            (email,)
        )
        user = cursor.fetchone()

        conn.close()

        if not user:
            return render_template("login.html", error="* Incorrect email or password")

        stored_hash = user[1]

        if check_password_hash(stored_hash, password):
            session.clear()
            session["user_id"] = user[0]
            session["parent_name"] = user[2]
            session["child_name"] = user[3]
            session["profile_icon"] = user[4] if len(user) > 4 and user[4] else "profileicon.png"
            session.permanent = True

            return redirect("/dashboard")
        else:
            return render_template("login.html", error="* Incorrect email or password")

    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
@csrf.exempt
def signup():
    if request.method == "POST":
        email = clean_short_setting(request.form.get("email"), 120).lower()
        parent_name = clean_short_setting(request.form.get("parent_name"), 50)
        parent_pin = clean_short_setting(request.form.get("parent_pin"), 4)
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        terms_check = 1 if request.form.get("terms_check") else 0

        if not email:
            return render_template("signup.html", error="* Email is required")

        if not parent_name:
            return render_template("signup.html", error="* Parent name is required")

        if not re.fullmatch(r"\d{4}", parent_pin or ""):
            return render_template("signup.html", error="* Parent PIN must be exactly 4 digits")

        if password != confirm_password:
            return render_template("signup.html", error="* Passwords do not match")

        error = validate_password(password)
        if error:
            return render_template("signup.html", error=error)

        hashed_password = generate_password_hash(password)

        child_name = None
        child_dob = None
        child_age = None

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT user_id FROM users WHERE email = ?", (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            conn.close()
            return render_template("signup.html", error="* Email already registered")

        cursor.execute("""
            INSERT INTO users (
                email,
                password,
                parent_name,
                child_name,
                child_dob,
                child_age,
                parent_pin,
                terms_check
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            email,
            hashed_password,
            parent_name,
            child_name,
            child_dob,
            child_age,
            parent_pin,
            terms_check
        ))

        user_id = cursor.lastrowid

        first_activity_id = initialize_user_progress(cursor, user_id)

        if first_activity_id is not None:
            cursor.execute("""
                UPDATE users
                SET current_activity_id = ?
                WHERE user_id = ?
            """, (first_activity_id, user_id))

        conn.commit()
        conn.close()

        session.clear()
        session["user_id"] = user_id
        session["parent_name"] = parent_name
        session["child_name"] = ""
        session["profile_icon"] = "profileicon.png"
        session.permanent = True

        return redirect(url_for("dashboard"))

    return render_template("signup.html")

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return wrapper

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
    return None

def ensure_settings_columns():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(users)")
    existing_columns = {row["name"] for row in cursor.fetchall()}

    columns_to_add = {
        "child_age": "ALTER TABLE users ADD COLUMN child_age INTEGER"
    }

    for column_name, alter_sql in columns_to_add.items():
        if column_name not in existing_columns:
            cursor.execute(alter_sql)

    conn.commit()
    conn.close()


def get_settings_status(status_key):
    messages = {
        "child_saved": ("Your child profile was updated.", "success"),
        "account_saved": ("Your parent account was updated.", "success"),
        "password_saved": ("Your password was updated.", "success"),
        "email_exists": ("That email is already being used by another account.", "error"),
        "password_wrong": ("Your current password was incorrect.", "error"),
        "password_mismatch": ("The new passwords do not match.", "error"),
        "password_invalid": ("Your new password does not meet the requirements.", "error")
    }

    return messages.get(status_key, (None, None))


def clean_short_setting(value, max_length=80):
    value = re.sub(r"\s+", " ", str(value or "")).strip()
    return value[:max_length]

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
    return render_template(
        "activity1.html",
        parent=session["parent_name"],
        child=session["child_name"]
    )

@app.route("/parent-pin", methods=["GET", "POST"])
@csrf.exempt
@login_required
def parent_pin_gate():
    if request.method == "POST":
        entered_pin = clean_short_setting(request.form.get("parent_pin"), 4)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT parent_pin FROM users WHERE user_id = ?", (session["user_id"],))
        user = cursor.fetchone()
        conn.close()

        if user and entered_pin == str(user["parent_pin"] or ""):
            session["parent_pin_dashboard_verified"] = True
            session.pop("needs_parent_pin_for_dashboard", None)
            return redirect(url_for("dashboard"))

        return render_template("parent_pin.html", error="Incorrect PIN. Try again.")

    return render_template("parent_pin.html", error=None)

@app.route("/admin/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
@csrf.exempt
def admin_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
        admin_password = os.getenv("ADMIN_PASSWORD", "")

        if email == admin_email and password == admin_password:
            session.clear()
            session["is_admin"] = True
            session.permanent = True
            return redirect(url_for("admin_user_overview"))

        return render_template("admin_login.html", error="* Incorrect admin email or password")

    return render_template("admin_login.html")


@app.route("/admin/user-overview")
def admin_user_overview():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            u.user_id,
            u.parent_name,
            u.email,
            u.child_name,
            u.child_age,
            COUNT(p.activity_id) AS total_activities,
            SUM(CASE WHEN p.is_unlocked = 1 THEN 1 ELSE 0 END) AS unlocked_activities,
            SUM(CASE WHEN p.is_completed = 1 THEN 1 ELSE 0 END) AS completed_activities,
            COALESCE(SUM(p.words_spoken), 0) AS total_words_spoken,
            COALESCE(SUM(p.active_minutes), 0) AS total_active_minutes,
            MAX(sl.completed_at) AS last_active
        FROM users u
        LEFT JOIN progress p ON u.user_id = p.user_id
        LEFT JOIN session_log sl ON u.user_id = sl.user_id
        GROUP BY u.user_id
        ORDER BY last_active DESC
    """)

    users = cursor.fetchall()
    conn.close()

    return render_template(
        "admin_user_overview.html",
        users=users,
        active_page="admin_user_overview"
    )

@app.route("/dashboard")
@login_required
def dashboard():

    if (
        session.get("needs_parent_pin_for_dashboard")
        and not session.get("parent_pin_dashboard_verified")
    ):
        return redirect(url_for("parent_pin_gate"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            COALESCE(SUM(words_spoken), 0) AS total_words,
            COALESCE(SUM(minutes_spoken), 0) AS total_minutes,
            COALESCE(SUM(active_minutes), 0) AS total_active_minutes,
            COUNT(*) AS total_activities
        FROM progress
        WHERE user_id = ?
    """, (session["user_id"],))
    stats = cursor.fetchone()

    cursor.execute("""
        SELECT current_activity_id, COALESCE(has_seen_tour, 0) AS has_seen_tour
        FROM users
        WHERE user_id = ?
    """, (session["user_id"],))
    user_row = cursor.fetchone()

    current_activity_id = user_row["current_activity_id"] if user_row else None
    has_seen_tour = user_row["has_seen_tour"] if user_row else 1

    cursor.execute("""
    SELECT
        a.activity_id,
        a.scene_id,
        a.activity_name,
        a.description,
        a.activity_order,
        a.level_of_realism,
        a.total_levels_of_realism,
        a.time_recommended,
        a.character_active,
        COALESCE(p.is_unlocked, 0) AS is_unlocked,
        COALESCE(p.words_spoken, 0) AS words_spoken,
        COALESCE(p.time_spent_on_activity, 0) AS time_spent_on_activity,
        COALESCE(p.active_minutes, 0) AS active_minutes
    FROM activity a
    LEFT JOIN progress p
        ON a.activity_id = p.activity_id
        AND p.user_id = ?
    WHERE a.is_active = 1
    ORDER BY a.level_of_realism, a.activity_order
    """, (session["user_id"],))

    activities = cursor.fetchall()

    cursor.execute("""
        SELECT
            session_id,
            activity_id,
            words_spoken,
            minutes_spoken,
            active_minutes,
            completed_at
        FROM session_log
        WHERE user_id = ?
        ORDER BY completed_at ASC, session_id ASC
    """, (session["user_id"],))

    session_rows = cursor.fetchall()

    session_chart_data = [
        {
            "session_number": i + 1,
            "words_spoken": row["words_spoken"],
            "minutes_spoken": float(row["minutes_spoken"] or 0),
            "active_minutes": float(row["active_minutes"] or 0)
        }
        for i, row in enumerate(session_rows)
    ]

    cursor.execute("""
    SELECT
        sl.session_id,
        sl.completed_at,
        a.activity_name,
        a.character_active
    FROM session_log sl
    JOIN activity a ON sl.activity_id = a.activity_id
    WHERE sl.user_id = ?
    ORDER BY sl.completed_at DESC, sl.session_id DESC
    LIMIT 8
    """, (session["user_id"],))

    recent_sessions = cursor.fetchall()

    default_slide_index = 0

    for i, activity in enumerate(activities):
        if activity["activity_id"] == current_activity_id:
            default_slide_index = i
            break

    conn.close()

    return render_template(
        "dashboard.html",
        parent=session["parent_name"],
        child=session["child_name"],
        active_page="dashboard",
        profile_icon=session.get("profile_icon", "profileicon.png"),
        total_words=stats["total_words"],
        total_minutes=stats["total_minutes"],
        total_active_minutes=stats["total_active_minutes"],
        total_activities=stats["total_activities"],
        activities=activities,
        has_seen_tour=has_seen_tour,
        current_activity_id=current_activity_id,
        default_slide_index=default_slide_index,
        session_chart_data=session_chart_data,
        recent_sessions=recent_sessions
    )

@app.route("/complete-tour", methods=["POST"])
@csrf.exempt
@login_required
def complete_tour():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE users
        SET has_seen_tour = 1
        WHERE user_id = ?
    """, (session["user_id"],))

    conn.commit()
    conn.close()

    return {"success": True}

@app.route("/lessons")
@login_required
def lessons():
    return render_template(
        "lessons.html",
        active_page="lessons",
        parent=session["parent_name"],
        child=session["child_name"],
        profile_icon=session.get("profile_icon", "profileicon.png")
    )


@app.route("/characters")
@login_required
def characters():
    return render_template(
        "characters.html",
        active_page="characters",
        parent=session["parent_name"],
        child=session["child_name"],
        profile_icon=session.get("profile_icon", "profileicon.png")
    )


@app.route("/settings")
@login_required
def settings():
    ensure_settings_columns()

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            email,
            parent_name,
            child_name,
            child_dob,
            child_age,
            parent_pin
        FROM users
        WHERE user_id = ?
    """, (session["user_id"],))

    user = cursor.fetchone()
    conn.close()

    if not user:
        session.clear()
        return redirect("/login")

    child_age = user["child_age"]

    if not child_age:
        child_age = calculate_child_age(user["child_dob"]) or 7

    child_age = max(3, min(12, int(child_age)))

    raw_child_name = str(user["child_name"] or "").strip()

    if raw_child_name.lower() in {"none", "child"}:
        child_name = ""
    else:
        child_name = raw_child_name
        
    status_key = request.args.get("status")
    settings_status, settings_status_type = get_settings_status(status_key)

    return render_template(
        "settings.html",
        active_page="settings",
        parent=user["parent_name"],
        child=child_name,
        email=user["email"],
        child_age=child_age,
        parent_pin=user["parent_pin"] or "",
        has_parent_pin=bool(user["parent_pin"]),
        settings_status=settings_status,
        settings_status_type=settings_status_type,
        profile_icon=session.get("profile_icon", "profileicon.png")
    )

@app.route("/settings/child-profile", methods=["POST"])
@login_required
def update_child_settings():
    ensure_settings_columns()

    child_name = clean_short_setting(request.form.get("child_name"), 40)

    try:
        child_age = int(request.form.get("child_age", 7))
    except (TypeError, ValueError):
        child_age = 7

    child_age = max(3, min(12, child_age))

    if not child_name:
        child_name = session.get("child_name", "Child")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE users
        SET child_name = ?, child_age = ?
        WHERE user_id = ?
    """, (child_name, child_age, session["user_id"]))

    conn.commit()
    conn.close()

    session["child_name"] = child_name

    return redirect(url_for("settings", status="child_saved"))


@app.route("/settings/parent-account", methods=["POST"])
@login_required
def update_parent_account():
    ensure_settings_columns()

    parent_name = clean_short_setting(request.form.get("parent_name"), 50)
    email = clean_short_setting(request.form.get("email"), 120).lower()

    if not parent_name:
        parent_name = session.get("parent_name", "Parent")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT user_id
        FROM users
        WHERE email = ? AND user_id != ?
    """, (email, session["user_id"]))

    existing_user = cursor.fetchone()

    if existing_user:
        conn.close()
        return redirect(url_for("settings", status="email_exists"))

    cursor.execute("""
        UPDATE users
        SET parent_name = ?, email = ?
        WHERE user_id = ?
    """, (parent_name, email, session["user_id"]))

    conn.commit()
    conn.close()

    session["parent_name"] = parent_name

    return redirect(url_for("settings", status="account_saved"))


@app.route("/settings/password", methods=["POST"])
@login_required
def update_parent_password():
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    if new_password != confirm_password:
        return redirect(url_for("settings", status="password_mismatch"))

    password_error = validate_password(new_password)

    if password_error:
        return redirect(url_for("settings", status="password_invalid"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT password
        FROM users
        WHERE user_id = ?
    """, (session["user_id"],))

    user = cursor.fetchone()

    if not user or not check_password_hash(user["password"], current_password):
        conn.close()
        return redirect(url_for("settings", status="password_wrong"))

    new_hash = generate_password_hash(new_password)

    cursor.execute("""
        UPDATE users
        SET password = ?
        WHERE user_id = ?
    """, (new_hash, session["user_id"]))

    conn.commit()
    conn.close()

    return redirect(url_for("settings", status="password_saved"))


@app.route("/update-profile-icon", methods=["POST"])
@csrf.exempt
@login_required
def update_profile_icon():
    icon = request.form.get("icon")

    allowed_icons = {
        "profileicon.png",
        "profileicon1.png",
        "profileicon2.png",
        "profileicon3.png"
    }

    if icon not in allowed_icons:
        return {"success": False, "error": "Invalid icon"}, 400

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE users SET profile_icon = ? WHERE user_id = ?",
        (icon, session["user_id"])
    )

    conn.commit()
    conn.close()

    session["profile_icon"] = icon

    return {"success": True}



def get_has_seen_tour_for_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COALESCE(has_seen_tour, 0) AS has_seen_tour
        FROM users
        WHERE user_id = ?
    """, (user_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return 1

    return row["has_seen_tour"]

@app.route("/delete-account", methods=["POST"])
@login_required
def delete_account():
    user_id = session["user_id"]

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM progress WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        return f"Error deleting account: {e}", 500

    conn.close()
    session.clear()
    return redirect("/login")

@app.route("/restart-activity", methods=["POST"])
@csrf.exempt
@login_required
def restart_activity():
    ensure_matching_game_progress_columns()
    ensure_mystery_animal_progress_columns()
    ensure_guessing_game_progress_columns()

    data = request.get_json(silent=True) or {}
    activity_id = data.get("activity_id")

    if not activity_id:
        return jsonify({"success": False, "error": "Missing activity_id"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT is_unlocked
        FROM progress
        WHERE user_id = ? AND activity_id = ?
    """, (session["user_id"], activity_id))

    progress_row = cursor.fetchone()

    if not progress_row:
        conn.close()
        return jsonify({"success": False, "error": "Activity not found"}), 404

    if not progress_row["is_unlocked"]:
        conn.close()
        return jsonify({"success": False, "error": "Activity is locked"}), 403

    cursor.execute("""
        UPDATE progress
        SET
            is_completed = 0,

            matching_rounds_completed = 0,
            matching_spoken_responses = 0,
            matching_silent_windows = 0,
            matching_wonder_prompts_asked = 0,
            matching_help_prompts_asked = 0,
            matching_clear_prompts_asked = 0,
            matching_child_choice_responses = 0,
            matching_child_opinion_responses = 0,
            matching_clear_child_responses = 0,
            matching_direct_child_question_silences = 0,
            matching_last_stage = 0,
            matching_last_played_at = NULL,

            mystery_animal_rounds_completed = 0,
            mystery_animal_last_played_at = NULL,

            guessing_game_rounds_completed = 0,
            guessing_game_last_played_at = NULL
        WHERE user_id = ? AND activity_id = ?
    """, (session["user_id"], activity_id))

    cursor.execute("""
        UPDATE users
        SET current_activity_id = ?
        WHERE user_id = ?
    """, (activity_id, session["user_id"]))

    conn.commit()
    conn.close()

    session.pop("mystery_animal_history", None)
    session.pop("mystery_animal_state", None)
    session.pop("guessing_game_history", None)
    session.pop("guessing_game_state", None)
    session.modified = True

    return jsonify({
        "success": True,
        "restart_activity": True,
        "activity_id": activity_id
    })

@app.route("/set-current", methods=["POST"])
@csrf.exempt
@login_required
def set_current():
    activity_id = request.json.get("activity_id")

    if not activity_id:
        return {"success": False, "error": "Missing activity_id"}, 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT is_unlocked
        FROM progress
        WHERE user_id = ? AND activity_id = ?
    """, (session["user_id"], activity_id))
    progress_row = cursor.fetchone()

    if not progress_row:
        conn.close()
        return {"success": False, "error": "Activity not found for user"}, 404

    if not progress_row["is_unlocked"]:
        conn.close()
        return {"success": False, "error": "Activity is locked"}, 403

    cursor.execute("""
        UPDATE users
        SET current_activity_id = ?
        WHERE user_id = ?
    """, (activity_id, session["user_id"]))

    conn.commit()
    conn.close()

    return {"success": True}


@app.route("/unlock-activity", methods=["POST"])
@csrf.exempt
@login_required
def unlock_activity():
    data = request.get_json(silent=True) or {}
    activity_id = data.get("activity_id")

    if not activity_id:
        return {"success": False, "error": "Missing activity_id"}, 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT activity_id, activity_order
        FROM activity
        WHERE activity_id = ? AND is_active = 1
    """, (activity_id,))
    activity = cursor.fetchone()

    if not activity:
        conn.close()
        return {"success": False, "error": "Activity does not exist"}, 404

    cursor.execute("""
        INSERT OR IGNORE INTO progress (
            user_id,
            activity_id,
            is_unlocked,
            is_completed,
            words_spoken,
            minutes_spoken,
            active_minutes,
            time_spent_on_activity
        )
        VALUES (?, ?, 0, 0, 0, 0, 0, 0)
    """, (session["user_id"], activity_id))

    if activity["activity_order"] > 1:
        cursor.execute("""
            SELECT p.is_unlocked
            FROM progress p
            JOIN activity a ON p.activity_id = a.activity_id
            WHERE p.user_id = ?
              AND a.activity_order = ?
              AND a.is_active = 1
        """, (
            session["user_id"],
            activity["activity_order"] - 1
        ))

        previous_row = cursor.fetchone()

        if not previous_row or not previous_row["is_unlocked"]:
            conn.close()
            return {
                "success": False,
                "error": "Previous activity must be unlocked first"
            }, 403

    cursor.execute("""
        UPDATE progress
        SET is_unlocked = 1
        WHERE user_id = ? AND activity_id = ?
    """, (session["user_id"], activity_id))

    cursor.execute("""
        UPDATE users
        SET current_activity_id = ?
        WHERE user_id = ?
    """, (activity_id, session["user_id"]))

    conn.commit()
    conn.close()

    return {"success": True}

@app.after_request
def add_no_chache_headers(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age-0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.route("/activity/<int:activity_id>")
@login_required
def open_activity(activity_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM activity
        WHERE activity_id = ?
          AND is_active = 1
    """, (activity_id,))
    activity = cursor.fetchone()

    if activity is None:
        conn.close()
        abort(404)

    cursor.execute("""
        SELECT is_unlocked
        FROM progress
        WHERE user_id = ? AND activity_id = ?
    """, (session["user_id"], activity_id))
    progress = cursor.fetchone()

    conn.close()

    if not progress or not progress["is_unlocked"]:
        return redirect(url_for("dashboard"))

    template_file = activity["template_file"]

    session["needs_parent_pin_for_dashboard"] = True
    session.pop("parent_pin_dashboard_verified", None)

    return render_template(
        template_file,
        activity=activity,
        parent=session["parent_name"],
        child=session["child_name"],
        active_page="dashboard",
        profile_icon=session.get("profile_icon", "profileicon.png")
    )

def calculate_child_age(child_dob):
    if not child_dob:
        return None

    try:
        dob = datetime.strptime(child_dob, "%Y-%m-%d").date()
        today = date.today()

        age = today.year - dob.year

        if (today.month, today.day) < (dob.month, dob.day):
            age -= 1

        return age
    except ValueError:
        return None
    
def generate_star_voice_elevenlabs(text):
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "piI8Kku0DcvcL6TTSeQt")

    response = eleven_client.text_to_speech.convert(
        voice_id=voice_id,
        text=text,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
        voice_settings={
            "stability": 0.99,
            "similarity_boost": 0.88,
            "style": 0.0,
            "use_speaker_boost": False
        }
    )

    return b"".join(response)

# =========================
# Guessing Game 2 — Toy Store Worker Guessing Game
# Single full backend block
# Frontend routes:
#   /api/guessing-game-2/thinking-audio
#   /api/guessing-game-2/message
#   /api/guessing-game-2/transcribe
# Requires:
#   templates/guessing_game_2.html
#   static/css/guessing_game_2.css
#   static/js/guessing_game_2.js
# Activity name in database:
#   guessing_game_2
# =========================

def generate_guessing_game_2_voice_elevenlabs(text, game_complete=False, thinking=False):
    voice_id = os.getenv("TOY_TRIVIA_VOICE_ID") or os.getenv("TOY_WORKER_VOICE_ID")

    if not voice_id:
        voice_id = os.getenv("ELEVENLABS_VOICE_ID", "piI8Kku0DcvcL6TTSeQt")

    if game_complete:
        voice_settings = {
            "stability": 0.84,
            "similarity_boost": 0.90,
            "style": 0.25,
            "use_speaker_boost": False
        }
    elif thinking:
        voice_settings = {
            "stability": 0.98,
            "similarity_boost": 0.88,
            "style": 0.02,
            "use_speaker_boost": False
        }
    else:
        voice_settings = {
            "stability": 0.94,
            "similarity_boost": 0.90,
            "style": 0.06,
            "use_speaker_boost": False
        }

    response = eleven_client.text_to_speech.convert(
        voice_id=voice_id,
        text=text,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
        voice_settings=voice_settings
    )

    return b"".join(response)


GUESSING_GAME_2_MAX_ROUNDS = 3

GUESSING_GAME_2_OBJECT_PROFILES = {
    "teddy_bear": {
        "display": "teddy bear",
        "aliases": {"teddy", "teddy bear", "bear"},
        "tags": {"toy_store", "toy", "stuffed", "soft", "fabric", "animal", "hug", "medium", "brown"},
        "colors": {"brown", "tan", "white"},
        "hints": [
            "This is soft and good for hugs.",
            "It is a stuffed animal.",
            "It often looks like a bear."
        ]
    },
    "doll": {
        "display": "doll",
        "aliases": {"doll", "baby doll"},
        "tags": {"toy_store", "toy", "person", "clothes", "hair", "plastic", "fabric", "small", "pretend"},
        "colors": {"pink", "purple", "blue", "brown"},
        "hints": [
            "Kids can pretend to take care of this.",
            "It may have clothes or hair.",
            "It looks a little like a person."
        ]
    },
    "toy_car": {
        "display": "toy car",
        "aliases": {"toy car", "car", "race car", "vehicle"},
        "tags": {"toy_store", "toy", "vehicle", "wheels", "plastic", "metal", "small", "roll", "fast"},
        "colors": {"red", "blue", "black", "yellow", "green"},
        "hints": [
            "This can roll across the floor.",
            "It has wheels.",
            "It is a small vehicle toy."
        ]
    },
    "train": {
        "display": "toy train",
        "aliases": {"train", "toy train", "train set"},
        "tags": {"toy_store", "toy", "vehicle", "wheels", "track", "long", "plastic", "metal", "medium"},
        "colors": {"red", "blue", "black", "green"},
        "hints": [
            "This might move on a track.",
            "It can have cars connected together.",
            "It is a vehicle toy."
        ]
    },
    "ball": {
        "display": "ball",
        "aliases": {"ball", "toy ball", "bouncy ball"},
        "tags": {"toy_store", "toy", "round", "bounce", "sports", "plastic", "rubber", "small", "medium"},
        "colors": {"red", "blue", "green", "yellow", "orange"},
        "hints": [
            "This is round.",
            "You can throw or roll it.",
            "Some kinds can bounce."
        ]
    },
    "blocks": {
        "display": "blocks",
        "aliases": {"blocks", "building blocks", "block", "legos", "lego"},
        "tags": {"toy_store", "toy", "build", "stack", "pieces", "plastic", "wood", "small", "colorful"},
        "colors": {"red", "blue", "green", "yellow", "purple"},
        "hints": [
            "You can stack these.",
            "You can build things with them.",
            "There is usually more than one piece."
        ]
    },
    "puzzle": {
        "display": "puzzle",
        "aliases": {"puzzle", "jigsaw puzzle", "puzzle pieces"},
        "tags": {"toy_store", "toy", "game", "pieces", "picture", "flat", "paper", "cardboard", "table"},
        "colors": {"red", "blue", "green", "yellow", "purple"},
        "hints": [
            "This has pieces that fit together.",
            "It can make a picture when it is finished.",
            "You might do it on a table."
        ]
    },
    "robot": {
        "display": "robot",
        "aliases": {"robot", "toy robot"},
        "tags": {"toy_store", "toy", "technology", "electric", "battery", "buttons", "plastic", "metal", "move", "medium"},
        "colors": {"silver", "gray", "blue", "red", "white"},
        "hints": [
            "This might have buttons.",
            "It may look like a machine person.",
            "Some kinds can move or make sounds."
        ]
    },
    "action_figure": {
        "display": "action figure",
        "aliases": {"action figure", "figure", "superhero", "toy figure"},
        "tags": {"toy_store", "toy", "person", "plastic", "small", "pretend", "move", "superhero"},
        "colors": {"red", "blue", "black", "green", "yellow"},
        "hints": [
            "Kids can use this for pretend adventures.",
            "It is a small toy person or character.",
            "Its arms or legs might move."
        ]
    },
    "board_game": {
        "display": "board game",
        "aliases": {"board game", "game", "box game"},
        "tags": {"toy_store", "toy", "game", "box", "pieces", "cards", "table", "flat", "group"},
        "colors": {"red", "blue", "green", "yellow", "black"},
        "hints": [
            "More than one person can play this.",
            "It may come in a box.",
            "It can have cards, pieces, or a board."
        ]
    },
    "yo_yo": {
        "display": "yo-yo",
        "aliases": {"yo-yo", "yoyo", "yo yo"},
        "tags": {"toy_store", "toy", "string", "round", "small", "plastic", "skill", "up_down"},
        "colors": {"red", "blue", "green", "yellow", "black"},
        "hints": [
            "This toy has a string.",
            "It can go down and come back up.",
            "You hold the string with your finger."
        ]
    }
}


def guessing_game_2_pick_non_repeating_line(options, recent_messages=None):
    import random

    recent_set = set(recent_messages or [])
    fresh_options = [line for line in options if line not in recent_set]

    if fresh_options:
        return random.choice(fresh_options)

    return random.choice(options)


def normalize_guessing_game_2_text(text):
    text = re.sub(r"\s+", " ", str(text or "")).strip().lower()
    text = text.replace("’", "'")
    text = re.sub(r"[^a-z0-9' -]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def guessing_game_2_words(text):
    return set(re.findall(r"[a-z']+", normalize_guessing_game_2_text(text)))


def get_guessing_game_2_default_state(rounds_completed=0, used_toys=None):
    import random

    used_so_far = [
        obj for obj in list(used_toys or [])
        if obj in GUESSING_GAME_2_OBJECT_PROFILES
    ]

    toy_names = [
        obj for obj in GUESSING_GAME_2_OBJECT_PROFILES.keys()
        if obj not in set(used_so_far)
    ]

    if not toy_names:
        toy_names = list(GUESSING_GAME_2_OBJECT_PROFILES.keys())

    secret_toy = random.choice(toy_names)
    used_toys_for_session = (used_so_far + [secret_toy])[-GUESSING_GAME_2_MAX_ROUNDS:]

    return {
        "stage": "intro",
        "secret_toy": secret_toy,
        "used_toys": used_toys_for_session,
        "rounds_completed": rounds_completed_int,
        "questions_asked": 0,
        "comfortable_question_count": 0,
        "unclear_or_silent_count": 0,
        "unclear_streak": 0,
        "hint_count": 0,
        "wrong_guess_count": 0,
        "wrong_guesses": [],
        "asked_questions": [],
        "asked_topics": [],
        "recent_hints": [],
        "recent_round_prompts": [],
        "recent_support_lines": [],
        "recent_good_question_prefixes": [],
        "recent_suggestion_topics": [],
        "last_hint_offer_question_count": 0,
        "recent_follow_ups": [],
        "game_complete": False,
        "last_response_mode": "none"
    }


def get_guessing_game_2_profile(game_state):
    secret_toy = normalize_guessing_game_2_text(game_state.get("secret_toy", "teddy_bear"))

    if secret_toy not in GUESSING_GAME_2_OBJECT_PROFILES:
        secret_toy = "teddy_bear"
        game_state["secret_toy"] = secret_toy

    return GUESSING_GAME_2_OBJECT_PROFILES[secret_toy]


def is_guessing_game_2_unclear_or_silent(text):
    lowered = normalize_guessing_game_2_text(text)

    if not lowered:
        return True

    unclear_phrases = {
        "i don't know", "i dont know", "i do not know", "don't know", "dont know",
        "do not know", "idk", "not sure", "i'm not sure", "im not sure",
        "maybe", "hmm", "hm", "mm", "mmm", "uh", "um"
    }

    if lowered in unclear_phrases:
        return True

    words = re.findall(r"[a-z']+", lowered)
    filler_words = {"hmm", "hm", "mm", "mmm", "uh", "um", "like", "wait"}

    return bool(words) and all(word in filler_words for word in words)


def is_guessing_game_2_hint_request(text):
    lowered = normalize_guessing_game_2_text(text)

    hint_phrases = [
        "hint", "clue", "give me a hint", "give me a clue",
        "can i have a hint", "can i have a clue", "tell me something",
        "help me", "i need help"
    ]

    return any(phrase in lowered for phrase in hint_phrases)


def get_guessing_game_2_named_toy(text):
    lowered = normalize_guessing_game_2_text(text)
    words = guessing_game_2_words(lowered)

    for toy_key, profile in GUESSING_GAME_2_OBJECT_PROFILES.items():
        for alias in profile.get("aliases", set()):
            alias_clean = normalize_guessing_game_2_text(alias)
            alias_words = set(re.findall(r"[a-z']+", alias_clean))

            if not alias_clean:
                continue

            if " " in alias_clean and alias_clean in lowered:
                return toy_key

            if alias_clean in words:
                return toy_key

            if alias_words and alias_words.issubset(words) and len(alias_words) > 1:
                return toy_key

    return None


def is_guessing_game_2_direct_guess(text):
    lowered = normalize_guessing_game_2_text(text)
    named_toy = get_guessing_game_2_named_toy(lowered)

    if not named_toy:
        return False

    direct_guess_phrases = [
        "is it", "is your toy", "is your thing", "are you thinking of",
        "i guess", "my guess", "i think", "it's", "it is", "maybe",
        "the toy is", "the thing is"
    ]

    if any(phrase in lowered for phrase in direct_guess_phrases):
        return True

    words = re.findall(r"[a-z']+", lowered)
    return len(words) <= 4


def is_guessing_game_2_question(text):
    lowered = normalize_guessing_game_2_text(text)
    words = re.findall(r"[a-z']+", lowered)

    if not words:
        return False

    question_starters = {
        "is", "are", "do", "does", "can", "could", "would",
        "has", "have", "what", "where", "how", "did", "will"
    }

    return words[0] in question_starters or "?" in str(text)


def guessing_game_2_question_key(text):
    lowered = normalize_guessing_game_2_text(text)
    lowered = re.sub(
        r"\b(the|a|an|your|toy|thing|it|does|do|is|are|can|could|would|has|have|what|where|how)\b",
        " ",
        lowered
    )
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered[:80]


def get_guessing_game_2_question_topic(text):
    words = guessing_game_2_words(text)

    if words & {"big", "small", "little", "tiny", "large", "huge", "size"}:
        return "size"

    if words & {"color", "colour", "black", "white", "brown", "orange", "yellow", "green", "gray", "grey", "blue", "red", "pink", "purple", "clear", "silver"}:
        return "color"

    if words & {"where", "store", "shelf", "box", "aisle", "toy", "toys", "floor", "table"}:
        return "place"

    if words & {"play", "pretend", "build", "stack", "roll", "bounce", "throw", "use", "used", "move", "button", "buttons", "game", "puzzle"}:
        return "use"

    if words & {"wood", "plastic", "metal", "paper", "cardboard", "fabric", "soft", "hard", "rubber", "flat", "screen", "buttons", "string"}:
        return "material"

    return "general"


def remember_guessing_game_2_question_topic(text, game_state):
    topic = get_guessing_game_2_question_topic(text)

    if topic:
        game_state.setdefault("asked_topics", []).append(topic)
        game_state["asked_topics"] = game_state["asked_topics"][-10:]

    return topic


def calm_guessing_game_2_line(text, game_complete=False):
    text = re.sub(r"\s+", " ", str(text or "")).strip()

    if not text:
        return "I'm thinking of a toy you can find in a toy store."

    replacements = {
        "Amazing": "Nice",
        "amazing": "nice",
        "Awesome": "Nice",
        "awesome": "nice",
        "Wow": "Hmm",
        "wow": "hmm",
        "Interesting question.": "Good question.",
        "Interesting.": "",
        "That is interesting.": "",
        "That gives me something to think about.": "",
        "Okay, that helps.": "",
        "That helps.": "",
        "I can work with that.": "",
        "Good job asking": "Good question",
        "Great job asking": "Great question",
        "Good job talking": "Thank you",
        "Great job talking": "Thank you",
        "Good job using your words": "Thank you",
        "I couldn't hear you": "That's okay",
        "I could not hear you": "That's okay"
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        text = "Good question."

    if not game_complete:
        text = text.replace("!", ".")

    if text.count("!") > 1:
        first = text.find("!")
        text = text[:first + 1] + text[first + 1:].replace("!", ".")

    return text[:300].strip()


def get_guessing_game_2_specific_color_answer(text, game_state):
    words = guessing_game_2_words(text)
    profile = get_guessing_game_2_profile(game_state)

    color_words = {
        "black", "white", "brown", "orange", "yellow", "green", "gray", "grey",
        "blue", "red", "pink", "purple", "clear", "silver", "tan"
    }

    asked_colors = [color for color in color_words if color in words]
    colors_for_secret = profile.get("colors", set())

    if asked_colors:
        spoken_color = asked_colors[0]
        normalized_color = "gray" if spoken_color == "grey" else spoken_color
        normalized_colors_for_secret = {
            "gray" if color == "grey" else color
            for color in colors_for_secret
        }

        if normalized_color in normalized_colors_for_secret:
            return {
                "type": "answer",
                "message": f"Yes, it can be {normalized_color}.",
                "question_answered": True
            }

        return {
            "type": "answer",
            "message": f"No, it is not usually {normalized_color}.",
            "question_answered": True
        }

    if "color" in words or "colour" in words:
        normalized_colors = sorted({
            "gray" if color == "grey" else color
            for color in colors_for_secret
        })

        if not normalized_colors:
            message = "It can be different colors."
        elif len(normalized_colors) == 1:
            message = f"It is often {normalized_colors[0]}."
        else:
            message = f"It can be {normalized_colors[0]}."

        return {
            "type": "answer",
            "message": message,
            "question_answered": True
        }

    return None


def get_guessing_game_2_ai_question_answer(text, game_state):
    import random

    profile = get_guessing_game_2_profile(game_state)
    secret_toy = game_state.get("secret_toy", "teddy_bear")
    display = profile.get("display", secret_toy)
    tags = sorted(list(profile.get("tags", [])))
    asked_topics = set(game_state.get("asked_topics", []))
    recent_support_lines = list(game_state.get("recent_support_lines", []))[-5:]

    topic_options = [
        ("place", "You can ask where I might find it in the toy store."),
        ("use", "You can ask what it is used for."),
        ("color", "You can ask what color it is."),
        ("size", "You can ask about its size."),
        ("material", "You can ask what it is made of."),
        ("general", "You can ask me a yes or no toy question.")
    ]

    fresh_topic_lines = [
        line for topic, line in topic_options
        if topic not in asked_topics and line not in recent_support_lines
    ]

    general_fallbacks = [
        "I can answer toy questions best.",
        "That one is tricky for this game.",
        "I might give away too much with that one.",
        "Try asking one toy clue question.",
        "You can ask me a yes or no question about it."
    ]

    def fallback_support():
        if fresh_topic_lines:
            line = random.choice(fresh_topic_lines)
        else:
            fresh = [item for item in general_fallbacks if item not in recent_support_lines]
            line = random.choice(fresh or general_fallbacks)

        game_state["recent_support_lines"] = (recent_support_lines + [line])[-5:]

        return {
            "type": "support",
            "message": line,
            "question_answered": False
        }

    try:
        system_prompt = f"""
You are a warm cartoon toy store worker playing Toy Guessing Game.

The toy store worker is thinking of one secret toy a child can find in a toy store.
The child asks questions to collect clues and guess what it is.

Secret toy:
{display}

Secret toy tags:
{tags}

Rules:
- Answer the child's question naturally and briefly.
- Do not reveal the secret toy's name unless the child directly guessed it.
- If the child asks a yes/no question, answer yes or no clearly.
- If the child asks an open question, give a tiny answer, not a big clue.
- Keep the answer to 1 short sentence.
- Do not invite another question every time.
- Do not say "interesting."
- Do not mention therapy, anxiety, selective mutism, treatment, progress, confidence, bravery, or speaking.
- Do not praise the child for talking.
- Keep the focus on the guessing game and the toy.
- Use calm periods, not excited exclamation marks.

Output JSON only:
{{
  "type": "answer",
  "message": "Toy Store Worker's spoken line",
  "question_answered": true
}}
"""

        user_prompt = f"""
Child question:
{text}

Recent support lines to avoid:
{recent_support_lines}

Answer the child's question about the secret toy without revealing its name.
"""

        response = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )

        raw = response.output_text.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()

        try:
            parsed = json.loads(raw)
        except Exception:
            return fallback_support()

        message = re.sub(r"\s+", " ", str(parsed.get("message", ""))).strip()

        if not message:
            return fallback_support()

        banned_bits = [
            "interesting",
            "something to think about",
            "good job talking",
            "great job talking",
            "use your words"
        ]

        lowered_message = message.lower()

        if any(bit in lowered_message for bit in banned_bits):
            return fallback_support()

        guessed_toy = get_guessing_game_2_named_toy(text)

        if guessed_toy != secret_toy:
            message = re.sub(
                rf"\b{re.escape(display)}s?\b",
                "it",
                message,
                flags=re.IGNORECASE
            )

        return {
            "type": parsed.get("type", "answer"),
            "message": calm_guessing_game_2_line(message),
            "question_answered": bool(parsed.get("question_answered", True))
        }

    except Exception as e:
        print("Guessing Game 2 flexible answer error:", repr(e))
        return fallback_support()


def answer_guessing_game_2_question(text, game_state):
    profile = get_guessing_game_2_profile(game_state)
    tags = profile.get("tags", set())
    lowered = normalize_guessing_game_2_text(text)
    words = guessing_game_2_words(lowered)
    secret_toy = game_state.get("secret_toy")

    named_toy = get_guessing_game_2_named_toy(lowered)

    if named_toy:
        if named_toy == secret_toy:
            return {
                "type": "correct_guess",
                "message": f"Yes, it is a {profile['display']}. You got it.",
                "question_answered": True
            }

        return {
            "type": "wrong_guess",
            "message": f"Not quite, it is not a {GUESSING_GAME_2_OBJECT_PROFILES[named_toy]['display']}.",
            "wrong_guess": named_toy,
            "question_answered": True
        }

    color_answer = get_guessing_game_2_specific_color_answer(text, game_state)

    if color_answer:
        return color_answer

    if (
        ("how" in words and ("big" in words or "small" in words or "size" in words))
        or ("big" in words and "small" in words)
        or ("size" in words)
    ):
        if "big" in tags or "large" in tags:
            message = "It is pretty big."
        elif "medium" in tags:
            message = "It is medium sized."
        elif "small" in tags:
            message = "It is small."
        else:
            message = "It is not especially big."

        return {"type": "answer", "message": message, "question_answered": True}

    if "where" in words or words & {"store", "shelf", "box", "aisle", "toy", "toys", "floor", "table"}:
        if "toy_store" in tags:
            message = "You could find it in a toy store."
        elif "box" in tags:
            message = "It might come in a box."
        elif "table" in tags:
            message = "You might play with it on a table or floor."
        else:
            message = "You could find it near other toys."

        return {"type": "answer", "message": message, "question_answered": True}

    toy_checks = [
        ({"wheel", "wheels", "roll", "rolling"}, {"wheels", "roll"}, "Yes, it can roll or has wheels.", "No, wheels are not a big clue."),
        ({"stuffed", "plush", "soft"}, {"stuffed", "soft"}, "Yes, it is soft or stuffed.", "No, it is not really a stuffed toy."),
        ({"build", "stack", "blocks", "lego", "legos"}, {"build", "stack", "pieces"}, "Yes, you can build or stack with it.", "No, it is not mainly for building."),
        ({"piece", "pieces", "card", "cards", "board"}, {"pieces", "cards", "game"}, "Yes, it can have pieces, cards, or a board.", "No, pieces are not the main clue."),
        ({"robot", "button", "buttons", "battery", "sound", "sounds", "move"}, {"technology", "electric", "battery", "buttons", "move"}, "Yes, it might have buttons, batteries, or moving parts.", "No, it is not really an electronic toy."),
        ({"round", "bounce", "bouncy"}, {"round", "bounce"}, "Yes, round or bouncy is a good clue.", "No, it is not mainly round or bouncy."),
        ({"pretend", "character", "person", "superhero"}, {"pretend", "person", "superhero"}, "Yes, you can use it for pretend play.", "No, pretend play is not the main clue."),
        ({"string", "yo", "yoyo"}, {"string", "up_down"}, "Yes, it has a string.", "No, it does not use a string."),
        ({"wood", "wooden"}, {"wood"}, "Yes, it can be made of wood.", "No, it is not usually wooden."),
        ({"plastic"}, {"plastic"}, "Yes, it can have plastic.", "No, plastic is not a big clue."),
        ({"metal"}, {"metal"}, "Yes, it can have metal.", "No, it does not usually have metal."),
        ({"fabric", "cloth"}, {"fabric"}, "Yes, it can be made of fabric.", "No, it is not usually fabric."),
        ({"game", "play"}, {"game", "toy", "pretend"}, "Yes, it is something you can play with.", "Yes, it is still something you can play with."),
        ({"box"}, {"box"}, "Yes, it might come in a box.", "No, a box is not the main clue."),
        ({"animal"}, {"animal"}, "Yes, it looks like an animal.", "No, it does not mainly look like an animal."),
        ({"vehicle", "car", "train", "truck"}, {"vehicle"}, "Yes, it is like a vehicle.", "No, it is not really a vehicle toy.")
    ]

    for trigger_words, needed_tags, yes_line, no_line in toy_checks:
        if words & trigger_words:
            if tags & needed_tags:
                return {"type": "answer", "message": yes_line, "question_answered": True}

            return {"type": "answer", "message": no_line, "question_answered": True}

    return get_guessing_game_2_ai_question_answer(text, game_state)


def get_guessing_game_2_hint(game_state):
    import random

    profile = get_guessing_game_2_profile(game_state)
    recent_hints = list(game_state.get("recent_hints", []))
    hints = list(profile.get("hints", []))

    fresh = [hint for hint in hints if hint not in recent_hints]

    if fresh:
        hint = random.choice(fresh)
    elif hints:
        hint = random.choice(hints)
    else:
        hint = "This is something many kids know from a toy store."

    game_state["recent_hints"] = (recent_hints + [hint])[-5:]
    game_state["hint_count"] = int(game_state.get("hint_count", 0)) + 1

    return hint


def classify_guessing_game_2_round_choice(text):
    lowered = normalize_guessing_game_2_text(text)
    words = guessing_game_2_words(lowered)

    if not lowered:
        return "unclear"

    stop_words = {"stop", "done", "finish", "finished", "end", "quit", "leave", "dashboard", "no", "nope", "nah"}
    same_game_words = {"again", "same", "replay", "more", "continue", "yes", "yeah", "yep", "yup", "sure", "okay", "ok", "alright", "fine", "good", "cool", "this"}

    if words & stop_words:
        return "stop"

    if words & same_game_words:
        return "same_game"

    same_game_phrases = [
        "play again", "play another round", "another round", "one more round",
        "same game", "let's play", "lets play", "keep playing", "do it again", "try again"
    ]

    if any(phrase in lowered for phrase in same_game_phrases):
        return "same_game"

    return "unclear"


def maybe_add_guessing_game_2_good_question_prefix(message, game_state):
    import random

    question_count = int(game_state.get("questions_asked", 0))

    should_add = (
        question_count <= 2
        or question_count in {4, 6, 8}
        or random.random() < 0.55
    )

    if not should_add:
        return message

    lowered = normalize_guessing_game_2_text(message)

    if lowered.startswith(("that's a good question", "that is a good question", "good question", "great question", "nice question")):
        return message

    prefixes = [
        "That's a good question.",
        "Good question.",
        "Great question.",
        "Nice question.",
        "That's a smart thing to ask."
    ]

    recent = list(game_state.get("recent_good_question_prefixes", []))[-3:]
    fresh = [prefix for prefix in prefixes if prefix not in recent]
    prefix = random.choice(fresh or prefixes)

    game_state["recent_good_question_prefixes"] = (recent + [prefix])[-3:]

    return f"{prefix} {message}"


def get_guessing_game_2_follow_up_after_answer(game_state):
    questions_asked = int(game_state.get("questions_asked", 0))
    wrong_guess_count = int(game_state.get("wrong_guess_count", 0))
    total_child_turns = questions_asked + wrong_guess_count
    last_hint_offer = int(game_state.get("last_hint_offer_question_count", 0))

    if total_child_turns >= 3 and total_child_turns - last_hint_offer >= 3:
        game_state["last_hint_offer_question_count"] = total_child_turns

        options = [
            "Let me know whenever you want a hint.",
            "Let me know if you want a clue.",
            "You can ask another question or guess what it is.",
            "Whenever you want a clue, you can ask me."
        ]

        recent = list(game_state.get("recent_follow_ups", []))[-4:]
        follow_up = guessing_game_2_pick_non_repeating_line(options, recent)
        game_state["recent_follow_ups"] = (recent + [follow_up])[-4:]

        return follow_up

    return ""


def make_guessing_game_2_audio_response(
    message,
    stage,
    response_mode,
    expects_response,
    game_complete,
    game_state,
    history,
    event_type="server_response",
    child_response="",
    next_event=None,
    pause_before_next_ms=None,
    next_url=None,
    redirect_after_ms=None,
    session_done=False
):
    message = calm_guessing_game_2_line(message, game_complete=game_complete)

    history.append({
        "event_type": event_type,
        "child_response": child_response,
        "toy_worker": message,
        "stage": stage,
        "response_mode": response_mode,
        "game_complete": game_complete,
        "session_done": session_done
    })

    game_state["stage"] = stage
    game_state["last_response_mode"] = response_mode
    game_state["game_complete"] = game_complete

    session["guessing_game_2_history"] = history[-20:]
    session["guessing_game_2_state"] = game_state
    session.modified = True

    audio_bytes = generate_guessing_game_2_voice_elevenlabs(
        message,
        game_complete=game_complete
    )
    audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

    payload = {
        "success": True,
        "message": message,
        "audio": f"data:audio/mpeg;base64,{audio_base64}",
        "stage": stage,
        "expects_response": expects_response,
        "response_mode": response_mode,
        "game_complete": game_complete,
        "session_done": session_done,
        "offer_next_game": False,
        "game_state": game_state
    }

    if next_event:
        payload["next_event"] = next_event

    if pause_before_next_ms is not None:
        payload["pause_before_next_ms"] = pause_before_next_ms

    if next_url:
        payload["next_url"] = next_url

    if redirect_after_ms is not None:
        payload["redirect_after_ms"] = redirect_after_ms

    return jsonify(payload)


def unlock_guessing_game_2_next_activity_for_user():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT activity_id, scene_id, activity_order
            FROM activity
            WHERE activity_name = ?
              AND is_active = 1
            LIMIT 1
        """, ("guessing_game_2",))

        current_activity = cursor.fetchone()

        if not current_activity:
            conn.close()
            return False

        cursor.execute("""
            SELECT activity_id
            FROM activity
            WHERE is_active = 1
              AND (
                scene_id > ?
                OR (scene_id = ? AND activity_order > ?)
              )
            ORDER BY scene_id ASC, activity_order ASC
            LIMIT 1
        """, (
            current_activity["scene_id"],
            current_activity["scene_id"],
            current_activity["activity_order"]
        ))

        next_activity = cursor.fetchone()

        if not next_activity:
            conn.close()
            return False

        next_activity_id = next_activity["activity_id"]

        cursor.execute("""
            INSERT OR IGNORE INTO progress (
                user_id,
                activity_id,
                is_unlocked,
                is_completed,
                words_spoken,
                minutes_spoken,
                active_minutes,
                time_spent_on_activity
            )
            VALUES (?, ?, 1, 0, 0, 0, 0, 0)
        """, (session["user_id"], next_activity_id))

        cursor.execute("""
            UPDATE progress
            SET is_unlocked = 1
            WHERE user_id = ? AND activity_id = ?
        """, (session["user_id"], next_activity_id))

        cursor.execute("""
            UPDATE users
            SET current_activity_id = ?
            WHERE user_id = ?
        """, (next_activity_id, session["user_id"]))

        conn.commit()
        conn.close()

        return True

    except Exception as e:
        print("Could not unlock next Guessing Game 2 activity:", repr(e))
        return False


def make_guessing_game_2_correct_round_response(
    profile,
    game_state,
    history,
    event_type,
    child_response,
    base_message
):
    rounds_completed = int(game_state.get("rounds_completed", 0)) + 1
    rounds_completed = save_guessing_game_progress_for_user(rounds_completed)
    game_state["rounds_completed"] = rounds_completed
    game_state["game_complete"] = True

    if rounds_completed >= GUESSING_GAME_2_MAX_ROUNDS:
        unlock_guessing_game_2_next_activity_for_user()

        message = (
            f"{base_message} "
            "That was our last one for today. "
            "This was a fun call. I'll see you next time. Bye."
        )

        return make_guessing_game_2_audio_response(
            message=message,
            stage="session_done",
            response_mode="none",
            expects_response=False,
            game_complete=True,
            game_state=game_state,
            history=history,
            event_type=event_type,
            child_response=child_response,
            next_url=url_for("dashboard"),
            redirect_after_ms=1800,
            session_done=True
        )

    if rounds_completed == GUESSING_GAME_2_MAX_ROUNDS - 1:
        message = f"{base_message} Do you want to play one last round before we end the call?"
    else:
        message = f"{base_message} Do you want to play another round?"

    return make_guessing_game_2_audio_response(
        message=message,
        stage="round_choice",
        response_mode="round_choice_voice",
        expects_response=True,
        game_complete=True,
        game_state=game_state,
        history=history,
        event_type=event_type,
        child_response=child_response
    )


@app.route("/api/guessing-game-2/thinking-audio", methods=["GET"])
@csrf.exempt
@login_required
@limiter.limit("50 per minute")
def guessing_game_2_thinking_audio():
    import hashlib
    import random

    thinking_lines = ["Hmm."]

    avoid_raw = request.args.get("avoid", "")
    avoid_lines = {
        re.sub(r"\s+", " ", item).strip().lower()
        for item in avoid_raw.split("|")
        if item.strip()
    }

    fresh_lines = [
        line for line in thinking_lines
        if re.sub(r"\s+", " ", line).strip().lower() not in avoid_lines
    ]

    if not fresh_lines:
        fresh_lines = thinking_lines

    line = random.choice(fresh_lines)
    cache_dir = os.path.join(BASE_DIR, "static", "audio", "guessing_game_2_thinking")
    os.makedirs(cache_dir, exist_ok=True)

    voice_id = (
        os.getenv("TOY_TRIVIA_VOICE_ID")
        or os.getenv("TOY_WORKER_VOICE_ID")
        or os.getenv("ELEVENLABS_VOICE_ID", "piI8Kku0DcvcL6TTSeQt")
    )

    cache_key = f"guessing-game-2-thinking-v1:{voice_id}:{line}"
    filename = hashlib.md5(cache_key.encode("utf-8")).hexdigest() + ".mp3"
    filepath = os.path.join(cache_dir, filename)

    try:
        if not os.path.exists(filepath):
            audio_bytes = generate_guessing_game_2_voice_elevenlabs(line, thinking=True)

            with open(filepath, "wb") as f:
                f.write(audio_bytes)

        return jsonify({
            "success": True,
            "line": line,
            "audio_url": url_for(
                "static",
                filename=f"audio/guessing_game_2_thinking/{filename}"
            )
        })

    except Exception as e:
        print("Guessing Game 2 thinking audio error:", repr(e))
        return jsonify({
            "success": False,
            "error": "Could not generate thinking audio"
        }), 500


@app.route("/api/guessing-game-2/message", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("30 per minute")
def guessing_game_2_message():
    data = request.get_json(silent=True) or {}

    event_type = re.sub(r"\s+", " ", str(data.get("event_type", "intro") or "intro")).strip()
    child_response = re.sub(r"\s+", " ", str(data.get("child_response", "") or "")).strip()
    previous_response_mode = re.sub(r"\s+", " ", str(data.get("response_mode", "none") or "none")).strip()

    allowed_events = {"intro", "restart", "first_prompt", "child_answer", "no_response"}

    if event_type not in allowed_events:
        return jsonify({"success": False, "error": "Invalid event_type"}), 400

    if event_type in {"intro", "restart"}:
        session.pop("guessing_game_2_history", None)
        session.pop("guessing_game_2_state", None)
        history = []
        game_state = get_guessing_game_2_default_state(rounds_completed=0)
        child_response = ""
        previous_response_mode = "none"
    else:
        history = session.get("guessing_game_2_history", [])
        game_state = session.get(
            "guessing_game_2_state",
            get_guessing_game_2_default_state()
        )

    profile = get_guessing_game_2_profile(game_state)

    if event_type in {"intro", "restart"}:
        intro_options = [
            "Hi, I'm the toy store worker. Let's play a guessing game. I'm thinking of a toy you can find in a toy store. Ask me questions so you can guess what it is.",
            "Hi, I'm the toy store worker. I picked a toy you can find in a toy store. Ask me questions, and when you know it, make a guess.",
            "Hi, I'm the toy store worker. I'm thinking of a toy from the toy store. Your job is to ask questions and guess what it is.",
            "Hi, I'm the toy store worker. I picked one toy. Ask me questions to get clues, then guess what it is."
        ]

        message = guessing_game_2_pick_non_repeating_line(
            intro_options,
            [item.get("toy_worker", "") for item in history[-8:] if isinstance(item, dict)]
        )

        try:
            return make_guessing_game_2_audio_response(
                message=message,
                stage="intro",
                response_mode="none",
                expects_response=False,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type=event_type,
                child_response="",
                next_event="first_prompt",
                pause_before_next_ms=2200
            )

        except Exception as e:
            print("Guessing Game 2 intro TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate Toy Store Worker intro"
            }), 500

    if event_type == "first_prompt":
        rounds_completed = int(game_state.get("rounds_completed", 0))

        if rounds_completed == GUESSING_GAME_2_MAX_ROUNDS - 1:
            prompts = [
                "I picked the last one for today. Ask me a question so you can figure out what it is.",
                "Okay, this is our last one for today. Ask me a question, then try to guess when you know it.",
                "I am thinking of the last one now. What question will help you guess it?",
                "Last one for today. Ask your first question so you can start guessing."
            ]
        else:
            prompts = [
                "I picked one. Ask me a question so you can guess what it is.",
                "I am thinking of it now. What question will help you guess it?",
                "You can ask me something about it, like what it looks like or what it is used for.",
                "Ask your first question so you can figure out what it is."
            ]

        recent_lines = [
            item.get("toy_worker", "")
            for item in history[-8:]
            if isinstance(item, dict)
        ]

        message = guessing_game_2_pick_non_repeating_line(prompts, recent_lines)

        try:
            return make_guessing_game_2_audio_response(
                message=message,
                stage="asking",
                response_mode="open_hint",
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type=event_type,
                child_response=child_response
            )

        except Exception as e:
            print("Guessing Game 2 first prompt TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate first prompt"
            }), 500

    if previous_response_mode in {"round_choice", "round_choice_voice"} and event_type in {"child_answer", "no_response"}:
        rounds_completed = int(game_state.get("rounds_completed", 0))

        if event_type == "no_response":
            choice = "unclear"
        else:
            choice = classify_guessing_game_2_round_choice(child_response)

        if choice == "same_game":
            previous_toy = game_state.get("secret_toy")
            used_toys = list(game_state.get("used_toys", []))

            if previous_toy and previous_toy not in used_toys:
                used_toys.append(previous_toy)

            new_game_state = get_guessing_game_2_default_state(
                rounds_completed=rounds_completed,
                used_toys=used_toys
            )

            if rounds_completed == GUESSING_GAME_2_MAX_ROUNDS - 1:
                replay_prompts = [
                    "Okay. Let's play one more round before we end our call today. I picked something new you can find at the toy store.",
                    "Okay. One more round for today. I have a new one in mind.",
                    "Sure. This will be our last one today. I picked something new."
                ]
            else:
                replay_prompts = [
                    "Okay. I picked something new you can find at the toy store.",
                    "Sure. I have a different one in mind now.",
                    "Okay. New one. Ask me questions so you can guess it.",
                    "Let's do another one. I picked something different."
                ]

            recent_prompts = game_state.get("recent_round_prompts", [])
            message = guessing_game_2_pick_non_repeating_line(replay_prompts, recent_prompts)
            new_game_state["recent_round_prompts"] = (recent_prompts + [message])[-4:]

            try:
                return make_guessing_game_2_audio_response(
                    message=message,
                    stage="intro",
                    response_mode="none",
                    expects_response=False,
                    game_complete=False,
                    game_state=new_game_state,
                    history=[],
                    event_type="replay",
                    child_response=child_response,
                    next_event="first_prompt",
                    pause_before_next_ms=1600
                )

            except Exception as e:
                print("Guessing Game 2 replay TTS error:", repr(e))
                return jsonify({
                    "success": False,
                    "error": "Could not generate replay response"
                }), 500

        if choice == "stop":
            message = "Okay. We can stop here. Thanks for playing Toy Guessing Game with me."

            try:
                return make_guessing_game_2_audio_response(
                    message=message,
                    stage="session_done",
                    response_mode="none",
                    expects_response=False,
                    game_complete=False,
                    game_state=game_state,
                    history=history,
                    event_type="stop",
                    child_response=child_response,
                    session_done=True
                )

            except Exception as e:
                print("Guessing Game 2 stop TTS error:", repr(e))
                return jsonify({
                    "success": False,
                    "error": "Could not end the game"
                }), 500

        message = "That's okay. Do you want to play another round?"

        try:
            return make_guessing_game_2_audio_response(
                message=message,
                stage="round_choice",
                response_mode="round_choice_voice",
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type="choice_clarification",
                child_response=child_response
            )

        except Exception as e:
            print("Guessing Game 2 choice clarification TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate choice response"
            }), 500

    if event_type == "no_response" or is_guessing_game_2_unclear_or_silent(child_response):
        game_state["unclear_or_silent_count"] = int(game_state.get("unclear_or_silent_count", 0)) + 1
        game_state["unclear_streak"] = int(game_state.get("unclear_streak", 0)) + 1

        options = [
            "That's okay. You can ask if it is big or small.",
            "No worries. You can ask what it is used for.",
            "That's okay. You can ask where you might find it in the toy store.",
            "No problem. You can ask for a hint whenever you want."
        ]

        recent_lines = [item.get("toy_worker", "") for item in history[-8:] if isinstance(item, dict)]
        message = guessing_game_2_pick_non_repeating_line(options, recent_lines)

        try:
            return make_guessing_game_2_audio_response(
                message=message,
                stage="support",
                response_mode="open_hint",
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type=event_type,
                child_response=child_response
            )

        except Exception as e:
            print("Guessing Game 2 no-response TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate support response"
            }), 500

    if is_guessing_game_2_hint_request(child_response):
        hint = get_guessing_game_2_hint(game_state)
        follow_up = get_guessing_game_2_follow_up_after_answer(game_state)
        message = f"Here's a hint. {hint} {follow_up}".strip()

        try:
            return make_guessing_game_2_audio_response(
                message=message,
                stage="hint",
                response_mode="open_hint",
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type="hint_request",
                child_response=child_response
            )

        except Exception as e:
            print("Guessing Game 2 hint TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate hint"
            }), 500

    if is_guessing_game_2_direct_guess(child_response):
        guessed_toy = get_guessing_game_2_named_toy(child_response)

        if guessed_toy:
            secret_toy = game_state.get("secret_toy")

            if guessed_toy == secret_toy:
                base_message = f"Yes, it is a {profile['display']}. You got it."

                try:
                    return make_guessing_game_2_correct_round_response(
                        profile=profile,
                        game_state=game_state,
                        history=history,
                        event_type="correct_guess",
                        child_response=child_response,
                        base_message=base_message
                    )

                except Exception as e:
                    print("Guessing Game 2 direct correct TTS error:", repr(e))
                    return jsonify({
                        "success": False,
                        "error": "Could not generate correct response"
                    }), 500

            game_state.setdefault("wrong_guesses", []).append(guessed_toy)
            game_state["wrong_guess_count"] = int(game_state.get("wrong_guess_count", 0)) + 1

            base_options = [
                f"Not quite, it is not a {GUESSING_GAME_2_OBJECT_PROFILES[guessed_toy]['display']}.",
                f"Good guess, but it is not a {GUESSING_GAME_2_OBJECT_PROFILES[guessed_toy]['display']}.",
                "Not that one.",
                f"It is not a {GUESSING_GAME_2_OBJECT_PROFILES[guessed_toy]['display']}."
            ]

            recent_lines = [item.get("toy_worker", "") for item in history[-8:] if isinstance(item, dict)]
            base_message = guessing_game_2_pick_non_repeating_line(base_options, recent_lines)
            follow_up = get_guessing_game_2_follow_up_after_answer(game_state)
            message = f"{base_message} {follow_up}".strip()

            try:
                return make_guessing_game_2_audio_response(
                    message=message,
                    stage="wrong_guess",
                    response_mode="open_hint",
                    expects_response=True,
                    game_complete=False,
                    game_state=game_state,
                    history=history,
                    event_type="wrong_guess",
                    child_response=child_response
                )

            except Exception as e:
                print("Guessing Game 2 wrong guess TTS error:", repr(e))
                return jsonify({
                    "success": False,
                    "error": "Could not generate wrong guess response"
                }), 500

    if is_guessing_game_2_question(child_response):
        answer = answer_guessing_game_2_question(child_response, game_state)

        if answer["type"] == "correct_guess":
            base_message = answer["message"]

            try:
                return make_guessing_game_2_correct_round_response(
                    profile=profile,
                    game_state=game_state,
                    history=history,
                    event_type="correct_guess",
                    child_response=child_response,
                    base_message=base_message
                )

            except Exception as e:
                print("Guessing Game 2 question correct TTS error:", repr(e))
                return jsonify({
                    "success": False,
                    "error": "Could not generate correct response"
                }), 500

        if answer["type"] == "wrong_guess":
            wrong_guess = answer.get("wrong_guess")

            if wrong_guess:
                game_state.setdefault("wrong_guesses", []).append(wrong_guess)

            game_state["wrong_guess_count"] = int(game_state.get("wrong_guess_count", 0)) + 1
            base_message = answer["message"]
            follow_up = get_guessing_game_2_follow_up_after_answer(game_state)
            message = f"{base_message} {follow_up}".strip()

            try:
                return make_guessing_game_2_audio_response(
                    message=message,
                    stage="wrong_guess",
                    response_mode="open_hint",
                    expects_response=True,
                    game_complete=False,
                    game_state=game_state,
                    history=history,
                    event_type="wrong_guess",
                    child_response=child_response
                )

            except Exception as e:
                print("Guessing Game 2 question wrong TTS error:", repr(e))
                return jsonify({
                    "success": False,
                    "error": "Could not generate wrong guess response"
                }), 500

        if answer.get("question_answered"):
            game_state["questions_asked"] = int(game_state.get("questions_asked", 0)) + 1
            game_state["comfortable_question_count"] = int(game_state.get("comfortable_question_count", 0)) + 1
            game_state["unclear_streak"] = 0

            question_key = guessing_game_2_question_key(child_response)

            if question_key:
                game_state.setdefault("asked_questions", []).append(question_key)
                game_state["asked_questions"] = game_state["asked_questions"][-12:]

            remember_guessing_game_2_question_topic(child_response, game_state)
            answer_message = maybe_add_guessing_game_2_good_question_prefix(answer["message"], game_state)
            follow_up = get_guessing_game_2_follow_up_after_answer(game_state)
            message = f"{answer_message} {follow_up}".strip()

            try:
                return make_guessing_game_2_audio_response(
                    message=message,
                    stage="answering",
                    response_mode="open_hint",
                    expects_response=True,
                    game_complete=False,
                    game_state=game_state,
                    history=history,
                    event_type=event_type,
                    child_response=child_response
                )

            except Exception as e:
                print("Guessing Game 2 answer TTS error:", repr(e))
                return jsonify({
                    "success": False,
                    "error": "Could not answer question"
                }), 500

        try:
            return make_guessing_game_2_audio_response(
                message=answer["message"],
                stage="support",
                response_mode="open_hint",
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type=event_type,
                child_response=child_response
            )

        except Exception as e:
            print("Guessing Game 2 support answer TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate support"
            }), 500

    named_toy = get_guessing_game_2_named_toy(child_response)

    if named_toy:
        secret_toy = game_state.get("secret_toy")

        if named_toy == secret_toy:
            base_message = f"Yes, it is a {profile['display']}. You got it."

            try:
                return make_guessing_game_2_correct_round_response(
                    profile=profile,
                    game_state=game_state,
                    history=history,
                    event_type="correct_guess",
                    child_response=child_response,
                    base_message=base_message
                )

            except Exception as e:
                print("Guessing Game 2 named correct TTS error:", repr(e))
                return jsonify({
                    "success": False,
                    "error": "Could not generate correct response"
                }), 500

        game_state.setdefault("wrong_guesses", []).append(named_toy)
        game_state["wrong_guess_count"] = int(game_state.get("wrong_guess_count", 0)) + 1
        base_message = f"Not quite, it is not a {GUESSING_GAME_2_OBJECT_PROFILES[named_toy]['display']}."
        follow_up = get_guessing_game_2_follow_up_after_answer(game_state)
        message = f"{base_message} {follow_up}".strip()

        try:
            return make_guessing_game_2_audio_response(
                message=message,
                stage="wrong_guess",
                response_mode="open_hint",
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type="wrong_guess",
                child_response=child_response
            )

        except Exception as e:
            print("Guessing Game 2 named wrong TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate wrong guess response"
            }), 500

    game_state["comfortable_question_count"] = int(game_state.get("comfortable_question_count", 0)) + 1

    fallback_lines = [
        "You can ask me a yes or no question about it.",
        "You can ask about the toy I'm thinking of.",
        "You can ask for a hint whenever you want.",
        "You can make a guess whenever you're ready."
    ]

    recent_lines = [item.get("toy_worker", "") for item in history[-8:] if isinstance(item, dict)]
    message = guessing_game_2_pick_non_repeating_line(fallback_lines, recent_lines)

    try:
        return make_guessing_game_2_audio_response(
            message=message,
            stage="support",
            response_mode="open_hint",
            expects_response=True,
            game_complete=False,
            game_state=game_state,
            history=history,
            event_type=event_type,
            child_response=child_response
        )

    except Exception as e:
        print("Guessing Game 2 fallback TTS error:", repr(e))
        return jsonify({
            "success": False,
            "error": "Could not generate fallback response"
        }), 500


@app.route("/api/guessing-game-2/transcribe", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("20 per minute")
def guessing_game_2_transcribe():
    if "audio" not in request.files:
        return jsonify({
            "success": False,
            "error": "Missing audio"
        }), 400

    audio_file = request.files["audio"]

    try:
        import io

        audio_bytes = audio_file.read()

        if not audio_bytes:
            return jsonify({
                "success": False,
                "error": "Empty audio file"
            }), 400

        file_obj = io.BytesIO(audio_bytes)
        file_obj.name = "guessing-game-2-response.webm"

        transcript = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=file_obj
        )

        text = transcript.text.strip()

        print("GUESSING GAME 2 TRANSCRIPT:", text)

        return jsonify({
            "success": True,
            "text": text
        })

    except Exception as e:
        print("Guessing Game 2 transcription error:", repr(e))
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/api/mystery-animal/thinking-audio", methods=["GET"])
@csrf.exempt
@login_required
@limiter.limit("50 per minute")
def mystery_animal_thinking_audio():
    import hashlib
    import random

    thinking_lines = [
        "Hmmmmm.",
        "Hmmm."
    ]

    avoid_raw = request.args.get("avoid", "")
    avoid_lines = {
        re.sub(r"\s+", " ", item).strip().lower()
        for item in avoid_raw.split("|")
        if item.strip()
    }

    fresh_lines = [
        line for line in thinking_lines
        if re.sub(r"\s+", " ", line).strip().lower() not in avoid_lines
    ]

    if not fresh_lines:
        fresh_lines = thinking_lines

    line = random.choice(fresh_lines)

    cache_dir = os.path.join(BASE_DIR, "static", "audio", "mystery_animal_thinking")
    os.makedirs(cache_dir, exist_ok=True)

    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "piI8Kku0DcvcL6TTSeQt")
    cache_key = f"star-thinking-v2:{voice_id}:{line}"
    filename = hashlib.md5(cache_key.encode("utf-8")).hexdigest() + ".mp3"
    filepath = os.path.join(cache_dir, filename)

    try:
        if not os.path.exists(filepath):
            audio_bytes = generate_star_voice_elevenlabs(line)

            with open(filepath, "wb") as f:
                f.write(audio_bytes)

        return jsonify({
            "success": True,
            "line": line,
            "audio_url": url_for(
                "static",
                filename=f"audio/mystery_animal_thinking/{filename}"
            )
        })

    except Exception as e:
        print("Mystery Animal thinking audio error:", repr(e))
        return jsonify({
            "success": False,
            "error": "Could not generate thinking audio"
        }), 500

@app.route("/api/star/tts", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("30 per minute")
def star_tts():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()

    allowed_intro_lines = {
        "Hi there. I'm Star. I'll hang out while you play a matching game today... Let me just share my screen...",
        "Hello! I'm Star. I'll be right here while you play a matching game today... Let me just share my screen...",
        "Hi there. I'm Star. I'll keep you company while you play today... Let me just share my screen...",
        "Hey! I'm Star. I'll be hanging out with you while you play a matching game... Let me just share my screen...",
        "Hi there. I'm Star. I'll be cheering you on while you play today... Let me just share my screen...",
        "Hey friends! I’m Star. I’ll keep you company while you find the matches... Let me just share my screen..."
    }

    if text not in allowed_intro_lines:
        return jsonify({"success": False, "error": "Invalid text"}), 400

    try:
        audio_bytes = generate_star_voice_elevenlabs(text)
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

        return jsonify({
            "success": True,
            "message": text,
            "audio": f"data:audio/mpeg;base64,{audio_base64}"
        })

    except Exception as e:
        print("Star TTS error:", e)
        return jsonify({
            "success": False,
            "error": "Could not generate audio"
        }), 500


def pick_non_repeating_line(options, recent_messages=None):
    import random

    recent_set = set(recent_messages or [])
    fresh_options = [line for line in options if line not in recent_set]

    if fresh_options:
        return random.choice(fresh_options)

    return random.choice(options)


def clean_card_label(card_name):
    labels = {
        "cat": "cat",
        "dog": "dog",
        "bunny": "bunny",
        "fish": "fish",
        "bird": "bird",
        "flower": "flower"
    }

    return labels.get(str(card_name or "").strip().lower(), "card")


def sanitize_short_line(text, fallback="Nice work.", max_len=220):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    text = text.replace('"', "")[:max_len]

    if not text:
        return fallback

    banned_terms = [
        "selective mutism",
        "anxiety",
        "therapy",
        "treatment",
        "exposure",
        "diagnosis",
        "progress",
        "bravery",
        "confidence",
        "use your words"
    ]

    lowered = text.lower()

    if any(term in lowered for term in banned_terms):
        return fallback

    return text


def clean_matching_child_name(value):
    name = re.sub(r"[^A-Za-z' -]", "", str(value or "")).strip()
    name = re.sub(r"\s+", " ", name)
    return name[:40]


def get_matching_cached_audio_url(text, namespace="matching-stitched-v1"):
    text = sanitize_short_line(text, fallback="Nice work.", max_len=220)

    cache_dir = os.path.join(BASE_DIR, "static", "audio", "matching_game")
    os.makedirs(cache_dir, exist_ok=True)

    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "piI8Kku0DcvcL6TTSeQt")
    cache_key = f"{namespace}:{voice_id}:{text}"
    filename = hashlib.md5(cache_key.encode("utf-8")).hexdigest() + ".mp3"
    filepath = os.path.join(cache_dir, filename)

    if not os.path.exists(filepath):
        audio_bytes = generate_star_voice_elevenlabs(text)

        with open(filepath, "wb") as f:
            f.write(audio_bytes)

    return url_for("static", filename=f"audio/matching_game/{filename}")


def choose_matching_name_callout(child_name, original_text):
    text = str(original_text or "")
    lowered = text.lower()

    has_question = "?" in text
    is_thanks = "thank" in lowered or "thanks" in lowered
    is_wonder = "wonder" in lowered
    is_match_line = (
        "found" in lowered
        or "matched" in lowered
        or "match" in lowered
        or "pair" in lowered
        or "both" in lowered
    )

    already_has_skill_praise = any(phrase in lowered for phrase in [
        "you're really good",
        "you're awesome",
        "you're great",
        "you are really good",
        "you found that fast",
        "good eye",
        "nice job",
        "great job",
        "awesome",
        "amazing"
    ])

    if has_question:
        options = [
            "I have a question for you, {child}.",
            "Can you help me with this, {child}?",
            "Let's think about this together, {child}.",
            "Your turn to help me, {child}.",
            "I want to ask you something, {child}."
        ]

    elif is_thanks:
        options = [
            "Thank you, {child}.",
            "I heard you, {child}.",
            "Nice answering, {child}!",
            "Thanks for helping me, {child}."
        ]

    elif is_wonder:
        options = [
            "Let's look together, {child}.",
            "I'm watching with you, {child}.",
            "Let's notice this together, {child}.",
            "Good looking, {child}!"
        ]

    elif is_match_line:
        if already_has_skill_praise:
            options = [
                "Nice, {child}!",
                "Awesome, {child}!",
                "Amazing, {child}!",
                "Great work, {child}!",
                "That was great, {child}!"
            ]
        else:
            options = [
                "Great job, {child}!",
                "Nice job, {child}!",
                "Amazing work, {child}!",
                "Awesome work, {child}!",
                "Good eye, {child}!",
                "That was great, {child}!",
                "You're doing awesome, {child}!"
            ]

    else:
        options = [
            "Nice work, {child}!",
            "Great job, {child}!",
            "You're doing great, {child}!",
            "Good job, {child}!",
            "I'm here with you, {child}."
        ]

    cache_basis = f"{child_name}:{original_text}:energetic-v2"
    index = int(hashlib.md5(cache_basis.encode("utf-8")).hexdigest(), 16) % len(options)

    return options[index].format(child=child_name)


def remove_child_name_from_matching_line(text, child_name):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    child_name = clean_matching_child_name(child_name)

    if not text or not child_name:
        return text

    escaped_name = re.escape(child_name)
    name_pattern = rf"(?<![A-Za-z]){escaped_name}(?![A-Za-z])"

    cleaned = text

    # "{child}, you found the cat pair." -> "you found the cat pair."
    cleaned = re.sub(
        rf"^\s*{name_pattern}\s*[,!.?]\s*",
        "",
        cleaned,
        flags=re.IGNORECASE
    )

    # "you found the cat pair, {child}. Only two left." -> "you found the cat pair. Only two left."
    cleaned = re.sub(
        rf"\s*,\s*{name_pattern}\s*([.!?])",
        r"\1",
        cleaned,
        flags=re.IGNORECASE
    )

    # "You're great at this, {child}. You found..." -> "You're great at this. You found..."
    cleaned = re.sub(
        rf"\s+{name_pattern}\s*([.!?])",
        r"\1",
        cleaned,
        flags=re.IGNORECASE
    )

    # Backup cleanup for any remaining awkward middle name placement.
    cleaned = re.sub(
        rf"\s*,\s*{name_pattern}\s*,\s*",
        ", ",
        cleaned,
        flags=re.IGNORECASE
    )

    cleaned = re.sub(
        rf"\s+{name_pattern}\s*",
        " ",
        cleaned,
        flags=re.IGNORECASE
    )

    cleaned = cleaned.replace(" ,", ",")
    cleaned = cleaned.replace(" .", ".")
    cleaned = cleaned.replace(" ?", "?")
    cleaned = cleaned.replace(" !", "!")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # Clean comma before sentence ending.
    cleaned = re.sub(r",\s*([.!?])", r"\1", cleaned)

    if cleaned and cleaned[-1] not in ".!?":
        cleaned += "."

    if cleaned:
        cleaned = cleaned[0].upper() + cleaned[1:]

    return cleaned


def split_matching_line_for_child_name(text, child_name):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    child_name = clean_matching_child_name(child_name)

    if not child_name or child_name.lower() in {"there", "child"}:
        return [text]

    escaped_name = re.escape(child_name)
    name_pattern = rf"(?<![A-Za-z]){escaped_name}(?![A-Za-z])"

    if not re.search(name_pattern, text, flags=re.IGNORECASE):
        return [text]

    generic_line = remove_child_name_from_matching_line(text, child_name)

    # If removing the name breaks the sentence, fall back to the original full line.
    if not generic_line or len(generic_line) < 4:
        return [text]

    name_callout = choose_matching_name_callout(child_name, text)

    return [
        name_callout,
        generic_line
    ]


@app.route("/api/matching-game/tts", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("60 per minute")
def matching_game_tts():
    data = request.get_json(silent=True) or {}
    text = sanitize_short_line(data.get("text", ""), fallback="Nice work.", max_len=220)

    if not text:
        return jsonify({"success": False, "error": "Missing text"}), 400

    child_name = clean_matching_child_name(session.get("child_name", ""))

    try:
        audio_parts_text = split_matching_line_for_child_name(text, child_name)

        audio_parts = [
            get_matching_cached_audio_url(part)
            for part in audio_parts_text
            if part and part.strip()
        ]

        return jsonify({
            "success": True,
            "message": text,
            "audio_parts": audio_parts,
            "audio_part_texts": audio_parts_text
        })

    except Exception as e:
        print("Matching game TTS error:", repr(e))
        return jsonify({
            "success": False,
            "error": "Could not generate audio"
        }), 500

@app.route("/api/matching-game/message", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("60 per minute")
def matching_game_message():
    data = request.get_json(silent=True) or {}

    event_type = str(data.get("event_type", "general")).strip()
    card_name = data.get("card_name", "")
    first_card = data.get("first_card", "")
    second_card = data.get("second_card", "")
    player = str(data.get("player", "child")).strip()
    ask_type = str(data.get("ask_type", "none")).strip()
    recent_messages = data.get("recent_star_messages", [])

    try:
        stage = int(data.get("stage", 0))
    except (TypeError, ValueError):
        stage = 0

    try:
        round_number = int(data.get("round_number", 1))
    except (TypeError, ValueError):
        round_number = 1

    try:
        rounds_completed = int(data.get("rounds_completed", 0))
    except (TypeError, ValueError):
        rounds_completed = 0

    try:
        matches_found = int(data.get("matches_found", 0))
    except (TypeError, ValueError):
        matches_found = 0

    stage = max(0, min(stage, 3))
    round_number = max(1, round_number)
    rounds_completed = max(0, rounds_completed)
    matches_found = max(0, matches_found)

    allowed_events = {
        "match_found",
        "no_match",
        "game_complete",
        "new_round",
        "general"
    }

    allowed_ask_types = {
        "none",
        "yes_no",
        "choice",
        "one_word",
        "play_again_team",
        "play_again_child"
    }

    if event_type not in allowed_events:
        return jsonify({"success": False, "error": "Invalid event_type"}), 400

    if ask_type not in allowed_ask_types:
        ask_type = "none"

    child_name = session.get("child_name", "there")
    child_name = re.sub(r"[^A-Za-z' -]", "", str(child_name)).strip() or "there"

    card = clean_card_label(card_name)
    first = clean_card_label(first_card)
    second = clean_card_label(second_card)

    expects_response = False
    intent = None
    response_seconds = 0

    # End-of-round play-again prompts. These are intentionally simple and direct.
    if event_type == "game_complete" and ask_type in {"play_again_team", "play_again_child"}:
        expects_response = True
        intent = "play_again"
        response_seconds = 7

        if ask_type == "play_again_child":
            options = [
                f"{child_name}, do you want to play another round?",
                f"{child_name}, should we try one more round?",
                f"{child_name}, would you like to play again?",
                f"{child_name}, do you want to match the cards again?"
            ]
        else:
            options = [
                "Do you two want to play another round?",
                "Should we try one more round together?",
                "Would you both like to play again?",
                "Do you want to keep playing together?"
            ]

        message = pick_non_repeating_line(options, recent_messages)

    # Simple verbal invitations during later stages.
    elif ask_type in {"yes_no", "choice", "one_word"}:
        expects_response = True
        response_seconds = 8 if ask_type == "one_word" else 7

        if ask_type == "yes_no":
            if event_type == "match_found" and card != "card":
                options = [
                    f"Did you remember where the {card} was?",
                    f"Was the {card} pair tricky?",
                    f"Did those two {card} cards match?",
                    f"Do you like the {card} card?",
                    f"Was that a good match with the {card}?"
                ]
            else:
                options = [
                    "Was that pair tricky?",
                    "Did those two cards match?",
                    "Do you want to look for an animal next?",
                    "Should we try another spot?",
                    "Was that a good try?"
                ]

        elif ask_type == "choice":
            options = [
                "Which card should we look for next, cat or dog?",
                "Which one do you like more, bunny or fish?",
                "Should we look for the bird or the flower next?",
                "Which card was easier to remember, cat or bunny?",
                "Should we try the top cards or the bottom cards next?"
            ]

            if first != "card" and second != "card" and first != second:
                options.extend([
                    f"Which should we remember, the {first} or the {second}?",
                    f"Which card did you like more, the {first} or the {second}?"
                ])

        else:
            options = [
                "What card should we look for next?",
                "Which card is your favorite?",
                "What animal did you just find?",
                "What card do you remember?",
                "What card should we try to match?"
            ]

            if card != "card":
                options.extend([
                    f"What card did you just match?",
                    f"Can you say {card}?"
                ])

        message = pick_non_repeating_line(options, recent_messages)

    # Grounded praise after a match.
    elif event_type == "match_found":
        if player == "child" and stage >= 1:
            options = [
                f"Great match with the {card}.",
                f"You found the {card} pair.",
                f"Nice job finding both {card} cards.",
                f"You remembered where the {card} was.",
                "Great job, you found that pair.",
                "Nice match, that was careful looking.",
                f"That was a strong match with the {card}.",
                f"You got both {card} cards together.",
                "Nice work finding that pair.",
                "That was a good memory move."
            ]

        elif player == "parent":
            options = [
                f"Nice match with the {card}.",
                "Great find, grown-up.",
                "You two are working well together.",
                "That was a good team match.",
                f"Nice, the {card} pair is found.",
                "Good teamwork on that one.",
                "That was a helpful turn.",
                "Nice remembering.",
                "You both are making a good team.",
                "That pair is off the board."
            ]

        else:
            options = [
                f"Great match with the {card}.",
                f"You found the {card} pair.",
                "Nice teamwork.",
                "That pair is found.",
                "Great job finding a match.",
                "That was a good match.",
                "You two found another pair.",
                "Nice, another match is done."
            ]

        if matches_found >= 4:
            options.extend([
                "You are getting close to the end of the board.",
                "Only a few matches left now.",
                "The board is almost cleared."
            ])

        message = pick_non_repeating_line(options, recent_messages)

    # Grounded comments after a mismatch.
    elif event_type == "no_match":
        options = [
            f"Not a match yet. You saw the {first} and the {second}.",
            "That pair was tricky.",
            f"Those two did not match, but now you know where the {first} and {second} are.",
            f"Good try. The {first} and {second} are useful to remember.",
            "Almost. Keep those two spots in mind.",
            "No match this time. You can remember those cards for later.",
            "That was a good look at both cards.",
            f"The {first} and {second} do not match this time.",
            "Good try. That helps you remember the board.",
            "Those were two helpful cards to see."
        ]

        if stage >= 1 and player == "child":
            options.extend([
                "Good try. You are learning where the cards are.",
                "That was a careful pick.",
                "You found two cards to remember for later.",
                "Nice looking. Those cards might help soon."
            ])

        if player == "parent":
            options.extend([
                "Good try, grown-up.",
                "That gives the team two cards to remember.",
                "Now you both know two more spots."
            ])

        message = pick_non_repeating_line(options, recent_messages)

    elif event_type == "new_round":
        if rounds_completed >= 2 or round_number >= 3:
            options = [
                "New round. Let’s see what you remember this time.",
                "The cards are mixed again. You two are getting good at this.",
                "Another board is ready.",
                "Let’s try another round together.",
                "Here comes a fresh board."
            ]
        else:
            options = [
                "Let’s try another round.",
                "New round, same teamwork.",
                "The cards are mixed again.",
                "Let’s see what matches you find this time.",
                "Here comes another board."
            ]

        message = pick_non_repeating_line(options, recent_messages)

    elif event_type == "game_complete":
        options = [
            "Great teamwork, you found them all.",
            "Nice round, every pair is matched.",
            "You two found every match.",
            "Great job finishing the board.",
            "All the matches are found.",
            "That was a full board of matches.",
            "You both did a great job with that round."
        ]

        message = pick_non_repeating_line(options, recent_messages)

    else:
        options = [
            "Nice work.",
            "Good teamwork.",
            "You two are doing great.",
            "Keep going.",
            "Nice job."
        ]

        message = pick_non_repeating_line(options, recent_messages)

    message = sanitize_short_line(message, fallback="Nice work.")

    try:
        audio_bytes = generate_star_voice_elevenlabs(message)
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

        return jsonify({
            "success": True,
            "message": message,
            "audio": f"data:audio/mpeg;base64,{audio_base64}",
            "ask_type": ask_type,
            "expects_response": expects_response,
            "intent": intent,
            "response_seconds": response_seconds
        })

    except Exception as e:
        print("Matching game message error:", e)
        return jsonify({
            "success": False,
            "error": "Could not generate message"
        }), 500


@app.route("/api/matching-game/response", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("60 per minute")
def matching_game_response():
    data = request.get_json(silent=True) or {}

    transcript = re.sub(r"\s+", " ", str(data.get("transcript", "")).strip())[:160]
    ask_type = str(data.get("ask_type", "none")).strip()
    intent = str(data.get("intent", "") or "").strip()
    wants_again = data.get("wants_again", None)
    recent_messages = data.get("recent_star_messages", [])

    if not transcript:
        return jsonify({"success": False, "error": "Missing transcript"}), 400

    words = [w for w in re.findall(r"[A-Za-z']+", transcript) if w]

    if not words:
        return jsonify({"success": False, "error": "No usable speech"}), 400

    if intent == "play_again":
        if wants_again is True:
            options = [
                "Okay, let’s play again.",
                "Great, I’ll mix the cards again.",
                "Sure, let’s do another round.",
                "Yes, let’s try another board.",
                "Okay, another round is coming."
            ]
        elif wants_again is False:
            options = [
                "That’s okay. You did a great job.",
                "Okay, we can stop here.",
                "That was a nice round together.",
                "No problem. You found every match.",
                "Okay, thanks for playing with me."
            ]
        else:
            options = [
                "I heard you.",
                "Got it.",
                "Okay.",
                "Thanks for telling me."
            ]

    elif ask_type == "yes_no":
        options = [
            "I heard you.",
            "Got it, let’s keep looking.",
            "Okay, thanks for telling me.",
            "Nice, let’s keep playing.",
            "That helps."
        ]

    elif ask_type == "choice":
        safe_choice = transcript[:30]
        options = [
            f"I heard {safe_choice}. Let’s look for that.",
            f"{safe_choice}, good choice.",
            f"Okay, {safe_choice}. Let’s keep looking.",
            f"Nice, let’s try {safe_choice}.",
            "Good choice."
        ]

    elif ask_type == "one_word":
        safe_word = words[0].lower().capitalize()
        options = [
            f"{safe_word}, nice.",
            f"I heard {safe_word}.",
            f"{safe_word}, good remembering.",
            f"Okay, {safe_word}.",
            f"Nice job saying {safe_word}."
        ]

    else:
        options = [
            "I heard you.",
            "Got it.",
            "Thanks for telling me.",
            "Okay, let’s keep playing.",
            "Nice."
        ]

    message = sanitize_short_line(
        pick_non_repeating_line(options, recent_messages),
        fallback="Got it, let’s keep playing.",
        max_len=180
    )

    try:
        audio_bytes = generate_star_voice_elevenlabs(message)
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

        return jsonify({
            "success": True,
            "message": message,
            "audio": f"data:audio/mpeg;base64,{audio_base64}",
            "word_count": len(words)
        })

    except Exception as e:
        print("Matching game response error:", e)
        return jsonify({
            "success": False,
            "error": "Could not generate response"
        }), 500


@app.route("/api/matching-game/transcribe", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("30 per minute")
def matching_game_transcribe():
    if "audio" not in request.files:
        return jsonify({
            "success": False,
            "error": "Missing audio"
        }), 400

    audio_file = request.files["audio"]

    try:
        import io

        audio_bytes = audio_file.read()

        if not audio_bytes:
            return jsonify({
                "success": False,
                "error": "Empty audio file"
            }), 400

        file_obj = io.BytesIO(audio_bytes)
        file_obj.name = "match-response.webm"

        transcript = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=file_obj
        )

        text = transcript.text.strip()
        print("MATCH CARDS TRANSCRIPT:", text)

        return jsonify({
            "success": True,
            "text": text
        })

    except Exception as e:
        print("Matching game transcription error:", repr(e))
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/api/matching-game/state", methods=["GET"])
@csrf.exempt
@login_required
@limiter.limit("60 per minute")
def matching_game_state():
    ensure_matching_game_progress_columns()

    try:
        activity_id = int(request.args.get("activity_id") or 1)
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "Invalid activity_id"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT activity_id
            FROM activity
            WHERE activity_id = ? AND is_active = 1
        """, (activity_id,))

        activity = cursor.fetchone()

        if not activity:
            conn.close()
            return jsonify({"success": False, "error": "Activity not found"}), 404

        cursor.execute("""
            INSERT OR IGNORE INTO progress (
                user_id,
                activity_id,
                is_unlocked,
                is_completed,
                words_spoken,
                minutes_spoken,
                active_minutes,
                time_spent_on_activity
            )
            VALUES (?, ?, 1, 0, 0, 0, 0, 0)
        """, (session["user_id"], activity_id))

        cursor.execute("""
            SELECT
                COALESCE(matching_rounds_completed, 0) AS matching_rounds_completed,
                COALESCE(matching_spoken_responses, 0) AS matching_spoken_responses,
                COALESCE(matching_silent_windows, 0) AS matching_silent_windows,
                COALESCE(matching_wonder_prompts_asked, 0) AS matching_wonder_prompts_asked,
                COALESCE(matching_help_prompts_asked, 0) AS matching_help_prompts_asked,
                COALESCE(matching_clear_prompts_asked, 0) AS matching_clear_prompts_asked,
                COALESCE(matching_child_choice_responses, 0) AS matching_child_choice_responses,
                COALESCE(matching_child_opinion_responses, 0) AS matching_child_opinion_responses,
                COALESCE(matching_clear_child_responses, 0) AS matching_clear_child_responses,
                COALESCE(matching_direct_child_question_silences, 0) AS matching_direct_child_question_silences,
                COALESCE(matching_last_stage, 0) AS matching_last_stage
            FROM progress
            WHERE user_id = ? AND activity_id = ?
        """, (session["user_id"], activity_id))

        row = cursor.fetchone()

        conn.commit()
        conn.close()

        saved_rounds = int(row["matching_rounds_completed"] or 0)
        clear_child_responses = int(row["matching_clear_child_responses"] or 0)

        return jsonify({
            "success": True,
            "target_rounds": MATCHING_GAME_TARGET_ROUNDS,
            "state": {
                "rounds_completed": saved_rounds,
                "start_round_number": saved_rounds + 1,

                "spoken_responses": int(row["matching_spoken_responses"] or 0),
                "silent_windows": int(row["matching_silent_windows"] or 0),

                "wonder_prompts_asked": int(row["matching_wonder_prompts_asked"] or 0),
                "help_prompts_asked": int(row["matching_help_prompts_asked"] or 0),
                "clear_prompts_asked": int(row["matching_clear_prompts_asked"] or 0),

                "child_choice_responses": int(row["matching_child_choice_responses"] or 0),
                "child_opinion_responses": int(row["matching_child_opinion_responses"] or 0),

                # Your JS currently reads clear_child_responses.
                "clear_child_responses": clear_child_responses,

                # This alias is harmless and protects you if you later rename it in JS.
                "child_clear_responses": clear_child_responses,

                "direct_child_question_silences": int(row["matching_direct_child_question_silences"] or 0),
                "last_stage": int(row["matching_last_stage"] or 0)
            }
        })

    except Exception as e:
        conn.rollback()
        conn.close()
        print("Matching game state error:", repr(e))
        return jsonify({
            "success": False,
            "error": "Could not load matching game state"
        }), 500

@app.route("/api/matching-game/complete", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("20 per minute")
def matching_game_complete():
    ensure_matching_game_progress_columns()

    data = request.get_json(silent=True) or {}

    try:
        activity_id = int(data.get("activity_id") or 1)

        words_spoken = safe_matching_int(data.get("words_spoken", 0))
        minutes_spoken = safe_matching_float(data.get("minutes_spoken", 0))
        active_minutes = safe_matching_float(data.get("active_minutes", 0))
        time_spent = safe_matching_float(
            data.get("time_spent_on_activity", active_minutes),
            active_minutes
        )

        rounds_completed = safe_matching_int(data.get("rounds_completed", 0))
        spoken_responses = safe_matching_int(data.get("spoken_responses", 0))
        silent_windows = safe_matching_int(data.get("silent_windows", 0))

        wonder_prompts_asked = safe_matching_int(data.get("wonder_prompts_asked", 0))
        help_prompts_asked = safe_matching_int(data.get("help_prompts_asked", 0))
        clear_prompts_asked = safe_matching_int(data.get("clear_prompts_asked", 0))

        child_choice_responses = safe_matching_int(data.get("child_choice_responses", 0))
        child_opinion_responses = safe_matching_int(data.get("child_opinion_responses", 0))

        # Your JS sends child_clear_responses.
        clear_child_responses = safe_matching_int(
            data.get("child_clear_responses", data.get("clear_child_responses", 0))
        )

        direct_child_question_silences = safe_matching_int(
            data.get("direct_child_question_silences", 0)
        )

        final_stage = safe_matching_int(data.get("final_stage", 0))

    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "Invalid completion data"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT activity_id, scene_id, activity_order
            FROM activity
            WHERE activity_id = ? AND is_active = 1
        """, (activity_id,))

        activity = cursor.fetchone()

        if not activity:
            conn.close()
            return jsonify({"success": False, "error": "Activity not found"}), 404

        cursor.execute("""
            INSERT OR IGNORE INTO progress (
                user_id,
                activity_id,
                is_unlocked,
                is_completed,
                words_spoken,
                minutes_spoken,
                active_minutes,
                time_spent_on_activity
            )
            VALUES (?, ?, 1, 0, 0, 0, 0, 0)
        """, (session["user_id"], activity_id))

        cursor.execute("""
            SELECT
                COALESCE(matching_rounds_completed, 0) AS previous_rounds_completed
            FROM progress
            WHERE user_id = ? AND activity_id = ?
        """, (session["user_id"], activity_id))

        previous_row = cursor.fetchone()
        previous_rounds_completed = int(previous_row["previous_rounds_completed"] or 0) if previous_row else 0

        activity_completed = rounds_completed >= MATCHING_GAME_TARGET_ROUNDS

        cursor.execute("""
            UPDATE progress
            SET
                is_completed = CASE
                    WHEN ? = 1 THEN 1
                    ELSE COALESCE(is_completed, 0)
                END,

                words_spoken = COALESCE(words_spoken, 0) + ?,
                minutes_spoken = COALESCE(minutes_spoken, 0) + ?,
                active_minutes = COALESCE(active_minutes, 0) + ?,
                time_spent_on_activity = COALESCE(time_spent_on_activity, 0) + ?,

                matching_rounds_completed = MAX(COALESCE(matching_rounds_completed, 0), ?),
                matching_spoken_responses = MAX(COALESCE(matching_spoken_responses, 0), ?),
                matching_silent_windows = MAX(COALESCE(matching_silent_windows, 0), ?),

                matching_wonder_prompts_asked = MAX(COALESCE(matching_wonder_prompts_asked, 0), ?),
                matching_help_prompts_asked = MAX(COALESCE(matching_help_prompts_asked, 0), ?),
                matching_clear_prompts_asked = MAX(COALESCE(matching_clear_prompts_asked, 0), ?),

                matching_child_choice_responses = MAX(COALESCE(matching_child_choice_responses, 0), ?),
                matching_child_opinion_responses = MAX(COALESCE(matching_child_opinion_responses, 0), ?),
                matching_clear_child_responses = MAX(COALESCE(matching_clear_child_responses, 0), ?),

                matching_direct_child_question_silences = MAX(COALESCE(matching_direct_child_question_silences, 0), ?),
                matching_last_stage = MAX(COALESCE(matching_last_stage, 0), ?),
                matching_last_played_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND activity_id = ?
        """, (
            1 if activity_completed else 0,

            words_spoken,
            minutes_spoken,
            active_minutes,
            time_spent,

            rounds_completed,
            spoken_responses,
            silent_windows,

            wonder_prompts_asked,
            help_prompts_asked,
            clear_prompts_asked,

            child_choice_responses,
            child_opinion_responses,
            clear_child_responses,

            direct_child_question_silences,
            final_stage,

            session["user_id"],
            activity_id
        ))

        # Only add a session log when the saved round count actually increases.
        # This prevents duplicate logs when the child leaves right after a round was already saved.
        if rounds_completed > previous_rounds_completed:
            cursor.execute("""
                INSERT INTO session_log (
                    user_id,
                    activity_id,
                    words_spoken,
                    minutes_spoken,
                    active_minutes,
                    completed_at
                )
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                session["user_id"],
                activity_id,
                words_spoken,
                minutes_spoken,
                active_minutes
            ))

        next_activity_id = None

        # Only unlock the next activity after the full 12-round fade-in progression.
        if activity_completed:
            cursor.execute("""
                SELECT activity_id
                FROM activity
                WHERE is_active = 1
                  AND (
                    scene_id > ?
                    OR (scene_id = ? AND activity_order > ?)
                  )
                ORDER BY scene_id ASC, activity_order ASC
                LIMIT 1
            """, (
                activity["scene_id"],
                activity["scene_id"],
                activity["activity_order"]
            ))

            next_activity = cursor.fetchone()

            if next_activity:
                next_activity_id = next_activity["activity_id"]

                cursor.execute("""
                    INSERT OR IGNORE INTO progress (
                        user_id,
                        activity_id,
                        is_unlocked,
                        is_completed,
                        words_spoken,
                        minutes_spoken,
                        active_minutes,
                        time_spent_on_activity
                    )
                    VALUES (?, ?, 1, 0, 0, 0, 0, 0)
                """, (session["user_id"], next_activity_id))

                cursor.execute("""
                    UPDATE progress
                    SET is_unlocked = 1
                    WHERE user_id = ? AND activity_id = ?
                """, (session["user_id"], next_activity_id))

                cursor.execute("""
                    UPDATE users
                    SET current_activity_id = ?
                    WHERE user_id = ?
                """, (next_activity_id, session["user_id"]))

        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "rounds_completed": rounds_completed,
            "target_rounds": MATCHING_GAME_TARGET_ROUNDS,
            "activity_completed": activity_completed,
            "next_activity_id": next_activity_id
        })

    except Exception as e:
        conn.rollback()
        conn.close()
        print("Matching completion error:", repr(e))
        return jsonify({
            "success": False,
            "error": "Could not save matching game completion"
        }), 500

MYSTERY_ANIMAL_LEVELS = [
    {
        "stage": "guided_choice",
        "response_mode": "choice",
        "description": "Ask one concrete either/or or small-choice question. Do not ask yes/no. Do not ask for hints or clues.",
        "examples": [
            "Is your animal big or small?",
            "Does your animal mostly walk or swim?",
            "Is your animal loud or quiet?"
        ],
        "fallback_questions": [
            "Is your animal big or small?",
            "Is your animal loud or quiet?",
            "Is your animal fast or slow?",
            "Does your animal mostly walk or swim?",
            "Does your animal mostly walk or fly?",
            "Does your animal live mostly on land or in water?",
            "Is your animal usually a pet or a wild animal?",
            "Does your animal have fur or feathers?",
            "Does your animal have legs or fins?",
            "Is your animal usually found at home or outside?",
            "Is your animal bigger than a backpack or smaller than a backpack?",
            "Does your animal move on the ground or in the air?"
        ]
    },
    {
        "stage": "guided_clue",
        "response_mode": "choice",
        "description": "Ask one concrete guided clue question with related choices only. Avoid broad abstract questions.",
        "examples": [
            "Does your animal have fur or scales?",
            "Does your animal live on a farm or in the wild?",
            "Does your animal have a tail or no tail?"
        ],
        "fallback_questions": [
            "Does your animal have fur or scales?",
            "Does your animal have wings or no wings?",
            "Does your animal have a tail or no tail?",
            "Does your animal live on a farm or in the wild?",
            "Does your animal live in a house or outside?",
            "Does your animal eat meat or plants?",
            "Does your animal have four legs or fewer than four legs?",
            "Does your animal swim in water or stay mostly on land?",
            "Is your animal usually gentle or scary?",
            "Is your animal real-life common or more of a zoo animal?"
        ]
    },
    {
        "stage": "tiny_hint",
        "response_mode": "short_phrase",
        "description": "Ask for one tiny concrete hint only after the early guided rounds.",
        "examples": [
            "Give me one tiny hint about what your animal looks like.",
            "Tell me one body part your animal has.",
            "Give me one small clue about how your animal moves."
        ],
        "fallback_questions": [
            "Give me one tiny hint about what your animal looks like.",
            "Tell me one body part your animal has.",
            "Give me one small clue about how your animal moves.",
            "Tell me one place your animal might be.",
            "Tell me one thing your animal has on its body.",
            "Give me one small clue that would help me guess."
        ]
    },
    {
        "stage": "open_hint",
        "response_mode": "open_hint",
        "description": "Ask for a hint or clue more openly, but still keep it simple.",
        "examples": [
            "Can you give me one more clue?",
            "What is one thing I should know about your animal?",
            "What clue should I remember before I guess?"
        ],
        "fallback_questions": [
            "Can you give me one more clue?",
            "What is one thing I should know about your animal?",
            "What clue should I remember before I guess?",
            "Tell me one more thing about your animal.",
            "Give me one clue that makes your animal different from other animals.",
            "What is one small hint that would help me make a better guess?"
        ]
    }
]

MYSTERY_ANIMAL_START_LEVEL_INDEX = 0
MYSTERY_ANIMAL_REQUIRED_ROUNDS = 9
MYSTERY_ANIMAL_NEXT_GAME_OFFER_ROUND = 9
MYSTERY_ANIMAL_PLAY_AGAIN_INTERVAL = 9
MYSTERY_ANIMAL_NEXT_ACTIVITY_ID = 3
MYSTERY_ANIMAL_MAX_QUESTIONS_PER_ROUND = 10

MYSTERY_ANIMAL_COMMON_ANIMALS = {
    # This is NOT used as a closed candidate list. It is only used to recognize
    # direct child reveals like "dog" or "lion" and to validate obvious animal names.
    "aardvark", "albatross", "alligator", "alpaca", "ant", "anteater", "antelope",
    "ape", "armadillo", "baboon", "badger", "bat", "bear", "bird", "fish", "beaver", "bee",
    "beetle", "bird", "bison", "bobcat", "buffalo", "butterfly", "camel",
    "capybara", "cat", "caterpillar", "cheetah", "chicken", "chimpanzee",
    "clam", "cobra", "cougar", "cow", "coyote", "crab", "cricket", "crocodile",
    "deer", "dinosaur", "dog", "dolphin", "donkey", "dragonfly", "duck", "eagle",
    "eel", "elephant", "falcon", "ferret", "fish", "flamingo", "fly", "fox",
    "frog", "gazelle", "giraffe", "goat", "goose", "gorilla", "grasshopper",
    "hamster", "hare", "hawk", "hedgehog", "hippo", "hippopotamus", "horse",
    "hyena", "jaguar", "jellyfish", "kangaroo", "kitten", "koala", "ladybug",
    "leopard", "lion", "lizard", "llama", "lobster", "monkey", "moose", "mosquito",
    "mouse", "octopus", "orangutan", "ostrich", "otter", "owl", "panda", "panther",
    "parrot", "peacock", "penguin", "pig", "puppy", "rabbit", "raccoon", "rat",
    "rhino", "rhinoceros", "rooster", "scorpion", "seal", "shark", "sheep",
    "skunk", "sloth", "snail", "snake", "spider", "squid", "squirrel", "starfish",
    "stingray", "swan", "tiger", "toad", "tortoise", "turkey", "turtle", "walrus",
    "wasp", "whale", "wolf", "worm", "zebra", "polar bear", "grizzly bear", "brown bear",
    "centipede", "millipede", "tarantula", "tree frog", "sea turtle", "goldfish",
    "clownfish", "butterfly", "moth", "lady beetle", "hermit crab", "blue whale",
    "killer whale", "orca", "sparrow", "robin", "crow", "raven", "pigeon", "dove",
    "cardinal", "blue jay", "woodpecker", "hummingbird", "seagull", "pelican",
    "macaw", "canary", "finch", "parakeet", "budgie", "cockatiel", "cockatoo",
    "toucan", "vulture", "condor", "kiwi", "emu", "cassowary",
    "black widow", "wolf spider", "jumping spider", "garden spider",
    "tree frog", "poison dart frog", "bullfrog", "leopard frog",
    "sea turtle", "box turtle", "painted turtle", "snapping turtle",
    "goldfish", "clownfish", "betta", "guppy", "tuna", "salmon", "trout",
    "blue whale", "killer whale", "orca", "bottlenose dolphin",
    "lady beetle", "hermit crab", "king crab"
}

# Star should guess broad animal groups, not tiny species.
# Example: sparrow -> bird, tarantula -> spider.
MYSTERY_ANIMAL_SPECIFIC_TO_BROAD_GUESS = {
    # birds
    "sparrow": "bird", "robin": "bird", "crow": "bird", "raven": "bird",
    "pigeon": "bird", "dove": "bird", "cardinal": "bird", "blue jay": "bird",
    "woodpecker": "bird", "hummingbird": "bird", "seagull": "bird",
    "pelican": "bird", "parrot": "bird", "macaw": "bird", "canary": "bird",
    "finch": "bird", "parakeet": "bird", "budgie": "bird", "cockatiel": "bird",
    "cockatoo": "bird", "toucan": "bird", "eagle": "bird", "hawk": "bird",
    "falcon": "bird", "owl": "bird", "vulture": "bird", "condor": "bird",
    "flamingo": "bird", "ostrich": "bird", "emu": "bird", "kiwi": "bird",
    "cassowary": "bird", "swan": "bird", "goose": "bird", "duck": "bird",
    "chicken": "bird", "rooster": "bird", "turkey": "bird",
    "peacock": "bird", "albatross": "bird",

    # spiders / insects / small groups
    "tarantula": "spider", "black widow": "spider", "wolf spider": "spider",
    "jumping spider": "spider", "garden spider": "spider",
    "lady beetle": "ladybug",

    # frogs / turtles / fish
    "tree frog": "frog", "poison dart frog": "frog", "bullfrog": "frog",
    "leopard frog": "frog", "toad": "frog",
    "sea turtle": "turtle", "box turtle": "turtle", "painted turtle": "turtle",
    "snapping turtle": "turtle", "tortoise": "turtle",
    "goldfish": "fish", "clownfish": "fish", "betta": "fish", "guppy": "fish",
    "tuna": "fish", "salmon": "fish", "trout": "fish",

    # whales/dolphins and crabs
    "blue whale": "whale", "killer whale": "whale", "orca": "whale",
    "bottlenose dolphin": "dolphin",
    "hermit crab": "crab", "king crab": "crab"
}

MYSTERY_ANIMAL_BROAD_GUESS_ANIMALS = set(MYSTERY_ANIMAL_GUESS_PROFILES.keys()) if 'MYSTERY_ANIMAL_GUESS_PROFILES' in globals() else {
    "bird", "fish", "snake", "spider", "crab", "turtle", "frog", "dog", "cat",
    "rabbit", "horse", "cow", "pig", "sheep", "goat", "lion", "tiger",
    "bear", "elephant", "giraffe", "zebra", "monkey", "kangaroo", "butterfly",
    "bee", "dolphin", "whale", "shark", "octopus", "crocodile", "lizard",
    "squirrel", "mouse", "hamster", "fox", "wolf", "deer", "snail", "polar bear", "panda", "grizzly bear"
}


def get_mystery_animal_default_state(rounds_completed=0):
    rounds_completed = max(0, int(rounds_completed or 0))

    return {
        "stage": "intro",
        "response_level_index": MYSTERY_ANIMAL_START_LEVEL_INDEX,
        "questions_asked": 0,
        "comfortable_answer_count": 0,
        "unclear_or_silent_count": 0,
        "comfortable_streak": 0,
        "unclear_streak": 0,
        "question_history": [],
        "qa_history": [],
        "known_clues": [],
        "asked_question_keys": [],
        "current_round_question_keys": [],
        "rejected_guesses": [],
        "possible_guess": None,
        "last_question": None,
        "last_question_key": None,
        "pending_question_key": None,
        "last_response_mode": "none",
        "game_complete": False,
        "rounds_completed": rounds_completed,
        "skip_guess_once": False,
        "guess_cooldown_questions": 0,
        "last_guess_question_count": 0,
        "last_acknowledgment_index": -1,
        "clear_answer_word_counts": [],
        "recent_question_families": [],
        "asked_question_families": [],
        "recent_guesses": [],
        "recent_acknowledgments": [],
        "open_hint_questions_asked": 0,
        "session_question_keys": list(session.get("mystery_animal_session_question_keys", []))[-40:],
        "unclear_question_keys": [],
        "give_up_asked": False,
        "gave_up_waiting_for_answer": False
    }


def get_mystery_animal_level(game_state=None):
    """
    Safely return the current Mystery Animal response level.
    """
    if game_state is None:
        game_state = {}

    try:
        index = int(game_state.get("response_level_index", MYSTERY_ANIMAL_START_LEVEL_INDEX))
    except (TypeError, ValueError):
        index = MYSTERY_ANIMAL_START_LEVEL_INDEX

    index = max(0, min(index, len(MYSTERY_ANIMAL_LEVELS) - 1))
    return MYSTERY_ANIMAL_LEVELS[index]


def ensure_mystery_animal_progress_columns():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(progress)")
    existing_columns = {row["name"] for row in cursor.fetchall()}

    columns_to_add = {
        "mystery_animal_rounds_completed": "ALTER TABLE progress ADD COLUMN mystery_animal_rounds_completed INTEGER DEFAULT 0",
        "mystery_animal_last_played_at": "ALTER TABLE progress ADD COLUMN mystery_animal_last_played_at TEXT"
    }

    for column_name, alter_sql in columns_to_add.items():
        if column_name not in existing_columns:
            cursor.execute(alter_sql)

    conn.commit()
    conn.close()


def get_mystery_animal_activity(cursor):
    cursor.execute("""
        SELECT activity_id, scene_id, activity_order
        FROM activity
        WHERE activity_name IN (?, ?, ?)
          AND is_active = 1
        ORDER BY
            CASE activity_name
                WHEN 'mystery_animal' THEN 1
                WHEN 'guessing_game' THEN 2
                WHEN 'animal_guessing_game' THEN 3
                ELSE 4
            END
        LIMIT 1
    """, (
        "mystery_animal",
        "guessing_game",
        "animal_guessing_game"
    ))

    return cursor.fetchone()


def get_saved_mystery_animal_rounds():
    ensure_mystery_animal_progress_columns()

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        activity = get_mystery_animal_activity(cursor)

        if not activity:
            conn.close()
            return 0

        activity_id = activity["activity_id"]

        cursor.execute("""
            INSERT OR IGNORE INTO progress (
                user_id,
                activity_id,
                is_unlocked,
                is_completed,
                words_spoken,
                minutes_spoken,
                active_minutes,
                time_spent_on_activity
            )
            VALUES (?, ?, 1, 0, 0, 0, 0, 0)
        """, (session["user_id"], activity_id))

        cursor.execute("""
            SELECT COALESCE(mystery_animal_rounds_completed, 0) AS rounds_completed
            FROM progress
            WHERE user_id = ? AND activity_id = ?
        """, (session["user_id"], activity_id))

        row = cursor.fetchone()
        conn.commit()
        conn.close()

        return int(row["rounds_completed"] or 0) if row else 0

    except Exception as e:
        conn.rollback()
        conn.close()
        print("Could not load Mystery Animal progress:", repr(e))
        return 0


def save_mystery_animal_round_progress(rounds_completed):
    ensure_mystery_animal_progress_columns()

    rounds_completed = max(0, int(rounds_completed or 0))

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        activity = get_mystery_animal_activity(cursor)

        if not activity:
            conn.close()
            return None

        activity_id = activity["activity_id"]

        cursor.execute("""
            INSERT OR IGNORE INTO progress (
                user_id,
                activity_id,
                is_unlocked,
                is_completed,
                words_spoken,
                minutes_spoken,
                active_minutes,
                time_spent_on_activity
            )
            VALUES (?, ?, 1, 0, 0, 0, 0, 0)
        """, (session["user_id"], activity_id))

        cursor.execute("""
            UPDATE progress
            SET
                is_unlocked = 1,
                mystery_animal_rounds_completed = MAX(
                    COALESCE(mystery_animal_rounds_completed, 0),
                    ?
                ),
                mystery_animal_last_played_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND activity_id = ?
        """, (rounds_completed, session["user_id"], activity_id))

        conn.commit()
        conn.close()

        return activity_id

    except Exception as e:
        conn.rollback()
        conn.close()
        print("Could not save Mystery Animal progress:", repr(e))
        return None


def complete_mystery_animal_and_unlock_next_for_user(rounds_completed=None):
    ensure_mystery_animal_progress_columns()

    saved_rounds = max(0, int(rounds_completed or 0))

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        current_activity = get_mystery_animal_activity(cursor)

        if not current_activity:
            conn.close()
            return None

        current_activity_id = current_activity["activity_id"]

        cursor.execute("""
            INSERT OR IGNORE INTO progress (
                user_id,
                activity_id,
                is_unlocked,
                is_completed,
                words_spoken,
                minutes_spoken,
                active_minutes,
                time_spent_on_activity
            )
            VALUES (?, ?, 1, 0, 0, 0, 0, 0)
        """, (session["user_id"], current_activity_id))

        cursor.execute("""
            UPDATE progress
            SET
                is_unlocked = 1,
                is_completed = 1,
                mystery_animal_rounds_completed = MAX(
                    COALESCE(mystery_animal_rounds_completed, 0),
                    ?
                ),
                mystery_animal_last_played_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND activity_id = ?
        """, (
            max(saved_rounds, MYSTERY_ANIMAL_REQUIRED_ROUNDS),
            session["user_id"],
            current_activity_id
        ))

        cursor.execute("""
            SELECT activity_id
            FROM activity
            WHERE is_active = 1
              AND (
                scene_id > ?
                OR (scene_id = ? AND activity_order > ?)
              )
            ORDER BY scene_id ASC, activity_order ASC
            LIMIT 1
        """, (
            current_activity["scene_id"],
            current_activity["scene_id"],
            current_activity["activity_order"]
        ))

        next_activity = cursor.fetchone()

        next_activity_id = None

        if next_activity:
            next_activity_id = next_activity["activity_id"]

            cursor.execute("""
                INSERT OR IGNORE INTO progress (
                    user_id,
                    activity_id,
                    is_unlocked,
                    is_completed,
                    words_spoken,
                    minutes_spoken,
                    active_minutes,
                    time_spent_on_activity
                )
                VALUES (?, ?, 1, 0, 0, 0, 0, 0)
            """, (session["user_id"], next_activity_id))

            cursor.execute("""
                UPDATE progress
                SET is_unlocked = 1
                WHERE user_id = ? AND activity_id = ?
            """, (session["user_id"], next_activity_id))

            cursor.execute("""
                UPDATE users
                SET current_activity_id = ?
                WHERE user_id = ?
            """, (next_activity_id, session["user_id"]))

        conn.commit()
        conn.close()

        return next_activity_id

    except Exception as e:
        conn.rollback()
        conn.close()
        print("Could not complete Mystery Animal and unlock next activity:", repr(e))
        return None


def should_mystery_animal_ask_round_choice(rounds_completed):
    rounds_completed = int(rounds_completed or 0)
    return rounds_completed >= MYSTERY_ANIMAL_REQUIRED_ROUNDS



def normalize_child_text(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def clean_open_ended_animal_name(value):
    """
    Clean an AI-provided or child-provided animal guess.

    Important: this is a GUARDRAIL, not a closed candidate list.
    It allows open-ended animal names, but it rejects clue fragments like
    "bigger than a", "on land", "antlers", "has fur", etc.
    """
    text = normalize_child_text(value).lower()
    text = text.replace("’", "'")
    text = re.sub(r"[^a-z' -]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        return None

    # Remove common wrapper words only from the beginning.
    text = re.sub(r"^(?:is it|could it be|maybe|i think|it is|it's|a|an|the)\s+", "", text).strip()

    # Cut off explanatory tails, but do NOT keep "or a type of..." as part of the guess.
    text = re.split(r"\b(?:because|that|with|and|or|but|so|which|who)\b", text, maxsplit=1)[0].strip()
    text = re.sub(r"\s+", " ", text).strip(" .,!?")

    if not text:
        return None

    words = text.split()

    generic_non_answers = {
        "animal", "pet", "wild animal", "farm animal", "sea animal", "water animal",
        "land animal", "air animal", "bug", "insect", "mammal", "reptile",
        "animal", "pet", "wild animal", "farm animal", "sea animal", "water animal",
        "land animal", "air animal", "bug", "insect", "mammal", "reptile",
        "thing", "creature", "one", "many", "it", "yes", "no",
        "type", "kind", "sort", "clue", "hint",
        "one color", "many colors", "same color", "different colors", "color", "colour"
    }

    invalid_exact_guesses = {
        "on land", "in water", "in the water", "in air", "in the air", "in sky", "in the sky",
        "land", "water", "air", "sky", "ground", "outside", "inside",
        "antler", "antlers", "horn", "horns", "shell", "fur", "feather", "feathers", "scale", "scales",
        "beak", "beaks", "claw", "claws", "talon", "talons", "paw", "paws", "hoof", "hooves",
        "snout", "nose", "ear", "ears", "eye", "eyes", "mouth", "tooth", "teeth", "stripe", "stripes", "spot", "spots",
        "leg", "legs", "arm", "arms", "tail", "tails", "wing", "wings", "fin", "fins",
        "soft arms", "hard shell", "no shell", "smooth skin",
        "backpack", "hand", "person", "human", "bigger", "smaller", "big", "small",
        "bigger than a", "smaller than a", "bigger than", "smaller than",
        "yes", "no", "maybe", "i don't know", "dont know", "don't know",
        "one color", "many colors", "same color", "different colors", "color", "colour",
        "mostly one color", "mostly many colors",
        "walk", "run", "jump", "crawl", "swim", "fly", "walks", "runs", "jumps", "crawls", "swims", "flies"
    }

    clue_only_words = {
        "land", "water", "air", "sky", "ground", "outside", "inside",
        "antler", "antlers", "horn", "horns", "shell", "fur", "feather", "feathers", "scale", "scales",
        "beak", "beaks", "claw", "claws", "talon", "talons", "paw", "paws", "hoof", "hooves",
        "snout", "nose", "ear", "ears", "eye", "eyes", "mouth", "tooth", "teeth", "stripe", "stripes", "spot", "spots",
        "leg", "legs", "arm", "arms", "tail", "tails", "wing", "wings", "fin", "fins", "skin",
        "big", "bigger", "small", "smaller", "large", "larger", "tiny", "person", "backpack", "hand",
        "one", "many", "color", "colors", "colour", "colours", "same", "different", "mostly",
        "crawl", "crawls", "walk", "walks", "run", "runs", "jump", "jumps", "swim", "swims", "fly", "flies",
        "on", "in", "at", "the", "a", "an", "it", "is", "has", "have", "with", "without", "than", "more", "less"
    }

    if text in generic_non_answers or text in invalid_exact_guesses:
        return None

    # Reject clue phrases and comparison fragments.
    if re.search(r"\b(?:than|bigger|smaller|larger|shorter|taller|on land|in water|in the air|in the sky)\b", text):
        return None

    if re.search(r"\b(?:one color|many colors|same color|different colors|mostly one color|mostly many colors)\b", text):
        return None

    if re.search(r"^(?:on|in|at|under|over|near|bigger|smaller|larger|more|less)\s+", text):
        return None

    if words and set(words).issubset(clue_only_words):
        return None

    # Reject "has X" / "with X" clue phrases.
    if re.search(r"^(?:has|have|with|without)\s+", text):
        return None

    if len(words) > 3:
        return None

    return text[:42].strip() or None

def is_probably_valid_mystery_animal_guess(value):
    """
    Strict guardrail for guesses Star says aloud.

    This intentionally does NOT allow random noun phrases anymore. That was how
    clue fragments like "one color" could become a spoken guess. A guess must be
    a known animal name or a specific animal that can be broadened safely.
    """
    guess = clean_open_ended_animal_name(value)

    if not guess:
        return False

    guess_l = guess.lower().strip()
    words = set(re.findall(r"[a-z']+", guess_l))

    invalid_single_words = {
        "land", "water", "air", "sky", "ground", "outside", "inside",
        "antler", "antlers", "horn", "horns", "shell", "fur", "feather", "feathers", "scale", "scales",
        "beak", "beaks", "claw", "claws", "talon", "talons", "paw", "paws", "hoof", "hooves",
        "snout", "nose", "ear", "ears", "eye", "eyes", "mouth", "tooth", "teeth", "stripe", "stripes", "spot", "spots",
        "leg", "legs", "arm", "arms", "tail", "tails", "wing", "wings", "fin", "fins", "skin",
        "backpack", "hand", "person", "human", "bigger", "smaller", "larger", "small", "big",
        "walk", "run", "jump", "crawl", "swim", "fly", "walks", "runs", "jumps", "crawls", "swims", "flies",
        "clue", "hint", "color", "colors", "colour", "colours", "food", "place", "one", "many", "same", "different"
    }

    invalid_anywhere = {
        "than", "bigger", "smaller", "larger", "shorter", "taller",
        "land", "water", "sky", "air", "backpack", "hand", "person",
        "antler", "antlers", "horn", "horns", "shell", "fur", "feather", "feathers", "scale", "scales",
        "beak", "beaks", "claw", "claws", "talon", "talons", "paw", "paws", "hoof", "hooves",
        "snout", "nose", "ear", "ears", "eye", "eyes", "mouth", "tooth", "teeth", "stripe", "stripes", "spot", "spots",
        "legs", "arms", "tail", "wings", "fins", "color", "colors", "colour", "colours", "one", "many"
    }

    invalid_exact = {
        "one color", "many colors", "same color", "different colors", "mostly one color",
        "mostly many colors", "one colour", "many colours", "same colour", "different colours"
    }

    if guess_l in invalid_exact:
        return False

    if len(words) == 1 and next(iter(words)) in invalid_single_words:
        return False

    if words and words.issubset(invalid_anywhere):
        return False

    if any(word in words for word in {"than", "bigger", "smaller", "larger"}):
        return False

    if re.search(r"\b(?:on land|in water|in the water|in air|in the air|in the sky|bigger than|smaller than|one color|many colors|same color|different colors)\b", guess_l):
        return False

    if re.search(r"^(?:on|in|at|under|over|near|with|without|has|have)\s+", guess_l):
        return False

    broad = broaden_specific_mystery_animal_guess(guess_l)
    if broad:
        return broad in MYSTERY_ANIMAL_COMMON_ANIMALS or broad in MYSTERY_ANIMAL_BROAD_GUESS_ANIMALS

    if guess_l in MYSTERY_ANIMAL_COMMON_ANIMALS:
        return True

    # OpenAI may know valid animals that are not in our local list. Allow short
    # animal-name-shaped guesses after the clue-fragment filters above.
    if 1 <= len(words) <= 3 and all(re.fullmatch(r"[a-z']+", word) for word in words):
        blocked_phrases = {"type of", "kind of", "sort of", "family of"}
        if not any(phrase in guess_l for phrase in blocked_phrases):
            return True

    return False

def get_mystery_animal_article(noun):
    noun = normalize_child_text(noun).lower()
    if not noun:
        return "a"
    first_word = noun.split()[0]
    if first_word[0] in "aeiou":
        return "an"
    return "a"


def broaden_specific_mystery_animal_guess(guess):
    """
    Keep the animal name OpenAI chose.

    Earlier versions collapsed sparrow -> bird and tarantula -> spider. That
    made later rounds feel less intelligent, especially when the child said
    something like "it is a type of bird." In rounds 7-9, Star should use the
    full clue history and make the best real animal guess it can, including
    specific kid-familiar animals.
    """
    guess = clean_open_ended_animal_name(guess)

    if not guess:
        return None

    return guess.lower().strip()

def make_mystery_animal_guess_line(raw_guess):
    guess = clean_open_ended_animal_name(raw_guess)

    if not is_probably_valid_mystery_animal_guess(guess):
        return None, None, None

    broad = broaden_specific_mystery_animal_guess(guess) or guess

    if not is_probably_valid_mystery_animal_guess(broad):
        return None, None, None

    article = get_mystery_animal_article(broad)
    question = f"Is it {article} {broad}?"
    message = f"Hmm, I think I have a guess. {question}"
    return broad, question, message

def get_child_revealed_animal(text):
    lowered = normalize_child_text(text).lower()

    if not lowered:
        return None

    cleaned = re.sub(r"[^a-z' -]", " ", lowered)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    words = set(re.findall(r"[a-z']+", cleaned))

    if not words:
        return None

    # Do NOT treat broad category clues as a final answer.
    # Example: "yes, it's a type of cat" should be stored as a clue,
    # not completed as "cat." Star must keep narrowing and later confirm.
    broad_category_patterns = [
        r"\b(type|kind|sort|family) of (cat|dog|fish|bird|bear|monkey)\b",
        r"\b(cat|dog|fish|bird|bear|monkey) (type|kind|family)\b",
        r"\bbig cat\b",
        r"\blittle cat\b"
    ]

    if any(re.search(pattern, cleaned) for pattern in broad_category_patterns):
        return None

    direct_reveal_patterns = [
        r"\bmy animal is (?:a |an |the )?([a-z -]+)\b",
        r"\bthe animal is (?:a |an |the )?([a-z -]+)\b",
        r"\bi picked (?:a |an |the )?([a-z -]+)\b",
        r"\bi chose (?:a |an |the )?([a-z -]+)\b",
        r"\bi was thinking of (?:a |an |the )?([a-z -]+)\b",
        r"\bi am thinking of (?:a |an |the )?([a-z -]+)\b",
        r"\bit was (?:a |an |the )?([a-z -]+)\b",
        r"\bit is (?:a |an |the )?([a-z -]+)\b",
        r"\bit's (?:a |an |the )?([a-z -]+)\b"
    ]

    for pattern in direct_reveal_patterns:
        match = re.search(pattern, cleaned)

        if not match:
            continue

        candidate_text = match.group(1).strip()
        candidate = clean_open_ended_animal_name(candidate_text)

        if candidate and is_probably_valid_mystery_animal_guess(candidate):
            return candidate

    # Direct short answers like "lion" or "a dog" count as a possible final answer,
    # but Star will still confirm it before ending the round.
    filler_words = {"a", "an", "the", "my", "animal", "is", "it", "it's", "it is"}
    meaningful_words = [word for word in re.findall(r"[a-z']+", cleaned) if word not in filler_words]

    if len(meaningful_words) <= 2:
        for animal in MYSTERY_ANIMAL_COMMON_ANIMALS:
            if animal in meaningful_words:
                return animal

    return None


def is_yes_response(text):
    lowered = normalize_child_text(text).lower()
    words = set(re.findall(r"[a-z']+", lowered))

    return bool(words & {
        "yes", "yeah", "yep", "yup", "sure", "correct", "right"
    }) or lowered in {"yes", "yeah", "yep", "yup"}


def is_no_response(text):
    lowered = normalize_child_text(text).lower()
    words = set(re.findall(r"[a-z']+", lowered))

    return bool(words & {
        "no", "nope", "nah", "not"
    }) or lowered in {"no", "nope", "nah"}


def classify_mystery_animal_choice_response(text, offer_next_game=False):
    lowered = normalize_child_text(text).lower()
    words = set(re.findall(r"[a-z']+", lowered))

    if not lowered:
        return "unclear"

    stop_words = {
        "stop", "done", "finish", "finished", "end", "quit", "leave",
        "dashboard", "no", "nope", "nah", "not", "dont", "don't"
    }

    next_game_words = {
        "different", "next", "other"
    }

    same_game_words = {
        "again", "same", "replay", "more", "continue",
        "yes", "yeah", "yep", "yup", "sure",
        "okay", "ok", "alright", "fine", "good", "cool",
        "this"
    }

    if words & stop_words:
        return "stop"

    if offer_next_game and words & next_game_words:
        return "next_game"

    if words & same_game_words:
        return "same_game"

    same_game_phrases = [
        "play again",
        "play another round",
        "another round",
        "one more round",
        "this game",
        "same game",
        "let's play",
        "lets play",
        "let us play",
        "keep playing",
        "do it again",
        "try again"
    ]

    if any(phrase in lowered for phrase in same_game_phrases):
        return "same_game"

    if offer_next_game:
        next_game_phrases = [
            "different game",
            "next game",
            "new game",
            "other game",
            "different version",
            "slightly different",
            "guessing game"
        ]

        if any(phrase in lowered for phrase in next_game_phrases):
            return "next_game"

    return "unclear"


def is_unclear_or_silent_response(text):
    lowered = normalize_child_text(text).lower()

    if not lowered:
        return True

    unclear_phrases = {
        "i don't know",
        "i dont know",
        "i do not know",
        "don't know",
        "dont know",
        "idk",
        "not sure",
        "not really sure",
        "i'm not sure",
        "im not sure",
        "maybe",
        "hmm",
        "uh",
        "um"
    }

    if lowered in unclear_phrases:
        return True

    usable_words = re.findall(r"[A-Za-z']+", lowered)

    if not usable_words:
        return True

    return False


def is_bare_yes_no_mystery_answer(text):
    lowered = normalize_child_text(text).lower()
    words = re.findall(r"[a-z']+", lowered)

    if not words:
        return False

    yes_no_words = {
        "yes", "yeah", "yep", "yup", "sure",
        "no", "nope", "nah", "not"
    }

    return len(words) <= 2 and all(word in yes_no_words for word in words)


def is_clear_mystery_animal_response(text, response_mode):
    cleaned = normalize_child_text(text)

    # A complaint like "that's a stupid question" is feedback about Star's
    # question, not an animal clue. Do not store it or praise it as helpful.
    if is_mystery_animal_question_complaint(cleaned):
        return False

    if is_unclear_or_silent_response(cleaned):
        return False

    if response_mode == "yes_no":
        return is_yes_response(cleaned) or is_no_response(cleaned)

    if response_mode == "guess_confirmation":
        return is_yes_response(cleaned) or is_no_response(cleaned)

    if response_mode == "round_choice":
        return len(re.findall(r"[A-Za-z']+", cleaned)) >= 1

    if response_mode in {
        "choice",
        "one_word",
        "short_phrase",
        "open_hint"
    }:
        if is_bare_yes_no_mystery_answer(cleaned):
            return False

        return len(re.findall(r"[A-Za-z']+", cleaned)) >= 1

    return len(re.findall(r"[A-Za-z']+", cleaned)) >= 1


def calm_mystery_animal_line(text, game_complete=False):
    text = re.sub(r"\s+", " ", str(text or "")).strip()

    if not text:
        return "Hmm, let me ask a tiny question."

    replacements = {
        "Amazing": "Nice",
        "amazing": "nice",
        "Awesome": "Nice",
        "awesome": "nice",
        "Wow": "Hmm",
        "wow": "hmm",
        "Ooo": "Hmm",
        "ooo": "hmm",
        "Oh, let me try to ask it in a simpler way": "That's okay. I have another question",
        "Let me try to ask it in a simpler way": "That's okay. I have another question",
        "Let me ask it in a simpler way": "That's okay. I have another question",
        "Maybe that was too hard": "That's okay",
        "That might have been too hard": "That's okay",
        "I couldn't hear you": "That's okay",
        "I could not hear you": "That's okay",
        "Great job talking": "Thank you, that helps",
        "Good job talking": "Thank you, that helps",
        "Good job saying that": "Thank you, that helps",
        "Great job saying that": "Thank you, that helps",
        "Good job using your words": "Thank you, that helps"
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    if not game_complete:
        text = text.replace("!", ".")

    if text.count("!") > 1:
        first = text.find("!")
        text = text[:first + 1] + text[first + 1:].replace("!", ".")

    return text[:260].strip()


def maybe_add_mystery_animal_acknowledgment(
    message,
    event_type,
    child_response,
    previous_response_mode,
    game_state
):
    import random

    if event_type != "child_answer":
        return message

    if previous_response_mode in {"none", "guess_confirmation", "round_choice"}:
        return message

    if not is_clear_mystery_animal_response(child_response, previous_response_mode):
        return message

    lowered_message = normalize_child_text(message).lower()

    existing_acknowledgments = [
        "thank you",
        "thanks",
        "that helps",
        "that's helpful",
        "that is helpful",
        "that gives me",
        "good clue",
        "helpful clue",
        "useful clue",
        "useful to know",
        "that narrows",
        "okay, that",
        "nice clue",
        "i can use",
        "that points me"
    ]

    if any(phrase in lowered_message for phrase in existing_acknowledgments):
        return message

    child_name = clean_mystery_child_name(session.get("child_name", ""))
    can_use_name = bool(child_name) and child_name.lower() not in {"there", "child"}

    clue_count = int(game_state.get("comfortable_answer_count", 0))
    use_name_now = can_use_name and clue_count > 0 and clue_count % 3 == 0

    if use_name_now:
        acknowledgments = [
            f"Thank you, {child_name}. That helps.",
            f"That is helpful, {child_name}.",
            f"Thanks, {child_name}. I can use that clue.",
            f"That clue helps, {child_name}."
        ]
    else:
        acknowledgments = [
            "Hmm, that helps.",
            "That helps.",
            "Okay, that helps.",
            "That gives me a clue.",
            "Hmm, that is useful.",
            "Okay, I can use that clue.",
            "That helps me narrow it down.",
            "Thank you, that helps."
        ]

    recent = list(game_state.get("recent_acknowledgments", []))[-5:]
    fresh = [ack for ack in acknowledgments if ack not in recent]

    acknowledgment = random.choice(fresh or acknowledgments)
    game_state["recent_acknowledgments"] = (recent + [acknowledgment])[-5:]

    return f"{acknowledgment} {message}"


MYSTERY_ANIMAL_STRUCTURED_QUESTIONS = {
    "simple": [
        {
            "key": "size_backpack",
            "question": "Is it bigger than a backpack, or smaller than a backpack?",
            "stage": "guided_choice",
            "response_mode": "choice"
        },
        {
            "key": "land_water_air",
            "question": "Does it mostly live on land, in water, or in the air?",
            "stage": "guided_choice",
            "response_mode": "choice"
        },
        {
            "key": "pet_wild",
            "question": "Is it usually a pet, a farm animal, or a wild animal?",
            "stage": "guided_choice",
            "response_mode": "choice"
        },
        {
            "key": "legs_count",
            "question": "Does it have no legs, two legs, four legs, or more than four legs?",
            "stage": "guided_choice",
            "response_mode": "choice"
        },
        {
            "key": "body_covering",
            "question": "Does it have fur, feathers, scales, smooth skin, or a hard shell?",
            "stage": "guided_choice",
            "response_mode": "choice"
        },
        {
            "key": "movement_simple",
            "question": "Does it mostly walk, run, jump, swim, crawl, or fly?",
            "stage": "guided_choice",
            "response_mode": "choice"
        }
    ],
    "details": [
        {
            "key": "size_hand",
            "question": "Is it smaller than your hand, or bigger than your hand?",
            "stage": "guided_choice",
            "response_mode": "choice"
        },
        {
            "key": "main_color",
            "question": "What are the main colors of your animal?",
            "stage": "guided_clue",
            "response_mode": "one_word"
        },
        {
            "key": "usual_place",
            "question": "Where would I usually find this animal?",
            "stage": "guided_clue",
            "response_mode": "short_phrase"
        },
        {
            "key": "food",
            "question": "What kind of food does it eat?",
            "stage": "guided_clue",
            "response_mode": "short_phrase"
        },
        {
            "key": "special_body_part",
            "question": "What body part should I notice first?",
            "stage": "tiny_hint",
            "response_mode": "short_phrase"
        },
        {
            "key": "movement_detail",
            "question": "How does it move most of the time?",
            "stage": "guided_clue",
            "response_mode": "short_phrase"
        },
        {
            "key": "animal_size_detail",
            "question": "Is it about the size of your hand, your backpack, or a grown-up?",
            "stage": "guided_clue",
            "response_mode": "short_phrase"
        }
    ],
    "hints": [
        {
            "key": "easy_look_hint",
            "question": "What does your animal look like?",
            "stage": "open_hint",
            "response_mode": "open_hint"
        },
        {
            "key": "easy_action_hint",
            "question": "What does your animal do a lot?",
            "stage": "open_hint",
            "response_mode": "open_hint"
        },
        {
            "key": "easy_place_hint",
            "question": "Where might I see your animal?",
            "stage": "open_hint",
            "response_mode": "open_hint"
        },
        {
            "key": "category_short_answer",
            "question": "What kind of animal is it? You can say bird, fish, bug, bear, or something else.",
            "stage": "guided_clue",
            "response_mode": "short_phrase"
        },
        {
            "key": "narrowing_choice",
            "question": "Is it more known for how it looks, where it lives, or what it does?",
            "stage": "guided_choice",
            "response_mode": "choice"
        },
        {
            "key": "best_clue",
            "question": "What is one clue I have not asked about yet?",
            "stage": "open_hint",
            "response_mode": "open_hint"
        },
        {
            "key": "final_helpful_hint",
            "question": "What hint would help me make my best guess?",
            "stage": "open_hint",
            "response_mode": "open_hint"
        }
    ]
}


def make_mystery_animal_question_item(key, question, stage="guided_choice", response_mode="choice"):
    return {
        "key": key,
        "question": question,
        "stage": stage,
        "response_mode": response_mode
    }



def get_mystery_animal_adaptive_question(game_state, event_type="child_answer"):
    """
    Deterministic follow-up picker.

    Star should sound smart because it asks the next useful branch of the
    decision tree, not because it randomly rephrases the same broad question.
    This function deliberately blocks back-to-back habitat/movement repeats.
    """
    asked_keys = set(game_state.get("current_round_question_keys", []))
    unclear_question_keys = set(game_state.get("unclear_question_keys", []))
    asked_families = set(game_state.get("asked_question_families", []))
    tags = get_mystery_animal_clue_tags(game_state)
    last_family = game_state.get("last_pending_question_family") or get_question_family(game_state.get("last_question", ""))

    def add(key, question, stage="guided_choice", response_mode="choice", family=None):
        family = family or get_question_family(question)

        if key in asked_keys or key in unclear_question_keys:
            return None

        # Do not ask a question that feels like the same thing in new words.
        if family in asked_families:
            return None

        # The child experiences habitat and movement questions as very similar
        # when they are asked back-to-back: land/water/air vs walk/swim/fly.
        if last_family in {"habitat", "movement"} and family in {"habitat", "movement"}:
            return None

        if key == "size_hand" and "big" in tags:
            return None

        if key == "size_person" and "small" in tags:
            return None

        return make_mystery_animal_question_item(key, question, stage, response_mode)

    candidates = []

    current_round_number = int(game_state.get("rounds_completed", 0) or 0) + 1
    declared_category = get_mystery_animal_declared_category(game_state)

    if current_round_number >= 7 and declared_category:
        candidates.append(add(
            f"narrow_{declared_category}_type",
            f"What kind of {declared_category} is it? You can tell me how it looks or what it does.",
            stage="open_hint",
            response_mode="open_hint",
            family="type_detail"
        ))
        candidates.append(add(
            f"different_{declared_category}_feature",
            f"What makes it different from other {declared_category}s?",
            stage="open_hint",
            response_mode="open_hint",
            family="type_detail"
        ))

    # If an answer gives a strong branch, ask the most useful narrowing question.
    # These only run when they are not repeating the same family.
    if "big" in tags:
        candidates.append(add(
            "size_person",
            "Is it bigger than a person, or smaller than a person?",
            family="size"
        ))

    if "small" in tags:
        candidates.append(add(
            "size_hand",
            "Is it smaller than your hand, or bigger than your hand?",
            family="size"
        ))

    if "air" in tags or "fly" in tags or "wings" in tags:
        candidates.append(add(
            "wings_covering",
            "Does it have feathers, or wings without feathers?",
            family="appearance"
        ))

    if "many_legs" in tags and "web" not in tags:
        candidates.append(add(
            "web_question",
            "Does it make a web, or not really?",
            family="appearance"
        ))

    if "water" in tags and "shell" not in tags and "scales" not in tags:
        candidates.append(add(
            "water_covering",
            "Does it have scales, a shell, or smooth skin?",
            family="appearance"
        ))

    if "fur" in tags and "pet" in tags:
        candidates.append(add(
            "bark_meow",
            "Is it more like a dog, or more like a cat?",
            family="category"
        ))

    if "crawl" in tags and "no_legs" in tags and "scales" not in tags:
        candidates.append(add(
            "snake_scales",
            "Does it have scales?",
            family="appearance"
        ))

    for item in candidates:
        if item:
            return item

    return None


def get_mystery_animal_round_band(game_state):
    round_number = int(game_state.get("rounds_completed", 0) or 0) + 1

    if round_number <= 3:
        return "simple"
    if round_number <= 6:
        return "details"
    return "hints"


def get_mystery_animal_declared_category(game_state):
    """
    Detect when the child has already given a broad category clue, such as
    "it is a type of bird." Later questions should narrow within that category
    instead of asking the category again or guessing only the category.
    """
    qa_items = game_state.get("qa_history") or game_state.get("known_clues", [])
    text_parts = []

    for item in qa_items:
        if not isinstance(item, dict):
            continue
        text_parts.append(str(item.get("answer", "")))
        text_parts.append(str(item.get("question", "")))

    text = normalize_child_text(" ".join(text_parts)).lower()

    category_aliases = {
        "bird": ["bird", "birds"],
        "bear": ["bear", "bears"],
        "fish": ["fish"],
        "bug": ["bug", "bugs", "insect", "insects"],
        "spider": ["spider", "spiders"],
        "snake": ["snake", "snakes"],
        "frog": ["frog", "frogs"],
        "cat": ["cat", "cats", "big cat", "big cats"],
        "dog": ["dog", "dogs"],
        "monkey": ["monkey", "monkeys", "ape", "apes"],
        "reptile": ["reptile", "reptiles"],
        "mammal": ["mammal", "mammals"]
    }

    for canonical, aliases in category_aliases.items():
        for alias in aliases:
            escaped = re.escape(alias)
            patterns = [
                rf"\b(type|kind|sort|family) of {escaped}\b",
                rf"\b{escaped} (type|kind|sort|family)\b",
                rf"\bit'?s (a |an )?{escaped}\b",
                rf"\bit is (a |an )?{escaped}\b",
                rf"\b{escaped}\b"
            ]
            if any(re.search(pattern, text) for pattern in patterns):
                return canonical

    return None


def mystery_animal_guess_is_too_broad_for_declared_type(guess, game_state):
    guess = clean_open_ended_animal_name(guess)
    declared_category = get_mystery_animal_declared_category(game_state)

    if not guess or not declared_category:
        return False

    return guess.lower().strip() == declared_category


def get_question_history_set(game_state):
    question_history = game_state.get("question_history", [])

    return {
        normalize_child_text(item.get("question", "")).lower()
        for item in question_history
        if isinstance(item, dict)
    }


def get_question_family(question):
    lowered = normalize_child_text(question).lower()

    if any(word in lowered for word in ["small", "big", "bigger", "smaller", "size", "backpack", "hand", "person"]):
        return "size"

    if any(word in lowered for word in ["land", "water", "where", "house", "outside", "farm", "zoo", "place", "live", "air", "sky"]):
        return "habitat"

    if any(word in lowered for word in ["fly", "walk", "swim", "crawl", "jump", "move", "hops", "runs", "float"]):
        return "movement"

    if any(word in lowered for word in ["fur", "wings", "wing", "tail", "legs", "leg", "fins", "body", "look", "color", "soft", "rough", "part", "picture", "feathers", "scales", "shell", "skin", "web", "beak"]):
        return "appearance"

    if any(word in lowered for word in ["eat", "food"]):
        return "food"

    if any(word in lowered for word in ["pet", "wild", "farm", "zoo", "house"]):
        return "category"

    if any(word in lowered for word in ["hint", "clue", "know", "guess", "special", "narrow"]):
        return "hint"

    return "general"


def pick_structured_mystery_animal_question(game_state, event_type="child_answer"):
    """
    Pick the next question from a true decision tree.

    Important behavior changes:
    - Never blocks early questions just because they were used in a previous
      animal round. That was why round 1-3 could fall through into body-part
      open hints.
    - Never asks the same key in the current animal round.
    - Avoids back-to-back habitat/movement questions that sound repetitive.
    - In rounds 1-3, never falls back to open-ended body-part prompts.
    """
    asked_this_round = set(game_state.get("current_round_question_keys", []))
    unclear_question_keys = set(game_state.get("unclear_question_keys", []))
    asked_families = set(game_state.get("asked_question_families", []))
    tags = get_mystery_animal_clue_tags(game_state)
    band = get_mystery_animal_round_band(game_state)

    adaptive = get_mystery_animal_adaptive_question(game_state, event_type)
    if adaptive and adaptive.get("key") not in asked_this_round and adaptive.get("key") not in unclear_question_keys:
        chosen = adaptive
    else:
        questions = list(MYSTERY_ANIMAL_STRUCTURED_QUESTIONS.get(band, []))

        # Smarter order for each progression band. This is the actual tree.
        order_by_band = {
            "simple": [
                "size_backpack",
                "body_covering",
                "legs_count",
                "pet_wild",
                "land_water_air",
                "movement_simple"
            ],
            "details": [
                "main_color",
                "usual_place",
                "food",
                "movement_detail",
                "animal_size_detail",
                "special_body_part",
                "size_hand"
            ],
            "hints": [
                "easy_look_hint",
                "easy_action_hint",
                "easy_place_hint",
                "category_short_answer",
                "narrowing_choice",
                "best_clue",
                "final_helpful_hint"
            ]
        }

        priority = order_by_band.get(band, [])
        questions.sort(key=lambda item: priority.index(item.get("key")) if item.get("key") in priority else 99)

        def allowed(item, avoid_family=True):
            key = item.get("key")
            question = item.get("question", "")
            family = get_question_family(question)
            last_family = game_state.get("last_pending_question_family") or get_question_family(game_state.get("last_question", ""))

            if key in asked_this_round or key in unclear_question_keys:
                return False

            if key == "size_hand" and "big" in tags:
                return False

            if key == "size_person" and "small" in tags:
                return False

            if key == "movement_simple" and "land_water_air" in asked_this_round:
                return False

            if key == "land_water_air" and any(k in asked_this_round for k in {"movement_simple", "movement_land", "water_movement", "movement_many_legs"}):
                return False

            if last_family in {"habitat", "movement"} and family in {"habitat", "movement"}:
                return False

            if avoid_family and family in asked_families:
                return False

            return True

        available = [item for item in questions if allowed(item, avoid_family=True)]
        if not available:
            available = [item for item in questions if allowed(item, avoid_family=False)]

        # For the first three activity rounds, stay concrete no matter what.
        if not available and band == "simple":
            simple_fallbacks = [
                make_mystery_animal_question_item("simple_color", "Is it mostly one color, or many colors?", "guided_choice", "choice"),
                make_mystery_animal_question_item("simple_tail", "Does it have a tail, or no tail?", "guided_choice", "choice"),
                make_mystery_animal_question_item("simple_noise", "Is it usually quiet, or loud?", "guided_choice", "choice")
            ]
            available = [
                item for item in simple_fallbacks
                if item["key"] not in asked_this_round and item["key"] not in unclear_question_keys
            ] or [item for item in simple_fallbacks if item["key"] not in asked_this_round] or simple_fallbacks

        # For rounds 4-6, concrete detail prompts are okay, but avoid broad hint wording.
        if not available and band == "details":
            detail_fallbacks = [
                make_mystery_animal_question_item("detail_tail", "Does it have a long tail, a short tail, or no tail?", "guided_choice", "choice"),
                make_mystery_animal_question_item("detail_skin", "Is its body soft, rough, smooth, or hard?", "guided_choice", "choice"),
                make_mystery_animal_question_item("detail_home", "Does it live near people, on a farm, in the wild, or in water?", "guided_choice", "choice")
            ]
            available = [
                item for item in detail_fallbacks
                if item["key"] not in asked_this_round and item["key"] not in unclear_question_keys
            ] or [item for item in detail_fallbacks if item["key"] not in asked_this_round] or detail_fallbacks

        if not available:
            hint_fallbacks = [
                make_mystery_animal_question_item("extra_hint_look", "What does your animal look like?", "open_hint", "open_hint"),
                make_mystery_animal_question_item("extra_hint_action", "What does your animal do a lot?", "open_hint", "open_hint"),
                make_mystery_animal_question_item("extra_hint_place", "Where might I see your animal?", "open_hint", "open_hint"),
                make_mystery_animal_question_item("extra_hint_choice", "Is your clue mostly about how it looks, where it lives, or what it does?", "guided_choice", "choice"),
                make_mystery_animal_question_item("extra_hint_clue", "What is one clue I have not asked about yet?", "open_hint", "open_hint")
            ]
            available = [
                item for item in hint_fallbacks
                if item["key"] not in asked_this_round and item["key"] not in unclear_question_keys
            ] or [item for item in hint_fallbacks if item["key"] not in asked_this_round] or hint_fallbacks

        if event_type == "no_response" and len(available) > 1:
            last_key = game_state.get("last_question_key")
            available = [item for item in available if item.get("key") != last_key] or available

        chosen = available[0]

    key = chosen["key"]
    game_state["pending_question_key"] = key

    family = get_question_family(chosen.get("question", ""))
    game_state["last_pending_question_family"] = family

    return chosen

def choose_non_repeating_question(level, game_state):
    import random

    asked_questions = get_question_history_set(game_state)
    recent_families = list(game_state.get("recent_question_families", []))[-3:]
    questions = list(level.get("fallback_questions", []))

    fresh_questions = [
        question for question in questions
        if normalize_child_text(question).lower() not in asked_questions
    ]

    pool = fresh_questions or questions

    if not pool:
        return "What is one clue?"

    # Prefer a different type of question than the last few turns.
    family_filtered = [
        question for question in pool
        if get_question_family(question) not in recent_families[-2:]
    ]

    if family_filtered:
        pool = family_filtered

    question = random.choice(pool)
    family = get_question_family(question)

    updated_families = recent_families + [family]
    game_state["recent_question_families"] = updated_families[-4:]

    return question


def get_fallback_mystery_animal_question(level, game_state=None, event_type="child_answer"):
    if game_state is None:
        game_state = {}

    structured_question = pick_structured_mystery_animal_question(game_state, event_type)
    question_text = structured_question["question"]
    stage = structured_question.get("stage", level["stage"])
    response_mode = structured_question.get("response_mode", level["response_mode"])

    if event_type == "no_response":
        calm_prefixes = [
            "That's okay.",
            "No problem.",
            "That's okay. We can try a different question.",
            "No worries."
        ]

        prefix_index = int(game_state.get("unclear_or_silent_count", 0)) % len(calm_prefixes)
        prefix = calm_prefixes[prefix_index]
        if prefix.endswith("question."):
            message = f"{prefix} {question_text}"
        else:
            message = f"{prefix} {question_text}"
    else:
        message = f"Hmm, {question_text[0].lower() + question_text[1:]}"

    return {
        "message": message,
        "stage": stage,
        "response_mode": response_mode,
        "question_text": question_text,
        "question_key": structured_question.get("key")
    }



def get_mystery_animal_clue_tags(game_state):
    """
    Convert the current round's Q/A history into tags/constraints.
    These tags are treated as evidence and hard filters before Star guesses.
    """
    tags = set()
    qa_items = game_state.get("qa_history") or game_state.get("known_clues", [])

    for item in qa_items:
        if not isinstance(item, dict):
            continue

        key = normalize_child_text(item.get("question_key", "")).lower()
        question = normalize_child_text(item.get("question", "")).lower()
        answer = normalize_child_text(item.get("answer", "")).lower()
        combined = f"{question} {answer}".lower()

        words = set(re.findall(r"[a-z']+", answer))

        # Broad category clues should be remembered as constraints, not guessed
        # back to the child. Example: "it is a type of bird" means Star should
        # now narrow within birds.
        for category in ["bird", "bear", "fish", "bug", "insect", "spider", "snake", "frog", "cat", "dog", "monkey", "reptile", "mammal"]:
            if re.search(rf"\b(type|kind|sort|family) of {category}s?\b", answer) or re.search(rf"\b{category}s? (type|kind|sort|family)\b", answer):
                tags.add(f"category_{category}")

        if key == "size_backpack" or "backpack" in question:
            if any(word in words for word in {"big", "bigger", "large", "larger", "huge"}) or "bigger than" in answer:
                tags.add("big")
            if any(word in words for word in {"small", "smaller", "little", "tiny"}) or "smaller than" in answer:
                tags.add("small")

        if key == "size_hand" or "your hand" in question:
            if any(word in words for word in {"big", "bigger", "larger"}) or "bigger than" in answer:
                tags.add("bigger_than_hand")
            if any(word in words for word in {"small", "smaller", "tiny"}) or "smaller than" in answer:
                tags.add("smaller_than_hand")
                tags.add("small")

        if key == "size_person" or "person" in question:
            if any(word in words for word in {"big", "bigger", "larger"}) or "bigger than" in answer:
                tags.add("bigger_than_person")
                tags.add("big")
            if any(word in words for word in {"small", "smaller"}) or "smaller than" in answer:
                tags.add("smaller_than_person")

        if key == "land_water_air" or "land" in question or "water" in question or "air" in question:
            if "water" in words or "ocean" in words or "pond" in words or "sea" in words:
                tags.add("water")
            if "air" in words or "sky" in words:
                tags.add("air")
            if "land" in words or "ground" in words or "tree" in words:
                tags.add("land")

        if key == "pet_wild" or "pet" in question or "wild" in question or "farm" in question:
            if "wild" in words or "zoo" in words:
                tags.add("wild")
            if "pet" in words or "house" in words or "home" in words:
                tags.add("pet")
            if "farm" in words:
                tags.add("farm")

        if key == "legs_count" or "legs" in question:
            if any(word in words for word in {"no", "zero", "none"}) or "0" in answer:
                tags.add("no_legs")
            if any(word in words for word in {"two"}) or "2" in answer:
                tags.add("two_legs")
            if any(word in words for word in {"four"}) or "4" in answer:
                tags.add("four_legs")
            if any(word in words for word in {"more", "lots", "many", "six", "eight", "multiple"}) or "6" in answer or "8" in answer or "more than four" in answer:
                tags.add("many_legs")

        if key in {"body_covering", "wings_covering"} or any(word in question for word in ["fur", "feathers", "scales", "smooth skin", "shell"]):
            if "fur" in words or "furry" in words:
                tags.add("fur")
            if "feather" in answer or "feathers" in words:
                tags.add("feathers")
            if "scale" in answer or "scales" in words or "scaly" in words:
                tags.add("scales")
            if "smooth" in words or "skin" in words:
                tags.add("smooth_skin")
            if "shell" in words:
                tags.add("shell")

        if key in {"movement_simple", "movement_detail", "movement_many_legs", "water_movement"} or any(word in question for word in ["walk", "swim", "fly", "crawl", "jump", "move"]):
            if any(word in words for word in {"jump", "jumps", "jumping", "hop", "hops", "hopping"}):
                tags.add("jump")
            if any(word in words for word in {"fly", "flies", "flying"}):
                tags.add("fly")
            if any(word in words for word in {"swim", "swims", "swimming"}):
                tags.add("swim")
            if any(word in words for word in {"walk", "walks", "walking", "run", "runs", "running"}):
                tags.add("walk")
            if any(word in words for word in {"crawl", "crawls", "crawling"}):
                tags.add("crawl")

        if key == "web_question" or "web" in question:
            if "yes" in words or "yeah" in words or "web" in words:
                tags.add("web")
            if "no" in words or "not" in words:
                tags.add("no_web")

        if key in {"shell_or_arms", "shell_question"} or "hard shell" in question or "no shell" in question:
            if "shell" in words or "hard" in words:
                tags.add("shell")
            if "no" in words or "not" in words:
                tags.add("no_shell")

        if key == "bark_meow" or "dog" in question or "cat" in question:
            if "dog" in words or "bark" in words:
                tags.add("dog_like")
            if "cat" in words or "meow" in words:
                tags.add("cat_like")

        # Catch useful clues even if they came from a more open-ended answer.
        if any(phrase in combined for phrase in ["has fur", "with fur", "furry"]):
            tags.add("fur")
        if any(phrase in combined for phrase in ["has feathers", "with feathers"]):
            tags.add("feathers")
        if any(word in words for word in {"feather", "feathers", "feathery"}):
            tags.add("feathers")
        if any(word in words for word in {"beak", "beaks", "bill"}):
            tags.add("beak")
        if any(word in words for word in {"wing", "wings"}):
            tags.add("wings")
        if any(phrase in combined for phrase in ["has scales", "with scales", "scaly"]):
            tags.add("scales")
        if "web" in answer:
            tags.add("web")
        if any(word in answer for word in ["spider", "arachnid"]):
            tags.add("spider_like")
        if any(word in answer for word in ["jump", "jumps", "jumping", "hop", "hops", "hopping"]):
            tags.add("jump")
        if any(word in answer for word in ["crawl", "crawls", "crawling"]):
            tags.add("crawl")
        if "bigger than a backpack" in combined or "larger than a backpack" in combined:
            tags.add("big")
        if "smaller than a backpack" in combined:
            tags.add("small")
        if "eight legs" in combined or "8 legs" in combined or "more than four legs" in combined:
            tags.add("many_legs")

        # High-signal round 4-6 clues. These make Star smarter without changing
        # the round 1-3 question flow. They are evidence, not hard-coded answers.
        if any(phrase in combined for phrase in [
            "antarctica", "antarctic", "south pole", "ice", "icy", "snow", "snowy", "very cold", "cold place"
        ]):
            tags.add("cold_place")
            if any(phrase in combined for phrase in ["antarctica", "antarctic", "south pole"]):
                tags.add("antarctica")

        if any(phrase in answer for phrase in ["waddle", "waddles", "waddling"]):
            tags.add("waddle")

        if ("black" in words and "white" in words) or any(phrase in combined for phrase in [
            "black and white", "white and black", "black white", "white black"
        ]):
            tags.add("black_white")

        # If the answer to a food question is fish, remember that it eats fish.
        # Do not treat that as the animal being a fish.
        if key == "food" or "food" in question or "eat" in question:
            if any(word in words for word in {"fish", "fishes"}):
                tags.add("eats_fish")

    return tags


def get_mystery_animal_clue_dictionary(game_state):
    """
    Build the actual clue memory for the current animal.
    This is the main intelligence layer: question type -> child's answer(s).
    It is not a closed animal candidate list.
    """
    clue_dict = {}
    qa_items = game_state.get("qa_history") or game_state.get("known_clues", [])

    for index, item in enumerate(qa_items, start=1):
        if not isinstance(item, dict):
            continue

        question_key = normalize_child_text(item.get("question_key", "general")).lower() or "general"
        question = normalize_child_text(item.get("question", ""))
        answer = normalize_child_text(item.get("answer", ""))

        if not answer:
            continue

        family = get_question_family(question or question_key)
        bucket_key = question_key or family or f"clue_{index}"

        normalized_value = normalize_mystery_animal_clue_value(
            question_key=question_key,
            question=question,
            answer=answer
        )

        if bucket_key not in clue_dict:
            clue_dict[bucket_key] = {
                "question_type": bucket_key,
                "family": family,
                "question": question,
                "answers": [],
                "latest_answer": "",
                "normalized_values": []
            }

        clue_dict[bucket_key]["answers"].append(answer[:120])
        clue_dict[bucket_key]["latest_answer"] = answer[:120]

        if normalized_value:
            clue_dict[bucket_key]["normalized_values"].append(normalized_value)

    return clue_dict


def normalize_mystery_animal_clue_value(question_key, question, answer):
    answer_l = normalize_child_text(answer).lower()
    question_l = normalize_child_text(question).lower()
    words = set(re.findall(r"[a-z']+", answer_l))

    if not answer_l:
        return None

    if question_key == "legs_count" or "legs" in question_l:
        if any(word in words for word in {"no", "zero", "none"}) or "0" in answer_l:
            return "no legs"
        if any(word in words for word in {"two"}) or "2" in answer_l:
            return "two legs"
        if any(word in words for word in {"four"}) or "4" in answer_l:
            return "four legs"
        if any(word in words for word in {"more", "many", "lots", "six", "eight", "multiple"}) or "6" in answer_l or "8" in answer_l or "more than four" in answer_l:
            return "more than four legs"

    if "backpack" in question_l:
        if any(word in words for word in {"small", "smaller", "little", "tiny"}) or "smaller than" in answer_l:
            return "smaller than a backpack"
        if any(word in words for word in {"big", "bigger", "large", "larger"}) or "bigger than" in answer_l:
            return "bigger than a backpack"

    if "hand" in question_l:
        if any(word in words for word in {"small", "smaller", "tiny"}) or "smaller than" in answer_l:
            return "smaller than a hand"
        if any(word in words for word in {"big", "bigger", "large", "larger"}) or "bigger than" in answer_l:
            return "bigger than a hand"

    if any(word in question_l for word in ["crawl", "walk", "jump", "swim", "fly", "move"]):
        found = []
        if any(word in words for word in {"crawl", "crawls", "crawling"}):
            found.append("crawls")
        if any(word in words for word in {"walk", "walks", "walking", "run", "runs", "running"}):
            found.append("walks")
        if any(word in words for word in {"jump", "jumps", "jumping", "hop", "hops", "hopping"}):
            found.append("jumps")
        if any(word in words for word in {"swim", "swims", "swimming"}):
            found.append("swims")
        if any(word in words for word in {"fly", "flies", "flying"}):
            found.append("flies")
        if found:
            return ", ".join(found)

    if any(word in question_l for word in ["land", "water", "air", "live"]):
        found = []
        if any(word in words for word in {"land", "ground", "tree", "outside"}):
            found.append("land")
        if any(word in words for word in {"water", "ocean", "sea", "pond", "lake"}):
            found.append("water")
        if any(word in words for word in {"air", "sky"}):
            found.append("air")
        if found:
            return ", ".join(found)

    return answer_l[:80]


def get_mystery_animal_required_guess_tags(game_state):
    clue_tags = set(get_mystery_animal_clue_tags(game_state))

    answer_text = " ".join(
        str(item.get('answer', ''))
        for item in (game_state.get("qa_history") or game_state.get("known_clues", []))
        if isinstance(item, dict)
    ).lower()

    if "wild" in answer_text:
        clue_tags.add("wild")
    if "pet" in answer_text:
        clue_tags.add("pet")
    if "farm" in answer_text:
        clue_tags.add("farm")
    if "fur" in answer_text or "furry" in answer_text:
        clue_tags.add("fur")
    if "feather" in answer_text:
        clue_tags.add("feathers")
    if "beak" in answer_text or " bill" in f" {answer_text}":
        clue_tags.add("beak")
    if "wing" in answer_text:
        clue_tags.add("wings")
    if "scale" in answer_text or "scaly" in answer_text:
        clue_tags.add("scales")
    if "web" in answer_text:
        clue_tags.add("web")
    if any(word in answer_text for word in ["bark", "barks", "barking", "woof", "dog-like", "dog like"]):
        clue_tags.add("dog_like")
    if any(word in answer_text for word in ["meow", "meows", "meowing", "purr", "purrs", "whisker", "whiskers", "cat-like", "cat like"]):
        clue_tags.add("cat_like")
    if any(word in answer_text for word in ["trunk"]):
        clue_tags.add("trunk")
    if any(phrase in answer_text for phrase in ["long neck", "really tall neck", "tall neck"]):
        clue_tags.add("long_neck")
    if any(word in answer_text for word in ["stripe", "stripes", "striped"]):
        clue_tags.add("stripes")
    if any(word in answer_text for word in ["spot", "spots", "spotted"]):
        clue_tags.add("spots")
    if any(word in answer_text for word in ["horn", "horns"]):
        clue_tags.add("horns")
    if any(word in answer_text for word in ["antler", "antlers"]):
        clue_tags.add("antlers")
    if (
        "black and white" in answer_text
        or "white and black" in answer_text
        or "black white" in answer_text
        or "white black" in answer_text
        or ("black" in answer_text and "white" in answer_text)
    ):
        clue_tags.add("black_white")
    if re.search(r"\bwhite\b", answer_text):
        clue_tags.add("white")
    if re.search(r"\bblack\b", answer_text):
        clue_tags.add("black")
    if re.search(r"\bbrown\b", answer_text):
        clue_tags.add("brown")
    if any(word in answer_text for word in ["mane"]):
        clue_tags.add("mane")
    if any(word in answer_text for word in ["quack", "quacks", "duck"]):
        clue_tags.add("duck_like")
    if any(word in answer_text for word in ["buzz", "buzzes", "buzzing", "stinger", "sting"]):
        clue_tags.add("bee_like")
    if any(word in answer_text for word in ["jump", "jumps", "jumping", "hop", "hops", "hopping"]):
        clue_tags.add("jump")
    if any(word in answer_text for word in ["swim", "swims", "swimming"]):
        clue_tags.add("swim")
    if any(word in answer_text for word in ["fly", "flies", "flying"]):
        clue_tags.add("fly")
    if any(word in answer_text for word in ["crawl", "crawls", "crawling"]):
        clue_tags.add("crawl")
    if "eight legs" in answer_text or "8 legs" in answer_text or "more than four legs" in answer_text:
        clue_tags.add("many_legs")
    if any(phrase in answer_text for phrase in ["antarctica", "antarctic", "south pole"]):
        clue_tags.add("antarctica")
        clue_tags.add("cold_place")
    elif any(phrase in answer_text for phrase in ["ice", "icy", "snow", "snowy", "very cold", "cold place"]):
        clue_tags.add("cold_place")
    if any(phrase in answer_text for phrase in ["waddle", "waddles", "waddling"]):
        clue_tags.add("waddle")
    if any(phrase in answer_text for phrase in ["eats fish", "eat fish", "fish to eat", "food is fish", "fish"]):
        # This is intentionally tagged as food evidence, not as a fish identity.
        clue_tags.add("eats_fish")

    return {
        tag for tag in clue_tags
        if tag in {
            "big", "small", "bigger_than_hand", "smaller_than_hand", "bigger_than_person", "smaller_than_person",
            "water", "air", "land", "wild", "pet", "farm",
            "fur", "feathers", "scales", "smooth_skin", "shell", "beak", "wings",
            "jump", "fly", "swim", "walk", "crawl", "web", "no_web", "soft_arms",
            "no_legs", "two_legs", "four_legs", "many_legs",
            "dog_like", "cat_like", "spider_like", "trunk", "long_neck", "stripes", "spots",
            "horns", "antlers", "black_white", "mane", "duck_like", "bee_like",
            "antarctica", "cold_place", "eats_fish", "waddle", "white", "black", "brown"
        }
    }


def mystery_animal_guess_contradicts_clues(guess, game_state):
    """
    This is not a candidate-list filter. It only blocks obvious contradictions.
    Unknown animals are allowed through so OpenAI can guess beyond anything we prelisted.
    """
    guess = clean_open_ended_animal_name(guess)

    if not guess:
        return False

    tags = get_mystery_animal_required_guess_tags(game_state)
    guess_words = set(re.findall(r"[a-z']+", guess.lower()))
    guess_l = guess.lower()

    obvious_four_leg_or_mammal = {
        "dog", "cat", "kangaroo", "rabbit", "horse", "cow", "lion", "tiger", "bear",
        "frog", "lizard", "elephant", "giraffe", "zebra", "pig", "goat", "sheep",
        "deer", "mouse", "hamster", "fox", "wolf", "leopard", "cheetah", "panda",
        "koala", "monkey", "gorilla"
    }

    obvious_no_leg_or_fish = {"snake", "fish", "shark", "dolphin", "whale", "eel"}
    obvious_two_leg_animals = {"bird", "duck", "chicken", "penguin", "owl", "ostrich", "flamingo", "kangaroo"}
    obvious_many_leg_animals = {"spider", "ant", "bee", "butterfly", "ladybug", "crab", "octopus", "squid", "centipede", "millipede"}

    if "many_legs" in tags and guess_l in obvious_four_leg_or_mammal.union(obvious_no_leg_or_fish).union(obvious_two_leg_animals):
        return True

    if "four_legs" in tags and guess_l in obvious_many_leg_animals.union(obvious_no_leg_or_fish).union({"bird", "duck", "chicken", "penguin", "owl"}):
        return True

    if "two_legs" in tags and guess_l in obvious_four_leg_or_mammal.union(obvious_many_leg_animals).union(obvious_no_leg_or_fish - {"fish"}):
        return True

    if "no_legs" in tags and guess_l in obvious_four_leg_or_mammal.union(obvious_two_leg_animals).union(obvious_many_leg_animals):
        return True

    if "web" in tags and guess_l in obvious_four_leg_or_mammal.union(obvious_two_leg_animals).union(obvious_no_leg_or_fish):
        return True

    if "dog_like" in tags and guess_l not in {"dog", "puppy", "wolf", "fox", "coyote"} and guess_l in obvious_four_leg_or_mammal:
        return True

    if "cat_like" in tags and guess_l not in {"cat", "kitten", "lion", "tiger", "leopard", "cheetah", "panther"} and guess_l in obvious_four_leg_or_mammal:
        return True

    return False



def get_mystery_animal_answer_families(game_state):
    families = set()

    for item in game_state.get("qa_history", []) or game_state.get("known_clues", []):
        if not isinstance(item, dict):
            continue

        key = normalize_child_text(item.get("question_key", "")).lower()
        question = normalize_child_text(item.get("question", "")).lower()
        answer = normalize_child_text(item.get("answer", "")).lower()

        if not answer:
            continue

        family = get_question_family(question or key)

        if key.startswith("size") or family == "size":
            families.add("size")
        elif key in {"land_water_air", "usual_place"} or family == "habitat":
            families.add("habitat")
        elif key in {"legs_count"}:
            families.add("legs")
        elif "movement" in key or family == "movement":
            families.add("movement")
        elif key in {"body_covering", "wings_covering", "shell_question", "web_question", "special_body_part"} or family == "appearance":
            families.add("appearance")
        elif key in {"pet_wild"} or family == "category":
            families.add("category")
        elif key in {"food"} or family == "food":
            families.add("food")
        else:
            families.add(family or "general")

    return families


MYSTERY_ANIMAL_GUESS_PROFILES = {
    # Broad categories first. These make Star willing to make educated guesses
    # without needing an impossible closed list of every species.
    "bird": {"feathers", "wings", "beak", "fly", "air", "two_legs"},
    "fish": {"water", "swim", "scales", "no_legs"},
    "snake": {"no_legs", "crawl", "scales", "land"},
    "spider": {"many_legs", "crawl", "web", "land"},
    "crab": {"many_legs", "water", "crawl", "shell"},
    "turtle": {"shell", "water", "four_legs", "swim"},
    "frog": {"jump", "water", "land", "smooth_skin", "small"},
    "dog": {"pet", "fur", "four_legs", "dog_like", "walk"},
    "cat": {"pet", "fur", "four_legs", "cat_like", "walk"},
    "rabbit": {"small", "fur", "four_legs", "jump", "pet"},
    "horse": {"big", "farm", "fur", "four_legs", "walk"},
    "cow": {"big", "farm", "four_legs", "walk"},
    "pig": {"farm", "four_legs", "walk"},
    "sheep": {"farm", "fur", "four_legs"},
    "goat": {"farm", "four_legs", "horns"},
    "lion": {"wild", "fur", "four_legs", "cat_like", "big"},
    "tiger": {"wild", "fur", "four_legs", "cat_like", "big"},
    "bear": {"wild", "fur", "four_legs", "big"},
    "polar bear": {"wild", "fur", "four_legs", "big", "white", "cold_place", "swim", "eats_fish"},
    "panda": {"wild", "fur", "four_legs", "big", "black_white"},
    "grizzly bear": {"wild", "fur", "four_legs", "big", "brown"},
    "elephant": {"wild", "big", "four_legs"},
    "giraffe": {"wild", "big", "four_legs"},
    "zebra": {"wild", "four_legs"},
    "monkey": {"wild", "fur", "walk", "small"},
    "kangaroo": {"jump", "big", "land", "wild"},
    "duck": {"bird", "feathers", "beak", "wings", "water", "swim", "two_legs"},
    "penguin": {"bird", "feathers", "beak", "wings", "water", "swim", "two_legs", "no_fly", "black_white", "antarctica", "cold_place", "eats_fish", "waddle", "white", "black", "brown"},
    "butterfly": {"wings", "fly", "small", "air"},
    "bee": {"wings", "fly", "small", "air"},
    "dolphin": {"water", "swim", "big", "smooth_skin"},
    "whale": {"water", "swim", "big", "smooth_skin"},
    "shark": {"water", "swim", "big"},
    "octopus": {"water", "swim", "soft_arms"},
    "crocodile": {"water", "land", "scales", "four_legs", "crawl"},
    "lizard": {"land", "scales", "four_legs", "crawl"},
    "squirrel": {"small", "fur", "four_legs", "land"},
    "mouse": {"small", "fur", "four_legs", "land"},
    "hamster": {"small", "fur", "four_legs", "pet"},
    "fox": {"wild", "fur", "four_legs", "dog_like"},
    "wolf": {"wild", "fur", "four_legs", "dog_like"},
    "deer": {"wild", "four_legs", "antlers"},
    "snail": {"small", "crawl", "shell"}
}

MYSTERY_ANIMAL_GUESS_PROFILES.update({
    "elephant": {"wild", "big", "four_legs", "trunk"},
    "giraffe": {"wild", "big", "four_legs", "long_neck", "spots"},
    "zebra": {"wild", "four_legs", "stripes", "black_white"},
    "tiger": {"wild", "fur", "four_legs", "cat_like", "big", "stripes"},
    "leopard": {"wild", "fur", "four_legs", "cat_like", "spots"},
    "cheetah": {"wild", "fur", "four_legs", "cat_like", "spots"},
    "lion": {"wild", "fur", "four_legs", "cat_like", "big", "mane"},
    "goat": {"farm", "four_legs", "horns"},
    "deer": {"wild", "four_legs", "antlers"},
    "duck": {"feathers", "beak", "wings", "water", "swim", "two_legs", "duck_like"},
    "bee": {"wings", "fly", "small", "air", "bee_like"},
    "butterfly": {"wings", "fly", "small", "air"},
    "shark": {"water", "swim", "big", "teeth"},
    "whale": {"water", "swim", "big", "smooth_skin"},
    "dolphin": {"water", "swim", "smooth_skin"},
    "octopus": {"water", "swim", "soft_arms"},
    "polar bear": {"wild", "fur", "four_legs", "big", "white", "cold_place", "swim", "eats_fish"},
    "panda": {"wild", "fur", "four_legs", "big", "black_white"},
    "grizzly bear": {"wild", "fur", "four_legs", "big", "brown"},
    "penguin": {"feathers", "beak", "wings", "water", "swim", "two_legs", "black_white", "antarctica", "cold_place", "eats_fish", "waddle", "white", "black", "brown"}
})

# Now that the profile dictionary exists, use it as the set of broad guesses Star can make.
MYSTERY_ANIMAL_BROAD_GUESS_ANIMALS = set(MYSTERY_ANIMAL_GUESS_PROFILES.keys()).union({
    "bird", "fish", "spider", "frog", "turtle", "crab", "dog", "cat",
    "whale", "dolphin", "shark", "snake", "lizard", "butterfly", "bee", "polar bear", "panda", "grizzly bear"
})


def get_rule_based_mystery_animal_guess(game_state):
    """
    Return a high-confidence educated guess from hard clue combinations.
    This runs before OpenAI and blocks dumb clue-fragment guesses like "beak".
    """
    tags = get_mystery_animal_required_guess_tags(game_state)
    answers_text = " ".join(
        normalize_child_text(item.get("answer", "")).lower()
        for item in (game_state.get("qa_history") or game_state.get("known_clues", []))
        if isinstance(item, dict)
    )

    if "web" in tags and "many_legs" in tags:
        return "spider"

    if "many_legs" in tags and "crawl" in tags and any(word in answers_text for word in ["eight", "8", "web", "spider"]):
        return "spider"

    if "many_legs" in tags and "water" in tags and "shell" in tags:
        return "crab"

    if "no_legs" in tags and ("crawl" in tags or "scales" in tags):
        return "snake"

    # Only use narrow rules for very distinctive combinations.
    # Do not assume "cold/white/Antarctica" means penguin; that can also be a bear-like clue.
    if (
        "polar bear" not in game_state.get("rejected_guesses", [])
        and "cold_place" in tags
        and "white" in tags
        and ("fur" in tags or "four_legs" in tags or "big" in tags or "bear" in answers_text)
    ):
        return "polar bear"

    if (
        "penguin" not in game_state.get("rejected_guesses", [])
        and (
            ("waddle" in tags and ("black_white" in tags or "cold_place" in tags or "antarctica" in tags))
            or ("black_white" in tags and "eats_fish" in tags and ("two_legs" in tags or "feathers" in tags or "beak" in tags or "no_fly" in tags))
        )
    ):
        return "penguin"

    if "water" in tags and "big" in tags and "swim" in tags:
        if any(word in answers_text for word in ["blowhole", "huge", "biggest", "whale"]):
            return "whale"
        return "dolphin"

    if "shell" in tags and "water" in tags and ("four_legs" in tags or "swim" in tags):
        return "turtle"

    # The exact failure you saw: flies + feathers/beak should become a bird,
    # never a beak. One strong bird answer is enough for an educated guess.
    if "feathers" in tags and ("fly" in tags or "air" in tags or "wings" in tags or "beak" in tags or "two_legs" in tags):
        return "bird"

    if "beak" in tags and ("fly" in tags or "feathers" in tags or "wings" in tags or "two_legs" in tags):
        return "bird"

    if "pet" in tags and "fur" in tags and "dog_like" in tags:
        return "dog"

    if "pet" in tags and "fur" in tags and "cat_like" in tags:
        return "cat"

    if "jump" in tags and "big" in tags and "land" in tags:
        return "kangaroo"

    if any(word in answers_text for word in ["antler", "antlers"]):
        if "big" in tags or "land" in tags:
            return "deer"

    if "trunk" in tags and ("big" in tags or "four_legs" in tags or "wild" in tags):
        return "elephant"

    if "long_neck" in tags and ("big" in tags or "four_legs" in tags or "wild" in tags):
        return "giraffe"

    if "black_white" in tags and "stripes" in tags and ("wild" in tags or "four_legs" in tags):
        return "zebra"

    if "mane" in tags and "cat_like" in tags:
        return "lion"

    if "duck_like" in tags and ("water" in tags or "beak" in tags or "feathers" in tags):
        return "duck"

    if "bee_like" in tags and "fly" in tags:
        return "bee"

    return get_profile_based_mystery_animal_guess(game_state)


def get_profile_based_mystery_animal_guess(game_state):
    """
    Score common animal profiles from normalized clue tags.
    This gives Star reasonable educated guesses across animal groups without
    pretending it can know every species from vague clues.
    """
    tags = get_mystery_animal_required_guess_tags(game_state)

    if not tags:
        return None

    rejected = {
        clean_open_ended_animal_name(item)
        for item in game_state.get("rejected_guesses", [])
        if clean_open_ended_animal_name(item)
    }

    scored = []
    for animal, profile_tags in MYSTERY_ANIMAL_GUESS_PROFILES.items():
        if animal in rejected:
            continue

        overlap = tags & set(profile_tags)
        score = len(overlap)

        # Stronger weight for highly identifying tags.
        for tag in overlap:
            if tag in {
                "feathers", "beak", "web", "shell", "many_legs", "no_legs",
                "dog_like", "cat_like", "trunk", "long_neck", "stripes", "spots",
                "antlers", "horns", "black_white", "mane", "duck_like", "bee_like",
                "antarctica", "cold_place", "eats_fish", "waddle", "white", "black", "brown"
            }:
                score += 1

        if score <= 0:
            continue

        if mystery_animal_guess_contradicts_clues(animal, game_state):
            continue

        scored.append((score, len(overlap), animal))

    if not scored:
        return None

    scored.sort(reverse=True)
    best_score, best_overlap, best_animal = scored[0]
    next_score = scored[1][0] if len(scored) > 1 else 0

    # Guess only when the profile is meaningfully supported.
    if best_score >= 4:
        return best_animal

    if best_score >= 3 and best_score - next_score >= 1:
        return best_animal

    return None

def is_mystery_animal_guess_ready(game_state):
    """
    Decide whether Star should make an educated guess now.

    Important fix: one answer can contain multiple strong clues. If the child
    says "it flies and has feathers," Star should guess bird immediately instead
    of demanding another question just because qa_count is 1.
    """
    tags = get_mystery_animal_required_guess_tags(game_state)
    families = get_mystery_animal_answer_families(game_state)
    qa_count = len(game_state.get("qa_history") or game_state.get("known_clues", []))

    rule_guess = get_rule_based_mystery_animal_guess(game_state)
    if qa_count >= 1 and rule_guess:
        return True

    if qa_count < 2:
        return False

    strong_combos = [
        {"many_legs", "crawl"},
        {"many_legs", "web"},
        {"many_legs", "water"},
        {"no_legs", "crawl"},
        {"water", "big", "swim"},
        {"water", "shell"},
        {"air", "fly"},
        {"feathers", "fly"},
        {"beak", "fly"},
        {"feathers", "wings"},
        {"pet", "fur", "dog_like"},
        {"pet", "fur", "cat_like"},
        {"jump", "big", "land"},
    ]

    if any(combo.issubset(tags) for combo in strong_combos):
        return True

    non_generic_families = families - {"size", "habitat", "general"}
    if len(families) >= 3 and len(non_generic_families) >= 1:
        return True

    if qa_count >= 4 and len(families) >= 3:
        return True

    return False


def has_confident_mystery_animal_guess(game_state):
    """
    Compatibility wrapper used by the message route.
    """
    return is_mystery_animal_guess_ready(game_state)

def extract_mystery_animal_guess_from_message(message):
    text = normalize_child_text(message).lower()

    patterns = [
        r"\bis it (?:a |an |the )?([a-z -]+?)\?",
        r"\bcould it be (?:a |an |the )?([a-z -]+?)\?",
        r"\bmaybe it is (?:a |an |the )?([a-z -]+?)(?:\.|\?|$)",
        r"\bi think it is (?:a |an |the )?([a-z -]+?)(?:\.|\?|$)"
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return clean_open_ended_animal_name(match.group(1))

    return None


def get_open_ended_mystery_animal_guess(game_state, child_name=""):
    """
    Ask OpenAI for a real animal guess only when the clues are strong enough.
    This is open-ended, but every guess must pass strict validation before Star speaks it.
    """
    clue_dictionary = get_mystery_animal_clue_dictionary(game_state)
    rejected = [
        clean_open_ended_animal_name(item)
        for item in game_state.get("rejected_guesses", [])
        if clean_open_ended_animal_name(item)
    ]
    required_tags = sorted(list(get_mystery_animal_required_guess_tags(game_state)))
    families = sorted(list(get_mystery_animal_answer_families(game_state)))

    if not is_mystery_animal_guess_ready(game_state):
        return None

    rule_guess = get_rule_based_mystery_animal_guess(game_state)

    prompt = f"""
You are helping Star play Mystery Animal.

The child is thinking of one real animal. There is no fixed candidate list.
Use the entire structured clue dictionary like a smart human would.
Your job is to make ONE animal guess only if the clues are strong enough.

Hard rules:
- Return ONLY a JSON object. No markdown.
- The guess must be a real animal common name.
- The guess may be any real animal, including animals not listed in code.
- Never return a clue, body part, habitat, movement, size, adjective, or phrase fragment.
- Invalid examples: "on land", "bigger than a", "antlers", "shell", "water", "the sky", "walks", "small", "one color", "many colors".
- If the clues are broad only, such as just size and habitat, return null.
- Do not guess an animal that contradicts the clue dictionary.
- Do not repeat rejected guesses: {rejected}
- Treat food answers as food evidence, not identity. If the child says it eats fish, do not guess fish unless other clues say the animal itself is a fish.
- Use reasoning, not a hardcoded clue map. For example, cold place + white + fur/four legs should suggest polar bear; black and white + waddles + eats fish should suggest penguin.
- If two animals are still plausible, return null so Star can ask one more useful question.
- If the child gives a broad category clue like "type of bird," do NOT guess only "bird." Use that as a constraint and either guess a specific animal that fits the full clue history, or return null and ask one narrowing question.
- You may guess specific kid-familiar animals and species when the clues support them. Examples: penguin, polar bear, panda, parrot, owl, eagle, duck, flamingo, ostrich, peacock, dolphin, shark, whale, turtle, snake, butterfly, bee, elephant, giraffe, zebra, lion, tiger, kangaroo.
- Do not collapse a specific correct guess into a broad category in later rounds. If the clues support penguin, return "penguin," not "bird."

Structured clue dictionary:
{json.dumps(clue_dictionary, ensure_ascii=False, indent=2)}

Normalized hard clue tags:
{required_tags}

Answered clue families:
{families}

Return JSON only:
{{"guess": "animal name or null", "confidence": 0.0, "why": "short reason"}}
"""

    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=[{"role": "user", "content": prompt}]
        )

        raw = response.output_text.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        data = json.loads(raw)
        guess = clean_open_ended_animal_name(data.get("guess"))

        try:
            confidence = float(data.get("confidence", 0) or 0)
        except (TypeError, ValueError):
            confidence = 0

        if confidence >= 0.55 and guess and guess not in rejected:
            if (
                is_probably_valid_mystery_animal_guess(guess)
                and not mystery_animal_guess_contradicts_clues(guess, game_state)
                and not mystery_animal_guess_is_too_broad_for_declared_type(guess, game_state)
            ):
                return guess

    except Exception as e:
        print("Open-ended Mystery Animal guess error:", repr(e))

    # Fallback only: use local scoring if OpenAI is unavailable or not confident.
    # This keeps the game working without letting hardcoded rules dominate smart guesses.
    if (
        rule_guess
        and rule_guess not in rejected
        and is_probably_valid_mystery_animal_guess(rule_guess)
        and not mystery_animal_guess_contradicts_clues(rule_guess, game_state)
        and not mystery_animal_guess_is_too_broad_for_declared_type(rule_guess, game_state)
    ):
        return rule_guess

    return None

def parse_child_told_mystery_animal(text):
    """
    Used only after Star gives up and asks the child to tell the animal.
    At that point, a short answer like "bird" or "axolotl" should be accepted
    as the child's answer, but clue fragments still should not be accepted.
    """
    revealed = get_child_revealed_animal(text)
    if revealed:
        return broaden_specific_mystery_animal_guess(revealed) or revealed

    candidate = clean_open_ended_animal_name(text)
    if not candidate:
        return None

    candidate_l = candidate.lower().strip()
    broad = broaden_specific_mystery_animal_guess(candidate_l) or candidate_l

    if is_probably_valid_mystery_animal_guess(broad):
        return broad

    # Last-resort acceptance for a child-supplied answer after give-up.
    # This allows unusual animals without letting Star itself guess random phrases.
    if re.fullmatch(r"[a-z]+(?: [a-z]+){0,2}", candidate_l):
        forbidden_words = {
            "color", "colors", "colour", "colours", "one", "many", "same", "different",
            "land", "water", "air", "sky", "ground", "fur", "feathers", "beak", "wings",
            "tail", "legs", "leg", "shell", "scales", "big", "small", "bigger", "smaller"
        }
        candidate_words = set(re.findall(r"[a-z']+", candidate_l))
        if candidate_words and not candidate_words.intersection(forbidden_words):
            return candidate_l

    return None


def make_mystery_animal_reveal_finish_message(revealed_animal):
    animal = broaden_specific_mystery_animal_guess(revealed_animal) or clean_open_ended_animal_name(revealed_animal)
    animal = animal or "that animal"

    article = get_mystery_animal_article(animal)
    display = f"{article} {animal}" if animal != "that animal" else animal

    if animal in MYSTERY_ANIMAL_GUESS_PROFILES or animal in MYSTERY_ANIMAL_BROAD_GUESS_ANIMALS:
        return f"Oh, it was {display}. I should have been able to guess that. Your clues were very good."

    return f"Oh, it was {display}. That one was a little tricky for me to guess. That's a good animal."


def ask_child_to_reveal_mystery_animal(game_state, history, event_type, child_response):
    game_state["stage"] = "give_up_reveal"
    game_state["last_response_mode"] = "animal_reveal"
    game_state["game_complete"] = False
    game_state["give_up_asked"] = True
    game_state["gave_up_waiting_for_answer"] = True
    game_state["last_question"] = "I do not know what it is yet. Could you tell me what animal you were thinking of?"
    game_state["last_question_key"] = "give_up_reveal"
    game_state.setdefault("question_history", []).append({
        "question_key": "give_up_reveal",
        "question": game_state["last_question"],
        "stage": "give_up_reveal",
        "response_mode": "animal_reveal"
    })
    game_state["questions_asked"] = int(game_state.get("questions_asked", 0)) + 1

    return make_mystery_animal_audio_response(
        message="Hmm, I do not know what it is yet. Could you tell me what animal you were thinking of?",
        stage="give_up_reveal",
        response_mode="animal_reveal",
        expects_response=True,
        game_complete=False,
        game_state=game_state,
        history=history,
        event_type=event_type,
        child_response=child_response
    )


def unlock_mystery_animal_next_game_for_user():
    rounds_completed = get_saved_mystery_animal_rounds()
    return complete_mystery_animal_and_unlock_next_for_user(rounds_completed) is not None



def is_mystery_animal_question_complaint(text):
    lowered = normalize_child_text(text).lower()

    complaint_phrases = [
        "stupid question",
        "dumb question",
        "bad question",
        "that does not make sense",
        "that doesn't make sense",
        "doesn't make sense",
        "does not make sense",
        "what if it doesn't",
        "what if it does not",
        "not a good question",
        "terrible question"
    ]

    return any(phrase in lowered for phrase in complaint_phrases)


def apply_mystery_animal_comfort_update(game_state, event_type, child_response, previous_response_mode):
    if event_type in {"intro", "restart", "first_question"}:
        return

    if game_state.get("game_complete"):
        return

    child_response = normalize_child_text(child_response)
    previous_stage = game_state.get("stage", "")

    if previous_stage == "guess":
        if is_yes_response(child_response):
            rounds_completed = int(game_state.get("rounds_completed", 0)) + 1

            game_state["rounds_completed"] = rounds_completed
            game_state["stage"] = "round_choice"
            game_state["last_response_mode"] = "round_choice"
            game_state["game_complete"] = False
            return

        possible_guess = game_state.get("possible_guess")

        if is_no_response(child_response):
            if possible_guess:
                game_state.setdefault("rejected_guesses", []).append(possible_guess)

            game_state["possible_guess"] = None
            game_state["skip_guess_once"] = True
            game_state["guess_cooldown_questions"] = 1

        elif event_type == "no_response":
            # Do not treat silence or a missed answer as "no."
            # The child may have said yes softly, taken time, or been unclear.
            # Move back to clue questions before guessing again.
            game_state["possible_guess"] = None
            game_state["skip_guess_once"] = True
            game_state["guess_cooldown_questions"] = 1

    clear_response = (
        event_type == "child_answer" and
        is_clear_mystery_animal_response(child_response, previous_response_mode)
    )

    if clear_response:
        game_state["comfortable_answer_count"] = int(game_state.get("comfortable_answer_count", 0)) + 1
        game_state["comfortable_streak"] = int(game_state.get("comfortable_streak", 0)) + 1
        game_state["unclear_streak"] = 0

        word_count = len(re.findall(r"[A-Za-z']+", child_response))
        game_state.setdefault("clear_answer_word_counts", []).append(word_count)
        game_state["clear_answer_word_counts"] = game_state["clear_answer_word_counts"][-8:]

        last_question = game_state.get("last_question")
        last_question_key = game_state.get("last_question_key")

        if last_question and previous_stage != "guess":
            qa_item = {
                "question_key": last_question_key,
                "question": last_question,
                "answer": child_response[:140]
            }

            game_state.setdefault("known_clues", []).append(qa_item)
            game_state["known_clues"] = game_state["known_clues"][-16:]

            game_state.setdefault("qa_history", []).append(qa_item)
            game_state["qa_history"] = game_state["qa_history"][-16:]

        current_index = int(game_state.get("response_level_index", MYSTERY_ANIMAL_START_LEVEL_INDEX))
        comfortable_count = int(game_state.get("comfortable_answer_count", 0))
        comfortable_streak = int(game_state.get("comfortable_streak", 0))

        # Move up gently but noticeably when the child is giving usable clues.
        # This lets Star ask for more open hints once the child seems comfortable.
        if comfortable_streak >= 2 and current_index < len(MYSTERY_ANIMAL_LEVELS) - 1:
            current_index += 1
            game_state["comfortable_streak"] = 0

        if word_count >= 2 and comfortable_count >= 2 and current_index < 3:
            current_index = 3

        if word_count >= 3 and comfortable_count >= 3 and current_index < 4:
            current_index = 4

        game_state["response_level_index"] = min(current_index, len(MYSTERY_ANIMAL_LEVELS) - 1)

    else:
        game_state["unclear_or_silent_count"] = int(game_state.get("unclear_or_silent_count", 0)) + 1
        game_state["unclear_streak"] = int(game_state.get("unclear_streak", 0)) + 1
        game_state["comfortable_streak"] = 0

        last_question_key = game_state.get("last_question_key")
        if last_question_key and previous_stage not in {"guess", "round_choice", "give_up_reveal"}:
            game_state.setdefault("unclear_question_keys", []).append(last_question_key)
            game_state["unclear_question_keys"] = game_state["unclear_question_keys"][-12:]

        if game_state["unclear_streak"] >= 2:
            current_index = int(game_state.get("response_level_index", MYSTERY_ANIMAL_START_LEVEL_INDEX))
            game_state["response_level_index"] = max(current_index - 1, 0)
            game_state["unclear_streak"] = 0



def clean_mystery_child_name(value):
    name = re.sub(r"[^A-Za-z' -]", "", str(value or "")).strip()
    name = re.sub(r"\s+", " ", name)
    return name[:40]


def get_mystery_animal_cached_audio_url(text, namespace="mystery-animal-main-v1"):
    text = sanitize_short_line(text, fallback="Hmm, let me think.", max_len=320)

    cache_dir = os.path.join(BASE_DIR, "static", "audio", "mystery_animal")
    os.makedirs(cache_dir, exist_ok=True)

    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "piI8Kku0DcvcL6TTSeQt")
    cache_key = f"{namespace}:{voice_id}:{text}"
    filename = hashlib.md5(cache_key.encode("utf-8")).hexdigest() + ".mp3"
    filepath = os.path.join(cache_dir, filename)

    if not os.path.exists(filepath):
        audio_bytes = generate_star_voice_elevenlabs(text)
        with open(filepath, "wb") as f:
            f.write(audio_bytes)

    return url_for("static", filename=f"audio/mystery_animal/{filename}")


def choose_mystery_name_callout(child_name, original_text):
    text = str(original_text or "")
    lowered = text.lower()

    if "?" in text:
        options = [
            "Thank you, {child}. That helps.",
            "That is helpful, {child}.",
            "Thanks, {child}. I can use that clue.",
            "That clue helps, {child}."
        ]
    elif "got it" in lowered or "i got" in lowered or "it was" in lowered:
        options = [
            "Thank you for playing, {child}.",
            "Nice thinking, {child}.",
            "You helped me figure it out, {child}.",
            "That was helpful, {child}."
        ]
    elif "thank" in lowered or "helps" in lowered or "clue" in lowered:
        options = [
            "Thank you, {child}.",
            "That helps, {child}.",
            "That is helpful, {child}.",
            "Thanks, {child}. I can use that."
        ]
    else:
        options = [
            "Thank you, {child}.",
            "That helps, {child}.",
            "That is helpful, {child}.",
            "Thanks, {child}."
        ]

    cache_basis = f"{child_name}:{original_text}:mystery-gentle-v2"
    index = int(hashlib.md5(cache_basis.encode("utf-8")).hexdigest(), 16) % len(options)
    return options[index].format(child=child_name)


def remove_child_name_from_mystery_line(text, child_name):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    child_name = clean_mystery_child_name(child_name)

    if not text or not child_name:
        return text

    escaped_name = re.escape(child_name)
    name_pattern = rf"(?<![A-Za-z]){escaped_name}(?![A-Za-z])"

    cleaned = text
    cleaned = re.sub(rf"^\s*{name_pattern}\s*[,!.?]\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(rf"\s*,\s*{name_pattern}\s*([.!?])", r"\1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(rf"\s+{name_pattern}\s*([.!?])", r"\1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(rf"\s*,\s*{name_pattern}\s*,\s*", ", ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(rf"\s+{name_pattern}\s*", " ", cleaned, flags=re.IGNORECASE)

    cleaned = cleaned.replace(" ,", ",").replace(" .", ".").replace(" ?", "?").replace(" !", "!")
    cleaned = re.sub(r",\s*([.!?])", r"\1", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if cleaned and cleaned[-1] not in ".!?":
        cleaned += "."

    if cleaned:
        cleaned = cleaned[0].upper() + cleaned[1:]

    return cleaned


def split_mystery_line_for_child_name(text, child_name):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    child_name = clean_mystery_child_name(child_name)

    if not child_name or child_name.lower() in {"there", "child"}:
        return [text]

    escaped_name = re.escape(child_name)
    name_pattern = rf"(?<![A-Za-z]){escaped_name}(?![A-Za-z])"

    if not re.search(name_pattern, text, flags=re.IGNORECASE):
        return [text]

    generic_line = remove_child_name_from_mystery_line(text, child_name)

    if not generic_line or len(generic_line) < 4:
        return [text]

    return [choose_mystery_name_callout(child_name, text), generic_line]


def add_mystery_audio_to_payload(payload, message):
    child_name = clean_mystery_child_name(session.get("child_name", ""))
    audio_text_parts = split_mystery_line_for_child_name(message, child_name)
    audio_parts = [
        get_mystery_animal_cached_audio_url(part)
        for part in audio_text_parts
        if part and str(part).strip()
    ]

    payload["audio_parts"] = audio_parts
    payload["audio_part_texts"] = audio_text_parts

    if audio_parts:
        payload["audio_url"] = audio_parts[0]

    return payload


def make_mystery_animal_audio_response(
    message,
    stage,
    response_mode,
    expects_response,
    game_complete,
    game_state,
    history,
    event_type="server_response",
    child_response="",
    next_event=None,
    pause_before_next_ms=None,
    next_url=None,
    redirect_after_ms=None,
    session_done=False
):
    message = calm_mystery_animal_line(message, game_complete=game_complete)

    history.append({
        "event_type": event_type,
        "child_response": child_response,
        "star": message,
        "stage": stage,
        "response_mode": response_mode,
        "game_complete": game_complete,
        "session_done": session_done
    })

    game_state["stage"] = stage
    game_state["last_response_mode"] = response_mode
    game_state["game_complete"] = game_complete

    session["mystery_animal_history"] = history[-20:]
    session["mystery_animal_state"] = game_state
    session.modified = True

    payload = {
        "success": True,
        "message": message,
        "stage": stage,
        "expects_response": expects_response,
        "response_mode": response_mode,
        "game_complete": game_complete,
        "session_done": session_done,
        "game_state": game_state
    }

    payload = add_mystery_audio_to_payload(payload, message)

    if next_event:
        payload["next_event"] = next_event

    if pause_before_next_ms is not None:
        payload["pause_before_next_ms"] = pause_before_next_ms

    if next_url:
        payload["next_url"] = next_url

    if redirect_after_ms is not None:
        payload["redirect_after_ms"] = redirect_after_ms

    return jsonify(payload)


@app.route("/api/mystery-animal/message", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("30 per minute")
def mystery_animal_message():
    data = request.get_json(silent=True) or {}

    event_type = normalize_child_text(data.get("event_type", "intro"))
    child_response = normalize_child_text(data.get("child_response", ""))
    previous_response_mode = normalize_child_text(data.get("response_mode", "none"))

    allowed_events = {
        "intro",
        "restart",
        "first_question",
        "child_answer",
        "no_response"
    }

    if event_type not in allowed_events:
        return jsonify({"success": False, "error": "Invalid event_type"}), 400

    child_name = session.get("child_name", "there")
    child_name = re.sub(r"[^A-Za-z' -]", "", str(child_name)).strip() or "there"

    def start_new_mystery_round(rounds_completed, message, event_label="replay", pause_ms=1800):
        new_game_state = get_mystery_animal_default_state(rounds_completed=rounds_completed)

        return make_mystery_animal_audio_response(
            message=message,
            stage="intro",
            response_mode="none",
            expects_response=False,
            game_complete=False,
            game_state=new_game_state,
            history=[],
            event_type=event_label,
            child_response=child_response,
            next_event="first_question",
            pause_before_next_ms=pause_ms
        )

    def end_mystery_call(message, game_state, history, event_label="stop", unlock_next=False):
        next_url = url_for("dashboard")
        rounds_completed = int(game_state.get("rounds_completed", 0))

        if unlock_next:
            complete_mystery_animal_and_unlock_next_for_user(rounds_completed)
        else:
            save_mystery_animal_round_progress(rounds_completed)

        return make_mystery_animal_audio_response(
            message=message,
            stage="session_done",
            response_mode="none",
            expects_response=False,
            game_complete=unlock_next,
            game_state=game_state,
            history=history,
            event_type=event_label,
            child_response=child_response,
            next_url=next_url,
            redirect_after_ms=1700,
            session_done=True
        )

    def finish_mystery_round(base_message, game_state, history, event_label):
        rounds_completed = int(game_state.get("rounds_completed", 0))
        save_mystery_animal_round_progress(rounds_completed)

        if not should_mystery_animal_ask_round_choice(rounds_completed):
            message = (
                f"{base_message} "
                "Let's play another round. Think of a new animal in your head."
            )

            return start_new_mystery_round(
                rounds_completed=rounds_completed,
                message=message,
                event_label=event_label,
                pause_ms=1900
            )

        if rounds_completed >= MYSTERY_ANIMAL_REQUIRED_ROUNDS:
            message = (
                f"{base_message} "
                "That finishes our nine Mystery Animal rounds for today. "
                f"{child_name}, do you want to play again, or do you want to end here?"
            )
        else:
            message = (
                f"{base_message} "
                f"{child_name}, do you want to play another round, or do you want to end early for today?"
            )

        return make_mystery_animal_audio_response(
            message=message,
            stage="round_choice",
            response_mode="round_choice",
            expects_response=True,
            game_complete=False,
            game_state=game_state,
            history=history,
            event_type=event_label,
            child_response=child_response
        )

    if event_type in {"intro", "restart"}:
        session.pop("mystery_animal_history", None)
        session.pop("mystery_animal_state", None)
        session.pop("mystery_animal_session_question_keys", None)

        saved_rounds = get_saved_mystery_animal_rounds()
        history = []
        game_state = get_mystery_animal_default_state(rounds_completed=saved_rounds)
        child_response = ""
        previous_response_mode = "none"

        if saved_rounds >= MYSTERY_ANIMAL_REQUIRED_ROUNDS:
            message = (
                "Hi, I'm Star. Welcome back to Mystery Animal. "
                "We finished our main rounds, but we can still play again if you want. "
                "Think of a new animal in your head."
            )
        elif saved_rounds > 0:
            message = (
                "Hi, I'm Star. Welcome back to Mystery Animal. "
                "We'll keep going from where you left off. "
                "Think of a new animal in your head."
            )
        else:
            message = (
                "Hi, I'm Star. We're going to play Mystery Animal. "
                "Think of any animal in your head. Take a second. "
                "I'll ask little questions to guess it."
            )

        try:
            return make_mystery_animal_audio_response(
                message=message,
                stage="intro",
                response_mode="none",
                expects_response=False,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type=event_type,
                child_response="",
                next_event="first_question",
                pause_before_next_ms=2200
            )

        except Exception as e:
            print("Mystery Animal intro TTS error:", e)
            return jsonify({
                "success": False,
                "error": "Could not generate Star intro"
            }), 500

    history = session.get("mystery_animal_history", [])
    game_state = session.get("mystery_animal_state", get_mystery_animal_default_state())

    # Handle the child response to the every-two-round choice before normal game logic.
    if previous_response_mode == "round_choice" and event_type in {"child_answer", "no_response"}:
        rounds_completed = int(game_state.get("rounds_completed", 0))
        ready_to_unlock_next = rounds_completed >= MYSTERY_ANIMAL_REQUIRED_ROUNDS

        if event_type == "no_response":
            choice = "stop" if ready_to_unlock_next else "same_game"
        else:
            choice = classify_mystery_animal_choice_response(
                child_response,
                offer_next_game=ready_to_unlock_next
            )

        if choice == "same_game":
            message = "Okay. Let's play another round. Think of a new animal in your head."

            try:
                return start_new_mystery_round(
                    rounds_completed=rounds_completed,
                    message=message,
                    event_label="replay",
                    pause_ms=1800
                )

            except Exception as e:
                print("Mystery Animal replay TTS error:", e)
                return jsonify({
                    "success": False,
                    "error": "Could not generate Star replay intro"
                }), 500

        if choice in {"stop", "next_game"}:
            if ready_to_unlock_next:
                message = (
                    "Okay. Great work today. We can end here. "
                    "Bye-bye. See you later."
                )

                try:
                    return end_mystery_call(
                        message=message,
                        game_state=game_state,
                        history=history,
                        event_label="complete_and_stop",
                        unlock_next=True
                    )

                except Exception as e:
                    print("Mystery Animal complete-and-stop TTS error:", e)
                    return jsonify({
                        "success": False,
                        "error": "Could not finish Mystery Animal"
                    }), 500

            message = (
                "Okay. We can end here for now. "
                "Your spot is saved. Bye-bye. See you later."
            )

            try:
                return end_mystery_call(
                    message=message,
                    game_state=game_state,
                    history=history,
                    event_label="early_stop",
                    unlock_next=False
                )

            except Exception as e:
                print("Mystery Animal early-stop TTS error:", e)
                return jsonify({
                    "success": False,
                    "error": "Could not end the game"
                }), 500

        if ready_to_unlock_next:
            message = (
                "That's okay. You can say play again, or you can say end here."
            )
        else:
            message = (
                "That's okay. We can play another round together."
            )

            try:
                return start_new_mystery_round(
                    rounds_completed=rounds_completed,
                    message=message,
                    event_label="choice_unclear_continue",
                    pause_ms=1500
                )

            except Exception as e:
                print("Mystery Animal unclear-choice replay error:", e)
                return jsonify({
                    "success": False,
                    "error": "Could not continue the game"
                }), 500

        try:
            return make_mystery_animal_audio_response(
                message=message,
                stage="round_choice",
                response_mode="round_choice",
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type="choice_clarification",
                child_response=child_response
            )

        except Exception as e:
            print("Mystery Animal choice clarification TTS error:", e)
            return jsonify({
                "success": False,
                "error": "Could not generate Star choice response"
            }), 500

    if (
        event_type == "child_answer"
        and (game_state.get("stage") == "give_up_reveal" or previous_response_mode == "animal_reveal")
    ):
        told_animal = parse_child_told_mystery_animal(child_response)

        if told_animal:
            game_state["gave_up_waiting_for_answer"] = False
            game_state["give_up_asked"] = False
            game_state["possible_guess"] = told_animal
            game_state["rounds_completed"] = int(game_state.get("rounds_completed", 0)) + 1
            base_message = make_mystery_animal_reveal_finish_message(told_animal)

            try:
                return finish_mystery_round(
                    base_message=base_message,
                    game_state=game_state,
                    history=history,
                    event_label="child_revealed_after_give_up"
                )

            except Exception as e:
                print("Mystery Animal give-up finish TTS error:", e)
                return jsonify({
                    "success": False,
                    "error": "Could not finish Mystery Animal round"
                }), 500

        try:
            return make_mystery_animal_audio_response(
                message="That's okay. What animal were you thinking of? You can say just the animal.",
                stage="give_up_reveal",
                response_mode="animal_reveal",
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type="give_up_reveal_clarification",
                child_response=child_response
            )

        except Exception as e:
            print("Mystery Animal give-up clarification TTS error:", e)
            return jsonify({
                "success": False,
                "error": "Could not generate Star reveal response"
            }), 500

    revealed_animal = get_child_revealed_animal(child_response)

    if event_type == "child_answer" and revealed_animal:
        # Even if the child names an animal directly, Star should confirm the guess
        # before marking the round complete. This prevents accidental false completions.
        game_state["stage"] = "guess"
        game_state["last_response_mode"] = "guess_confirmation"
        game_state["game_complete"] = False

        normalized_revealed, question_text, guess_message = make_mystery_animal_guess_line(revealed_animal)

        if not normalized_revealed:
            revealed_animal = None
        else:
            revealed_animal = normalized_revealed

        message = guess_message or "I think I know now. What animal were you thinking of?"
        question_text = question_text or "What animal were you thinking of?"
        game_state["possible_guess"] = revealed_animal

        game_state["last_question"] = question_text
        game_state["last_question_key"] = "direct_reveal_confirmation"
        game_state.setdefault("question_history", []).append({
            "question_key": "direct_reveal_confirmation",
            "question": question_text,
            "stage": "guess",
            "response_mode": "guess_confirmation"
        })
        game_state["questions_asked"] = int(game_state.get("questions_asked", 0)) + 1

        history.append({
            "event_type": "direct_reveal_confirmation",
            "child_response": child_response,
            "star": message,
            "stage": "guess",
            "response_mode": "guess_confirmation",
            "game_complete": False
        })

        session["mystery_animal_history"] = history[-20:]
        session["mystery_animal_state"] = game_state
        session.modified = True

        try:
            payload = {
                "success": True,
                "message": message,
                "stage": "guess",
                "expects_response": True,
                "response_mode": "guess_confirmation",
                "game_complete": False,
                "session_done": False,
                "game_state": game_state
            }
            payload = add_mystery_audio_to_payload(payload, message)
            return jsonify(payload)

        except Exception as e:
            print("Mystery Animal direct reveal confirmation TTS error:", e)
            return jsonify({
                "success": False,
                "error": "Could not generate Star response"
            }), 500

    apply_mystery_animal_comfort_update(
        game_state,
        event_type,
        child_response,
        previous_response_mode
    )

    # Correct guess flow: no modal/card. Star verbally asks what the child wants next.
    if game_state.get("stage") == "round_choice":
        confirmed_guess = normalize_child_text(game_state.get("possible_guess", ""))
        if confirmed_guess:
            base_message = f"Okay, it was a {confirmed_guess}. I got it."
        else:
            base_message = "Okay, I got it."

        try:
            return finish_mystery_round(
                base_message=base_message,
                game_state=game_state,
                history=history,
                event_label="round_choice"
            )

        except Exception as e:
            print("Mystery Animal round-choice TTS error:", e)
            return jsonify({
                "success": False,
                "error": "Could not generate Star round-choice response"
            }), 500

    level = get_mystery_animal_level(game_state)
    fallback = get_fallback_mystery_animal_question(level, game_state, event_type)

    child_answer_was_complaint = (
        event_type == "child_answer"
        and is_mystery_animal_question_complaint(child_response)
    )

    if child_answer_was_complaint:
        next_question = fallback.get("question_text") or "What is one clue I should use instead?"
        next_question = str(next_question or "").strip()
        if next_question:
            next_question = next_question[0].upper() + next_question[1:]
            fallback["message"] = f"You're right. Let me ask a better question. {next_question}"
        else:
            fallback["message"] = "You're right. Let me ask a better question."

    child_answer_was_unclear = (
        event_type == "no_response"
        or (
            event_type == "child_answer"
            and previous_response_mode not in {"guess_confirmation", "round_choice"}
            and not is_clear_mystery_animal_response(child_response, previous_response_mode)
        )
    )

    if child_answer_was_unclear and not child_answer_was_complaint:
        next_question = fallback.get("question_text") or "What is one clue I should know?"
        next_question = str(next_question or "").strip()
        if next_question:
            next_question = next_question[0].upper() + next_question[1:]
            fallback["message"] = f"That's okay. We can try a different question. {next_question}"
        else:
            fallback["message"] = "That's okay. We can try a different question."

    if previous_response_mode == "guess_confirmation" and is_no_response(child_response):
        next_question = fallback.get("question_text") or fallback.get("message", "What is one more clue?")
        fallback["message"] = f"Okay, that was not it. Let me use another clue. {next_question[0].upper() + next_question[1:]}"

    known_clues = game_state.get("known_clues", [])
    questions_asked = int(game_state.get("questions_asked", 0))

    guess_cooldown_questions = int(game_state.get("guess_cooldown_questions", 0))
    comfortable_count = int(game_state.get("comfortable_answer_count", 0))
    current_round_number = int(game_state.get("rounds_completed", 0)) + 1

    last_answer_word_count = len(re.findall(r"[A-Za-z']+", child_response))
    total_clue_words = sum(
        len(re.findall(r"[A-Za-z']+", str(item.get("answer", ""))))
        for item in known_clues
        if isinstance(item, dict)
    )
    open_hint_questions_asked = int(game_state.get("open_hint_questions_asked", 0))
    clue_tags_for_guess = get_mystery_animal_clue_tags(game_state)
    strong_clue_count = len(clue_tags_for_guess)

    # Guess more often once Star has useful clues, but only after a clear answer.
    confident_guess_available = has_confident_mystery_animal_guess(game_state)
    rule_guess_available = get_rule_based_mystery_animal_guess(game_state)

    rejected_guess_count = len(game_state.get("rejected_guesses", []))
    last_guess_question_count = int(game_state.get("last_guess_question_count", 0) or 0)

    if last_guess_question_count:
        questions_since_last_guess = max(0, questions_asked - last_guess_question_count)
    else:
        questions_since_last_guess = questions_asked

    clear_answer_for_guessing = (
        event_type == "child_answer"
        and previous_response_mode not in {"guess_confirmation", "round_choice"}
        and is_clear_mystery_animal_response(child_response, previous_response_mode)
    )

    guess_ready = is_mystery_animal_guess_ready(game_state)

    should_guess = (
        clear_answer_for_guessing
        and not bool(game_state.get("skip_guess_once", False))
        and guess_cooldown_questions <= 0
        and (len(known_clues) >= 2 or bool(rule_guess_available))
        and guess_ready
        and (
            confident_guess_available
            or questions_since_last_guess >= 2
            or rejected_guess_count >= 1
            or previous_response_mode == "open_hint"
        )
    )

    max_questions_reached = (
        questions_asked >= MYSTERY_ANIMAL_MAX_QUESTIONS_PER_ROUND
        and not bool(game_state.get("give_up_asked", False))
        and previous_response_mode not in {"guess_confirmation", "round_choice", "animal_reveal"}
        and game_state.get("stage") != "give_up_reveal"
    )

    if max_questions_reached and not should_guess:
        try:
            return ask_child_to_reveal_mystery_animal(game_state, history, event_type, child_response)
        except Exception as e:
            print("Mystery Animal give-up ask TTS error:", e)
            return jsonify({
                "success": False,
                "error": "Could not generate Star reveal question"
            }), 500

    should_invite_open_hint = (
        False and current_round_number >= 5 and
        comfortable_count >= 3 and
        int(game_state.get("response_level_index", MYSTERY_ANIMAL_START_LEVEL_INDEX)) >= 2 and
        not should_guess
    )

    system_prompt = f"""
You are Star, a warm animated star mascot playing a Mystery Animal guessing game.

The child is thinking of an animal. Star asks gentle questions to guess it.

Core goal:
Make the child feel safe while giving them a real reason to communicate.

Hard rules:
- Never mention selective mutism, anxiety, therapy, treatment, exposure, stages, progress, confidence, or bravery.
- Never pressure the child to speak.
- Never say "use your words."
- Never sound disappointed.
- Never overpraise.
- Never make the child feel evaluated.
- Keep attention on the animal game, not on the child.
- Ask only one question at a time.
- Do not repeat previous questions or repeat the same question family inside one round.
- Use the clues already given as hard constraints. If the child says more than four legs, never guess a four-legged animal.
- Do not jump into open-ended questions unless the required response level says to.
- Keep Star's line to 1-2 short sentences.
- In rounds 1 through 3, ask simple guided-choice questions with clear answer options.
- In rounds 1 through 3, avoid open-ended hints.
- In rounds 4 through 6, ask clear concrete detail questions. These may ask for one word or a short phrase.
- In rounds 7 through 9, use a mix of easy open-ended questions, short-answer questions, and occasional either/or questions. Start with concrete open-ended prompts like what it looks like, what it does, or where it is seen. Do not open with vague prompts like "Can you give me a hint?"

Acknowledging child responses:
- When the child gives a clear answer or hint, acknowledge the clue before asking the next question.
- Do not praise the act of speaking.
- Do not say "good job saying that" or "great talking."
- Focus on the clue, not the performance.
- Good examples:
  - "Thank you, that helps."
  - "Okay, that gives me a clue."
  - "That is a helpful hint."
  - "That helps me narrow it down."
  - "Thank you, that is useful to know."
- Bad examples:
  - "Great job talking."
  - "Good job using your words."
  - "I'm proud of you for answering."

Direct animal reveal:
- If the child directly names the animal, like "dog", "it's a dog", or "my animal is dog", accept that as the answer.
- Do not ask for another hint after the child directly names the animal.

Silence and no-response handling:
- If the child does not answer, do not say "let me ask it in a simpler way."
- Do not imply the previous question was too hard.
- Do not repeat the same question.
- Do not say "I couldn't hear you."
- Do not call attention to the child being silent.
- Gently move on with a different low-pressure question.
- Use calm acceptance first, then continue the game.

Calm voice style:
- Star should sound warm, gentle, steady, and quietly playful.
- Use mostly periods.
- Avoid sounding hyper, surprised, loud, or teacher-like.
- Avoid frequent exclamation marks.
- Do not say "Wow", "Amazing", "Awesome", or "Ooo".
- Treat answers as helpful clues, not performances.
- Do not overuse praise.

Current round number:
{current_round_number}

Required response level:
Stage: {level["stage"]}
Response mode: {level["response_mode"]}
Description: {level["description"]}
Examples: {level["examples"]}

Guessing rule:
- should_guess is currently {should_guess}.
- If should_guess is false, do not guess the animal yet.
- If should_guess is true, you must make one calm open-ended animal guess now, and the guess must fit every stored clue.
- There is no fixed animal candidate list. You may guess any real animal.
- Do not keep asking more clue questions when should_guess is true unless the clues are truly too vague.
- Do not ask what sound the animal makes.
- Avoid asking the child to make animal noises.
- Vary your wording and question type. Do not ask questions in the same order every round.
- When guessing, ask it as a confirmation question, like "Is it a frog?"
- Never say "I know what it is" unless the child has already confirmed yes to your exact guess.
- A category clue is not a final answer. If the child says "type of cat", do not guess "cat" just because the word cat appeared.
- If the child says a broad category such as "type of bird," store it as a clue. Do not ask whether it is a bird again. Do not guess only "bird"; either guess a specific animal that fits the full clue history or ask a narrowing question within that category.

Output JSON only:
{{
  "message": "Star's spoken line",
  "stage": "intro | guided_choice | guided_clue | tiny_hint | open_hint | guess | support | complete",
  "expects_response": true,
  "response_mode": "none | choice | one_word | short_phrase | open_hint | guess_confirmation",
  "is_question": true,
  "question_text": "the exact question Star asked, or null",
  "game_complete": false,
  "possible_guess": null
}}
"""

    user_prompt = f"""
Child name:
{child_name}

Current game state:
{game_state}

Recent history:
{history[-12:]}

Known clues:
{known_clues}

Question-answer history for the current animal:
{game_state.get("qa_history", [])}

Structured clue dictionary for the current animal:
{get_mystery_animal_clue_dictionary(game_state)}

Normalized hard clue tags:
{sorted(list(get_mystery_animal_required_guess_tags(game_state)))}

Question history:
{game_state.get("question_history", [])}

Question keys already asked this round:
{game_state.get("current_round_question_keys", [])}

Rejected guesses:
{game_state.get("rejected_guesses", [])}

New event:
event_type: {event_type}
child_response: {child_response}
previous_response_mode: {previous_response_mode}

If the child directly names the animal, like "dog", "it's a dog", or "my animal is dog":
- Accept that as the mystery animal.
- Do not ask for another hint.
- Do not keep guessing.
- Move to the end-of-round choice.

If event_type is child_answer and the child gave a clear answer:
- Acknowledge the clue first.
- Do not praise speaking itself.
- Use the full question-answer history before choosing the next question or guess.
- Do not ask for the same clue again unless the child was silent or unclear.
- Then ask one useful next question or make one guess if should_guess is true.
- If should_guess is true, the guess must fit every previous answer. If the child said more than four legs or eight legs, do not guess dog, cat, kangaroo, rabbit, horse, cow, lion, tiger, bear, frog, or lizard. You may guess any other real animal that fits the clues. If the child said "type of bird" or another broad category, do not guess that broad category; use the full clue history to guess a specific animal inside that category, or ask one narrowing question.

If event_type is no_response:
- Start with a calm accepting phrase like "That's okay" or "No problem."
- Do not repeat the last question.
- Do not say you are making the question easier.
- Ask a different low-pressure question at the current or easier response level.

Generate the next Star line now.

Remember:
- Ask at the required response level unless should_guess is true.
- Ask only one question.
- Keep it calm.
- Do not repeat a previous question.
- If this is the first_question event, ask the first question only. Do not reintroduce the game.
"""

    try:
        if should_guess:
            open_guess = get_open_ended_mystery_animal_guess(game_state, child_name)

            if open_guess:
                normalized_guess, guess_question, guess_message = make_mystery_animal_guess_line(open_guess)

                if normalized_guess:
                    parsed = {
                        "message": guess_message,
                        "stage": "guess",
                        "expects_response": True,
                        "response_mode": "guess_confirmation",
                        "is_question": True,
                        "question_text": guess_question,
                        "game_complete": False,
                        "possible_guess": normalized_guess
                    }
                else:
                    parsed = {
                        "message": f"Hmm, that helps. {fallback['question_text']}",
                        "stage": fallback["stage"],
                        "expects_response": True,
                        "response_mode": fallback["response_mode"],
                        "is_question": True,
                        "question_text": fallback["question_text"],
                        "game_complete": False,
                        "possible_guess": None
                    }
            else:
                if max_questions_reached:
                    try:
                        return ask_child_to_reveal_mystery_animal(game_state, history, event_type, child_response)
                    except Exception as e:
                        print("Mystery Animal give-up after failed guess TTS error:", e)
                        return jsonify({
                            "success": False,
                            "error": "Could not generate Star reveal question"
                        }), 500

                parsed = {
                    "message": f"Hmm, that helps. {fallback['question_text']}",
                    "stage": fallback["stage"],
                    "expects_response": True,
                    "response_mode": fallback["response_mode"],
                    "is_question": True,
                    "question_text": fallback["question_text"],
                    "game_complete": False,
                    "possible_guess": None
                }
        else:
            parsed = {
                "message": fallback["message"],
                "stage": fallback["stage"],
                "expects_response": True,
                "response_mode": fallback["response_mode"],
                "is_question": True,
                "question_text": fallback["question_text"],
                "game_complete": False,
                "possible_guess": None
            }

        stage = normalize_child_text(parsed.get("stage", fallback["stage"]))
        response_mode = normalize_child_text(parsed.get("response_mode", fallback["response_mode"]))
        question_text = parsed.get("question_text")
        possible_guess = parsed.get("possible_guess")

        if stage == "guess" and not should_guess:
            parsed = {
                "message": fallback["message"],
                "stage": fallback["stage"],
                "expects_response": True,
                "response_mode": fallback["response_mode"],
                "is_question": True,
                "question_text": fallback["question_text"],
                "game_complete": False,
                "possible_guess": None
            }

            stage = parsed["stage"]
            response_mode = parsed["response_mode"]
            question_text = parsed["question_text"]
            possible_guess = None

        if should_invite_open_hint and not should_guess and stage != "guess":
            lowered_question = normalize_child_text(question_text or parsed.get("message", "")).lower()
            asks_for_hint = any(phrase in lowered_question for phrase in [
                "hint", "clue", "what should i know", "what is one"
            ])

            if not asks_for_hint:
                question_text = choose_non_repeating_question(MYSTERY_ANIMAL_LEVELS[-1], game_state)
                parsed["message"] = question_text
                parsed["stage"] = "open_hint"
                parsed["response_mode"] = "open_hint"
                parsed["is_question"] = True
                parsed["question_text"] = question_text
                stage = "open_hint"
                response_mode = "open_hint"

        if stage != "guess":
            if stage == "open_hint" and should_invite_open_hint:
                response_mode = "open_hint"
            elif parsed.get("question_text") == fallback.get("question_text"):
                stage = fallback["stage"]
                response_mode = fallback["response_mode"]
            else:
                stage = level["stage"]
                response_mode = level["response_mode"]
        else:
            response_mode = "guess_confirmation"

        game_complete = False

        message = parsed.get("message", "").strip().replace('"', "")

        if not message:
            message = fallback["message"]

        message = sanitize_short_line(
            message,
            fallback=fallback["message"],
            max_len=300
        )

        message = calm_mystery_animal_line(message, game_complete=game_complete)

        message = maybe_add_mystery_animal_acknowledgment(
            message=message,
            event_type=event_type,
            child_response=child_response,
            previous_response_mode=previous_response_mode,
            game_state=game_state
        )

        message = calm_mystery_animal_line(message, game_complete=game_complete)

        if not question_text and parsed.get("is_question"):
            question_text = message

        if stage == "guess":
            response_mode = "guess_confirmation"

            if possible_guess:
                normalized_guess = normalize_child_text(possible_guess).lower()
                if mystery_animal_guess_contradicts_clues(normalized_guess, game_state):
                    replacement_guess = get_open_ended_mystery_animal_guess(game_state, child_name)

                    if replacement_guess:
                        normalized_guess, question_text, message = make_mystery_animal_guess_line(replacement_guess)
                    else:
                        stage = fallback["stage"]
                        response_mode = fallback["response_mode"]
                        possible_guess = None
                        question_text = fallback["question_text"]
                        message = f"Hmm, that clue helps. {question_text}"
                        parsed["stage"] = stage
                        parsed["response_mode"] = response_mode
                        parsed["question_text"] = question_text
                        parsed["possible_guess"] = None
                        game_state["possible_guess"] = None
                        normalized_guess = None

                if normalized_guess:
                    game_state["possible_guess"] = normalized_guess
            else:
                guess_match = re.search(r"is it (?:a |an )?([A-Za-z -]+)\??", message.lower())

                if guess_match:
                    normalized_guess = clean_open_ended_animal_name(guess_match.group(1))

                    if not is_probably_valid_mystery_animal_guess(normalized_guess):
                        normalized_guess = None

                    if normalized_guess and mystery_animal_guess_contradicts_clues(normalized_guess, game_state):
                        replacement_guess = get_open_ended_mystery_animal_guess(game_state, child_name)

                        if replacement_guess:
                            normalized_guess, question_text, message = make_mystery_animal_guess_line(replacement_guess)
                        else:
                            stage = fallback["stage"]
                            response_mode = fallback["response_mode"]
                            possible_guess = None
                            question_text = fallback["question_text"]
                            message = f"Hmm, that clue helps. {question_text}"
                            parsed["stage"] = stage
                            parsed["response_mode"] = response_mode
                            parsed["question_text"] = question_text
                            parsed["possible_guess"] = None
                            game_state["possible_guess"] = None
                            normalized_guess = None

                    if normalized_guess:
                        game_state["possible_guess"] = normalized_guess

        game_state["stage"] = stage
        game_state["last_response_mode"] = response_mode
        game_state["game_complete"] = False

        if stage != "guess":
            if game_state.get("skip_guess_once"):
                game_state["skip_guess_once"] = False

            if int(game_state.get("guess_cooldown_questions", 0)) > 0:
                game_state["guess_cooldown_questions"] = max(
                    0,
                    int(game_state.get("guess_cooldown_questions", 0)) - 1
                )

        if parsed.get("is_question") and question_text:
            if question_text == fallback.get("question_text"):
                question_key = game_state.get("pending_question_key") or get_question_family(question_text)
            else:
                question_key = get_question_family(question_text)

            game_state["last_question"] = normalize_child_text(question_text)
            game_state["last_question_key"] = question_key
            game_state["pending_question_key"] = None

            if stage != "guess":
                game_state.setdefault("current_round_question_keys", []).append(question_key)
                game_state["current_round_question_keys"] = game_state["current_round_question_keys"][-16:]
                question_family = get_question_family(question_text)
                game_state.setdefault("asked_question_families", []).append(question_family)
                game_state["asked_question_families"] = game_state["asked_question_families"][-16:]
                game_state.setdefault("asked_question_keys", []).append(question_key)
                game_state["asked_question_keys"] = game_state["asked_question_keys"][-30:]
                game_state.setdefault("session_question_keys", []).append(question_key)
                game_state["session_question_keys"] = game_state["session_question_keys"][-40:]
                session["mystery_animal_session_question_keys"] = game_state["session_question_keys"]

            game_state.setdefault("question_history", []).append({
                "question_key": question_key,
                "question": normalize_child_text(question_text),
                "stage": stage,
                "response_mode": response_mode
            })
            game_state["questions_asked"] = int(game_state.get("questions_asked", 0)) + 1

            if stage == "open_hint" or response_mode == "open_hint":
                game_state["open_hint_questions_asked"] = int(game_state.get("open_hint_questions_asked", 0)) + 1

            if stage == "guess":
                game_state["last_guess_question_count"] = int(game_state.get("questions_asked", 0))

        history.append({
            "event_type": event_type,
            "child_response": child_response,
            "star": message,
            "stage": game_state["stage"],
            "response_mode": response_mode,
            "game_complete": False
        })

        session["mystery_animal_history"] = history[-20:]
        session["mystery_animal_state"] = game_state
        session.modified = True

        payload = {
            "success": True,
            "message": message,
            "stage": game_state["stage"],
            "expects_response": bool(parsed.get("expects_response", True)),
            "response_mode": response_mode,
            "game_complete": False,
            "session_done": False,
            "game_state": game_state
        }
        payload = add_mystery_audio_to_payload(payload, message)
        return jsonify(payload)

    except Exception as e:
        print("Mystery Animal AI error:", e)
        return jsonify({
            "success": False,
            "error": "Could not generate Star response"
        }), 500

@app.route("/api/mystery-animal/transcribe", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("20 per minute")
def mystery_animal_transcribe():
    if "audio" not in request.files:
        return jsonify({
            "success": False,
            "error": "Missing audio"
        }), 400

    audio_file = request.files["audio"]

    try:
        import io

        audio_bytes = audio_file.read()

        if not audio_bytes:
            return jsonify({
                "success": False,
                "error": "Empty audio file"
            }), 400

        file_obj = io.BytesIO(audio_bytes)
        file_obj.name = "child-response.webm"

        transcript = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=file_obj
        )

        text = transcript.text.strip()

        print("TRANSCRIPT:", text)

        return jsonify({
            "success": True,
            "text": text
        })

    except Exception as e:
        print("Mystery Animal transcription error:", repr(e))
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    
GUESSING_GAME_MAX_ROUNDS = 3
GUESSING_GAME_PRESET_ANIMAL_ORDER = [
    "cat",
    "giraffe",
    "shark"
]
GUESSING_GAME_NEXT_GAME_OFFER_ROUND = 999
# Guessing Game is activity 3, but the next activity in the user journey is Drawing Game, activity 7.
GUESSING_GAME_NEXT_ACTIVITY_ID = 7

GUESSING_GAME_ANIMAL_PROFILES = {
    "dog": {
        "display": "dog",
        "tags": {"land", "pet", "fur", "tail", "four_legs", "house", "medium", "fast", "mammal"},
        "hints": [
            "This animal is a common pet.",
            "It often has fur and a tail.",
            "Many kids know this animal from homes or parks."
        ]
    },
    "cat": {
        "display": "cat",
        "tags": {"land", "pet", "fur", "tail", "four_legs", "house", "small", "quiet", "mammal"},
        "hints": [
            "This animal is a common pet.",
            "It has fur and often likes quiet places.",
            "It can climb and move very softly."
        ]
    },
    "fish": {
        "display": "fish",
        "tags": {"water", "swim", "fins", "scales", "small", "pet", "no_legs", "fish"},
        "hints": [
            "This animal lives in water.",
            "It swims and has fins.",
            "Some people keep this animal in a tank."
        ]
    },
    "bird": {
        "display": "bird",
        "tags": {"land", "fly", "wings", "feathers", "tail", "small", "sky", "bird"},
        "hints": [
            "This animal has wings.",
            "Many kinds of this animal can fly.",
            "It has feathers."
        ]
    },
    "rabbit": {
        "display": "rabbit",
        "tags": {"land", "pet", "fur", "tail", "four_legs", "small", "hop", "ears", "mammal"},
        "hints": [
            "This animal has long ears.",
            "It can hop.",
            "It has soft fur."
        ]
    },
    "frog": {
        "display": "frog",
        "tags": {"land", "water", "jump", "small", "pond", "green", "swim", "amphibian"},
        "hints": [
            "This animal can live near ponds.",
            "It can jump.",
            "It is often green or brown."
        ]
    },
    "horse": {
        "display": "horse",
        "tags": {"land", "farm", "four_legs", "tail", "fur", "big", "fast", "mammal"},
        "hints": [
            "This animal is big.",
            "It has four legs and a tail.",
            "People can ride this animal."
        ]
    },
    "cow": {
        "display": "cow",
        "tags": {"land", "farm", "four_legs", "tail", "fur", "big", "grass", "mammal"},
        "hints": [
            "This animal is often on a farm.",
            "It is big and has four legs.",
            "It eats grass."
        ]
    },
    "duck": {
        "display": "duck",
        "tags": {"land", "water", "swim", "fly", "wings", "feathers", "pond", "small", "bird"},
        "hints": [
            "This animal can swim on water.",
            "It has feathers and wings.",
            "You might see it at a pond."
        ]
    },
    "lion": {
        "display": "lion",
        "tags": {"land", "wild", "zoo", "fur", "tail", "four_legs", "big", "meat", "mammal"},
        "hints": [
            "This animal is wild.",
            "It is a big cat.",
            "You might see it at a zoo."
        ]
    },
    "tiger": {
        "display": "tiger",
        "tags": {"land", "wild", "zoo", "fur", "tail", "four_legs", "big", "stripes", "meat", "mammal", "orange"},
        "hints": [
            "This animal is wild.",
            "It has stripes.",
            "It is often orange and black."
        ]
    },
    "elephant": {
        "display": "elephant",
        "tags": {"land", "wild", "zoo", "four_legs", "tail", "very_big", "trunk", "gray", "mammal"},
        "hints": [
            "This animal is very big.",
            "It has a trunk.",
            "It is usually gray."
        ]
    },
    "giraffe": {
        "display": "giraffe",
        "tags": {"land", "wild", "zoo", "four_legs", "tail", "big", "tall", "neck", "spots", "mammal"},
        "hints": [
            "This animal is very tall.",
            "It has a long neck.",
            "It has spots."
        ]
    },
    "penguin": {
        "display": "penguin",
        "tags": {"land", "water", "swim", "wings", "feathers", "bird", "cold", "black_white"},
        "hints": [
            "This animal is a bird, but it does not fly like most birds.",
            "It swims very well.",
            "It is often black and white."
        ]
    },
    "dolphin": {
        "display": "dolphin",
        "tags": {"water", "swim", "ocean", "big", "gray", "smart", "no_legs", "mammal"},
        "hints": [
            "This animal lives in the ocean.",
            "It swims and can jump out of water.",
            "It is often gray."
        ]
    },
    "shark": {
        "display": "shark",
        "tags": {"water", "swim", "ocean", "fins", "big", "meat", "no_legs", "fish"},
        "hints": [
            "This animal lives in the ocean.",
            "It has fins.",
            "It is a strong swimmer."
        ]
    },
    "turtle": {
        "display": "turtle",
        "tags": {"land", "water", "swim", "shell", "small", "slow", "four_legs", "reptile"},
        "hints": [
            "This animal has a shell.",
            "It can move slowly.",
            "Some live near water."
        ]
    },
    "monkey": {
        "display": "monkey",
        "tags": {"land", "wild", "zoo", "fur", "tail", "tree", "small", "banana", "mammal"},
        "hints": [
            "This animal can climb trees.",
            "It has fur.",
            "You might see it at a zoo."
        ]
    },
    "zebra": {
        "display": "zebra",
        "tags": {"land", "wild", "zoo", "four_legs", "tail", "stripes", "big", "black_white", "mammal"},
        "hints": [
            "This animal has stripes.",
            "It is black and white.",
            "It has four legs."
        ]
    },
    "panda": {
        "display": "panda",
        "tags": {"land", "wild", "zoo", "fur", "four_legs", "black_white", "big", "bamboo", "mammal"},
        "hints": [
            "This animal is black and white.",
            "It has fur.",
            "It is often shown eating bamboo."
        ]
    }
}


GUESSING_GAME_ANIMAL_DETAILS = {
    "cat": {
        "color": "It can be black, white, orange, gray, brown, or a mix of colors.",
        "habitat": "It usually lives with people at home. Some also spend time outside.",
        "category": "It is usually a pet.",
        "appearance": "It is furry, has four legs, a tail, whiskers, and pointy ears. It can be small or medium-sized, and it can be black, white, orange, gray, brown, or a mix of colors.",
        "size": "It is usually small or medium-sized.",
        "food": "It usually eats pet food, and it can also eat meat.",
        "sound": "It can meow.",
        "movement": "It walks on four legs, can climb, and can move very quietly."
    },
    "giraffe": {
        "color": "It is usually tan or yellowish with brown spots.",
        "habitat": "It lives in the wild, usually in grassy areas with trees.",
        "category": "It is a wild animal, not a pet.",
        "appearance": "It is very tall, has a very long neck, four long legs, small horns, a tail, and brown spots on a tan or yellowish body.",
        "size": "It is very big and very tall.",
        "food": "It eats leaves from trees.",
        "sound": "It is usually quiet.",
        "movement": "It walks and runs on four long legs."
    },
    "shark": {
        "color": "It is often gray, white, or blue-gray.",
        "habitat": "It lives in the ocean.",
        "category": "It is a wild animal that lives in the ocean.",
        "appearance": "It has fins, a tail, sharp teeth, and a long body made for swimming. It is often gray or blue-gray on top and lighter underneath.",
        "size": "It is usually big, but some kinds are smaller than others.",
        "food": "It eats fish and other ocean animals.",
        "sound": "It is usually quiet.",
        "movement": "It swims through the ocean using its fins and tail."
    }
}


def get_guessing_game_detail(game_state, key, fallback=""):
    secret = normalize_guessing_text(game_state.get("secret_animal", ""))
    details = GUESSING_GAME_ANIMAL_DETAILS.get(secret, {})
    return details.get(key, fallback)


def get_guessing_game_default_state(rounds_completed=0, avoid_animals=None, used_animals=None):
    try:
        rounds_completed_int = max(0, int(rounds_completed or 0))
    except (TypeError, ValueError):
        rounds_completed_int = 0

    rounds_completed_int = min(rounds_completed_int, GUESSING_GAME_MAX_ROUNDS)
    preset_index = min(rounds_completed_int, len(GUESSING_GAME_PRESET_ANIMAL_ORDER) - 1)
    secret_animal = GUESSING_GAME_PRESET_ANIMAL_ORDER[preset_index]

    if secret_animal not in GUESSING_GAME_ANIMAL_PROFILES:
        secret_animal = "cat"

    used_so_far = [
        animal for animal in list(used_animals or [])
        if animal in GUESSING_GAME_ANIMAL_PROFILES
    ]

    if secret_animal not in used_so_far:
        used_so_far.append(secret_animal)

    used_animals_for_session = used_so_far[-GUESSING_GAME_MAX_ROUNDS:]

    return {
        "stage": "intro",
        "secret_animal": secret_animal,
        "used_animals": used_animals_for_session,
        "rounds_completed": rounds_completed_int,
        "questions_asked": 0,
        "comfortable_question_count": 0,
        "unclear_or_silent_count": 0,
        "unclear_streak": 0,
        "hint_count": 0,
        "wrong_guess_count": 0,
        "wrong_guesses": [],
        "asked_questions": [],
        "asked_topics": [],
        "recent_hints": [],
        "recent_round_prompts": [],
        "recent_support_lines": [],
        "recent_good_question_prefixes": [],
        "recent_suggestion_topics": [],
        "last_hint_offer_question_count": 0,
        "recent_follow_ups": [],
        "last_reveal_offer_turn": 0,
        "recent_reveal_offer_lines": [],
        "game_complete": False,
        "last_response_mode": "none"
    }


def get_guessing_game_profile(game_state):
    animal = normalize_child_text(game_state.get("secret_animal", "dog")).lower()

    if animal not in GUESSING_GAME_ANIMAL_PROFILES:
        animal = "dog"
        game_state["secret_animal"] = animal

    return GUESSING_GAME_ANIMAL_PROFILES[animal]


def normalize_guessing_text(text):
    text = normalize_child_text(text).lower()
    text = text.replace("’", "'")
    text = re.sub(r"[^a-z0-9' -]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def guessing_words(text):
    return set(re.findall(r"[a-z']+", normalize_guessing_text(text)))


def is_guessing_unclear_or_silent(text):
    lowered = normalize_guessing_text(text)

    if not lowered:
        return True

    unclear_phrases = {
        "i don't know",
        "i dont know",
        "i do not know",
        "don't know",
        "dont know",
        "idk",
        "not sure",
        "not really sure",
        "i'm not sure",
        "im not sure",
        "maybe",
        "hmm",
        "hm",
        "mm",
        "uh",
        "um",
        "mmm"
    }

    if lowered in unclear_phrases:
        return True

    words = re.findall(r"[a-z']+", lowered)

    if not words:
        return True

    filler_words = {"hmm", "hm", "mm", "mmm", "uh", "um", "like", "wait"}

    return all(word in filler_words for word in words)

def is_guessing_i_dont_know_response(text):
    lowered = normalize_guessing_text(text)

    dont_know_phrases = [
        "i don't know",
        "i dont know",
        "i do not know",
        "don't know",
        "dont know",
        "do not know",
        "idk",
        "not sure",
        "not really sure",
        "i'm not sure",
        "im not sure",
        "i have no idea",
        "no idea"
    ]

    return any(phrase in lowered for phrase in dont_know_phrases)

def is_guessing_example_question_request(text):
    lowered = normalize_guessing_text(text)

    example_question_phrases = [
        "example question",
        "example questions",
        "sample question",
        "sample questions",
        "question ideas",
        "ideas for questions",
        "what can i ask",
        "what should i ask",
        "what do i ask",
        "what question can i ask",
        "what questions can i ask",
        "what question should i ask",
        "what questions should i ask",
        "help thinking of questions",
        "help me think of questions",
        "help me with questions",
        "help me",
        "i need help",
        "i need help thinking of questions",
        "give me questions",
        "give me some questions",
        "questions that might help",
        "questions might help"
    ]

    if any(phrase in lowered for phrase in example_question_phrases):
        return True

    words = guessing_words(lowered)
    if words & {"examples", "questions"}:
        return True
    return bool({"help", "examples", "questions"} <= words)


def is_guessing_hint_request(text):
    lowered = normalize_guessing_text(text)

    hint_phrases = [
        "hint",
        "clue",
        "give me a hint",
        "give me a clue",
        "can i have a hint",
        "can i have a clue",
        "tell me something about it",
        "tell me something about the animal"
    ]

    return any(phrase in lowered for phrase in hint_phrases)


def get_guessing_named_animal(text):
    lowered = normalize_guessing_text(text)
    words = guessing_words(lowered)

    for animal in GUESSING_GAME_ANIMAL_PROFILES.keys():
        if animal in words:
            return animal

    animal_aliases = {
        "bunny": "rabbit",
        "kitty": "cat",
        "puppy": "dog",
        "monk": "monkey"
    }

    for alias, animal in animal_aliases.items():
        if alias in words:
            return animal

    return None



def is_guessing_direct_guess(text):
    lowered = normalize_guessing_text(text)
    named_animal = get_guessing_named_animal(lowered)

    if not named_animal:
        return False

    # Treat broad category questions like "Is it a bird?" as questions,
    # not as final guesses. This prevents a penguin/shark/etc. from being
    # marked wrong when the child is really asking about the animal type.
    category_words = {"bird", "fish"}
    if named_animal in category_words and lowered.startswith(("is it", "is your animal", "are you thinking of")):
        return False

    direct_guess_phrases = [
        "is it",
        "is your animal",
        "are you thinking of",
        "i guess",
        "my guess",
        "i think",
        "it's",
        "it is",
        "maybe",
        "the animal is"
    ]

    if any(phrase in lowered for phrase in direct_guess_phrases):
        return True

    words = re.findall(r"[a-z']+", lowered)

    return len(words) <= 4


def is_guessing_question(text):
    lowered = normalize_guessing_text(text)
    words = re.findall(r"[a-z']+", lowered)

    if not words:
        return False

    question_starters = {
        "is", "are", "do", "does", "can", "could", "would",
        "has", "have", "what", "where", "how", "did", "will"
    }

    if words[0] in question_starters or "?" in str(text):
        return True

    # Children often answer a guided prompt with a fragment like
    # "where it lives" or "what color it is." Treat those as the question
    # they chose, so Star answers instead of giving generic guidance.
    if words[0] in {"ask", "asking", "question"}:
        return get_guessing_question_topic(lowered) != "general"

    fragment_starts = {
        "color", "size", "big", "small", "where", "live", "lives", "home",
        "habitat", "sound", "noise", "eat", "eats", "food", "look", "looks",
        "fur", "wings", "legs", "tail", "swim", "fly", "move", "moves"
    }

    if words[0] in fragment_starts:
        return True

    return False

def guessing_question_key(text):
    lowered = normalize_guessing_text(text)
    lowered = re.sub(
        r"\b(the|a|an|your|animal|it|does|do|is|are|can|could|would|has|have|what|where|how)\b",
        " ",
        lowered
    )
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered[:80]


def get_guessing_question_topic(text):
    words = guessing_words(text)

    if words & {"big", "small", "little", "tiny", "large", "huge", "size"}:
        return "size"

    if words & {
        "color", "colour", "black", "white", "brown", "orange", "yellow",
        "green", "gray", "grey", "blue", "red", "gold", "golden", "tan", "pink"
    }:
        return "color"

    if words & {
        "where", "live", "lives", "habitat", "water", "ocean", "sea",
        "pond", "lake", "land", "ground", "farm", "zoo", "house", "home"
    }:
        return "habitat"

    if words & {
        "fur", "furry", "hair", "wings", "wing", "feathers", "feather",
        "tail", "legs", "fins", "fin", "scales", "scaly", "shell",
        "trunk", "stripes", "striped", "spots", "spotted", "neck",
        "look", "looks", "appearance"
    }:
        return "appearance"

    if words & {"eat", "eats", "food", "grass", "bamboo", "banana", "meat"}:
        return "food"

    if words & {"sound", "sounds", "noise", "noises", "loud", "quiet", "bark", "meow"}:
        return "sound"

    if words & {
        "fly", "flies", "flying", "swim", "swims", "swimming",
        "jump", "jumps", "hop", "hops", "fast", "slow", "climb", "climbs"
    }:
        return "movement"

    if words & {"pet", "wild", "mammal", "reptile", "amphibian"}:
        return "category"

    return "general"


def remember_guessing_question_topic(text, game_state):
    topic = get_guessing_question_topic(text)

    if topic:
        game_state.setdefault("asked_topics", []).append(topic)
        game_state["asked_topics"] = game_state["asked_topics"][-10:]

    return topic



def get_guessing_game_suggestion_line(game_state, max_ideas=3, include_guess=True):
    import random

    asked_topics = set(game_state.get("asked_topics", []))
    recent_topics = list(game_state.get("recent_suggestion_topics", []))[-6:]

    topic_options = [
        ("color", "What color is it?"),
        ("habitat", "Where does it live?"),
        ("size", "How big is it?"),
        ("appearance", "What does it look like?"),
        ("movement", "How does it move?"),
        ("food", "What does it eat?"),
        ("sound", "What sound does it make?"),
        ("category", "Is it a pet or a wild animal?")
    ]

    fresh = [
        (topic, phrase)
        for topic, phrase in topic_options
        if topic not in asked_topics and topic not in recent_topics
    ]

    if len(fresh) < max_ideas:
        fresh += [
            (topic, phrase)
            for topic, phrase in topic_options
            if topic not in asked_topics and (topic, phrase) not in fresh
        ]

    if not fresh:
        if include_guess:
            return "You can ask another question or make a guess when you're ready."
        return "You can ask another question about the animal."

    chosen = fresh[:]
    random.shuffle(chosen)
    chosen = chosen[:max_ideas]

    game_state["recent_suggestion_topics"] = (recent_topics + [topic for topic, _ in chosen])[-6:]

    phrases = [phrase for _, phrase in chosen]

    examples_text = " ".join(phrases)

    if include_guess:
        return f"Here are a few questions that might help: {examples_text}"

    return f"Here are a few questions that might help: {examples_text}"

def get_guessing_game_ai_question_answer(text, game_state):
    import random

    recent_support_lines = list(game_state.get("recent_support_lines", []))[-5:]

    if is_guessing_example_question_request(text):
        line = get_guessing_game_suggestion_line(game_state, max_ideas=3, include_guess=False)
    else:
        options = [
            "You can ask me questions to try to figure out the animal, ask for a hint, or guess whenever you're ready.",
            "You can ask another animal question, ask for a hint, or make a guess when you feel ready.",
            "That's okay. Ask me one question about the animal, ask for example questions, or guess when you're ready."
        ]

        fresh = [item for item in options if item not in recent_support_lines]
        line = random.choice(fresh or options)

    game_state["recent_support_lines"] = (recent_support_lines + [line])[-5:]

    return {
        "type": "support",
        "message": line,
        "question_answered": False
    }

def answer_guessing_question(text, game_state):
    profile = get_guessing_game_profile(game_state)
    tags = profile.get("tags", set())
    lowered = normalize_guessing_text(text)
    words = guessing_words(lowered)
    secret = game_state.get("secret_animal")

    named_animal = get_guessing_named_animal(lowered)

    if "mammal" in words:
        return {
            "type": "answer",
            "message": "Yes, it is a mammal." if "mammal" in tags else "No, it is not a mammal.",
            "question_answered": True
        }

    if "bird" in words:
        return {
            "type": "answer",
            "message": "Yes, it is a kind of bird." if "bird" in tags else "No, it is not a bird.",
            "question_answered": True
        }

    if "fish" in words:
        return {
            "type": "answer",
            "message": "Yes, it is a kind of fish." if "fish" in tags else "No, it is not a fish.",
            "question_answered": True
        }

    if "reptile" in words:
        return {
            "type": "answer",
            "message": "Yes, it is a reptile." if "reptile" in tags else "No, it is not a reptile.",
            "question_answered": True
        }

    if "amphibian" in words:
        return {
            "type": "answer",
            "message": "Yes, it is an amphibian." if "amphibian" in tags else "No, it is not an amphibian.",
            "question_answered": True
        }

    if named_animal:
        if named_animal == secret:
            return {
                "type": "correct_guess",
                "message": f"Yes, it is a {profile['display']}. You got it.",
                "question_answered": True
            }

        return {
            "type": "wrong_guess",
            "message": f"Not quite, it is not a {GUESSING_GAME_ANIMAL_PROFILES[named_animal]['display']}.",
            "wrong_guess": named_animal,
            "question_answered": True
        }

    color_answer = get_guessing_game_specific_color_answer(text, game_state)

    if color_answer:
        return color_answer

    if (
        ("how" in words and ("big" in words or "small" in words or "size" in words))
        or ("big" in words and "small" in words)
        or ("size" in words)
    ):
        detail = get_guessing_game_detail(game_state, "size")
        if detail:
            message = detail
        elif "very_big" in tags:
            message = "It is very big."
        elif "big" in tags:
            message = "It is big."
        elif "small" in tags:
            message = "It is small."
        else:
            message = "It is not very big or very small."

        return {
            "type": "answer",
            "message": message,
            "question_answered": True
        }

    if (
        ("where" in words and ("live" in words or "lives" in words or "home" in words))
        or ("habitat" in words)
        or (("live" in words or "lives" in words) and len(words) <= 5)
        or ("home" in words and ("what" in words or "where" in words or len(words) <= 5))
    ):
        detail = get_guessing_game_detail(game_state, "habitat")
        if detail:
            message = detail
        elif "ocean" in tags:
            message = "It lives in the ocean."
        elif "water" in tags and "land" in tags:
            message = "It can be around water and land."
        elif "water" in tags:
            message = "It lives in water."
        elif "farm" in tags:
            message = "You might see it on a farm."
        elif "zoo" in tags:
            message = "You might see it at a zoo."
        elif "house" in tags or "pet" in tags:
            message = "It can live around people."
        elif "land" in tags:
            message = "It lives on land."
        else:
            message = "It can live in different places."

        return {
            "type": "answer",
            "message": message,
            "question_answered": True
        }

    if ("what" in words and ("sound" in words or "noise" in words)) or ("sound" in words) or ("noise" in words):
        detail = get_guessing_game_detail(game_state, "sound")
        animal_sounds = {
            "cat": "It can meow.",
            "dog": "It can bark.",
            "shark": "It is usually quiet.",
            "rabbit": "It is usually quiet.",
            "penguin": "It can make bird sounds.",
            "elephant": "It can make a loud trumpet sound."
        }

        return {
            "type": "answer",
            "message": detail or animal_sounds.get(secret, "It can make animal sounds."),
            "question_answered": True
        }

    if ("how" in words and "many" in words and "legs" in words) or ("legs" in words and "many" in words):
        if "no_legs" in tags:
            message = "It does not have legs."
        elif "four_legs" in tags:
            message = "It has four legs."
        elif "bird" in tags:
            message = "It has two legs."
        else:
            message = "The number of legs depends on the animal."

        return {
            "type": "answer",
            "message": message,
            "question_answered": True
        }

    if ("what" in words and "look" in words) or ("looks" in words) or ("appearance" in words):
        detail = get_guessing_game_detail(game_state, "appearance")
        if detail:
            message = detail
        elif "stripes" in tags:
            message = "It has stripes."
        elif "spots" in tags:
            message = "It has spots."
        elif "trunk" in tags:
            message = "It has a long trunk."
        elif "neck" in tags:
            message = "It has a long neck."
        elif "shell" in tags:
            message = "It has a shell."
        elif "fur" in tags:
            message = "It has fur."
        elif "feathers" in tags:
            message = "It has feathers."
        elif "fins" in tags:
            message = "It has fins."
        else:
            message = "It can look different depending on the kind."

        return {
            "type": "answer",
            "message": message,
            "question_answered": True
        }

    if words & {"pet", "wild", "home", "house"}:
        detail = get_guessing_game_detail(game_state, "category")
        if detail:
            return {
                "type": "answer",
                "message": detail,
                "question_answered": True
            }

    if words & {"move", "moves", "walk", "walks", "run", "runs", "swim", "swims", "jump", "jumps", "hop", "hops", "fly", "flies"}:
        detail = get_guessing_game_detail(game_state, "movement")
        if detail:
            return {
                "type": "answer",
                "message": detail,
                "question_answered": True
            }

    checks = [
        ({"water", "ocean", "sea", "pond", "lake"}, {"water", "swim", "ocean", "pond"}, "Yes, it can live in or near water.", "No, it does not live in water."),
        ({"land", "ground"}, {"land"}, "Yes, it lives on land.", "No, it does not mainly live on land."),
        ({"fly", "flies", "flying"}, {"fly"}, "Yes, it can fly.", "No, it does not fly."),
        ({"wings", "wing"}, {"wings"}, "Yes, it has wings.", "No, it does not have wings."),
        ({"feathers", "feather"}, {"feathers"}, "Yes, it has feathers.", "No, it does not have feathers."),
        ({"fur", "furry", "hair"}, {"fur"}, "Yes, it has fur.", "No, it does not have fur."),
        ({"tail"}, {"tail"}, "Yes, it has a tail.", "No, it does not really have a tail."),
        ({"four", "legs"}, {"four_legs"}, "Yes, it has four legs.", "No, it does not have four legs."),
        ({"fins", "fin"}, {"fins"}, "Yes, it has fins.", "No, it does not have fins."),
        ({"scales", "scaly"}, {"scales"}, "Yes, it has scales.", "No, it does not have scales."),
        ({"shell"}, {"shell"}, "Yes, it has a shell.", "No, it does not have a shell."),
        ({"trunk"}, {"trunk"}, "Yes, it has a trunk.", "No, it does not have a trunk."),
        ({"stripes", "striped"}, {"stripes"}, "Yes, it has stripes.", "No, it does not have stripes."),
        ({"spots", "spotted"}, {"spots"}, "Yes, it has spots.", "No, it does not have spots."),
        ({"neck"}, {"neck"}, "Yes, it has a long neck.", "No, it does not have a long neck."),
        ({"pet", "home", "house"}, {"pet", "house"}, "Yes, it can be around people at home.", "No, it is not usually a house pet."),
        ({"farm", "barn"}, {"farm"}, "Yes, you might see it on a farm.", "No, it is not usually a farm animal."),
        ({"zoo"}, {"zoo"}, "Yes, you might see it at a zoo.", "No, it is not usually a zoo animal."),
        ({"wild"}, {"wild"}, "Yes, it is a wild animal.", "No, it is not usually a wild animal."),
        ({"big", "large", "huge"}, {"big", "very_big"}, "Yes, it is big.", "No, it is not very big."),
        ({"small", "little", "tiny"}, {"small"}, "Yes, it is small.", "No, it is not especially small."),
        ({"swim", "swims", "swimming"}, {"swim"}, "Yes, it can swim.", "No, it does not really swim."),
        ({"jump", "jumps", "jumping", "hop", "hops"}, {"jump", "hop"}, "Yes, it can jump.", "No, it is not known for jumping."),
        ({"tree", "trees", "climb", "climbs"}, {"tree"}, "Yes, it can climb or be around trees.", "No, trees are not a big clue."),
        ({"cold", "snow", "ice"}, {"cold"}, "Yes, it can live in cold places.", "No, cold places are not a big clue."),
        ({"fast", "quick"}, {"fast"}, "Yes, it can be fast.", "No, it is not especially fast."),
        ({"slow"}, {"slow"}, "Yes, it can be slow.", "No, it is not especially slow.")
    ]

    for trigger_words, needed_tags, yes_line, no_line in checks:
        if words & trigger_words:
            if tags & needed_tags:
                return {
                    "type": "answer",
                    "message": yes_line,
                    "question_answered": True
                }

            return {
                "type": "answer",
                "message": no_line,
                "question_answered": True
            }

    if any(word in words for word in {"eat", "eats", "food"}):
        detail = get_guessing_game_detail(game_state, "food")
        if detail:
            answer = detail
        elif "grass" in tags:
            answer = "It eats grass."
        elif "bamboo" in tags:
            answer = "It eats bamboo."
        elif "banana" in tags:
            answer = "It can eat bananas."
        elif "meat" in tags:
            answer = "It eats meat."
        else:
            answer = "It can eat different kinds of food."

        return {
            "type": "answer",
            "message": answer,
            "question_answered": True
        }

    return get_guessing_game_ai_question_answer(text, game_state)


def get_guessing_game_hint(game_state):
    import random

    profile = get_guessing_game_profile(game_state)
    recent_hints = list(game_state.get("recent_hints", []))
    hints = list(profile.get("hints", []))

    fresh = [hint for hint in hints if hint not in recent_hints]

    if fresh:
        hint = random.choice(fresh)
    elif hints:
        hint = random.choice(hints)
    else:
        hint = "This animal is one many kids know."

    game_state["recent_hints"] = (recent_hints + [hint])[-5:]
    game_state["hint_count"] = int(game_state.get("hint_count", 0)) + 1

    return hint


def classify_guessing_game_round_choice(text, offer_next_game=False):
    lowered = normalize_guessing_text(text)
    words = guessing_words(lowered)

    if not lowered:
        return "unclear"

    stop_words = {
        "stop", "done", "finish", "finished", "end", "quit",
        "leave", "dashboard", "no", "nope", "nah", "early"
    }

    same_game_words = {
        "again", "same", "replay", "more", "continue",
        "yes", "yeah", "yep", "yup", "sure", "okay", "ok",
        "alright", "fine", "good", "cool", "this", "play"
    }

    stop_phrases = [
        "end early",
        "end a little early",
        "little early",
        "stop early",
        "done for today",
        "finish today",
        "i want to stop",
        "i want to end",
        "let's stop",
        "lets stop"
    ]

    if words & stop_words or any(phrase in lowered for phrase in stop_phrases):
        return "stop"

    same_game_phrases = [
        "play again",
        "play another round",
        "another round",
        "one more round",
        "same game",
        "let's play",
        "lets play",
        "keep playing",
        "keep going",
        "continue playing",
        "do it again",
        "try again"
    ]

    if words & same_game_words or any(phrase in lowered for phrase in same_game_phrases):
        return "same_game"

    return "unclear"

def calm_guessing_game_line(text, game_complete=False):
    text = re.sub(r"\s+", " ", str(text or "")).strip()

    if not text:
        return "I'm thinking of an animal."

    replacements = {
        "Amazing": "Nice",
        "amazing": "nice",
        "Awesome": "Nice",
        "awesome": "nice",
        "Wow": "Hmm",
        "wow": "hmm",
        "Ooo": "Hmm",
        "ooo": "hmm",
        "Interesting question.": "Good question.",
        "Interesting.": "",
        "That is interesting.": "",
        "That gives me something to think about.": "",
        "Okay, that helps.": "",
        "That helps.": "",
        "I can work with that.": "",
        "Good job asking": "Good question",
        "Great job asking": "Great question",
        "Good job talking": "Thank you",
        "Great job talking": "Thank you",
        "Good job using your words": "Thank you",
        "I couldn't hear you": "That's okay",
        "I could not hear you": "That's okay"
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        text = "Good question."

    if not game_complete:
        text = text.replace("!", ".")

    if text.count("!") > 1:
        first = text.find("!")
        text = text[:first + 1] + text[first + 1:].replace("!", ".")

    return text[:300].strip()


def get_guessing_game_specific_color_answer(text, game_state):
    words = guessing_words(text)
    secret = game_state.get("secret_animal", "dog")

    color_words = {
        "black", "white", "brown", "orange", "yellow", "green",
        "gray", "grey", "blue", "red", "gold", "golden", "tan", "pink"
    }

    asked_colors = [color for color in color_words if color in words]

    animal_colors = {
        "dog": {"brown", "black", "white", "tan", "golden"},
        "cat": {"black", "white", "orange", "gray", "grey", "brown"},
        "fish": {"orange", "gold", "golden", "blue", "yellow"},
        "bird": {"blue", "red", "yellow", "black", "white", "brown"},
        "rabbit": {"white", "brown", "gray", "grey"},
        "frog": {"green", "brown"},
        "horse": {"brown", "black", "white", "tan"},
        "cow": {"black", "white", "brown"},
        "duck": {"yellow", "white", "brown"},
        "lion": {"yellow", "tan", "gold", "golden", "brown"},
        "tiger": {"orange", "black", "white"},
        "elephant": {"gray", "grey"},
        "giraffe": {"yellow", "brown", "tan"},
        "penguin": {"black", "white"},
        "dolphin": {"gray", "grey"},
        "shark": {"gray", "grey"},
        "turtle": {"green", "brown"},
        "monkey": {"brown", "black"},
        "zebra": {"black", "white"},
        "panda": {"black", "white"}
    }

    colors_for_secret = animal_colors.get(secret, set())

    if asked_colors:
        spoken_color = asked_colors[0]
        normalized_color = "gray" if spoken_color == "grey" else spoken_color

        normalized_colors_for_secret = {
            "gray" if color == "grey" else color
            for color in colors_for_secret
        }

        if normalized_color in normalized_colors_for_secret:
            return {
                "type": "answer",
                "message": f"Yes, it can be {normalized_color}.",
                "question_answered": True
            }

        return {
            "type": "answer",
            "message": f"No, it is not {normalized_color}.",
            "question_answered": True
        }

    if "color" in words or "colour" in words:
        detail = get_guessing_game_detail(game_state, "color")
        if detail:
            message = detail
        else:
            normalized_colors = sorted({
                "gray" if color == "grey" else color
                for color in colors_for_secret
            })

            if not normalized_colors:
                message = "It can be different colors."
            elif "black" in normalized_colors and "white" in normalized_colors:
                message = "It can be black and white."
            elif len(normalized_colors) == 1:
                message = f"It is often {normalized_colors[0]}."
            else:
                message = f"It can be {normalized_colors[0]}."

        return {
            "type": "answer",
            "message": message,
            "question_answered": True
        }

    return None


def maybe_add_good_question_prefix(message, game_state):
    import random

    question_count = int(game_state.get("questions_asked", 0))

    should_add = (
        question_count <= 2
        or question_count in {4, 6, 8}
        or random.random() < 0.55
    )

    if not should_add:
        return message

    lowered = normalize_guessing_text(message)

    if lowered.startswith((
        "that's a good question",
        "that is a good question",
        "good question",
        "great question",
        "nice question"
    )):
        return message

    prefixes = [
        "That's a good question.",
        "Good question.",
        "Great question.",
        "Nice question.",
        "That's a smart thing to ask."
    ]

    recent = list(game_state.get("recent_good_question_prefixes", []))[-3:]
    fresh = [prefix for prefix in prefixes if prefix not in recent]
    prefix = random.choice(fresh or prefixes)

    game_state["recent_good_question_prefixes"] = (recent + [prefix])[-3:]

    return f"{prefix} {message}"



def get_guessing_game_follow_up_after_answer(game_state):
    questions_asked = int(game_state.get("questions_asked", 0))
    wrong_guess_count = int(game_state.get("wrong_guess_count", 0))
    total_child_turns = questions_asked + wrong_guess_count

    # Most of the time, just answer the child's question and give space.
    if total_child_turns not in {4, 8}:
        return ""

    recent = list(game_state.get("recent_follow_ups", []))[-4:]
    options = [
        "You can keep asking questions, ask for example questions, or ask for a hint if you need one.",
        "You can ask another question, ask for a hint, or ask me for example questions.",
        "You can keep going with your own questions, or ask me for example questions if you want help."
    ]

    follow_up = pick_non_repeating_line(options, recent)
    game_state["recent_follow_ups"] = (recent + [follow_up])[-4:]
    return follow_up

def make_guessing_game_audio_response(
    message,
    stage,
    response_mode,
    expects_response,
    game_complete,
    game_state,
    history,
    event_type="server_response",
    child_response="",
    next_event=None,
    pause_before_next_ms=None,
    next_url=None,
    redirect_after_ms=None,
    session_done=False
):
    message = calm_guessing_game_line(message, game_complete=game_complete)

    history.append({
        "event_type": event_type,
        "child_response": child_response,
        "star": message,
        "stage": stage,
        "response_mode": response_mode,
        "game_complete": game_complete,
        "session_done": session_done
    })

    game_state["stage"] = stage
    game_state["last_response_mode"] = response_mode
    game_state["game_complete"] = game_complete

    session["guessing_game_history"] = history[-20:]
    session["guessing_game_state"] = game_state
    session.modified = True

    audio_bytes = generate_star_voice_elevenlabs(message)
    audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

    payload = {
        "success": True,
        "message": message,
        "audio": f"data:audio/mpeg;base64,{audio_base64}",
        "stage": stage,
        "expects_response": expects_response,
        "response_mode": response_mode,
        "game_complete": game_complete,
        "session_done": session_done,
        "offer_next_game": False,
        "game_state": game_state
    }

    if next_event:
        payload["next_event"] = next_event

    if pause_before_next_ms is not None:
        payload["pause_before_next_ms"] = pause_before_next_ms

    if next_url:
        payload["next_url"] = next_url

    if redirect_after_ms is not None:
        payload["redirect_after_ms"] = redirect_after_ms

    return jsonify(payload)


def get_guessing_game_correct_praise(event_type="correct_guess"):
    if event_type == "revealed_answer":
        return None

    child_name = clean_short_setting(session.get("child_name", ""), 40)

    if child_name and child_name.lower() not in {"none", "child"}:
        return f"Great job, {child_name}. You got it."

    return "Great job. You got it."


def make_guessing_game_correct_round_response(
    profile,
    game_state,
    history,
    event_type,
    child_response,
    base_message
):
    rounds_completed = int(game_state.get("rounds_completed", 0)) + 1
    rounds_completed = save_guessing_game_progress_for_user(rounds_completed)
    game_state["rounds_completed"] = rounds_completed
    game_state["game_complete"] = True

    praise_message = get_guessing_game_correct_praise(event_type) or base_message

    if rounds_completed >= GUESSING_GAME_MAX_ROUNDS:
        unlock_guessing_game_next_activity_for_user()

        message = (
            f"{praise_message} "
            "That was our last animal for today. "
            "This was a fun call. I'll see you next time. Bye."
        )

        return make_guessing_game_audio_response(
            message=message,
            stage="session_done",
            response_mode="none",
            expects_response=False,
            game_complete=True,
            game_state=game_state,
            history=history,
            event_type=event_type,
            child_response=child_response,
            next_url=url_for("dashboard"),
            redirect_after_ms=1800,
            session_done=True
        )

    used_animals = list(game_state.get("used_animals", []))
    current_animal = game_state.get("secret_animal")

    if current_animal and current_animal not in used_animals:
        used_animals.append(current_animal)

    new_game_state = get_guessing_game_default_state(
        rounds_completed=rounds_completed,
        used_animals=used_animals
    )

    if rounds_completed in {2}:
        check_in_options = [
            f"{praise_message} Do you want to play again, or do you want to end a little early today?",
            f"{praise_message} Do you want to keep playing, or end a little early today?",
            f"{praise_message} Do you want to play again, or stop here for today?"
        ]

        recent_star_lines = [
            item.get("star", "")
            for item in history[-8:]
            if isinstance(item, dict)
        ]

        message = pick_non_repeating_line(check_in_options, recent_star_lines)

        return make_guessing_game_audio_response(
            message=message,
            stage="round_choice",
            response_mode="round_choice_voice",
            expects_response=True,
            game_complete=False,
            game_state=new_game_state,
            history=[],
            event_type=event_type,
            child_response=child_response
        )

    message = praise_message

    return make_guessing_game_audio_response(
        message=message,
        stage="intro",
        response_mode="none",
        expects_response=False,
        game_complete=False,
        game_state=new_game_state,
        history=[],
        event_type=event_type,
        child_response=child_response,
        next_event="first_prompt",
        pause_before_next_ms=3600
    )


def unlock_guessing_game_next_activity_for_user():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT activity_id
            FROM activity
            WHERE activity_id = ?
              AND is_active = 1
        """, (GUESSING_GAME_NEXT_ACTIVITY_ID,))

        activity = cursor.fetchone()

        if not activity:
            conn.close()
            return False

        cursor.execute("""
            INSERT OR IGNORE INTO progress (
                user_id,
                activity_id,
                is_unlocked,
                is_completed,
                words_spoken,
                minutes_spoken,
                active_minutes,
                time_spent_on_activity
            )
            VALUES (?, ?, 1, 0, 0, 0, 0, 0)
        """, (session["user_id"], GUESSING_GAME_NEXT_ACTIVITY_ID))

        cursor.execute("""
            UPDATE progress
            SET is_unlocked = 1
            WHERE user_id = ? AND activity_id = ?
        """, (session["user_id"], GUESSING_GAME_NEXT_ACTIVITY_ID))

        cursor.execute("""
            UPDATE users
            SET current_activity_id = ?
            WHERE user_id = ?
        """, (GUESSING_GAME_NEXT_ACTIVITY_ID, session["user_id"]))

        conn.commit()
        conn.close()

        return True

    except Exception as e:
        print("Could not unlock next Guessing Game activity:", repr(e))
        return False


def ensure_guessing_game_progress_columns():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(progress)")
    existing_columns = {row["name"] for row in cursor.fetchall()}

    columns_to_add = {
        "guessing_game_rounds_completed": "ALTER TABLE progress ADD COLUMN guessing_game_rounds_completed INTEGER DEFAULT 0",
        "guessing_game_last_played_at": "ALTER TABLE progress ADD COLUMN guessing_game_last_played_at TEXT"
    }

    for column_name, alter_sql in columns_to_add.items():
        if column_name not in existing_columns:
            cursor.execute(alter_sql)

    conn.commit()
    conn.close()


def get_guessing_game_saved_rounds_for_user():
    ensure_guessing_game_progress_columns()

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COALESCE(p.guessing_game_rounds_completed, 0) AS rounds_completed
        FROM progress p
        JOIN activity a ON p.activity_id = a.activity_id
        WHERE p.user_id = ?
          AND a.activity_name = 'guessing_game'
        LIMIT 1
    """, (session["user_id"],))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return 0

    try:
        return max(0, min(GUESSING_GAME_MAX_ROUNDS, int(row["rounds_completed"] or 0)))
    except (TypeError, ValueError):
        return 0


def save_guessing_game_progress_for_user(rounds_completed):
    ensure_guessing_game_progress_columns()

    try:
        rounds_completed = max(0, min(GUESSING_GAME_MAX_ROUNDS, int(rounds_completed or 0)))
    except (TypeError, ValueError):
        rounds_completed = 0

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE progress
        SET
            guessing_game_rounds_completed = MAX(COALESCE(guessing_game_rounds_completed, 0), ?),
            guessing_game_last_played_at = ?,
            is_completed = CASE
                WHEN ? >= ? THEN 1
                ELSE is_completed
            END
        WHERE user_id = ?
          AND activity_id = (
              SELECT activity_id
              FROM activity
              WHERE activity_name = 'guessing_game'
              LIMIT 1
          )
    """, (
        rounds_completed,
        datetime.utcnow().isoformat(),
        rounds_completed,
        GUESSING_GAME_MAX_ROUNDS,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    return rounds_completed


def reset_guessing_game_progress_for_user():
    ensure_guessing_game_progress_columns()

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE progress
        SET
            guessing_game_rounds_completed = 0,
            guessing_game_last_played_at = NULL,
            is_completed = 0
        WHERE user_id = ?
          AND activity_id = (
              SELECT activity_id
              FROM activity
              WHERE activity_name = 'guessing_game'
              LIMIT 1
          )
    """, (session["user_id"],))

    conn.commit()
    conn.close()

    return 0

@app.route("/api/guessing-game/thinking-audio", methods=["GET"])
@csrf.exempt
@login_required
@limiter.limit("50 per minute")
def guessing_game_thinking_audio():
    return jsonify({
        "success": True,
        "line": "",
        "audio_url": None,
        "silent": True
    })


@app.route("/api/guessing-game/message", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("30 per minute")
def guessing_game_message():
    data = request.get_json(silent=True) or {}

    event_type = normalize_child_text(data.get("event_type", "intro"))
    child_response = normalize_child_text(data.get("child_response", ""))
    previous_response_mode = normalize_child_text(data.get("response_mode", "none"))

    allowed_events = {
        "intro",
        "restart",
        "first_prompt",
        "child_answer",
        "no_response"
    }

    if event_type not in allowed_events:
        return jsonify({"success": False, "error": "Invalid event_type"}), 400

    if event_type in {"intro", "restart"}:
        ensure_guessing_game_progress_columns()
        session.pop("guessing_game_history", None)
        session.pop("guessing_game_state", None)
        history = []

        if event_type == "restart":
            saved_rounds_completed = reset_guessing_game_progress_for_user()
        else:
            saved_rounds_completed = get_guessing_game_saved_rounds_for_user()

        game_state = get_guessing_game_default_state(rounds_completed=saved_rounds_completed)
        child_response = ""
        previous_response_mode = "none"
    else:
        history = session.get("guessing_game_history", [])
        game_state = session.get("guessing_game_state", get_guessing_game_default_state())

    profile = get_guessing_game_profile(game_state)

    if event_type in {"intro", "restart"}:
        intro_options = [
            "Hi, I'm Star. Let's play animal guessing together.",
            "Hi, I'm Star. I have an animal guessing game for us.",
            "Hi, I'm Star. Let's try an animal guessing game."
        ]

        message = pick_non_repeating_line(
            intro_options,
            [item.get("star", "") for item in history[-8:] if isinstance(item, dict)]
        )

        try:
            return make_guessing_game_audio_response(
                message=message,
                stage="intro",
                response_mode="none",
                expects_response=False,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type=event_type,
                child_response="",
                next_event="first_prompt",
                pause_before_next_ms=2200
            )

        except Exception as e:
            print("Guessing Game intro TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate Star intro"
            }), 500

    if event_type == "first_prompt":
        rounds_completed = int(game_state.get("rounds_completed", 0))

        if rounds_completed == 0:
            prompts = [
                "I picked an animal. You can ask me questions to try to figure out what animal I'm thinking of. You can ask for a hint if you need one, or guess whenever you're ready. If you need help thinking of questions, ask me for example questions.",
                "I have an animal in my head. Ask me questions to figure it out. You can ask for a hint, make a guess, or ask me for example questions if you want help getting started.",
                "I'm thinking of an animal. You can ask me questions to figure it out, ask for a hint, or guess when you're ready. If you need help, ask me for example questions."
            ]
        else:
            prompts = [
                "Let's play again. I'm going to think of another animal. You can ask me some questions to try to guess what it is.",
                "Let's try another one. I'm thinking of a new animal. Ask me questions to figure out what it is.",
                "Okay, new animal. You can ask me questions to try to guess what it is."
            ]

        recent_star_lines = [
            item.get("star", "")
            for item in history[-8:]
            if isinstance(item, dict)
        ]

        message = pick_non_repeating_line(prompts, recent_star_lines)

        try:
            return make_guessing_game_audio_response(
                message=message,
                stage="asking",
                response_mode="open_hint",
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type=event_type,
                child_response=child_response
            )

        except Exception as e:
            print("Guessing Game first prompt TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate first prompt"
            }), 500

    if previous_response_mode in {"round_choice", "round_choice_voice"} and event_type in {"child_answer", "no_response"}:
        rounds_completed = int(game_state.get("rounds_completed", 0))

        if event_type == "no_response":
            choice = "unclear"
        else:
            choice = classify_guessing_game_round_choice(
                child_response,
                offer_next_game=False
            )

        if choice == "same_game":
            previous_animal = game_state.get("secret_animal")

            used_animals = list(game_state.get("used_animals", []))

            if previous_animal and previous_animal not in used_animals:
                used_animals.append(previous_animal)

            new_game_state = get_guessing_game_default_state(
                rounds_completed=rounds_completed,
                used_animals=used_animals
            )

            replay_prompts = [
                "Okay, let's play again.",
                "Okay. Let's do another one.",
                "Sure. Let's keep going."
            ]

            recent_prompts = game_state.get("recent_round_prompts", [])
            message = pick_non_repeating_line(replay_prompts, recent_prompts)
            new_game_state["recent_round_prompts"] = (recent_prompts + [message])[-4:]

            try:
                return make_guessing_game_audio_response(
                    message=message,
                    stage="intro",
                    response_mode="none",
                    expects_response=False,
                    game_complete=False,
                    game_state=new_game_state,
                    history=[],
                    event_type="replay",
                    child_response=child_response,
                    next_event="first_prompt",
                    pause_before_next_ms=1600
                )

            except Exception as e:
                print("Guessing Game replay TTS error:", repr(e))
                return jsonify({
                    "success": False,
                    "error": "Could not start another round"
                }), 500

        if choice == "stop":
            message = (
                "Okay. We can end a little early today. "
                "Thanks for playing the animal guessing game with me. Bye."
            )

            try:
                return make_guessing_game_audio_response(
                    message=message,
                    stage="session_done",
                    response_mode="none",
                    expects_response=False,
                    game_complete=False,
                    game_state=game_state,
                    history=history,
                    event_type="stop",
                    child_response=child_response,
                    next_url=url_for("dashboard"),
                    redirect_after_ms=1200,
                    session_done=True
                )

            except Exception as e:
                print("Guessing Game stop TTS error:", repr(e))
                return jsonify({
                    "success": False,
                    "error": "Could not end the game"
                }), 500

        message = "That's okay. Do you want to play again, or do you want to end a little early today?"

        try:
            return make_guessing_game_audio_response(
                message=message,
                stage="round_choice",
                response_mode="round_choice_voice",
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type="choice_clarification",
                child_response=child_response
            )

        except Exception as e:
            print("Guessing Game choice clarification TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate choice response"
            }), 500

    if previous_response_mode == "reveal_choice" and event_type in {"child_answer", "no_response"}:
        if event_type == "child_answer" and is_yes_response(child_response):
            base_message = f"Okay. It is a {profile['display']}."

            try:
                return make_guessing_game_correct_round_response(
                    profile=profile,
                    game_state=game_state,
                    history=history,
                    event_type="revealed_answer",
                    child_response=child_response,
                    base_message=base_message
                )

            except Exception as e:
                print("Guessing Game reveal answer TTS error:", repr(e))
                return jsonify({
                    "success": False,
                    "error": "Could not reveal the answer"
                }), 500

        if event_type == "child_answer" and is_no_response(child_response):
            message = "Okay. We can keep guessing. You can ask me a question, ask for a hint, ask for example questions, or make a guess."

            try:
                return make_guessing_game_audio_response(
                    message=message,
                    stage="support",
                    response_mode="open_hint",
                    expects_response=True,
                    game_complete=False,
                    game_state=game_state,
                    history=history,
                    event_type="reveal_declined",
                    child_response=child_response
                )

            except Exception as e:
                print("Guessing Game reveal declined TTS error:", repr(e))
                return jsonify({
                    "success": False,
                    "error": "Could not continue the game"
                }), 500

        message = "That's okay. Do you want me to tell you what it is?"

        try:
            return make_guessing_game_audio_response(
                message=message,
                stage="support",
                response_mode="reveal_choice",
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type="reveal_choice_repeat",
                child_response=child_response
            )

        except Exception as e:
            print("Guessing Game reveal repeat TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not repeat reveal choice"
            }), 500

    if event_type == "no_response" or is_guessing_unclear_or_silent(child_response):
        game_state["unclear_or_silent_count"] = int(game_state.get("unclear_or_silent_count", 0)) + 1
        game_state["unclear_streak"] = int(game_state.get("unclear_streak", 0)) + 1

        # Keep silence support calm and infrequent. Do not keep repeating
        # "guess whenever you're ready" after every quiet window.
        if is_guessing_i_dont_know_response(child_response):
            message = "That's okay. You can ask me for a hint, or ask me for some example questions to help you out."
        elif int(game_state.get("unclear_streak", 0)) >= 3:
            message = "No problem. I can give you a tiny hint if you want."
        else:
            message = "Take your time. You can ask me for a hint, or ask me for some example questions to help you out."

        try:
            return make_guessing_game_audio_response(
                message=message,
                stage="support",
                response_mode="open_hint",
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type=event_type,
                child_response=child_response
            )

        except Exception as e:
            print("Guessing Game support TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate support response"
            }), 500

    game_state["unclear_streak"] = 0

    if is_guessing_example_question_request(child_response):
        message = get_guessing_game_suggestion_line(game_state, max_ideas=3, include_guess=False)

        try:
            return make_guessing_game_audio_response(
                message=message,
                stage="support",
                response_mode="open_hint",
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type="example_questions",
                child_response=child_response
            )

        except Exception as e:
            print("Guessing Game example question TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate example questions"
            }), 500

    if is_guessing_hint_request(child_response):
        hint = get_guessing_game_hint(game_state)

        hint_prefixes = [
            "Here is a tiny clue.",
            "I can give you a clue.",
            "Okay, here is one hint.",
            "Sure. Here is a hint."
        ]

        recent_star_lines = [
            item.get("star", "")
            for item in history[-8:]
            if isinstance(item, dict)
        ]

        prefix = pick_non_repeating_line(hint_prefixes, recent_star_lines)
        message = f"{prefix} {hint}"

        try:
            return make_guessing_game_audio_response(
                message=message,
                stage="hint",
                response_mode="open_hint",
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type=event_type,
                child_response=child_response
            )

        except Exception as e:
            print("Guessing Game hint TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate hint"
            }), 500

    if is_guessing_direct_guess(child_response):
        guessed_animal = get_guessing_named_animal(child_response)
        secret_animal = game_state.get("secret_animal")

        if guessed_animal == secret_animal:
            base_message = f"Yes, it is a {profile['display']}. You got it."

            try:
                return make_guessing_game_correct_round_response(
                    profile=profile,
                    game_state=game_state,
                    history=history,
                    event_type="correct_guess",
                    child_response=child_response,
                    base_message=base_message
                )

            except Exception as e:
                print("Guessing Game correct guess TTS error:", repr(e))
                return jsonify({
                    "success": False,
                    "error": "Could not generate correct guess response"
                }), 500

        if guessed_animal:
            game_state.setdefault("wrong_guesses", []).append(guessed_animal)
            game_state["wrong_guess_count"] = int(game_state.get("wrong_guess_count", 0)) + 1

            base_options = [
                f"Not quite, it is not a {GUESSING_GAME_ANIMAL_PROFILES[guessed_animal]['display']}.",
                f"Good guess, but it is not a {GUESSING_GAME_ANIMAL_PROFILES[guessed_animal]['display']}.",
                "Not that one.",
                f"It is not a {GUESSING_GAME_ANIMAL_PROFILES[guessed_animal]['display']}."
            ]

            recent_star_lines = [
                item.get("star", "")
                for item in history[-8:]
                if isinstance(item, dict)
            ]

            base_message = pick_non_repeating_line(base_options, recent_star_lines)
            follow_up = get_guessing_game_follow_up_after_answer(game_state)

            if follow_up:
                message = f"{base_message} {follow_up}"
            else:
                message = base_message

            try:
                return make_guessing_game_audio_response(
                    message=message,
                    stage="wrong_guess",
                    response_mode="open_hint",
                    expects_response=True,
                    game_complete=False,
                    game_state=game_state,
                    history=history,
                    event_type="wrong_guess",
                    child_response=child_response
                )

            except Exception as e:
                print("Guessing Game wrong guess TTS error:", repr(e))
                return jsonify({
                    "success": False,
                    "error": "Could not generate wrong guess response"
                }), 500

    if is_guessing_question(child_response):
        answer = answer_guessing_question(child_response, game_state)

        if answer["type"] == "correct_guess":
            base_message = answer["message"]

            try:
                return make_guessing_game_correct_round_response(
                    profile=profile,
                    game_state=game_state,
                    history=history,
                    event_type="correct_guess",
                    child_response=child_response,
                    base_message=base_message
                )

            except Exception as e:
                print("Guessing Game question correct TTS error:", repr(e))
                return jsonify({
                    "success": False,
                    "error": "Could not generate correct response"
                }), 500

        if answer["type"] == "wrong_guess":
            wrong_guess = answer.get("wrong_guess")

            if wrong_guess:
                game_state.setdefault("wrong_guesses", []).append(wrong_guess)

            game_state["wrong_guess_count"] = int(game_state.get("wrong_guess_count", 0)) + 1

            base_message = answer["message"]
            follow_up = get_guessing_game_follow_up_after_answer(game_state)

            if follow_up:
                message = f"{base_message} {follow_up}"
            else:
                message = base_message

            try:
                return make_guessing_game_audio_response(
                    message=message,
                    stage="wrong_guess",
                    response_mode="open_hint",
                    expects_response=True,
                    game_complete=False,
                    game_state=game_state,
                    history=history,
                    event_type="wrong_guess",
                    child_response=child_response
                )

            except Exception as e:
                print("Guessing Game question wrong TTS error:", repr(e))
                return jsonify({
                    "success": False,
                    "error": "Could not generate wrong guess response"
                }), 500

        if answer.get("question_answered"):
            game_state["questions_asked"] = int(game_state.get("questions_asked", 0)) + 1
            game_state["comfortable_question_count"] = int(game_state.get("comfortable_question_count", 0)) + 1

            question_key = guessing_question_key(child_response)

            if question_key:
                game_state.setdefault("asked_questions", []).append(question_key)
                game_state["asked_questions"] = game_state["asked_questions"][-12:]

            remember_guessing_question_topic(child_response, game_state)

            answer_message = maybe_add_good_question_prefix(
                answer["message"],
                game_state
            )

            follow_up = get_guessing_game_follow_up_after_answer(game_state)

            if follow_up:
                message = f"{answer_message} {follow_up}"
            else:
                message = answer_message

            try:
                return make_guessing_game_audio_response(
                    message=message,
                    stage="answering",
                    response_mode="open_hint",
                    expects_response=True,
                    game_complete=False,
                    game_state=game_state,
                    history=history,
                    event_type=event_type,
                    child_response=child_response
                )

            except Exception as e:
                print("Guessing Game answer TTS error:", repr(e))
                return jsonify({
                    "success": False,
                    "error": "Could not answer question"
                }), 500

        try:
            return make_guessing_game_audio_response(
                message=answer["message"],
                stage="support",
                response_mode="open_hint",
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type=event_type,
                child_response=child_response
            )

        except Exception as e:
            print("Guessing Game support answer TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate support"
            }), 500

    named_animal = get_guessing_named_animal(child_response)

    if named_animal:
        secret_animal = game_state.get("secret_animal")

        if named_animal == secret_animal:
            base_message = f"Yes, it is a {profile['display']}. You got it."

            try:
                return make_guessing_game_correct_round_response(
                    profile=profile,
                    game_state=game_state,
                    history=history,
                    event_type="correct_guess",
                    child_response=child_response,
                    base_message=base_message
                )

            except Exception as e:
                print("Guessing Game named correct TTS error:", repr(e))
                return jsonify({
                    "success": False,
                    "error": "Could not generate correct response"
                }), 500

        game_state.setdefault("wrong_guesses", []).append(named_animal)
        game_state["wrong_guess_count"] = int(game_state.get("wrong_guess_count", 0)) + 1

        base_message = (
            f"Not quite, it is not a {GUESSING_GAME_ANIMAL_PROFILES[named_animal]['display']}."
        )

        follow_up = get_guessing_game_follow_up_after_answer(game_state)

        if follow_up:
            message = f"{base_message} {follow_up}"
        else:
            message = base_message

        try:
            return make_guessing_game_audio_response(
                message=message,
                stage="wrong_guess",
                response_mode="open_hint",
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type="wrong_guess",
                child_response=child_response
            )

        except Exception as e:
            print("Guessing Game named wrong TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate wrong guess response"
            }), 500

    game_state["comfortable_question_count"] = int(game_state.get("comfortable_question_count", 0)) + 1

    fallback_lines = [
        "You can ask me a question to figure out the animal, ask for a hint, ask for example questions, or guess whenever you're ready.",
        "That's okay. You can ask me about the animal, ask for a hint, or guess when you're ready.",
        "No problem. Ask me a question, ask for example questions, or make a guess whenever you're ready."
    ]

    recent_star_lines = [
        item.get("star", "")
        for item in history[-8:]
        if isinstance(item, dict)
    ]

    message = pick_non_repeating_line(fallback_lines, recent_star_lines)

    try:
        return make_guessing_game_audio_response(
            message=message,
            stage="support",
            response_mode="open_hint",
            expects_response=True,
            game_complete=False,
            game_state=game_state,
            history=history,
            event_type=event_type,
            child_response=child_response
        )

    except Exception as e:
        print("Guessing Game fallback TTS error:", repr(e))
        return jsonify({
            "success": False,
            "error": "Could not generate fallback response"
        }), 500


@app.route("/api/guessing-game/transcribe", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("20 per minute")
def guessing_game_transcribe():
    if "audio" not in request.files:
        return jsonify({
            "success": False,
            "error": "Missing audio"
        }), 400

    audio_file = request.files["audio"]

    try:
        import io

        audio_bytes = audio_file.read()

        if not audio_bytes:
            return jsonify({
                "success": False,
                "error": "Empty audio file"
            }), 400

        file_obj = io.BytesIO(audio_bytes)
        file_obj.name = "child-response.webm"

        transcript = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=file_obj
        )

        text = transcript.text.strip()

        print("GUESSING GAME TRANSCRIPT:", text)

        return jsonify({
            "success": True,
            "text": text
        })

    except Exception as e:
        print("Guessing Game transcription error:", repr(e))
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# =========================
# Toy Trivia Game — smoother Toy Trivia interaction
#
# This block intentionally uses the smoother Toy Trivia flow, and all public
# routes, session keys, logs, and restart names are Toy Trivia names.
# =========================

def generate_toy_trivia_voice_elevenlabs(text, game_complete=False, thinking=False):
    voice_id = os.getenv("TOY_TRIVIA_VOICE_ID")

    if not voice_id:
        voice_id = os.getenv("ELEVENLABS_VOICE_ID", "piI8Kku0DcvcL6TTSeQt")

    if game_complete:
        voice_settings = {
            "stability": 0.84,
            "similarity_boost": 0.90,
            "style": 0.25,
            "use_speaker_boost": False
        }
    elif thinking:
        voice_settings = {
            "stability": 0.98,
            "similarity_boost": 0.88,
            "style": 0.02,
            "use_speaker_boost": False
        }
    else:
        voice_settings = {
            "stability": 0.94,
            "similarity_boost": 0.90,
            "style": 0.06,
            "use_speaker_boost": False
        }

    response = eleven_client.text_to_speech.convert(
        voice_id=voice_id,
        text=text,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
        voice_settings=voice_settings
    )

    return b"".join(response)


@app.route("/api/toy-trivia-game/thinking-audio", methods=["GET"])
@csrf.exempt
@login_required
@limiter.limit("50 per minute")
def toy_trivia_game_thinking_audio():
    import hashlib
    import random

    thinking_lines = [
        "Hmm.",
        "Hmmmm.",
        "Hmmm.",
        "Uhmmmm.",
        "Uhmmm."   
    ]

    avoid_raw = request.args.get("avoid", "")
    avoid_lines = {
        re.sub(r"\s+", " ", item).strip().lower()
        for item in avoid_raw.split("|")
        if item.strip()
    }

    fresh_lines = [
        line for line in thinking_lines
        if re.sub(r"\s+", " ", line).strip().lower() not in avoid_lines
    ]

    if not fresh_lines:
        fresh_lines = thinking_lines

    line = random.choice(fresh_lines)

    cache_dir = os.path.join(BASE_DIR, "static", "audio", "toy_trivia_thinking")
    os.makedirs(cache_dir, exist_ok=True)

    voice_id = os.getenv("TOY_TRIVIA_VOICE_ID") or os.getenv("ELEVENLABS_VOICE_ID", "piI8Kku0DcvcL6TTSeQt")
    cache_key = f"toy-trivia-thinking-v2:{voice_id}:{line}"
    filename = hashlib.md5(cache_key.encode("utf-8")).hexdigest() + ".mp3"
    filepath = os.path.join(cache_dir, filename)

    try:
        if not os.path.exists(filepath):
            audio_bytes = generate_toy_trivia_voice_elevenlabs(line, thinking=True)

            with open(filepath, "wb") as f:
                f.write(audio_bytes)

        return jsonify({
            "success": True,
            "line": line,
            "audio_url": url_for(
                "static",
                filename=f"audio/toy_trivia_thinking/{filename}"
            )
        })

    except Exception as e:
        print("Toy Trivia thinking audio error:", repr(e))
        return jsonify({
            "success": False,
            "error": "Could not generate thinking audio"
        }), 500


TOY_TRIVIA_LEVELS = [
    {
        "stage": "yes_no",
        "response_mode": "yes_no",
        "description": "Ask a concrete yes/no toy question.",
        "examples": [
            "Is it something you can hold?",
            "Does it have wheels?",
            "Is it soft?"
        ],
        "fallback_questions": [
            "Does it have wheels?",
            "Is it soft?",
            "Can you build with it?",
            "Does it make noise?",
            "Is it bigger than your hand?",
            "Would you play with it outside?",
            "Can it roll?",
            "Does it have colors on it?",
            "Is it a toy you can hug?",
            "Would you see it in a toy store?",
            "Can it fit in a backpack?",
            "Does it have pretend people or animals?"
        ]
    },
    {
        "stage": "forced_choice",
        "response_mode": "choice",
        "description": "Ask a two-option toy question.",
        "examples": [
            "Is it soft or hard?",
            "Is it big or small?",
            "Would it be on a shelf or in a bin?"
        ],
        "fallback_questions": [
            "Is it soft or hard?",
            "Is it big or small?",
            "Does it roll or stay still?",
            "Would you play with it inside or outside?",
            "Is it a toy car or a stuffed animal?",
            "Is it made for building or pretending?",
            "Would it be red or blue?",
            "Does it have wheels or no wheels?"
        ]
    },
    {
        "stage": "one_word",
        "response_mode": "one_word",
        "description": "Ask for one simple word.",
        "examples": [
            "What color is it?",
            "What size is it?",
            "What is one thing it has?"
        ],
        "fallback_questions": [
            "What color is it?",
            "What size is it?",
            "What is one thing it has?",
            "Can you give me one clue?",
            "What shape is it?"
        ]
    },
    {
        "stage": "short_phrase",
        "response_mode": "short_phrase",
        "description": "Ask for a tiny phrase.",
        "examples": [
            "What do you do with it?",
            "What does it look like?"
        ],
        "fallback_questions": [
            "What do you do with it?",
            "What does it look like?",
            "Where would I find it in the toy store?",
            "Tell me one small clue.",
            "What part should I look for?"
        ]
    },
    {
        "stage": "open_hint",
        "response_mode": "open_hint",
        "description": "Ask for any small hint the child wants to give.",
        "examples": [
            "Can you give me a tiny hint?",
            "What is one fun thing about this toy?",
            "What is your favorite thing about this toy?"
        ],
        "fallback_questions": [
            "Can you give me a tiny hint?",
            "What is one fun thing about this toy?",
            "What is your favorite thing about this toy?",
            "What should I know about the toy?"
        ]
    }
]

TOY_TRIVIA_START_LEVEL_INDEX = 2
TOY_TRIVIA_NEXT_GAME_OFFER_ROUND = 3
TOY_TRIVIA_NEXT_ACTIVITY_ID = 6  # Change this if your next toy-store activity uses a different activity_id.
TOY_TRIVIA_SOFT_REVEAL_QUESTION_LIMIT = 15

TOY_TRIVIA_COMMON_TOYS = {
    "ball", "blocks", "block", "toy car", "car", "truck", "toy truck",
    "train", "toy train", "doll", "teddy bear", "bear", "stuffed animal",
    "plush", "robot", "puzzle", "kite", "crayons", "crayon", "jump rope",
    "rubber duck", "duck", "dinosaur", "dinosaur toy", "yo-yo", "yoyo",
    "spinner", "drum", "toy phone", "phone", "action figure", "lego", "legos",
    "board game", "cards", "marbles", "play dough", "playdough", "slinky"
}


def get_toy_trivia_game_default_state(rounds_completed=0):
    return {
        "stage": "intro",
        "response_level_index": TOY_TRIVIA_START_LEVEL_INDEX,
        "questions_asked": 0,
        "comfortable_answer_count": 0,
        "unclear_or_silent_count": 0,
        "comfortable_streak": 0,
        "unclear_streak": 0,
        "question_history": [],
        "known_clues": [],
        "rejected_guesses": [],
        "possible_guess": None,
        "last_question": None,
        "last_response_mode": "none",
        "game_complete": False,
        "rounds_completed": rounds_completed_int,
        "skip_guess_once": False,
        "guess_cooldown_questions": 0,
        "last_acknowledgment_index": -1,
        "clear_answer_word_counts": [],
        "recent_question_families": [],
        "asked_question_families": [],
        "recent_guesses": [],
        "recent_acknowledgments": [],
        "open_hint_questions_asked": 0,
        "soft_reveal_used": False
    }


def normalize_child_text(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def get_child_revealed_toy(text):
    lowered = normalize_child_text(text).lower()

    if not lowered:
        return None

    cleaned = re.sub(r"[^a-z' -]", " ", lowered)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    words = set(re.findall(r"[a-z']+", cleaned))

    if not words:
        return None

    direct_reveal_phrases = [
        "it's",
        "it is",
        "my toy is",
        "the toy is",
        "i picked",
        "i chose",
        "i was thinking of",
        "i am thinking of",
        "it was",
        "it's a",
        "it is a"
    ]

    has_direct_reveal = any(phrase in cleaned for phrase in direct_reveal_phrases)

    if has_direct_reveal:
        for toy in TOY_TRIVIA_COMMON_TOYS:
            if toy in words:
                return toy

    # Also handle direct short answers like "ball", "a toy car", or "teddy bear".
    # In Toy Trivia, if the child names a familiar toy directly,
    # Toy Store Worker should accept that instead of asking for more hints.
    if len(words) <= 4:
        for toy in TOY_TRIVIA_COMMON_TOYS:
            if toy in words:
                return toy

    return None


def is_yes_response(text):
    lowered = normalize_child_text(text).lower()
    words = set(re.findall(r"[a-z']+", lowered))

    return bool(words & {
        "yes", "yeah", "yep", "yup", "sure", "correct", "right"
    }) or lowered in {"yes", "yeah", "yep", "yup"}


def is_no_response(text):
    lowered = normalize_child_text(text).lower()
    words = set(re.findall(r"[a-z']+", lowered))

    return bool(words & {
        "no", "nope", "nah", "not"
    }) or lowered in {"no", "nope", "nah"}


def classify_toy_trivia_game_choice_response(text, offer_next_game=False):
    lowered = normalize_child_text(text).lower()
    words = set(re.findall(r"[a-z']+", lowered))

    if not lowered:
        return "unclear"

    stop_words = {
        "stop", "done", "finish", "finished", "end", "quit", "leave",
        "dashboard", "no", "nope", "nah"
    }

    next_game_words = {
        "different", "new", "next", "other", "guessing"
    }

    same_game_words = {
        "again", "same", "replay", "more", "continue",
        "yes", "yeah", "yep", "yup", "sure",
        "okay", "ok", "alright", "fine", "good", "cool",
        "this"
    }

    if words & stop_words:
        return "stop"

    if offer_next_game and words & next_game_words:
        return "next_game"

    if words & same_game_words:
        return "same_game"

    same_game_phrases = [
        "play again",
        "play another round",
        "another round",
        "one more round",
        "this game",
        "same game",
        "let's play",
        "lets play",
        "let us play",
        "keep playing",
        "do it again",
        "try again"
    ]

    if any(phrase in lowered for phrase in same_game_phrases):
        return "same_game"

    if offer_next_game:
        next_game_phrases = [
            "different game",
            "next game",
            "new game",
            "other game",
            "different version",
            "slightly different",
            "guessing game"
        ]

        if any(phrase in lowered for phrase in next_game_phrases):
            return "next_game"

    return "unclear"


def is_unclear_or_silent_response(text):
    lowered = normalize_child_text(text).lower()

    if not lowered:
        return True

    unclear_phrases = {
        "i don't know",
        "i dont know",
        "i do not know",
        "don't know",
        "dont know",
        "idk",
        "not sure",
        "not really sure",
        "i'm not sure",
        "im not sure",
        "maybe",
        "hmm",
        "uh",
        "um"
    }

    if lowered in unclear_phrases:
        return True

    usable_words = re.findall(r"[A-Za-z']+", lowered)

    if not usable_words:
        return True

    return False


def is_clear_toy_trivia_game_response(text, response_mode):
    cleaned = normalize_child_text(text)

    if is_unclear_or_silent_response(cleaned):
        return False

    if response_mode == "yes_no":
        return is_yes_response(cleaned) or is_no_response(cleaned)

    if response_mode == "guess_confirmation":
        return is_yes_response(cleaned) or is_no_response(cleaned)

    if response_mode in {
        "choice",
        "one_word",
        "short_phrase",
        "open_hint",
        "round_choice"
    }:
        return len(re.findall(r"[A-Za-z']+", cleaned)) >= 1

    return len(re.findall(r"[A-Za-z']+", cleaned)) >= 1


def calm_toy_trivia_game_line(text, game_complete=False):
    text = re.sub(r"\s+", " ", str(text or "")).strip()

    if not text:
        return "Hmm, let me ask a tiny question."

    replacements = {
        "Amazing": "Nice",
        "amazing": "nice",
        "Awesome": "Nice",
        "awesome": "nice",
        "Wow": "Hmm",
        "wow": "hmm",
        "Ooo": "Hmm",
        "ooo": "hmm",
        "Oh, let me try to ask it in a simpler way": "That's okay. I have another question",
        "Let me try to ask it in a simpler way": "That's okay. I have another question",
        "Let me ask it in a simpler way": "That's okay. I have another question",
        "Maybe that was too hard": "That's okay",
        "That might have been too hard": "That's okay",
        "I couldn't hear you": "That's okay",
        "I could not hear you": "That's okay",
        "Great job talking": "Thank you, that helps",
        "Good job talking": "Thank you, that helps",
        "Good job saying that": "Thank you, that helps",
        "Great job saying that": "Thank you, that helps",
        "Good job using your words": "Thank you, that helps"
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    if not game_complete:
        text = text.replace("!", ".")

    if text.count("!") > 1:
        first = text.find("!")
        text = text[:first + 1] + text[first + 1:].replace("!", ".")

    return text[:260].strip()


def maybe_add_toy_trivia_game_acknowledgment(
    message,
    event_type,
    child_response,
    previous_response_mode,
    game_state
):
    import random

    if event_type != "child_answer":
        return message

    if previous_response_mode in {"none", "guess_confirmation", "round_choice"}:
        return message

    if not is_clear_toy_trivia_game_response(child_response, previous_response_mode):
        return message

    lowered_message = normalize_child_text(message).lower()

    existing_acknowledgments = [
        "thank you",
        "thanks",
        "that helps",
        "that's helpful",
        "that is helpful",
        "that gives me",
        "good clue",
        "helpful clue",
        "useful clue",
        "useful to know",
        "that makes",
        "okay, that",
        "hmm, that",
        "interesting clue",
        "i can work with"
    ]

    if any(phrase in lowered_message for phrase in existing_acknowledgments):
        return message

    acknowledgments = [
        "That helps.",
        "Okay, that gives me a clue.",
        "That narrows it down.",
        "Interesting, that changes my guess.",
        "That gives me something to think about.",
        "Okay, I can work with that clue.",
        "That helps me picture it.",
        "Nice clue.",
        "Okay, I have a little more to go on.",
        "That makes the toy easier to picture."
    ]

    recent = list(game_state.get("recent_acknowledgments", []))[-4:]
    fresh = [ack for ack in acknowledgments if ack not in recent]

    acknowledgment = random.choice(fresh or acknowledgments)
    game_state["recent_acknowledgments"] = (recent + [acknowledgment])[-4:]

    return f"{acknowledgment} {message}"


def get_toy_trivia_game_level(game_state):
    index = int(game_state.get("response_level_index", TOY_TRIVIA_START_LEVEL_INDEX))
    index = max(0, min(index, len(TOY_TRIVIA_LEVELS) - 1))
    game_state["response_level_index"] = index
    return TOY_TRIVIA_LEVELS[index]


def get_question_history_set(game_state):
    question_history = game_state.get("question_history", [])

    return {
        normalize_child_text(item.get("question", "")).lower()
        for item in question_history
        if isinstance(item, dict)
    }


def choose_non_repeating_question(level, game_state):
    import random

    asked_questions = get_question_history_set(game_state)
    recent_families = list(game_state.get("recent_question_families", []))[-3:]
    questions = list(level.get("fallback_questions", []))

    fresh_questions = [
        question for question in questions
        if normalize_child_text(question).lower() not in asked_questions
    ]

    pool = fresh_questions or questions

    if not pool:
        return "What is one clue?"

    # Prefer a different type of question than the last few turns.
    family_filtered = [
        question for question in pool
        if get_question_family(question) not in recent_families[-2:]
    ]

    if family_filtered:
        pool = family_filtered

    question = random.choice(pool)
    family = get_question_family(question)

    updated_families = recent_families + [family]
    game_state["recent_question_families"] = updated_families[-4:]

    return question


def get_fallback_toy_trivia_game_question(level, game_state=None, event_type="child_answer"):
    if game_state is None:
        game_state = {}

    stage = level["stage"]
    question_text = choose_non_repeating_question(level, game_state)

    if event_type == "no_response":
        calm_prefixes = [
            "That's okay.",
            "No problem.",
            "That's okay. We can try a different question.",
            "No worries."
        ]

        prefix_index = int(game_state.get("unclear_or_silent_count", 0)) % len(calm_prefixes)
        prefix = calm_prefixes[prefix_index]
        if prefix.endswith("question."):
            message = f"{prefix} {question_text}"
        else:
            message = f"{prefix} {question_text}"
    else:
        message = f"Hmm, {question_text[0].lower() + question_text[1:]}"

    return {
        "message": message,
        "stage": stage,
        "response_mode": level["response_mode"],
        "question_text": question_text
    }


def pick_fallback_toy_guess(game_state):
    import random

    toy_profiles = {
        "ball": ["round", "bounce", "roll", "outside", "sport", "throw", "kick"],
        "blocks": ["build", "stack", "tower", "wood", "colors", "square", "hard"],
        "toy car": ["wheels", "roll", "vroom", "drive", "small", "road", "race"],
        "toy truck": ["wheels", "big", "carry", "drive", "construction", "dump", "road"],
        "train": ["tracks", "choo", "wheels", "cars", "rail", "long"],
        "doll": ["pretend", "person", "clothes", "hair", "small", "dress"],
        "teddy bear": ["soft", "hug", "stuffed", "bear", "brown", "bed"],
        "stuffed animal": ["soft", "hug", "animal", "plush", "bed", "fuzzy"],
        "robot": ["metal", "buttons", "beep", "move", "pretend", "machine"],
        "puzzle": ["pieces", "picture", "fit", "table", "shapes", "solve"],
        "kite": ["fly", "outside", "wind", "string", "sky"],
        "crayons": ["color", "draw", "paper", "box", "rainbow"],
        "jump rope": ["jump", "rope", "outside", "swing", "exercise"],
        "rubber duck": ["duck", "bath", "yellow", "water", "squeak"],
        "dinosaur toy": ["dinosaur", "roar", "green", "pretend", "animal"],
        "yo-yo": ["string", "up", "down", "round", "trick"],
        "action figure": ["person", "hero", "pretend", "small", "pose"],
        "legos": ["build", "blocks", "plastic", "pieces", "connect"],
        "board game": ["game", "board", "pieces", "turns", "family"],
        "play dough": ["soft", "squish", "make", "shape", "color"]
    }
    rejected = {
        str(item).lower().strip()
        for item in game_state.get("rejected_guesses", [])
        if item
    }

    recent = {
        str(item).lower().strip()
        for item in game_state.get("recent_guesses", [])[-4:]
        if item
    }

    possible_guess = str(game_state.get("possible_guess") or "").lower().strip()

    clue_text = " ".join(
        str(item.get("answer", ""))
        for item in game_state.get("known_clues", [])
        if isinstance(item, dict)
    ).lower()

    candidates = []

    for toy, keywords in toy_profiles.items():
        if toy in rejected or toy == possible_guess:
            continue

        score = 0
        for keyword in keywords:
            if keyword in clue_text:
                score += 2

        if toy in clue_text:
            score += 5

        if toy in recent:
            score -= 3

        candidates.append((score, toy))

    if not candidates:
        return "ball"

    best_score = max(score for score, _ in candidates)

    if best_score > 0:
        best = [toy for score, toy in candidates if score == best_score]
    else:
        # No clue match yet. Pick randomly instead of always starting with ball.
        best = [toy for score, toy in candidates if toy not in recent]
        if not best:
            best = [toy for _, toy in candidates]

    guess = random.choice(best)
    game_state["recent_guesses"] = (list(game_state.get("recent_guesses", [])) + [guess])[-5:]

    return guess


def unlock_toy_trivia_game_next_game_for_user():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT activity_id
            FROM activity
            WHERE activity_id = ?
              AND is_active = 1
        """, (TOY_TRIVIA_NEXT_ACTIVITY_ID,))

        activity = cursor.fetchone()

        if not activity:
            conn.close()
            return False

        cursor.execute("""
            INSERT OR IGNORE INTO progress (
                user_id,
                activity_id,
                is_unlocked,
                is_completed,
                words_spoken,
                minutes_spoken,
                active_minutes,
                time_spent_on_activity
            )
            VALUES (?, ?, 1, 0, 0, 0, 0, 0)
        """, (session["user_id"], TOY_TRIVIA_NEXT_ACTIVITY_ID))

        cursor.execute("""
            UPDATE progress
            SET is_unlocked = 1
            WHERE user_id = ? AND activity_id = ?
        """, (session["user_id"], TOY_TRIVIA_NEXT_ACTIVITY_ID))

        cursor.execute("""
            UPDATE users
            SET current_activity_id = ?
            WHERE user_id = ?
        """, (TOY_TRIVIA_NEXT_ACTIVITY_ID, session["user_id"]))

        conn.commit()
        conn.close()

        return True

    except Exception as e:
        print("Could not unlock next Toy Trivia game:", repr(e))
        return False


def apply_toy_trivia_game_comfort_update(game_state, event_type, child_response, previous_response_mode):
    if event_type in {"intro", "restart", "first_question"}:
        return

    if game_state.get("game_complete"):
        return

    child_response = normalize_child_text(child_response)
    previous_stage = game_state.get("stage", "")

    if previous_stage == "guess":
        if is_yes_response(child_response):
            rounds_completed = int(game_state.get("rounds_completed", 0)) + 1

            game_state["rounds_completed"] = rounds_completed
            game_state["stage"] = "round_choice"
            game_state["last_response_mode"] = "round_choice"
            game_state["game_complete"] = False
            return

        possible_guess = game_state.get("possible_guess")

        if is_no_response(child_response):
            if possible_guess:
                game_state.setdefault("rejected_guesses", []).append(possible_guess)

            game_state["possible_guess"] = None
            game_state["skip_guess_once"] = True
            game_state["guess_cooldown_questions"] = 3

        elif event_type == "no_response":
            # Do not treat silence or a missed answer as "no."
            # The child may have said yes softly, taken time, or been unclear.
            # Move back to clue questions before guessing again.
            game_state["possible_guess"] = None
            game_state["skip_guess_once"] = True
            game_state["guess_cooldown_questions"] = 3

    clear_response = (
        event_type == "child_answer" and
        is_clear_toy_trivia_game_response(child_response, previous_response_mode)
    )

    if clear_response:
        game_state["comfortable_answer_count"] = int(game_state.get("comfortable_answer_count", 0)) + 1
        game_state["comfortable_streak"] = int(game_state.get("comfortable_streak", 0)) + 1
        game_state["unclear_streak"] = 0

        word_count = len(re.findall(r"[A-Za-z']+", child_response))
        game_state.setdefault("clear_answer_word_counts", []).append(word_count)
        game_state["clear_answer_word_counts"] = game_state["clear_answer_word_counts"][-8:]

        last_question = game_state.get("last_question")

        if last_question and previous_stage != "guess":
            game_state.setdefault("known_clues", []).append({
                "question": last_question,
                "answer": child_response[:100]
            })

        current_index = int(game_state.get("response_level_index", TOY_TRIVIA_START_LEVEL_INDEX))
        comfortable_count = int(game_state.get("comfortable_answer_count", 0))
        comfortable_streak = int(game_state.get("comfortable_streak", 0))

        # Move up gently but noticeably when the child is giving usable clues.
        # This lets Toy Store Worker ask for more open hints once the child seems comfortable.
        if comfortable_streak >= 2 and current_index < len(TOY_TRIVIA_LEVELS) - 1:
            current_index += 1
            game_state["comfortable_streak"] = 0

        if word_count >= 2 and comfortable_count >= 2 and current_index < 3:
            current_index = 3

        if word_count >= 3 and comfortable_count >= 3 and current_index < 4:
            current_index = 4

        game_state["response_level_index"] = min(current_index, len(TOY_TRIVIA_LEVELS) - 1)

    else:
        game_state["unclear_or_silent_count"] = int(game_state.get("unclear_or_silent_count", 0)) + 1
        game_state["unclear_streak"] = int(game_state.get("unclear_streak", 0)) + 1
        game_state["comfortable_streak"] = 0

        if game_state["unclear_streak"] >= 2:
            current_index = int(game_state.get("response_level_index", TOY_TRIVIA_START_LEVEL_INDEX))
            game_state["response_level_index"] = max(current_index - 1, 0)
            game_state["unclear_streak"] = 0


def make_toy_trivia_game_audio_response(
    message,
    stage,
    response_mode,
    expects_response,
    game_complete,
    game_state,
    history,
    event_type="server_response",
    child_response="",
    next_event=None,
    pause_before_next_ms=None,
    next_url=None,
    redirect_after_ms=None,
    session_done=False
):
    message = calm_toy_trivia_game_line(message, game_complete=game_complete)

    history.append({
        "event_type": event_type,
        "child_response": child_response,
        "star": message,
        "stage": stage,
        "response_mode": response_mode,
        "game_complete": game_complete,
        "session_done": session_done
    })

    game_state["stage"] = stage
    game_state["last_response_mode"] = response_mode
    game_state["game_complete"] = game_complete

    session["toy_trivia_game_history"] = history[-20:]
    session["toy_trivia_game_state"] = game_state
    session.modified = True

    audio_bytes = generate_toy_trivia_voice_elevenlabs(message, game_complete=game_complete)
    audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

    payload = {
        "success": True,
        "message": message,
        "audio": f"data:audio/mpeg;base64,{audio_base64}",
        "stage": stage,
        "expects_response": expects_response,
        "response_mode": response_mode,
        "game_complete": game_complete,
        "session_done": session_done,
        "offer_next_game": bool(
            int(game_state.get("rounds_completed", 0) or 0) >= TOY_TRIVIA_GAME_NEXT_GAME_OFFER_ROUND
        ),
        "game_state": game_state
    }

    if next_event:
        payload["next_event"] = next_event

    if pause_before_next_ms is not None:
        payload["pause_before_next_ms"] = pause_before_next_ms

    if next_url:
        payload["next_url"] = next_url

    if redirect_after_ms is not None:
        payload["redirect_after_ms"] = redirect_after_ms

    return jsonify(payload)


TOY_TRIVIA_GAME_MAX_ROUNDS = 3
TOY_TRIVIA_GAME_SOFT_REVEAL_QUESTION_LIMIT = 18
TOY_TRIVIA_GAME_NEXT_GAME_OFFER_ROUND = 3


TOY_TRIVIA_COMMON_PLAYTHINGS = {
    "ball": {"ball", "basketball", "soccer ball", "bouncy ball"},
    "blocks": {"blocks", "block", "building blocks", "lego", "legos"},
    "toy car": {"toy car", "car", "race car"},
    "toy truck": {"toy truck", "truck"},
    "train": {"train", "toy train", "train set"},
    "doll": {"doll", "baby doll", "barbie"},
    "teddy bear": {"teddy bear", "teddy", "bear", "stuffed bear"},
    "stuffed animal": {"stuffed animal", "plush", "plushie", "stuffie"},
    "robot": {"robot", "robot toy"},
    "puzzle": {"puzzle", "jigsaw", "jigsaw puzzle"},
    "kite": {"kite"},
    "crayons": {"crayons", "crayon"},
    "jump rope": {"jump rope"},
    "rubber duck": {"rubber duck", "duck"},
    "dinosaur toy": {"dinosaur", "dinosaur toy"},
    "yo-yo": {"yo-yo", "yoyo"},
    "action figure": {"action figure", "figure", "superhero"},
    "board game": {"board game", "game"},
    "play dough": {"play dough", "playdough"},
    "toy phone": {"toy phone", "phone"},
    "drum": {"drum", "toy drum"}
}

def get_child_revealed_plaything(text):
    lowered = normalize_child_text(text).lower()

    if not lowered:
        return None

    cleaned = re.sub(r"[^a-z' -]", " ", lowered)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    words = set(re.findall(r"[a-z']+", cleaned))

    if not words:
        return None

    direct_reveal_phrases = [
        "it's",
        "it is",
        "my toy is",
        "the toy is",
        "my thing is",
        "the thing is",
        "i picked",
        "i chose",
        "i was thinking of",
        "i am thinking of",
        "i'm thinking of",
        "it was",
        "it's a",
        "it is a"
    ]

    has_direct_reveal = any(phrase in cleaned for phrase in direct_reveal_phrases)

    # Also allow short answers like "teddy bear" or "a puzzle".
    can_treat_as_reveal = has_direct_reveal or len(words) <= 6

    if not can_treat_as_reveal:
        return None

    for display, aliases in TOY_TRIVIA_COMMON_PLAYTHINGS.items():
        for alias in aliases:
            alias_clean = normalize_child_text(alias).lower()
            alias_words = set(re.findall(r"[a-z']+", alias_clean))

            if not alias_clean:
                continue

            if " " in alias_clean and alias_clean in cleaned:
                return display

            if alias_clean in words:
                return display

            if alias_words and alias_words.issubset(words):
                return display

    return None


def get_toy_trivia_play_again_question(rounds_completed, child_name):
    rounds_completed = int(rounds_completed or 0)
    offer_next_game = rounds_completed >= TOY_TRIVIA_GAME_NEXT_GAME_OFFER_ROUND

    if offer_next_game:
        return (
            "Do you want to play this game again, try a slightly different toy game, "
            "or stop here? You can tell me what you want."
        ), True, False

    return (
        f"Do you want to play another round, {child_name}?"
    ), True, False


@app.route("/api/toy-trivia-game/message", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("30 per minute")
def toy_trivia_game_message():
    data = request.get_json(silent=True) or {}

    event_type = normalize_child_text(data.get("event_type", "intro"))
    child_response = normalize_child_text(data.get("child_response", ""))
    previous_response_mode = normalize_child_text(data.get("response_mode", "none"))

    allowed_events = {
        "intro",
        "restart",
        "first_question",
        "round_choice_prompt",
        "child_answer",
        "no_response"
    }

    if event_type not in allowed_events:
        return jsonify({"success": False, "error": "Invalid event_type"}), 400

    child_name = session.get("child_name", "there")
    child_name = re.sub(r"[^A-Za-z' -]", "", str(child_name)).strip() or "there"

    if event_type in {"intro", "restart"}:
        session.pop("toy_trivia_game_history", None)
        session.pop("toy_trivia_game_state", None)
        history = []
        game_state = get_toy_trivia_game_default_state(rounds_completed=0)
        child_response = ""
        previous_response_mode = "none"
    else:
        history = session.get("toy_trivia_game_history", [])
        game_state = session.get(
            "toy_trivia_game_state",
            get_toy_trivia_game_default_state()
        )

    if event_type in {"intro", "restart"}:
        message = (
            "Hi, I'm the toy store worker. We're going to play Toy Trivia. "
            "Think of a toy, puzzle, game, or anything you like to play with. "
            "It can be something in your room, your toy box, or anywhere else in your house. "
            "Take a second. I'll ask little questions to guess it."
        )

        try:
            return make_toy_trivia_game_audio_response(
                message=message,
                stage="intro",
                response_mode="none",
                expects_response=False,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type=event_type,
                child_response="",
                next_event="first_question",
                pause_before_next_ms=2200
            )

        except Exception as e:
            print("Toy Trivia intro TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate Toy Store Worker intro"
            }), 500

    if event_type == "round_choice_prompt":
        rounds_completed = int(game_state.get("rounds_completed", 0))
        message, expects_response, session_done = get_toy_trivia_play_again_question(
            rounds_completed,
            child_name
        )

        try:
            return make_toy_trivia_game_audio_response(
                message=message,
                stage="round_choice" if expects_response else "session_done",
                response_mode="round_choice" if expects_response else "none",
                expects_response=expects_response,
                game_complete=True,
                game_state=game_state,
                history=history,
                event_type="round_choice_prompt",
                child_response=child_response,
                session_done=session_done
            )

        except Exception as e:
            print("Toy Trivia round choice prompt TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate round choice prompt"
            }), 500

    # Handle child response to end-of-round choice.
    # This now mirrors the Mystery Animal ending pattern:
    # after enough rounds, the child can choose this game again, a different toy game, or stopping.
    if previous_response_mode == "round_choice" and event_type in {"child_answer", "no_response"}:
        rounds_completed = int(game_state.get("rounds_completed", 0))
        offer_next_game = rounds_completed >= TOY_TRIVIA_GAME_NEXT_GAME_OFFER_ROUND

        if event_type == "no_response":
            choice = "unclear"
        else:
            choice = classify_toy_trivia_game_choice_response(
                child_response,
                offer_next_game=offer_next_game
            )

        if choice == "same_game":
            new_game_state = get_toy_trivia_game_default_state(
                rounds_completed=rounds_completed
            )

            if offer_next_game:
                message = (
                    "Okay. Let's play this game again. "
                    "Think of a new toy, puzzle, game, stuffed animal, or play thing."
                )
            else:
                message = (
                    "Okay. Let's play another round. "
                    "Think of a new toy, puzzle, game, stuffed animal, or play thing."
                )

            try:
                return make_toy_trivia_game_audio_response(
                    message=message,
                    stage="intro",
                    response_mode="none",
                    expects_response=False,
                    game_complete=False,
                    game_state=new_game_state,
                    history=[],
                    event_type="replay",
                    child_response=child_response,
                    next_event="first_question",
                    pause_before_next_ms=1800
                )

            except Exception as e:
                print("Toy Trivia replay TTS error:", repr(e))
                return jsonify({
                    "success": False,
                    "error": "Could not generate Toy Store Worker replay intro"
                }), 500

        if choice == "next_game" and offer_next_game:
            unlock_toy_trivia_game_next_game_for_user()

            next_url = url_for("open_activity", activity_id=TOY_TRIVIA_NEXT_ACTIVITY_ID)

            message = (
                "Okay, I'll call you right back so we can play the next toy game. "
                "See you soon."
            )

            try:
                return make_toy_trivia_game_audio_response(
                    message=message,
                    stage="transition_next_game",
                    response_mode="none",
                    expects_response=False,
                    game_complete=False,
                    game_state=game_state,
                    history=history,
                    event_type="next_game",
                    child_response=child_response,
                    next_url=next_url,
                    redirect_after_ms=1700,
                    session_done=True
                )

            except Exception as e:
                print("Toy Trivia next-game TTS error:", repr(e))
                return jsonify({
                    "success": False,
                    "error": "Could not move to the next game"
                }), 500

        if choice == "stop":
            message = (
                "Okay. We can stop here. "
                "Thanks for playing Toy Trivia with me."
            )

            try:
                return make_toy_trivia_game_audio_response(
                    message=message,
                    stage="session_done",
                    response_mode="none",
                    expects_response=False,
                    game_complete=False,
                    game_state=game_state,
                    history=history,
                    event_type="stop",
                    child_response=child_response,
                    session_done=True
                )

            except Exception as e:
                print("Toy Trivia stop TTS error:", repr(e))
                return jsonify({
                    "success": False,
                    "error": "Could not end the game"
                }), 500

        if offer_next_game:
            message = (
                "That's okay. We can play this game again, try a slightly different toy game, "
                "or stop here. You can tell me what you want."
            )
        else:
            message = (
                f"That's okay. Do you want to play another round, {child_name}?"
            )

        try:
            return make_toy_trivia_game_audio_response(
                message=message,
                stage="round_choice",
                response_mode="round_choice",
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type="choice_clarification",
                child_response=child_response
            )

        except Exception as e:
            print("Toy Trivia choice clarification TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate Toy Store Worker choice response"
            }), 500

    if event_type == "first_question":
        level = get_toy_trivia_game_level(game_state)
        fallback = get_fallback_toy_trivia_game_question(
            level,
            game_state,
            event_type="first_question"
        )

        question_text = fallback["question_text"]
        message = f"Okay. {question_text}"

        game_state["stage"] = fallback["stage"]
        game_state["last_response_mode"] = fallback["response_mode"]
        game_state["game_complete"] = False
        game_state["last_question"] = normalize_child_text(question_text)

        game_state.setdefault("question_history", []).append({
            "question": normalize_child_text(question_text),
            "stage": fallback["stage"],
            "response_mode": fallback["response_mode"]
        })

        game_state["questions_asked"] = int(game_state.get("questions_asked", 0)) + 1

        try:
            return make_toy_trivia_game_audio_response(
                message=message,
                stage=fallback["stage"],
                response_mode=fallback["response_mode"],
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type="first_question",
                child_response=""
            )

        except Exception as e:
            print("Toy Trivia first question TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate Toy Store Worker first question"
            }), 500

    # If child says "it's a teddy bear", do NOT immediately end.
    # Treat it as the worker's guess and confirm first.
    revealed_plaything = get_child_revealed_plaything(child_response)

    if event_type == "child_answer" and revealed_plaything and previous_response_mode != "guess_confirmation":
        game_state["stage"] = "guess"
        game_state["last_response_mode"] = "guess_confirmation"
        game_state["possible_guess"] = revealed_plaything

        message = f"That gives me a guess. Is it a {revealed_plaything}?"

        try:
            return make_toy_trivia_game_audio_response(
                message=message,
                stage="guess",
                response_mode="guess_confirmation",
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type="direct_reveal_as_guess",
                child_response=child_response
            )

        except Exception as e:
            print("Toy Trivia direct reveal confirmation TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate Toy Store Worker response"
            }), 500

    apply_toy_trivia_game_comfort_update(
        game_state,
        event_type,
        child_response,
        previous_response_mode
    )

    # If the worker guessed and the child confirmed yes, end the round in the same
    # response, like Mystery Animal. Do NOT repeat the guessed toy name here:
    # if the child just said "stuffed animal," repeating it again sounds unnatural.
    if game_state.get("stage") == "round_choice":
        import random

        rounds_completed = int(game_state.get("rounds_completed", 0))

        success_options = [
            "Yes! I got it.",
            "Aha, I got it!",
            "Yes, that was it!",
            "I found it!",
            "Okay, I got it.",
            "There it is. I found it."
        ]

        success_line = random.choice(success_options)
        play_again_line, expects_response, session_done = get_toy_trivia_play_again_question(
            rounds_completed,
            child_name
        )

        message = f"{success_line} {play_again_line}"

        try:
            return make_toy_trivia_game_audio_response(
                message=message,
                stage="round_choice" if expects_response else "session_done",
                response_mode="round_choice" if expects_response else "none",
                expects_response=expects_response,
                game_complete=True,
                game_state=game_state,
                history=history,
                event_type="correct_guess_confirmed",
                child_response=child_response,
                session_done=session_done
            )

        except Exception as e:
            print("Toy Trivia correct guess TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate Toy Store Worker round-choice response"
            }), 500

    if (
        not bool(game_state.get("soft_reveal_used", False))
        and int(game_state.get("questions_asked", 0)) >= TOY_TRIVIA_GAME_SOFT_REVEAL_QUESTION_LIMIT
        and game_state.get("stage") != "round_choice"
    ):
        game_state["soft_reveal_used"] = True

        message = (
            "Hmm, this is a tricky one. "
            "You can tell me the toy if you want."
        )

        try:
            return make_toy_trivia_game_audio_response(
                message=message,
                stage="soft_reveal",
                response_mode="open_hint",
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type="soft_reveal",
                child_response=child_response
            )

        except Exception as e:
            print("Toy Trivia soft reveal TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate toy worker soft reveal"
            }), 500

    level = get_toy_trivia_game_level(game_state)
    fallback = get_fallback_toy_trivia_game_question(level, game_state, event_type)

    known_clues = game_state.get("known_clues", [])
    questions_asked = int(game_state.get("questions_asked", 0))
    guess_cooldown_questions = int(game_state.get("guess_cooldown_questions", 0))
    comfortable_count = int(game_state.get("comfortable_answer_count", 0))
    last_answer_word_count = len(re.findall(r"[A-Za-z']+", child_response))

    total_clue_words = sum(
        len(re.findall(r"[A-Za-z']+", str(item.get("answer", ""))))
        for item in known_clues
        if isinstance(item, dict)
    )

    open_hint_questions_asked = int(game_state.get("open_hint_questions_asked", 0))

    should_guess = (
        not bool(game_state.get("skip_guess_once", False))
        and guess_cooldown_questions <= 0
        and (
            (len(known_clues) >= 3 and questions_asked >= 3)
            or (len(known_clues) >= 2 and total_clue_words >= 5)
            or (previous_response_mode == "open_hint" and len(known_clues) >= 2 and last_answer_word_count >= 2)
            or (open_hint_questions_asked >= 1 and len(known_clues) >= 2 and last_answer_word_count >= 1)
            or questions_asked >= 5
        )
    )

    should_invite_open_hint = (
        comfortable_count >= 3
        and int(game_state.get("response_level_index", TOY_TRIVIA_START_LEVEL_INDEX)) >= 3
        and not should_guess
    )

    system_prompt = f"""
You are the Toy Store Worker, a warm cartoon toy store worker playing Toy Trivia.

The child is thinking of a toy, puzzle, game, stuffed animal, or anything they like to play with.
You ask gentle questions to guess it.

Core goal:
Make the child feel safe while giving them a real reason to communicate.

Hard rules:
- Never mention selective mutism, anxiety, therapy, treatment, exposure, stages, progress, confidence, or bravery.
- Never pressure the child to speak.
- Never say "use your words."
- Never sound disappointed.
- Never overpraise.
- Never make the child feel evaluated.
- Keep attention on the toy game, not on the child.
- Ask only one question at a time.
- Do not repeat previous questions or repeat the same question family inside one round.
- Use the clues already given as hard constraints. If the child says more than four legs, never guess a four-legged animal.
- Keep the line to 1-2 short sentences.
- Address the child by name only occasionally.
- If you use the child's name, put it at the END of the sentence, not the beginning.

Acknowledging child responses:
- When the child gives a clear answer or hint, acknowledge the clue before asking the next question.
- Do not praise the act of speaking.
- Do not say "good job saying that" or "great talking."
- Focus on the clue, not the performance.

Direct toy reveal:
- If the child names a toy, do not end the round automatically.
- Confirm it as a guess.
- Example: if the child says "it's a teddy bear", ask "Is it a teddy bear?"

Silence and no-response handling:
- If the child does not answer, do not say "let me ask it in a simpler way."
- Do not imply the previous question was too hard.
- Do not repeat the same question.
- Do not say "I couldn't hear you."
- Gently move on with a different low-pressure question.

Voice style:
- During clue questions, sound warm, gentle, steady, and quietly playful.
- During a correct guess, it is okay to sound a little excited and playful.
- Use mostly periods for normal questions.
- Use at most one exclamation mark in a correct-guess celebration.
- Avoid sounding hyper, surprised, loud, or teacher-like.
- Do not say "Wow", "Amazing", "Awesome", or "Ooo".

Required response level:
Stage: {level["stage"]}
Response mode: {level["response_mode"]}
Description: {level["description"]}
Examples: {level["examples"]}

Guessing rule:
- should_guess is currently {should_guess}.
- If should_guess is false, do not guess yet.
- If should_guess is true, make one calm guess now.
- When guessing, ask it as a yes/no question, like "Is it a teddy bear?"

Output JSON only:
{{
  "message": "Toy Store Worker's spoken line",
  "stage": "intro | yes_no | forced_choice | one_word | short_phrase | open_hint | guess | support | complete",
  "expects_response": true,
  "response_mode": "none | yes_no | choice | one_word | short_phrase | open_hint | guess_confirmation",
  "is_question": true,
  "question_text": "the exact question asked, or null",
  "game_complete": false,
  "possible_guess": null
}}
"""

    user_prompt = f"""
Child name:
{child_name}

Current game state:
{game_state}

Recent history:
{history[-12:]}

Known clues:
{known_clues}

Question history:
{game_state.get("question_history", [])}

Rejected guesses:
{game_state.get("rejected_guesses", [])}

New event:
event_type: {event_type}
child_response: {child_response}
previous_response_mode: {previous_response_mode}

If this is the first_question event:
- Ask one simple first question only.
- Do not reintroduce the game.

If event_type is child_answer and the child gave a clear answer:
- Acknowledge the clue first.
- Do not praise speaking itself.
- Then ask one useful next question or make one guess if should_guess is true.

If event_type is no_response:
- Start with a calm accepting phrase like "That's okay" or "No problem."
- Do not repeat the last question.
- Ask a different low-pressure question.

Generate the next Toy Store Worker line now.
"""

    try:
        text_response = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )

        raw = text_response.output_text.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()

        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {
                "message": fallback["message"],
                "stage": fallback["stage"],
                "expects_response": True,
                "response_mode": fallback["response_mode"],
                "is_question": True,
                "question_text": fallback["question_text"],
                "game_complete": False,
                "possible_guess": None
            }

        stage = normalize_child_text(parsed.get("stage", fallback["stage"]))
        response_mode = normalize_child_text(parsed.get("response_mode", fallback["response_mode"]))
        question_text = parsed.get("question_text")
        possible_guess = parsed.get("possible_guess")

        if stage == "guess" and not should_guess:
            parsed = {
                "message": fallback["message"],
                "stage": fallback["stage"],
                "expects_response": True,
                "response_mode": fallback["response_mode"],
                "is_question": True,
                "question_text": fallback["question_text"],
                "game_complete": False,
                "possible_guess": None
            }

            stage = parsed["stage"]
            response_mode = parsed["response_mode"]
            question_text = parsed["question_text"]
            possible_guess = None

        if should_guess and stage != "guess":
            fallback_guess = pick_fallback_toy_guess(game_state)

            parsed = {
                "message": f"I think I have a guess. Is it a {fallback_guess}?",
                "stage": "guess",
                "expects_response": True,
                "response_mode": "guess_confirmation",
                "is_question": True,
                "question_text": f"Is it a {fallback_guess}?",
                "game_complete": False,
                "possible_guess": fallback_guess
            }

            stage = "guess"
            response_mode = "guess_confirmation"
            question_text = parsed["question_text"]
            possible_guess = fallback_guess

        if should_invite_open_hint and not should_guess and stage != "guess":
            lowered_question = normalize_child_text(question_text or parsed.get("message", "")).lower()
            asks_for_hint = any(phrase in lowered_question for phrase in [
                "hint",
                "clue",
                "what should i know",
                "what is one"
            ])

            if not asks_for_hint:
                question_text = choose_non_repeating_question(TOY_TRIVIA_LEVELS[-1], game_state)
                parsed["message"] = question_text
                parsed["stage"] = "open_hint"
                parsed["response_mode"] = "open_hint"
                parsed["is_question"] = True
                parsed["question_text"] = question_text
                stage = "open_hint"
                response_mode = "open_hint"

        if stage != "guess":
            if stage == "open_hint" and should_invite_open_hint:
                response_mode = "open_hint"
            else:
                stage = level["stage"]
                response_mode = level["response_mode"]
        else:
            response_mode = "guess_confirmation"

        game_complete = False
        message = parsed.get("message", "").strip().replace('"', "")

        if not message:
            message = fallback["message"]

        message = sanitize_short_line(
            message,
            fallback=fallback["message"],
            max_len=220
        )

        message = calm_toy_trivia_game_line(message, game_complete=game_complete)

        message = maybe_add_toy_trivia_game_acknowledgment(
            message=message,
            event_type=event_type,
            child_response=child_response,
            previous_response_mode=previous_response_mode,
            game_state=game_state
        )

        message = calm_toy_trivia_game_line(message, game_complete=game_complete)

        if not question_text and parsed.get("is_question"):
            question_text = message

        if stage == "guess":
            response_mode = "guess_confirmation"

            if possible_guess:
                game_state["possible_guess"] = normalize_child_text(possible_guess)
            else:
                guess_match = re.search(r"is it (?:a |an )?([A-Za-z -]+)\??", message.lower())

                if guess_match:
                    game_state["possible_guess"] = guess_match.group(1).strip()

        game_state["stage"] = stage
        game_state["last_response_mode"] = response_mode
        game_state["game_complete"] = False

        if stage != "guess":
            if game_state.get("skip_guess_once"):
                game_state["skip_guess_once"] = False

            if int(game_state.get("guess_cooldown_questions", 0)) > 0:
                game_state["guess_cooldown_questions"] = max(
                    0,
                    int(game_state.get("guess_cooldown_questions", 0)) - 1
                )

        if parsed.get("is_question") and question_text:
            game_state["last_question"] = normalize_child_text(question_text)
            game_state.setdefault("question_history", []).append({
                "question": normalize_child_text(question_text),
                "stage": stage,
                "response_mode": response_mode
            })

            game_state["questions_asked"] = int(game_state.get("questions_asked", 0)) + 1

            if stage == "open_hint" or response_mode == "open_hint":
                game_state["open_hint_questions_asked"] = int(
                    game_state.get("open_hint_questions_asked", 0)
                ) + 1

        history.append({
            "event_type": event_type,
            "child_response": child_response,
            "worker": message,
            "stage": game_state["stage"],
            "response_mode": response_mode,
            "game_complete": False
        })

        session["toy_trivia_game_history"] = history[-20:]
        session["toy_trivia_game_state"] = game_state
        session.modified = True

        audio_bytes = generate_toy_trivia_voice_elevenlabs(message)
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

        return jsonify({
            "success": True,
            "message": message,
            "audio": f"data:audio/mpeg;base64,{audio_base64}",
            "stage": game_state["stage"],
            "expects_response": bool(parsed.get("expects_response", True)),
            "response_mode": response_mode,
            "game_complete": False,
            "session_done": False,
            "game_state": game_state
        })

    except Exception as e:
        print("Toy Trivia AI error:", repr(e))
        return jsonify({
            "success": False,
            "error": "Could not generate Toy Store Worker response"
        }), 500


@app.route("/api/toy-trivia-game/transcribe", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("30 per minute")
def toy_trivia_game_transcribe():
    if "audio" not in request.files:
        return jsonify({
            "success": False,
            "error": "Missing audio"
        }), 400

    audio_file = request.files["audio"]

    try:
        import io

        audio_bytes = audio_file.read()

        if not audio_bytes:
            return jsonify({
                "success": False,
                "error": "Empty audio file"
            }), 400

        file_obj = io.BytesIO(audio_bytes)
        file_obj.name = "toy-trivia-response.webm"

        transcript = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=file_obj
        )

        text = transcript.text.strip()

        print("TOY TRIVIA TRANSCRIPT:", text)

        return jsonify({
            "success": True,
            "text": text
        })

    except Exception as e:
        print("Toy Trivia transcription error:", repr(e))
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    
# =========================
# Book Guessing Game — Librarian/library version of Mystery Animal
# Replace the old Book Guessing Game block with this complete block.
# =========================

def generate_book_guessing_voice_elevenlabs(text, game_complete=False, thinking=False):
    voice_id = os.getenv("LIBRARIAN_VOICE_ID")

    if not voice_id:
        voice_id = os.getenv("ELEVENLABS_VOICE_ID", "piI8Kku0DcvcL6TTSeQt")

    if game_complete:
        voice_settings = {
            "stability": 0.84,
            "similarity_boost": 0.90,
            "style": 0.25,
            "use_speaker_boost": False
        }
    elif thinking:
        voice_settings = {
            "stability": 0.98,
            "similarity_boost": 0.88,
            "style": 0.02,
            "use_speaker_boost": False
        }
    else:
        voice_settings = {
            "stability": 0.94,
            "similarity_boost": 0.90,
            "style": 0.06,
            "use_speaker_boost": False
        }

    response = eleven_client.text_to_speech.convert(
        voice_id=voice_id,
        text=text,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
        voice_settings=voice_settings
    )

    return b"".join(response)


@app.route("/api/book-guessing-game/thinking-audio", methods=["GET"])
@csrf.exempt
@login_required
@limiter.limit("50 per minute")
def book_guessing_game_thinking_audio():
    import hashlib
    import random

    thinking_lines = [
        "Hmm."
    ]

    avoid_raw = request.args.get("avoid", "")
    avoid_lines = {
        re.sub(r"\s+", " ", item).strip().lower()
        for item in avoid_raw.split("|")
        if item.strip()
    }

    fresh_lines = [
        line for line in thinking_lines
        if re.sub(r"\s+", " ", line).strip().lower() not in avoid_lines
    ]

    if not fresh_lines:
        fresh_lines = thinking_lines

    line = random.choice(fresh_lines)

    cache_dir = os.path.join(BASE_DIR, "static", "audio", "book_guessing_thinking")
    os.makedirs(cache_dir, exist_ok=True)

    voice_id = os.getenv("LIBRARIAN_VOICE_ID") or os.getenv("ELEVENLABS_VOICE_ID", "piI8Kku0DcvcL6TTSeQt")
    cache_key = f"book-guessing-thinking-v2:{voice_id}:{line}"
    filename = hashlib.md5(cache_key.encode("utf-8")).hexdigest() + ".mp3"
    filepath = os.path.join(cache_dir, filename)

    try:
        if not os.path.exists(filepath):
            audio_bytes = generate_book_guessing_voice_elevenlabs(line, thinking=True)

            with open(filepath, "wb") as f:
                f.write(audio_bytes)

        return jsonify({
            "success": True,
            "line": line,
            "audio_url": url_for(
                "static",
                filename=f"audio/book_guessing_thinking/{filename}"
            )
        })

    except Exception as e:
        print("Book Guessing Game thinking audio error:", repr(e))
        return jsonify({
            "success": False,
            "error": "Could not generate thinking audio"
        }), 500


BOOK_GUESSING_LEVELS = [
    {
        "stage": "yes_no",
        "response_mode": "yes_no",
        "description": "Ask a concrete yes/no book question.",
        "examples": [
            "Does the book have pictures?",
            "Is there an animal in the story?",
            "Is the story funny?"
        ],
        "fallback_questions": [
            "Does the book have pictures?",
            "Is there an animal in the story?",
            "Is there a kid in the story?",
            "Is the story funny?",
            "Is the cover bright?",
            "Does something magical happen?",
            "Is it a chapter book?",
            "Is the main character a person?",
            "Is the book silly?",
            "Is the book about an adventure?",
            "Does the title have more than one word?",
            "Would I find it in the children's section?"
        ]
    },
    {
        "stage": "forced_choice",
        "response_mode": "choice",
        "description": "Ask a two-option book question.",
        "examples": [
            "Is it a picture book or a chapter book?",
            "Is it funny or exciting?",
            "Is the main character a person or an animal?"
        ],
        "fallback_questions": [
            "Is it a picture book or a chapter book?",
            "Is it funny or exciting?",
            "Is it short or long?",
            "Is the cover dark or bright?",
            "Is the main character a person or an animal?",
            "Is it more silly or adventurous?",
            "Is it realistic or magical?",
            "Is the title short or long?"
        ]
    },
    {
        "stage": "one_word",
        "response_mode": "one_word",
        "description": "Ask for one simple word.",
        "examples": [
            "What color is the cover?",
            "Who is in the book?",
            "What is one thing in the story?"
        ],
        "fallback_questions": [
            "What color is the cover?",
            "Who is in the book?",
            "What is one thing in the story?",
            "Can you give me one book clue?",
            "What is one word from the title?"
        ]
    },
    {
        "stage": "short_phrase",
        "response_mode": "short_phrase",
        "description": "Ask for a tiny phrase.",
        "examples": [
            "What happens in the story?",
            "What does the cover look like?"
        ],
        "fallback_questions": [
            "What happens in the story?",
            "What does the cover look like?",
            "Tell me one tiny book clue.",
            "What part of the story should I think about?",
            "What kind of character is in it?"
        ]
    },
    {
        "stage": "open_hint",
        "response_mode": "open_hint",
        "description": "Ask for any small hint the child wants to give.",
        "examples": [
            "Can you give me a tiny hint?",
            "What is one fun thing about this book?",
            "What is your favorite thing about this book?"
        ],
        "fallback_questions": [
            "Can you give me a tiny hint?",
            "What is one fun thing about this book?",
            "What is your favorite thing about this book?",
            "What should I know about the book?"
        ]
    }
]
BOOK_GUESSING_START_LEVEL_INDEX = 2
BOOK_GUESSING_NEXT_GAME_OFFER_ROUND = 3
BOOK_GUESSING_NEXT_ACTIVITY_ID = None
BOOK_GUESSING_SOFT_REVEAL_QUESTION_LIMIT = 15

BOOK_GUESSING_COMMON_BOOKS = {
    "book", "story", "chapter book", "picture book", "novel",
    "harry potter", "dog man", "cat in the hat", "green eggs and ham",
    "wimpy kid", "diary of a wimpy kid", "hungry caterpillar",
    "where the wild things are", "charlotte's web", "matilda",
    "narnia", "the hobbit", "wonder", "pigeon", "elephant and piggie"
}


def get_book_guessing_game_default_state(rounds_completed=0):
    return {
        "stage": "intro",
        "response_level_index": BOOK_GUESSING_START_LEVEL_INDEX,
        "questions_asked": 0,
        "comfortable_answer_count": 0,
        "unclear_or_silent_count": 0,
        "comfortable_streak": 0,
        "unclear_streak": 0,
        "question_history": [],
        "known_clues": [],
        "rejected_guesses": [],
        "possible_guess": None,
        "last_question": None,
        "last_response_mode": "none",
        "game_complete": False,
        "rounds_completed": rounds_completed_int,
        "skip_guess_once": False,
        "guess_cooldown_questions": 0,
        "last_acknowledgment_index": -1,
        "clear_answer_word_counts": [],
        "recent_question_families": [],
        "asked_question_families": [],
        "recent_guesses": [],
        "recent_acknowledgments": [],
        "open_hint_questions_asked": 0,
        "soft_reveal_used": False
    }


def normalize_child_text(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def get_child_revealed_book(text):
    lowered = normalize_child_text(text).lower()

    if not lowered:
        return None

    cleaned = re.sub(r"[^a-z' -]", " ", lowered)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    words = set(re.findall(r"[a-z']+", cleaned))

    if not words:
        return None

    direct_reveal_phrases = [
        "it's",
        "it is",
        "my book is",
        "the book is",
        "i picked",
        "i chose",
        "i was thinking of",
        "i am thinking of",
        "it was",
        "it's a",
        "it is a"
    ]

    has_direct_reveal = any(phrase in cleaned for phrase in direct_reveal_phrases)

    if has_direct_reveal:
        for book in BOOK_GUESSING_COMMON_BOOKS:
            if book in words:
                return book

    # Also handle direct short answers like "ball", "a book car", or "teddy bear".
    # In Book Guessing Game, if the child names a familiar book directly,
    # Librarian should accept that instead of asking for more hints.
    if len(words) <= 4:
        for book in BOOK_GUESSING_COMMON_BOOKS:
            if book in words:
                return book

    return None


def is_yes_response(text):
    lowered = normalize_child_text(text).lower()
    words = set(re.findall(r"[a-z']+", lowered))

    return bool(words & {
        "yes", "yeah", "yep", "yup", "sure", "correct", "right"
    }) or lowered in {"yes", "yeah", "yep", "yup"}


def is_no_response(text):
    lowered = normalize_child_text(text).lower()
    words = set(re.findall(r"[a-z']+", lowered))

    return bool(words & {
        "no", "nope", "nah", "not"
    }) or lowered in {"no", "nope", "nah"}


def classify_book_guessing_game_choice_response(text, offer_next_game=False):
    lowered = normalize_child_text(text).lower()
    words = set(re.findall(r"[a-z']+", lowered))

    if not lowered:
        return "unclear"

    stop_words = {
        "stop", "done", "finish", "finished", "end", "quit", "leave",
        "dashboard", "no", "nope", "nah"
    }

    next_game_words = {
        "different", "new", "next", "other", "guessing"
    }

    same_game_words = {
        "again", "same", "replay", "more", "continue",
        "yes", "yeah", "yep", "yup", "sure",
        "okay", "ok", "alright", "fine", "good", "cool",
        "this"
    }

    if words & stop_words:
        return "stop"

    if offer_next_game and words & next_game_words:
        return "next_game"

    if words & same_game_words:
        return "same_game"

    same_game_phrases = [
        "play again",
        "play another round",
        "another round",
        "one more round",
        "this game",
        "same game",
        "let's play",
        "lets play",
        "let us play",
        "keep playing",
        "do it again",
        "try again"
    ]

    if any(phrase in lowered for phrase in same_game_phrases):
        return "same_game"

    if offer_next_game:
        next_game_phrases = [
            "different game",
            "next game",
            "new game",
            "other game",
            "different version",
            "slightly different",
            "guessing game"
        ]

        if any(phrase in lowered for phrase in next_game_phrases):
            return "next_game"

    return "unclear"


def is_unclear_or_silent_response(text):
    lowered = normalize_child_text(text).lower()

    if not lowered:
        return True

    unclear_phrases = {
        "i don't know",
        "i dont know",
        "i do not know",
        "don't know",
        "dont know",
        "idk",
        "not sure",
        "not really sure",
        "i'm not sure",
        "im not sure",
        "maybe",
        "hmm",
        "uh",
        "um"
    }

    if lowered in unclear_phrases:
        return True

    usable_words = re.findall(r"[A-Za-z']+", lowered)

    if not usable_words:
        return True

    return False


def is_clear_book_guessing_game_response(text, response_mode):
    cleaned = normalize_child_text(text)

    if is_unclear_or_silent_response(cleaned):
        return False

    if response_mode == "yes_no":
        return is_yes_response(cleaned) or is_no_response(cleaned)

    if response_mode == "guess_confirmation":
        return is_yes_response(cleaned) or is_no_response(cleaned)

    if response_mode in {
        "choice",
        "one_word",
        "short_phrase",
        "open_hint",
        "round_choice"
    }:
        return len(re.findall(r"[A-Za-z']+", cleaned)) >= 1

    return len(re.findall(r"[A-Za-z']+", cleaned)) >= 1


def calm_book_guessing_game_line(text, game_complete=False):
    text = re.sub(r"\s+", " ", str(text or "")).strip()

    if not text:
        return "Hmm, let me ask a tiny question."

    replacements = {
        "Amazing": "Nice",
        "amazing": "nice",
        "Awesome": "Nice",
        "awesome": "nice",
        "Wow": "Hmm",
        "wow": "hmm",
        "Ooo": "Hmm",
        "ooo": "hmm",
        "Oh, let me try to ask it in a simpler way": "That's okay. I have another question",
        "Let me try to ask it in a simpler way": "That's okay. I have another question",
        "Let me ask it in a simpler way": "That's okay. I have another question",
        "Maybe that was too hard": "That's okay",
        "That might have been too hard": "That's okay",
        "I couldn't hear you": "That's okay",
        "I could not hear you": "That's okay",
        "Great job talking": "Thank you, that helps",
        "Good job talking": "Thank you, that helps",
        "Good job saying that": "Thank you, that helps",
        "Great job saying that": "Thank you, that helps",
        "Good job using your words": "Thank you, that helps"
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    if not game_complete:
        text = text.replace("!", ".")

    if text.count("!") > 1:
        first = text.find("!")
        text = text[:first + 1] + text[first + 1:].replace("!", ".")

    return text[:260].strip()


def maybe_add_book_guessing_game_acknowledgment(
    message,
    event_type,
    child_response,
    previous_response_mode,
    game_state
):
    import random

    if event_type != "child_answer":
        return message

    if previous_response_mode in {"none", "guess_confirmation", "round_choice"}:
        return message

    if not is_clear_book_guessing_game_response(child_response, previous_response_mode):
        return message

    lowered_message = normalize_child_text(message).lower()

    existing_acknowledgments = [
        "thank you",
        "thanks",
        "that helps",
        "that's helpful",
        "that is helpful",
        "that gives me",
        "good clue",
        "helpful clue",
        "useful clue",
        "useful to know",
        "that makes",
        "okay, that",
        "hmm, that",
        "interesting clue",
        "i can work with"
    ]

    if any(phrase in lowered_message for phrase in existing_acknowledgments):
        return message

    acknowledgments = [
        "That helps.",
        "Okay, that gives me a clue.",
        "That narrows it down.",
        "Interesting, that changes my guess.",
        "That gives me something to think about.",
        "Okay, I can work with that clue.",
        "That helps me picture it.",
        "Nice clue.",
        "Okay, I have a little more to go on.",
        "That makes the book easier to picture."
    ]

    recent = list(game_state.get("recent_acknowledgments", []))[-4:]
    fresh = [ack for ack in acknowledgments if ack not in recent]

    acknowledgment = random.choice(fresh or acknowledgments)
    game_state["recent_acknowledgments"] = (recent + [acknowledgment])[-4:]

    return f"{acknowledgment} {message}"


def get_book_guessing_game_level(game_state):
    index = int(game_state.get("response_level_index", BOOK_GUESSING_START_LEVEL_INDEX))
    index = max(0, min(index, len(BOOK_GUESSING_LEVELS) - 1))
    game_state["response_level_index"] = index
    return BOOK_GUESSING_LEVELS[index]


def get_question_history_set(game_state):
    question_history = game_state.get("question_history", [])

    return {
        normalize_child_text(item.get("question", "")).lower()
        for item in question_history
        if isinstance(item, dict)
    }


def choose_non_repeating_question(level, game_state):
    import random

    asked_questions = get_question_history_set(game_state)
    recent_families = list(game_state.get("recent_question_families", []))[-3:]
    questions = list(level.get("fallback_questions", []))

    fresh_questions = [
        question for question in questions
        if normalize_child_text(question).lower() not in asked_questions
    ]

    pool = fresh_questions or questions

    if not pool:
        return "What is one clue?"

    # Prefer a different type of question than the last few turns.
    family_filtered = [
        question for question in pool
        if get_question_family(question) not in recent_families[-2:]
    ]

    if family_filtered:
        pool = family_filtered

    question = random.choice(pool)
    family = get_question_family(question)

    updated_families = recent_families + [family]
    game_state["recent_question_families"] = updated_families[-4:]

    return question


def get_fallback_book_guessing_game_question(level, game_state=None, event_type="child_answer"):
    if game_state is None:
        game_state = {}

    stage = level["stage"]
    question_text = choose_non_repeating_question(level, game_state)

    if event_type == "no_response":
        calm_prefixes = [
            "That's okay.",
            "No problem.",
            "That's okay. We can try a different question.",
            "No worries."
        ]

        prefix_index = int(game_state.get("unclear_or_silent_count", 0)) % len(calm_prefixes)
        prefix = calm_prefixes[prefix_index]
        if prefix.endswith("question."):
            message = f"{prefix} {question_text}"
        else:
            message = f"{prefix} {question_text}"
    else:
        message = f"Hmm, {question_text[0].lower() + question_text[1:]}"

    return {
        "message": message,
        "stage": stage,
        "response_mode": level["response_mode"],
        "question_text": question_text
    }


def pick_fallback_book_guess(game_state):
    import random

    book_profiles = {
        "Harry Potter": ["magic", "wizard", "school", "castle", "wand", "hogwarts", "scar"],
        "Dog Man": ["dog", "police", "funny", "comic", "captain", "underpants"],
        "Diary of a Wimpy Kid": ["funny", "school", "kid", "diary", "cartoon", "middle"],
        "The Cat in the Hat": ["cat", "hat", "rhyme", "red", "silly", "dr seuss"],
        "Green Eggs and Ham": ["eggs", "ham", "green", "rhyme", "seuss", "food"],
        "The Very Hungry Caterpillar": ["caterpillar", "hungry", "food", "butterfly", "colors"],
        "Where the Wild Things Are": ["wild", "monster", "things", "boat", "island", "max"],
        "Goodnight Moon": ["moon", "bed", "sleep", "bunny", "night", "bedtime"],
        "Brown Bear, Brown Bear": ["bear", "brown", "animals", "colors"],
        "Charlotte's Web": ["pig", "spider", "farm", "web", "charlotte", "wilbur"],
        "Matilda": ["girl", "school", "books", "powers", "teacher"],
        "Wonder": ["school", "kid", "face", "kind", "friend"],
        "Magic Tree House": ["tree", "house", "magic", "siblings", "adventure"],
        "The Hobbit": ["dragon", "hobbit", "adventure", "ring", "dwarf"],
        "Narnia": ["lion", "wardrobe", "snow", "magic", "children"]
    }
    rejected = {
        str(item).lower().strip()
        for item in game_state.get("rejected_guesses", [])
        if item
    }

    recent = {
        str(item).lower().strip()
        for item in game_state.get("recent_guesses", [])[-4:]
        if item
    }

    possible_guess = str(game_state.get("possible_guess") or "").lower().strip()

    clue_text = " ".join(
        str(item.get("answer", ""))
        for item in game_state.get("known_clues", [])
        if isinstance(item, dict)
    ).lower()

    candidates = []

    for book, keywords in book_profiles.items():
        book_key = book.lower().strip()
        if book_key in rejected or book_key == possible_guess:
            continue

        score = 0
        for keyword in keywords:
            if keyword in clue_text:
                score += 2

        if book_key in clue_text:
            score += 5

        if book_key in recent:
            score -= 3

        candidates.append((score, book))

    if not candidates:
        return "Dog Man"

    best_score = max(score for score, _ in candidates)

    if best_score > 0:
        best = [book for score, book in candidates if score == best_score]
    else:
        # No clue match yet. Pick randomly instead of always starting with the same book.
        best = [book for score, book in candidates if book.lower().strip() not in recent]
        if not best:
            best = [book for _, book in candidates]

    guess = random.choice(best)
    game_state["recent_guesses"] = (list(game_state.get("recent_guesses", [])) + [guess])[-5:]

    return guess


def unlock_book_guessing_game_next_game_for_user():
    """
    Unlock the next active activity after book_guessing_game in the journey order.
    Returns the next activity_id, or None if there is no next activity.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT activity_id, scene_id, activity_order
            FROM activity
            WHERE activity_name = ?
              AND is_active = 1
            LIMIT 1
        """, ("book_guessing_game",))

        current_activity = cursor.fetchone()

        if not current_activity:
            conn.close()
            return None

        cursor.execute("""
            SELECT activity_id
            FROM activity
            WHERE is_active = 1
              AND (
                scene_id > ?
                OR (scene_id = ? AND activity_order > ?)
              )
            ORDER BY scene_id ASC, activity_order ASC
            LIMIT 1
        """, (
            current_activity["scene_id"],
            current_activity["scene_id"],
            current_activity["activity_order"]
        ))

        next_activity = cursor.fetchone()

        if not next_activity:
            conn.close()
            return None

        next_activity_id = next_activity["activity_id"]

        cursor.execute("""
            INSERT OR IGNORE INTO progress (
                user_id,
                activity_id,
                is_unlocked,
                is_completed,
                words_spoken,
                minutes_spoken,
                active_minutes,
                time_spent_on_activity
            )
            VALUES (?, ?, 1, 0, 0, 0, 0, 0)
        """, (session["user_id"], next_activity_id))

        cursor.execute("""
            UPDATE progress
            SET is_unlocked = 1
            WHERE user_id = ? AND activity_id = ?
        """, (session["user_id"], next_activity_id))

        cursor.execute("""
            UPDATE users
            SET current_activity_id = ?
            WHERE user_id = ?
        """, (next_activity_id, session["user_id"]))

        conn.commit()
        conn.close()

        return next_activity_id

    except Exception as e:
        print("Could not unlock next Book Guessing Game activity:", repr(e))
        return None

def apply_book_guessing_game_comfort_update(game_state, event_type, child_response, previous_response_mode):
    if event_type in {"intro", "restart", "first_question"}:
        return

    if game_state.get("game_complete"):
        return

    child_response = normalize_child_text(child_response)
    previous_stage = game_state.get("stage", "")

    if previous_stage == "guess":
        if is_yes_response(child_response):
            rounds_completed = int(game_state.get("rounds_completed", 0)) + 1

            game_state["rounds_completed"] = rounds_completed
            game_state["stage"] = "round_choice"
            game_state["last_response_mode"] = "round_choice"
            game_state["game_complete"] = False
            return

        possible_guess = game_state.get("possible_guess")

        if is_no_response(child_response):
            if possible_guess:
                game_state.setdefault("rejected_guesses", []).append(possible_guess)

            game_state["possible_guess"] = None
            game_state["skip_guess_once"] = True
            game_state["guess_cooldown_questions"] = 3

        elif event_type == "no_response":
            # Do not treat silence or a missed answer as "no."
            # The child may have said yes softly, taken time, or been unclear.
            # Move back to clue questions before guessing again.
            game_state["possible_guess"] = None
            game_state["skip_guess_once"] = True
            game_state["guess_cooldown_questions"] = 3

    clear_response = (
        event_type == "child_answer" and
        is_clear_book_guessing_game_response(child_response, previous_response_mode)
    )

    if clear_response:
        game_state["comfortable_answer_count"] = int(game_state.get("comfortable_answer_count", 0)) + 1
        game_state["comfortable_streak"] = int(game_state.get("comfortable_streak", 0)) + 1
        game_state["unclear_streak"] = 0

        word_count = len(re.findall(r"[A-Za-z']+", child_response))
        game_state.setdefault("clear_answer_word_counts", []).append(word_count)
        game_state["clear_answer_word_counts"] = game_state["clear_answer_word_counts"][-8:]

        last_question = game_state.get("last_question")

        if last_question and previous_stage != "guess":
            game_state.setdefault("known_clues", []).append({
                "question": last_question,
                "answer": child_response[:100]
            })

        current_index = int(game_state.get("response_level_index", BOOK_GUESSING_START_LEVEL_INDEX))
        comfortable_count = int(game_state.get("comfortable_answer_count", 0))
        comfortable_streak = int(game_state.get("comfortable_streak", 0))

        # Move up gently but noticeably when the child is giving usable clues.
        # This lets Librarian ask for more open hints once the child seems comfortable.
        if comfortable_streak >= 2 and current_index < len(BOOK_GUESSING_LEVELS) - 1:
            current_index += 1
            game_state["comfortable_streak"] = 0

        if word_count >= 2 and comfortable_count >= 2 and current_index < 3:
            current_index = 3

        if word_count >= 3 and comfortable_count >= 3 and current_index < 4:
            current_index = 4

        game_state["response_level_index"] = min(current_index, len(BOOK_GUESSING_LEVELS) - 1)

    else:
        game_state["unclear_or_silent_count"] = int(game_state.get("unclear_or_silent_count", 0)) + 1
        game_state["unclear_streak"] = int(game_state.get("unclear_streak", 0)) + 1
        game_state["comfortable_streak"] = 0

        if game_state["unclear_streak"] >= 2:
            current_index = int(game_state.get("response_level_index", BOOK_GUESSING_START_LEVEL_INDEX))
            game_state["response_level_index"] = max(current_index - 1, 0)
            game_state["unclear_streak"] = 0


def make_book_guessing_game_audio_response(
    message,
    stage,
    response_mode,
    expects_response,
    game_complete,
    game_state,
    history,
    event_type="server_response",
    child_response="",
    next_event=None,
    pause_before_next_ms=None,
    next_url=None,
    redirect_after_ms=None,
    session_done=False
):
    message = calm_book_guessing_game_line(message, game_complete=game_complete)

    history.append({
        "event_type": event_type,
        "child_response": child_response,
        "star": message,
        "stage": stage,
        "response_mode": response_mode,
        "game_complete": game_complete,
        "session_done": session_done
    })

    game_state["stage"] = stage
    game_state["last_response_mode"] = response_mode
    game_state["game_complete"] = game_complete

    session["book_guessing_game_history"] = history[-20:]
    session["book_guessing_game_state"] = game_state
    session.modified = True

    audio_bytes = generate_book_guessing_voice_elevenlabs(message, game_complete=game_complete)
    audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

    payload = {
        "success": True,
        "message": message,
        "audio": f"data:audio/mpeg;base64,{audio_base64}",
        "stage": stage,
        "expects_response": expects_response,
        "response_mode": response_mode,
        "game_complete": game_complete,
        "session_done": session_done,
        "offer_next_game": bool(
            int(game_state.get("rounds_completed", 0) or 0) >= BOOK_GUESSING_GAME_NEXT_GAME_OFFER_ROUND
        ),
        "game_state": game_state
    }

    if next_event:
        payload["next_event"] = next_event

    if pause_before_next_ms is not None:
        payload["pause_before_next_ms"] = pause_before_next_ms

    if next_url:
        payload["next_url"] = next_url

    if redirect_after_ms is not None:
        payload["redirect_after_ms"] = redirect_after_ms

    return jsonify(payload)


BOOK_GUESSING_GAME_MAX_ROUNDS = 3
BOOK_GUESSING_GAME_SOFT_REVEAL_QUESTION_LIMIT = 15
BOOK_GUESSING_GAME_NEXT_GAME_OFFER_ROUND = 3


BOOK_GUESSING_COMMON_BOOKS_BY_TITLE = {
    "Harry Potter": {"harry potter", "hogwarts"},
    "Dog Man": {"dog man"},
    "Diary of a Wimpy Kid": {"diary of a wimpy kid", "wimpy kid"},
    "The Cat in the Hat": {"cat in the hat", "the cat in the hat"},
    "Green Eggs and Ham": {"green eggs and ham"},
    "The Very Hungry Caterpillar": {"very hungry caterpillar", "hungry caterpillar"},
    "Where the Wild Things Are": {"where the wild things are", "wild things"},
    "Goodnight Moon": {"goodnight moon"},
    "Brown Bear, Brown Bear": {"brown bear brown bear", "brown bear"},
    "Charlotte's Web": {"charlotte's web", "charlottes web"},
    "Matilda": {"matilda"},
    "Wonder": {"wonder"},
    "The Giving Tree": {"giving tree", "the giving tree"},
    "Elephant and Piggie": {"elephant and piggie", "piggie", "elephant"},
    "Don't Let the Pigeon Drive the Bus": {"pigeon", "don't let the pigeon drive the bus", "dont let the pigeon drive the bus"},
    "Magic Tree House": {"magic tree house"},
    "The Hobbit": {"hobbit", "the hobbit"},
    "Narnia": {"narnia", "lion witch wardrobe", "lion the witch and the wardrobe"}
}

def get_child_revealed_book(text):
    lowered = normalize_child_text(text).lower()

    if not lowered:
        return None

    cleaned = re.sub(r"[^a-z' -]", " ", lowered)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    words = set(re.findall(r"[a-z']+", cleaned))

    if not words:
        return None

    direct_reveal_phrases = [
        "it's",
        "it is",
        "my book is",
        "the book is",
        "my thing is",
        "the thing is",
        "i picked",
        "i chose",
        "i was thinking of",
        "i am thinking of",
        "i'm thinking of",
        "it was",
        "it's a",
        "it is a"
    ]

    has_direct_reveal = any(phrase in cleaned for phrase in direct_reveal_phrases)

    # Also allow short answers like "teddy bear" or "a puzzle".
    can_treat_as_reveal = has_direct_reveal or len(words) <= 6

    if not can_treat_as_reveal:
        return None

    for display, aliases in BOOK_GUESSING_COMMON_BOOKS_BY_TITLE.items():
        for alias in aliases:
            alias_clean = normalize_child_text(alias).lower()
            alias_words = set(re.findall(r"[a-z']+", alias_clean))

            if not alias_clean:
                continue

            if " " in alias_clean and alias_clean in cleaned:
                return display

            if alias_clean in words:
                return display

            if alias_words and alias_words.issubset(words):
                return display

    return None


def get_book_guessing_play_again_question(rounds_completed, child_name):
    rounds_completed = int(rounds_completed or 0)
    offer_next_game = rounds_completed >= BOOK_GUESSING_GAME_NEXT_GAME_OFFER_ROUND

    if offer_next_game:
        return (
            "Do you want to play this game again, try a slightly different game, "
            "or stop here? You can tell me what you want."
        ), True, False

    if rounds_completed == BOOK_GUESSING_GAME_MAX_ROUNDS - 1:
        return (
            f"Do you want to play one last round before we end the call, {child_name}?"
        ), True, False

    return (
        f"Do you want to play another round, {child_name}?"
    ), True, False


@app.route("/api/book-guessing-game/message", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("30 per minute")
def book_guessing_game_message():
    data = request.get_json(silent=True) or {}

    event_type = normalize_child_text(data.get("event_type", "intro"))
    child_response = normalize_child_text(data.get("child_response", ""))
    previous_response_mode = normalize_child_text(data.get("response_mode", "none"))

    allowed_events = {
        "intro",
        "restart",
        "first_question",
        "round_choice_prompt",
        "child_answer",
        "no_response"
    }

    if event_type not in allowed_events:
        return jsonify({"success": False, "error": "Invalid event_type"}), 400

    child_name = session.get("child_name", "there")
    child_name = re.sub(r"[^A-Za-z' -]", "", str(child_name)).strip() or "there"

    if event_type in {"intro", "restart"}:
        session.pop("book_guessing_game_history", None)
        session.pop("book_guessing_game_state", None)
        history = []
        game_state = get_book_guessing_game_default_state(rounds_completed=0)
        child_response = ""
        previous_response_mode = "none"
    else:
        history = session.get("book_guessing_game_history", [])
        game_state = session.get(
            "book_guessing_game_state",
            get_book_guessing_game_default_state()
        )

    if event_type in {"intro", "restart"}:
        message = (
            "Hi, I'm the librarian. We're going to play Book Guessing Game. "
            "Think of a book, picture book, chapter book, or story you like. "
            "Take a second. I'll ask little questions to guess it."
        )

        try:
            return make_book_guessing_game_audio_response(
                message=message,
                stage="intro",
                response_mode="none",
                expects_response=False,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type=event_type,
                child_response="",
                next_event="first_question",
                pause_before_next_ms=2200
            )

        except Exception as e:
            print("Book Guessing Game intro TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate Librarian intro"
            }), 500

    if event_type == "round_choice_prompt":
        rounds_completed = int(game_state.get("rounds_completed", 0))
        message, expects_response, session_done = get_book_guessing_play_again_question(
            rounds_completed,
            child_name
        )

        try:
            return make_book_guessing_game_audio_response(
                message=message,
                stage="round_choice" if expects_response else "session_done",
                response_mode="round_choice" if expects_response else "none",
                expects_response=expects_response,
                game_complete=True,
                game_state=game_state,
                history=history,
                event_type="round_choice_prompt",
                child_response=child_response,
                session_done=session_done
            )

        except Exception as e:
            print("Book Guessing Game round choice prompt TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate round choice prompt"
            }), 500

    # Handle child response to end-of-round choice.
    # This now mirrors the Mystery Animal ending pattern:
    # after enough rounds, the child can choose this game again, a different game, or stopping.
    if previous_response_mode == "round_choice" and event_type in {"child_answer", "no_response"}:
        rounds_completed = int(game_state.get("rounds_completed", 0))
        offer_next_game = rounds_completed >= BOOK_GUESSING_GAME_NEXT_GAME_OFFER_ROUND

        if event_type == "no_response":
            choice = "unclear"
        else:
            choice = classify_book_guessing_game_choice_response(
                child_response,
                offer_next_game=offer_next_game
            )

        if choice == "same_game":
            new_game_state = get_book_guessing_game_default_state(
                rounds_completed=rounds_completed
            )

            if offer_next_game:
                message = (
                    "Okay. Let's play this game again. "
                    "Think of a new book, picture book or story."
                )
            else:
                message = (
                    "Okay. Let's play another round. "
                    "Think of a new book, picture book or story."
                )

            try:
                return make_book_guessing_game_audio_response(
                    message=message,
                    stage="intro",
                    response_mode="none",
                    expects_response=False,
                    game_complete=False,
                    game_state=new_game_state,
                    history=[],
                    event_type="replay",
                    child_response=child_response,
                    next_event="first_question",
                    pause_before_next_ms=1800
                )

            except Exception as e:
                print("Book Guessing Game replay TTS error:", repr(e))
                return jsonify({
                    "success": False,
                    "error": "Could not generate Librarian replay intro"
                }), 500

        if choice == "next_game" and offer_next_game:
            next_activity_id = unlock_book_guessing_game_next_game_for_user()

            if next_activity_id:
                next_url = url_for("open_activity", activity_id=next_activity_id)
                message = (
                    "Okay, I'll call you right back so we can try the next library game. "
                    "See you soon."
                )
            else:
                next_url = url_for("dashboard")
                message = (
                    "Okay, I'll call you right back so we can head back to the dashboard. "
                    "See you soon."
                )

            try:
                return make_book_guessing_game_audio_response(
                    message=message,
                    stage="transition_next_game",
                    response_mode="none",
                    expects_response=False,
                    game_complete=False,
                    game_state=game_state,
                    history=history,
                    event_type="next_game",
                    child_response=child_response,
                    next_url=next_url,
                    redirect_after_ms=1700,
                    session_done=True
                )

            except Exception as e:
                print("Book Guessing Game next-game TTS error:", repr(e))
                return jsonify({
                    "success": False,
                    "error": "Could not move to the next game"
                }), 500

        if choice == "stop":
            message = (
                "Okay. We can stop here. "
                "Thanks for playing Book Guessing Game with me."
            )

            try:
                return make_book_guessing_game_audio_response(
                    message=message,
                    stage="session_done",
                    response_mode="none",
                    expects_response=False,
                    game_complete=False,
                    game_state=game_state,
                    history=history,
                    event_type="stop",
                    child_response=child_response,
                    session_done=True
                )

            except Exception as e:
                print("Book Guessing Game stop TTS error:", repr(e))
                return jsonify({
                    "success": False,
                    "error": "Could not end the game"
                }), 500

        if offer_next_game:
            message = (
                "That's okay. We can play this game again, try a slightly different game, "
                "or stop here. You can tell me what you want."
            )
        else:
            message = (
                f"That's okay. Do you want to play another round, {child_name}?"
            )

        try:
            return make_book_guessing_game_audio_response(
                message=message,
                stage="round_choice",
                response_mode="round_choice",
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type="choice_clarification",
                child_response=child_response
            )

        except Exception as e:
            print("Book Guessing Game choice clarification TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate Librarian choice response"
            }), 500

    if event_type == "first_question":
        level = get_book_guessing_game_level(game_state)
        fallback = get_fallback_book_guessing_game_question(
            level,
            game_state,
            event_type="first_question"
        )

        question_text = fallback["question_text"]
        message = f"Okay. {question_text}"

        game_state["stage"] = fallback["stage"]
        game_state["last_response_mode"] = fallback["response_mode"]
        game_state["game_complete"] = False
        game_state["last_question"] = normalize_child_text(question_text)

        game_state.setdefault("question_history", []).append({
            "question": normalize_child_text(question_text),
            "stage": fallback["stage"],
            "response_mode": fallback["response_mode"]
        })

        game_state["questions_asked"] = int(game_state.get("questions_asked", 0)) + 1

        try:
            return make_book_guessing_game_audio_response(
                message=message,
                stage=fallback["stage"],
                response_mode=fallback["response_mode"],
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type="first_question",
                child_response=""
            )

        except Exception as e:
            print("Book Guessing Game first question TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate Librarian first question"
            }), 500

    # If the child names a book directly, confirm it as the Librarian's guess first.
    revealed_book = get_child_revealed_book(child_response)

    if event_type == "child_answer" and revealed_book and previous_response_mode != "guess_confirmation":
        game_state["stage"] = "guess"
        game_state["last_response_mode"] = "guess_confirmation"
        game_state["possible_guess"] = revealed_book

        message = f"That gives me a guess. Is it {revealed_book}?"

        try:
            return make_book_guessing_game_audio_response(
                message=message,
                stage="guess",
                response_mode="guess_confirmation",
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type="direct_reveal_as_guess",
                child_response=child_response
            )

        except Exception as e:
            print("Book Guessing Game direct reveal confirmation TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate Librarian response"
            }), 500

    apply_book_guessing_game_comfort_update(
        game_state,
        event_type,
        child_response,
        previous_response_mode
    )

    # If the Librarian guessed and the child confirmed yes, end the round in the same
    # response, like Mystery Animal. Do NOT repeat the guessed book name here:
    # if the child just said "stuffed animal," repeating it again sounds unnatural.
    if game_state.get("stage") == "round_choice":
        import random

        rounds_completed = int(game_state.get("rounds_completed", 0))

        success_options = [
            "Yes! I got it.",
            "Aha, I got it!",
            "Yes, that was it!",
            "I found it!",
            "Okay, I got it.",
            "There it is. I found it."
        ]

        success_line = random.choice(success_options)
        play_again_line, expects_response, session_done = get_book_guessing_play_again_question(
            rounds_completed,
            child_name
        )

        message = f"{success_line} {play_again_line}"

        try:
            return make_book_guessing_game_audio_response(
                message=message,
                stage="round_choice" if expects_response else "session_done",
                response_mode="round_choice" if expects_response else "none",
                expects_response=expects_response,
                game_complete=True,
                game_state=game_state,
                history=history,
                event_type="correct_guess_confirmed",
                child_response=child_response,
                session_done=session_done
            )

        except Exception as e:
            print("Book Guessing Game correct guess TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate Librarian round-choice response"
            }), 500

    if (
        not bool(game_state.get("soft_reveal_used", False))
        and int(game_state.get("questions_asked", 0)) >= BOOK_GUESSING_GAME_SOFT_REVEAL_QUESTION_LIMIT
        and game_state.get("stage") != "round_choice"
    ):
        game_state["soft_reveal_used"] = True

        message = (
            "Hmm, this is a tricky one. "
            "You can tell me the book if you want."
        )

        try:
            return make_book_guessing_game_audio_response(
                message=message,
                stage="soft_reveal",
                response_mode="open_hint",
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type="soft_reveal",
                child_response=child_response
            )

        except Exception as e:
            print("Book Guessing Game soft reveal TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate librarian soft reveal"
            }), 500

    level = get_book_guessing_game_level(game_state)
    fallback = get_fallback_book_guessing_game_question(level, game_state, event_type)

    known_clues = game_state.get("known_clues", [])
    questions_asked = int(game_state.get("questions_asked", 0))
    guess_cooldown_questions = int(game_state.get("guess_cooldown_questions", 0))
    comfortable_count = int(game_state.get("comfortable_answer_count", 0))
    last_answer_word_count = len(re.findall(r"[A-Za-z']+", child_response))

    total_clue_words = sum(
        len(re.findall(r"[A-Za-z']+", str(item.get("answer", ""))))
        for item in known_clues
        if isinstance(item, dict)
    )

    open_hint_questions_asked = int(game_state.get("open_hint_questions_asked", 0))

    should_guess = (
        not bool(game_state.get("skip_guess_once", False))
        and guess_cooldown_questions <= 0
        and (
            (len(known_clues) >= 3 and questions_asked >= 3)
            or (len(known_clues) >= 2 and total_clue_words >= 5)
            or (previous_response_mode == "open_hint" and len(known_clues) >= 2 and last_answer_word_count >= 2)
            or (open_hint_questions_asked >= 1 and len(known_clues) >= 2 and last_answer_word_count >= 1)
            or questions_asked >= 5
        )
    )

    should_invite_open_hint = (
        comfortable_count >= 3
        and int(game_state.get("response_level_index", BOOK_GUESSING_START_LEVEL_INDEX)) >= 3
        and not should_guess
    )

    system_prompt = f"""
You are the Librarian, a warm cartoon librarian playing Book Guessing Game.

The child is thinking of a book, picture book, chapter book, or story they like.
You ask gentle questions to guess it.

Core goal:
Make the child feel safe while giving them a real reason to communicate.

Hard rules:
- Never mention selective mutism, anxiety, therapy, treatment, exposure, stages, progress, confidence, or bravery.
- Never pressure the child to speak.
- Never say "use your words."
- Never sound disappointed.
- Never overpraise.
- Never make the child feel evaluated.
- Keep attention on the book game, not on the child.
- Ask only one question at a time.
- Do not repeat previous questions or repeat the same question family inside one round.
- Use the clues already given as hard constraints. If the child says more than four legs, never guess a four-legged animal.
- Keep the line to 1-2 short sentences.
- Address the child by name only occasionally.
- If you use the child's name, put it at the END of the sentence, not the beginning.

Acknowledging child responses:
- When the child gives a clear answer or hint, acknowledge the clue before asking the next question.
- Do not praise the act of speaking.
- Do not say "good job saying that" or "great talking."
- Focus on the clue, not the performance.

Direct book reveal:
- If the child names a book, do not end the round automatically.
- Confirm it as a guess.
- Example: if the child says "it's Dog Man", ask "Is it Dog Man?"

Silence and no-response handling:
- If the child does not answer, do not say "let me ask it in a simpler way."
- Do not imply the previous question was too hard.
- Do not repeat the same question.
- Do not say "I couldn't hear you."
- Gently move on with a different low-pressure question.

Voice style:
- During clue questions, sound warm, gentle, steady, and quietly playful.
- During a correct guess, it is okay to sound a little excited and playful.
- Use mostly periods for normal questions.
- Use at most one exclamation mark in a correct-guess celebration.
- Avoid sounding hyper, surprised, loud, or teacher-like.
- Do not say "Wow", "Amazing", "Awesome", or "Ooo".

Required response level:
Stage: {level["stage"]}
Response mode: {level["response_mode"]}
Description: {level["description"]}
Examples: {level["examples"]}

Guessing rule:
- should_guess is currently {should_guess}.
- If should_guess is false, do not guess yet.
- If should_guess is true, make one calm guess now.
- When guessing, ask it as a yes/no question, like "Is it Dog Man?"

Output JSON only:
{{
  "message": "Librarian's spoken line",
  "stage": "intro | yes_no | forced_choice | one_word | short_phrase | open_hint | guess | support | complete",
  "expects_response": true,
  "response_mode": "none | yes_no | choice | one_word | short_phrase | open_hint | guess_confirmation",
  "is_question": true,
  "question_text": "the exact question asked, or null",
  "game_complete": false,
  "possible_guess": null
}}
"""

    user_prompt = f"""
Child name:
{child_name}

Current game state:
{game_state}

Recent history:
{history[-12:]}

Known clues:
{known_clues}

Question history:
{game_state.get("question_history", [])}

Rejected guesses:
{game_state.get("rejected_guesses", [])}

New event:
event_type: {event_type}
child_response: {child_response}
previous_response_mode: {previous_response_mode}

If this is the first_question event:
- Ask one simple first question only.
- Do not reintroduce the game.

If event_type is child_answer and the child gave a clear answer:
- Acknowledge the clue first.
- Do not praise speaking itself.
- Then ask one useful next question or make one guess if should_guess is true.

If event_type is no_response:
- Start with a calm accepting phrase like "That's okay" or "No problem."
- Do not repeat the last question.
- Ask a different low-pressure question.

Generate the next Librarian line now.
"""

    try:
        text_response = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )

        raw = text_response.output_text.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()

        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {
                "message": fallback["message"],
                "stage": fallback["stage"],
                "expects_response": True,
                "response_mode": fallback["response_mode"],
                "is_question": True,
                "question_text": fallback["question_text"],
                "game_complete": False,
                "possible_guess": None
            }

        stage = normalize_child_text(parsed.get("stage", fallback["stage"]))
        response_mode = normalize_child_text(parsed.get("response_mode", fallback["response_mode"]))
        question_text = parsed.get("question_text")
        possible_guess = parsed.get("possible_guess")

        if stage == "guess" and not should_guess:
            parsed = {
                "message": fallback["message"],
                "stage": fallback["stage"],
                "expects_response": True,
                "response_mode": fallback["response_mode"],
                "is_question": True,
                "question_text": fallback["question_text"],
                "game_complete": False,
                "possible_guess": None
            }

            stage = parsed["stage"]
            response_mode = parsed["response_mode"]
            question_text = parsed["question_text"]
            possible_guess = None

        if should_guess and stage != "guess":
            fallback_guess = pick_fallback_book_guess(game_state)

            parsed = {
                "message": f"I have a guess. Is it {fallback_guess}?",
                "stage": "guess",
                "expects_response": True,
                "response_mode": "guess_confirmation",
                "is_question": True,
                "question_text": f"Is it {fallback_guess}?",
                "game_complete": False,
                "possible_guess": fallback_guess
            }

            stage = "guess"
            response_mode = "guess_confirmation"
            question_text = parsed["question_text"]
            possible_guess = fallback_guess

        if should_invite_open_hint and not should_guess and stage != "guess":
            lowered_question = normalize_child_text(question_text or parsed.get("message", "")).lower()
            asks_for_hint = any(phrase in lowered_question for phrase in [
                "hint",
                "clue",
                "what should i know",
                "what is one"
            ])

            if not asks_for_hint:
                question_text = choose_non_repeating_question(BOOK_GUESSING_LEVELS[-1], game_state)
                parsed["message"] = question_text
                parsed["stage"] = "open_hint"
                parsed["response_mode"] = "open_hint"
                parsed["is_question"] = True
                parsed["question_text"] = question_text
                stage = "open_hint"
                response_mode = "open_hint"

        if stage != "guess":
            if stage == "open_hint" and should_invite_open_hint:
                response_mode = "open_hint"
            else:
                stage = level["stage"]
                response_mode = level["response_mode"]
        else:
            response_mode = "guess_confirmation"

        game_complete = False
        message = parsed.get("message", "").strip().replace('"', "")

        if not message:
            message = fallback["message"]

        message = sanitize_short_line(
            message,
            fallback=fallback["message"],
            max_len=220
        )

        message = calm_book_guessing_game_line(message, game_complete=game_complete)

        message = maybe_add_book_guessing_game_acknowledgment(
            message=message,
            event_type=event_type,
            child_response=child_response,
            previous_response_mode=previous_response_mode,
            game_state=game_state
        )

        message = calm_book_guessing_game_line(message, game_complete=game_complete)

        if not question_text and parsed.get("is_question"):
            question_text = message

        if stage == "guess":
            response_mode = "guess_confirmation"

            if possible_guess:
                game_state["possible_guess"] = normalize_child_text(possible_guess)
            else:
                guess_match = re.search(r"is it (?:a |an )?([A-Za-z -]+)\??", message.lower())

                if guess_match:
                    game_state["possible_guess"] = guess_match.group(1).strip()

        game_state["stage"] = stage
        game_state["last_response_mode"] = response_mode
        game_state["game_complete"] = False

        if stage != "guess":
            if game_state.get("skip_guess_once"):
                game_state["skip_guess_once"] = False

            if int(game_state.get("guess_cooldown_questions", 0)) > 0:
                game_state["guess_cooldown_questions"] = max(
                    0,
                    int(game_state.get("guess_cooldown_questions", 0)) - 1
                )

        if parsed.get("is_question") and question_text:
            game_state["last_question"] = normalize_child_text(question_text)
            game_state.setdefault("question_history", []).append({
                "question": normalize_child_text(question_text),
                "stage": stage,
                "response_mode": response_mode
            })

            game_state["questions_asked"] = int(game_state.get("questions_asked", 0)) + 1

            if stage == "open_hint" or response_mode == "open_hint":
                game_state["open_hint_questions_asked"] = int(
                    game_state.get("open_hint_questions_asked", 0)
                ) + 1

        history.append({
            "event_type": event_type,
            "child_response": child_response,
            "librarian": message,
            "stage": game_state["stage"],
            "response_mode": response_mode,
            "game_complete": False
        })

        session["book_guessing_game_history"] = history[-20:]
        session["book_guessing_game_state"] = game_state
        session.modified = True

        audio_bytes = generate_book_guessing_voice_elevenlabs(message)
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

        return jsonify({
            "success": True,
            "message": message,
            "audio": f"data:audio/mpeg;base64,{audio_base64}",
            "stage": game_state["stage"],
            "expects_response": bool(parsed.get("expects_response", True)),
            "response_mode": response_mode,
            "game_complete": False,
            "session_done": False,
            "game_state": game_state
        })

    except Exception as e:
        print("Book Guessing Game AI error:", repr(e))
        return jsonify({
            "success": False,
            "error": "Could not generate Librarian response"
        }), 500


@app.route("/api/book-guessing-game/transcribe", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("30 per minute")
def book_guessing_game_transcribe():
    if "audio" not in request.files:
        return jsonify({
            "success": False,
            "error": "Missing audio"
        }), 400

    audio_file = request.files["audio"]

    try:
        import io

        audio_bytes = audio_file.read()

        if not audio_bytes:
            return jsonify({
                "success": False,
                "error": "Empty audio file"
            }), 400

        file_obj = io.BytesIO(audio_bytes)
        file_obj.name = "book-guessing-response.webm"

        transcript = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=file_obj
        )

        text = transcript.text.strip()

        print("BOOK GUESSING GAME TRANSCRIPT:", text)

        return jsonify({
            "success": True,
            "text": text
        })

    except Exception as e:
        print("Book Guessing Game transcription error:", repr(e))
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    
# =========================
# Library Guessing Game — Librarian thinks of something you can find at school
# Add this block to app.py after your existing Guessing Game block, or use it to replace any old library/book guessing backend.
# =========================

def generate_library_guessing_voice_elevenlabs(text, game_complete=False, thinking=False):
    voice_id = os.getenv("LIBRARIAN_VOICE_ID")

    if not voice_id:
        voice_id = os.getenv("ELEVENLABS_VOICE_ID", "piI8Kku0DcvcL6TTSeQt")

    if game_complete:
        voice_settings = {
            "stability": 0.84,
            "similarity_boost": 0.90,
            "style": 0.25,
            "use_speaker_boost": False
        }
    elif thinking:
        voice_settings = {
            "stability": 0.98,
            "similarity_boost": 0.88,
            "style": 0.02,
            "use_speaker_boost": False
        }
    else:
        voice_settings = {
            "stability": 0.94,
            "similarity_boost": 0.90,
            "style": 0.06,
            "use_speaker_boost": False
        }

    response = eleven_client.text_to_speech.convert(
        voice_id=voice_id,
        text=text,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
        voice_settings=voice_settings
    )

    return b"".join(response)


LIBRARY_GUESSING_GAME_MAX_ROUNDS = 3
LIBRARY_GUESSING_GAME_NEXT_GAME_OFFER_ROUND = 999

LIBRARY_GUESSING_GAME_OBJECT_PROFILES = {
    "pencil": {
        "display": "pencil",
        "aliases": {"pencil", "lead pencil"},
        "tags": {"classroom", "desk", "writing", "drawing", "wood", "pointy", "small", "yellow", "long", "school_supply"},
        "colors": {"yellow", "black", "wood"},
        "hints": [
            "You can use this to write.",
            "It is often yellow and pointy.",
            "You might keep it in a pencil box."
        ]
    },
    "eraser": {
        "display": "eraser",
        "aliases": {"eraser", "rubber"},
        "tags": {"classroom", "desk", "erase", "small", "soft", "pink", "school_supply"},
        "colors": {"pink", "white"},
        "hints": [
            "This helps fix a pencil mistake.",
            "It is small and often soft.",
            "You might keep it near a pencil."
        ]
    },
    "crayon": {
        "display": "crayon",
        "aliases": {"crayon", "crayons"},
        "tags": {"classroom", "art", "color", "drawing", "small", "wax", "school_supply"},
        "colors": {"red", "blue", "green", "yellow", "orange", "purple", "black"},
        "hints": [
            "You use this to color pictures.",
            "It can come in many colors.",
            "You might use it during art time."
        ]
    },
    "marker": {
        "display": "marker",
        "aliases": {"marker", "markers"},
        "tags": {"classroom", "art", "color", "drawing", "writing", "plastic", "small", "school_supply"},
        "colors": {"red", "blue", "green", "black", "purple"},
        "hints": [
            "This can make bright lines.",
            "You use it to write or draw.",
            "It usually has a cap."
        ]
    },
    "glue_stick": {
        "display": "glue stick",
        "aliases": {"glue", "glue stick", "gluestick"},
        "tags": {"classroom", "art", "craft", "sticky", "plastic", "small", "school_supply"},
        "colors": {"white", "purple", "clear"},
        "hints": [
            "This helps paper stick together.",
            "You might use it for crafts.",
            "It can twist up from a tube."
        ]
    },
    "scissors": {
        "display": "scissors",
        "aliases": {"scissors", "scissor"},
        "tags": {"classroom", "art", "cutting", "metal", "plastic", "sharp", "school_supply"},
        "colors": {"blue", "red", "green", "silver"},
        "hints": [
            "This is used for cutting paper.",
            "It has handles.",
            "A teacher might remind you to use it carefully."
        ]
    },
    "ruler": {
        "display": "ruler",
        "aliases": {"ruler", "measuring stick"},
        "tags": {"classroom", "desk", "measure", "straight", "long", "flat", "wood", "plastic", "school_supply"},
        "colors": {"brown", "clear", "yellow", "blue"},
        "hints": [
            "This helps you measure.",
            "It is long and straight.",
            "It can help draw a straight line."
        ]
    },
    "folder": {
        "display": "folder",
        "aliases": {"folder", "folders"},
        "tags": {"classroom", "desk", "paper", "flat", "organize", "backpack", "school_supply"},
        "colors": {"red", "blue", "green", "yellow", "purple"},
        "hints": [
            "This can hold papers.",
            "It is flat and can go in a backpack.",
            "It helps keep schoolwork organized."
        ]
    },
    "backpack": {
        "display": "backpack",
        "aliases": {"backpack", "bag", "school bag", "bookbag"},
        "tags": {"school", "carry", "fabric", "zipper", "big", "wear", "straps"},
        "colors": {"black", "blue", "red", "pink", "green", "purple"},
        "hints": [
            "You can carry school supplies in this.",
            "It often has straps.",
            "You might wear it on your back."
        ]
    },
    "lunchbox": {
        "display": "lunchbox",
        "aliases": {"lunchbox", "lunch box", "lunch bag"},
        "tags": {"school", "cafeteria", "food", "carry", "container", "small", "plastic", "fabric"},
        "colors": {"blue", "red", "pink", "green", "black"},
        "hints": [
            "This can hold food.",
            "You might bring it to school for lunchtime.",
            "It is something you carry."
        ]
    },
    "whiteboard": {
        "display": "whiteboard",
        "aliases": {"whiteboard", "board", "dry erase board"},
        "tags": {"classroom", "teacher", "writing", "large", "white", "wall", "flat"},
        "colors": {"white"},
        "hints": [
            "A teacher might write on this.",
            "It is usually big and white.",
            "It is often at the front of a classroom."
        ]
    },
    "desk": {
        "display": "desk",
        "aliases": {"desk", "student desk"},
        "tags": {"classroom", "furniture", "wood", "metal", "large", "sit", "flat", "work"},
        "colors": {"brown", "tan", "gray"},
        "hints": [
            "A student might sit at this.",
            "It has a flat top.",
            "You can work on it in class."
        ]
    },
    "chair": {
        "display": "chair",
        "aliases": {"chair", "seat"},
        "tags": {"classroom", "furniture", "sit", "plastic", "wood", "metal", "medium"},
        "colors": {"blue", "brown", "gray", "black", "red"},
        "hints": [
            "You can sit on this.",
            "It is classroom furniture.",
            "It is often next to a desk."
        ]
    },
    "computer": {
        "display": "computer",
        "aliases": {"computer", "laptop", "chromebook"},
        "tags": {"classroom", "technology", "screen", "keyboard", "electric", "learning", "medium"},
        "colors": {"black", "gray", "silver"},
        "hints": [
            "This has a screen.",
            "You might type on it.",
            "It is used for learning or games at school."
        ]
    },
    "calculator": {
        "display": "calculator",
        "aliases": {"calculator", "calculater"},
        "tags": {"classroom", "math", "numbers", "buttons", "small", "plastic", "technology"},
        "colors": {"black", "gray", "blue"},
        "hints": [
            "This helps with math.",
            "It has number buttons.",
            "You might use it for adding."
        ]
    },
    "paintbrush": {
        "display": "paintbrush",
        "aliases": {"paintbrush", "paint brush", "brush"},
        "tags": {"classroom", "art", "painting", "wood", "bristles", "small", "school_supply"},
        "colors": {"brown", "black", "wood"},
        "hints": [
            "You use this with paint.",
            "It has bristles.",
            "You might use it during art time."
        ]
    },
    "tape": {
        "display": "tape",
        "aliases": {"tape", "tape roll", "scotch tape"},
        "tags": {"classroom", "sticky", "clear", "roll", "craft", "small", "school_supply"},
        "colors": {"clear", "white"},
        "hints": [
            "This can stick things together.",
            "It often comes on a roll.",
            "You might use it for posters or crafts."
        ]
    },
    "stapler": {
        "display": "stapler",
        "aliases": {"stapler", "staple"},
        "tags": {"classroom", "teacher", "paper", "metal", "plastic", "small", "organize"},
        "colors": {"black", "gray", "red", "blue"},
        "hints": [
            "This can hold papers together.",
            "It uses tiny metal staples.",
            "A teacher might have one on a desk."
        ]
    }
}


def normalize_library_guessing_text(text):
    text = re.sub(r"\s+", " ", str(text or "")).strip().lower()
    text = text.replace("’", "'")
    text = re.sub(r"[^a-z0-9' -]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def library_guessing_words(text):
    return set(re.findall(r"[a-z']+", normalize_library_guessing_text(text)))


def get_library_guessing_game_default_state(rounds_completed=0, used_objects=None):
    import random

    used_so_far = [
        obj for obj in list(used_objects or [])
        if obj in LIBRARY_GUESSING_GAME_OBJECT_PROFILES
    ]

    object_names = [
        obj for obj in LIBRARY_GUESSING_GAME_OBJECT_PROFILES.keys()
        if obj not in set(used_so_far)
    ]

    if not object_names:
        object_names = list(LIBRARY_GUESSING_GAME_OBJECT_PROFILES.keys())

    secret_object = random.choice(object_names)
    used_objects_for_session = (used_so_far + [secret_object])[-LIBRARY_GUESSING_GAME_MAX_ROUNDS:]

    return {
        "stage": "intro",
        "secret_object": secret_object,
        "used_objects": used_objects_for_session,
        "rounds_completed": rounds_completed_int,
        "questions_asked": 0,
        "comfortable_question_count": 0,
        "unclear_or_silent_count": 0,
        "unclear_streak": 0,
        "hint_count": 0,
        "wrong_guess_count": 0,
        "wrong_guesses": [],
        "asked_questions": [],
        "asked_topics": [],
        "recent_hints": [],
        "recent_round_prompts": [],
        "recent_support_lines": [],
        "recent_good_question_prefixes": [],
        "recent_suggestion_topics": [],
        "last_hint_offer_question_count": 0,
        "recent_follow_ups": [],
        "game_complete": False,
        "last_response_mode": "none"
    }


def get_library_guessing_game_profile(game_state):
    secret_object = normalize_library_guessing_text(game_state.get("secret_object", "pencil"))

    if secret_object not in LIBRARY_GUESSING_GAME_OBJECT_PROFILES:
        secret_object = "pencil"
        game_state["secret_object"] = secret_object

    return LIBRARY_GUESSING_GAME_OBJECT_PROFILES[secret_object]


def is_library_guessing_unclear_or_silent(text):
    lowered = normalize_library_guessing_text(text)

    if not lowered:
        return True

    unclear_phrases = {
        "i don't know", "i dont know", "i do not know", "don't know", "dont know",
        "do not know", "idk", "not sure", "i'm not sure", "im not sure",
        "maybe", "hmm", "hm", "mm", "mmm", "uh", "um"
    }

    if lowered in unclear_phrases:
        return True

    words = re.findall(r"[a-z']+", lowered)
    filler_words = {"hmm", "hm", "mm", "mmm", "uh", "um", "like", "wait"}

    return bool(words) and all(word in filler_words for word in words)


def is_library_guessing_hint_request(text):
    lowered = normalize_library_guessing_text(text)

    hint_phrases = [
        "hint", "clue", "give me a hint", "give me a clue",
        "can i have a hint", "can i have a clue", "tell me something",
        "help me", "i need help"
    ]

    return any(phrase in lowered for phrase in hint_phrases)


def get_library_guessing_named_object(text):
    lowered = normalize_library_guessing_text(text)
    words = library_guessing_words(lowered)

    for object_key, profile in LIBRARY_GUESSING_GAME_OBJECT_PROFILES.items():
        for alias in profile.get("aliases", set()):
            alias_clean = normalize_library_guessing_text(alias)
            alias_words = set(re.findall(r"[a-z']+", alias_clean))

            if not alias_clean:
                continue

            if " " in alias_clean and alias_clean in lowered:
                return object_key

            if alias_clean in words:
                return object_key

            if alias_words and alias_words.issubset(words) and len(alias_words) > 1:
                return object_key

    return None


def is_library_guessing_direct_guess(text):
    lowered = normalize_library_guessing_text(text)
    named_object = get_library_guessing_named_object(lowered)

    if not named_object:
        return False

    direct_guess_phrases = [
        "is it", "is your object", "is your thing", "are you thinking of",
        "i guess", "my guess", "i think", "it's", "it is", "maybe",
        "the object is", "the thing is"
    ]

    if any(phrase in lowered for phrase in direct_guess_phrases):
        return True

    words = re.findall(r"[a-z']+", lowered)
    return len(words) <= 4


def is_library_guessing_question(text):
    lowered = normalize_library_guessing_text(text)
    words = re.findall(r"[a-z']+", lowered)

    if not words:
        return False

    question_starters = {
        "is", "are", "do", "does", "can", "could", "would",
        "has", "have", "what", "where", "how", "did", "will"
    }

    return words[0] in question_starters or "?" in str(text)


def library_guessing_question_key(text):
    lowered = normalize_library_guessing_text(text)
    lowered = re.sub(
        r"\b(the|a|an|your|object|thing|it|does|do|is|are|can|could|would|has|have|what|where|how)\b",
        " ",
        lowered
    )
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered[:80]


def get_library_guessing_question_topic(text):
    words = library_guessing_words(text)

    if words & {"big", "small", "little", "tiny", "large", "huge", "size"}:
        return "size"

    if words & {"color", "colour", "black", "white", "brown", "orange", "yellow", "green", "gray", "grey", "blue", "red", "pink", "purple", "clear", "silver"}:
        return "color"

    if words & {"where", "classroom", "library", "desk", "backpack", "cafeteria", "art", "front", "wall"}:
        return "place"

    if words & {"write", "draw", "color", "cut", "measure", "glue", "stick", "erase", "carry", "eat", "sit", "type", "math", "paint", "staple", "tape", "use", "used"}:
        return "use"

    if words & {"wood", "plastic", "metal", "paper", "fabric", "soft", "hard", "sharp", "sticky", "flat", "screen", "buttons"}:
        return "material"

    return "general"


def remember_library_guessing_question_topic(text, game_state):
    topic = get_library_guessing_question_topic(text)

    if topic:
        game_state.setdefault("asked_topics", []).append(topic)
        game_state["asked_topics"] = game_state["asked_topics"][-10:]

    return topic


def calm_library_guessing_game_line(text, game_complete=False):
    text = re.sub(r"\s+", " ", str(text or "")).strip()

    if not text:
        return "I'm thinking of something you can find at school."

    replacements = {
        "Amazing": "Nice",
        "amazing": "nice",
        "Awesome": "Nice",
        "awesome": "nice",
        "Wow": "Hmm",
        "wow": "hmm",
        "Interesting question.": "Good question.",
        "Interesting.": "",
        "That is interesting.": "",
        "That gives me something to think about.": "",
        "Okay, that helps.": "",
        "That helps.": "",
        "I can work with that.": "",
        "Good job asking": "Good question",
        "Great job asking": "Great question",
        "Good job talking": "Thank you",
        "Great job talking": "Thank you",
        "Good job using your words": "Thank you",
        "I couldn't hear you": "That's okay",
        "I could not hear you": "That's okay"
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        text = "Good question."

    if not game_complete:
        text = text.replace("!", ".")

    if text.count("!") > 1:
        first = text.find("!")
        text = text[:first + 1] + text[first + 1:].replace("!", ".")

    return text[:300].strip()


def get_library_guessing_game_specific_color_answer(text, game_state):
    words = library_guessing_words(text)
    profile = get_library_guessing_game_profile(game_state)

    color_words = {
        "black", "white", "brown", "orange", "yellow", "green", "gray", "grey",
        "blue", "red", "pink", "purple", "clear", "silver", "tan"
    }

    asked_colors = [color for color in color_words if color in words]
    colors_for_secret = profile.get("colors", set())

    if asked_colors:
        spoken_color = asked_colors[0]
        normalized_color = "gray" if spoken_color == "grey" else spoken_color
        normalized_colors_for_secret = {
            "gray" if color == "grey" else color
            for color in colors_for_secret
        }

        if normalized_color in normalized_colors_for_secret:
            return {
                "type": "answer",
                "message": f"Yes, it can be {normalized_color}.",
                "question_answered": True
            }

        return {
            "type": "answer",
            "message": f"No, it is not usually {normalized_color}.",
            "question_answered": True
        }

    if "color" in words or "colour" in words:
        normalized_colors = sorted({
            "gray" if color == "grey" else color
            for color in colors_for_secret
        })

        if not normalized_colors:
            message = "It can be different colors."
        elif len(normalized_colors) == 1:
            message = f"It is often {normalized_colors[0]}."
        else:
            message = f"It can be {normalized_colors[0]}."

        return {
            "type": "answer",
            "message": message,
            "question_answered": True
        }

    return None


def get_library_guessing_game_ai_question_answer(text, game_state):
    import random

    profile = get_library_guessing_game_profile(game_state)
    secret_object = game_state.get("secret_object", "pencil")
    display = profile.get("display", secret_object)
    tags = sorted(list(profile.get("tags", [])))
    asked_topics = set(game_state.get("asked_topics", []))
    recent_support_lines = list(game_state.get("recent_support_lines", []))[-5:]

    topic_options = [
        ("place", "You can ask where I might find it in school."),
        ("use", "You can ask what it is used for."),
        ("color", "You can ask what color it is."),
        ("size", "You can ask about its size."),
        ("material", "You can ask what it is made of."),
        ("general", "You can ask me a yes or no school question.")
    ]

    fresh_topic_lines = [
        line for topic, line in topic_options
        if topic not in asked_topics and line not in recent_support_lines
    ]

    general_fallbacks = [
        "I can answer school questions best.",
        "That one is tricky for this game.",
        "I might give away too much with that one.",
        "Try asking one school clue question.",
        "You can ask me a yes or no question about it."
    ]

    def fallback_support():
        if fresh_topic_lines:
            line = random.choice(fresh_topic_lines)
        else:
            fresh = [item for item in general_fallbacks if item not in recent_support_lines]
            line = random.choice(fresh or general_fallbacks)

        game_state["recent_support_lines"] = (recent_support_lines + [line])[-5:]

        return {
            "type": "support",
            "message": line,
            "question_answered": False
        }

    try:
        system_prompt = f"""
You are a warm cartoon librarian playing Library Guessing Game.

The librarian is thinking of one secret thing a child can find at school.
The child asks questions to collect clues and guess what it is.

Secret object:
{display}

Secret object tags:
{tags}

Rules:
- Answer the child's question naturally and briefly.
- Do not reveal the secret object's name unless the child directly guessed it.
- If the child asks a yes/no question, answer yes or no clearly.
- If the child asks an open question, give a tiny answer, not a big clue.
- Keep the answer to 1 short sentence.
- Do not invite another question every time.
- Do not say "interesting."
- Do not mention therapy, anxiety, selective mutism, treatment, progress, confidence, bravery, or speaking.
- Do not praise the child for talking.
- Keep the focus on the guessing game and the school item.
- Use calm periods, not excited exclamation marks.

Output JSON only:
{{
  "type": "answer",
  "message": "Librarian's spoken line",
  "question_answered": true
}}
"""

        user_prompt = f"""
Child question:
{text}

Recent support lines to avoid:
{recent_support_lines}

Answer the child's question about the secret thing without revealing its name.
"""

        response = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )

        raw = response.output_text.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()

        try:
            parsed = json.loads(raw)
        except Exception:
            return fallback_support()

        message = re.sub(r"\s+", " ", str(parsed.get("message", ""))).strip()

        if not message:
            return fallback_support()

        banned_bits = [
            "interesting",
            "something to think about",
            "good job talking",
            "great job talking",
            "use your words"
        ]

        lowered_message = message.lower()

        if any(bit in lowered_message for bit in banned_bits):
            return fallback_support()

        guessed_object = get_library_guessing_named_object(text)

        if guessed_object != secret_object:
            message = re.sub(
                rf"\b{re.escape(display)}s?\b",
                "it",
                message,
                flags=re.IGNORECASE
            )

        return {
            "type": parsed.get("type", "answer"),
            "message": calm_library_guessing_game_line(message),
            "question_answered": bool(parsed.get("question_answered", True))
        }

    except Exception as e:
        print("Library Guessing Game flexible answer error:", repr(e))
        return fallback_support()


def answer_library_guessing_question(text, game_state):
    profile = get_library_guessing_game_profile(game_state)
    tags = profile.get("tags", set())
    lowered = normalize_library_guessing_text(text)
    words = library_guessing_words(lowered)
    secret_object = game_state.get("secret_object")

    named_object = get_library_guessing_named_object(lowered)

    if named_object:
        if named_object == secret_object:
            return {
                "type": "correct_guess",
                "message": f"Yes, it is a {profile['display']}. You got it.",
                "question_answered": True
            }

        return {
            "type": "wrong_guess",
            "message": f"Not quite, it is not a {LIBRARY_GUESSING_GAME_OBJECT_PROFILES[named_object]['display']}.",
            "wrong_guess": named_object,
            "question_answered": True
        }

    color_answer = get_library_guessing_game_specific_color_answer(text, game_state)

    if color_answer:
        return color_answer

    if (
        ("how" in words and ("big" in words or "small" in words or "size" in words))
        or ("big" in words and "small" in words)
        or ("size" in words)
    ):
        if "big" in tags or "large" in tags:
            message = "It is pretty big."
        elif "medium" in tags:
            message = "It is medium sized."
        elif "small" in tags:
            message = "It is small."
        else:
            message = "It is not especially big."

        return {"type": "answer", "message": message, "question_answered": True}

    if "where" in words or words & {"classroom", "library", "cafeteria", "desk", "backpack", "wall", "front"}:
        if "cafeteria" in tags:
            message = "You might use it around lunchtime."
        elif "backpack" in tags:
            message = "You might keep it in a backpack."
        elif "wall" in tags or "front" in tags:
            message = "You might see it near the front of a classroom."
        elif "desk" in tags:
            message = "You might find it on or near a desk."
        elif "classroom" in tags:
            message = "You might find it in a classroom."
        else:
            message = "You could find it somewhere at school."

        return {"type": "answer", "message": message, "question_answered": True}

    if words & {"pet", "wild", "home", "house"}:
        detail = get_guessing_game_detail(game_state, "category")
        if detail:
            return {
                "type": "answer",
                "message": detail,
                "question_answered": True
            }

    if words & {"move", "moves", "walk", "walks", "run", "runs", "swim", "swims", "jump", "jumps", "hop", "hops", "fly", "flies"}:
        detail = get_guessing_game_detail(game_state, "movement")
        if detail:
            return {
                "type": "answer",
                "message": detail,
                "question_answered": True
            }

    checks = [
        ({"write", "writing"}, {"writing"}, "Yes, you can use it for writing.", "No, it is not mainly for writing."),
        ({"draw", "drawing"}, {"drawing"}, "Yes, you can use it for drawing.", "No, it is not mainly for drawing."),
        ({"color", "colour", "coloring"}, {"color"}, "Yes, it can be used for coloring.", "No, it is not mainly for coloring."),
        ({"cut", "cutting"}, {"cutting"}, "Yes, it is used for cutting.", "No, it is not used for cutting."),
        ({"measure", "measuring"}, {"measure"}, "Yes, it is used for measuring.", "No, it is not used for measuring."),
        ({"glue", "sticky", "stick"}, {"sticky"}, "Yes, it can be sticky or used for sticking things.", "No, it is not sticky."),
        ({"erase", "erasing", "mistake"}, {"erase"}, "Yes, it can erase pencil marks.", "No, it does not erase things."),
        ({"carry", "hold"}, {"carry"}, "Yes, it can carry or hold things.", "No, it is not mainly for carrying things."),
        ({"food", "lunch", "eat"}, {"food"}, "Yes, it has to do with food or lunch.", "No, it is not for food."),
        ({"sit", "seat"}, {"sit"}, "Yes, you can sit on it.", "No, you do not sit on it."),
        ({"type", "keyboard"}, {"keyboard"}, "Yes, you can type on it.", "No, you do not type on it."),
        ({"screen"}, {"screen"}, "Yes, it has a screen.", "No, it does not have a screen."),
        ({"math", "number", "numbers"}, {"math", "numbers"}, "Yes, it is used for math or numbers.", "No, it is not mainly for math."),
        ({"paint", "painting"}, {"painting"}, "Yes, it is used with paint.", "No, it is not used with paint."),
        ({"paper", "papers"}, {"paper"}, "Yes, it has to do with paper.", "No, paper is not the main clue."),
        ({"staple", "stapler"}, {"organize", "paper", "metal"}, "Yes, it can help keep papers together.", "No, it is not used for stapling."),
        ({"tape"}, {"sticky", "roll"}, "Yes, it can be tape or tape-like.", "No, it is not tape."),
        ({"wood", "wooden"}, {"wood"}, "Yes, it can be made of wood.", "No, it is not usually wooden."),
        ({"plastic"}, {"plastic"}, "Yes, it can have plastic.", "No, plastic is not a big clue."),
        ({"metal"}, {"metal"}, "Yes, it can have metal.", "No, it does not usually have metal."),
        ({"fabric", "cloth"}, {"fabric"}, "Yes, it can be made of fabric.", "No, it is not usually fabric."),
        ({"sharp", "pointy"}, {"sharp", "pointy"}, "Yes, it can be sharp or pointy.", "No, it is not really sharp or pointy."),
        ({"flat"}, {"flat"}, "Yes, it is pretty flat.", "No, flat is not a big clue."),
        ({"teacher"}, {"teacher"}, "Yes, a teacher might use it.", "A teacher could use many things, but that is not the main clue."),
        ({"art", "craft", "crafts"}, {"art", "craft"}, "Yes, you might use it for art or crafts.", "No, it is not mainly for art or crafts."),
        ({"furniture"}, {"furniture"}, "Yes, it is classroom furniture.", "No, it is not furniture."),
        ({"technology", "electric", "electronic"}, {"technology", "electric"}, "Yes, it is technology.", "No, it is not technology.")
    ]

    for trigger_words, needed_tags, yes_line, no_line in checks:
        if words & trigger_words:
            if tags & needed_tags:
                return {"type": "answer", "message": yes_line, "question_answered": True}

            return {"type": "answer", "message": no_line, "question_answered": True}

    return get_library_guessing_game_ai_question_answer(text, game_state)


def get_library_guessing_game_hint(game_state):
    import random

    profile = get_library_guessing_game_profile(game_state)
    recent_hints = list(game_state.get("recent_hints", []))
    hints = list(profile.get("hints", []))

    fresh = [hint for hint in hints if hint not in recent_hints]

    if fresh:
        hint = random.choice(fresh)
    elif hints:
        hint = random.choice(hints)
    else:
        hint = "This is something many kids know from school."

    game_state["recent_hints"] = (recent_hints + [hint])[-5:]
    game_state["hint_count"] = int(game_state.get("hint_count", 0)) + 1

    return hint


def classify_library_guessing_game_round_choice(text, offer_next_game=False):
    lowered = normalize_library_guessing_text(text)
    words = library_guessing_words(lowered)

    if not lowered:
        return "unclear"

    stop_words = {"stop", "done", "finish", "finished", "end", "quit", "leave", "dashboard", "no", "nope", "nah"}
    same_game_words = {"again", "same", "replay", "more", "continue", "yes", "yeah", "yep", "yup", "sure", "okay", "ok", "alright", "fine", "good", "cool", "this"}

    if words & stop_words:
        return "stop"

    if words & same_game_words:
        return "same_game"

    same_game_phrases = [
        "play again", "play another round", "another round", "one more round",
        "same game", "let's play", "lets play", "keep playing", "do it again", "try again"
    ]

    if any(phrase in lowered for phrase in same_game_phrases):
        return "same_game"

    return "unclear"


def maybe_add_library_good_question_prefix(message, game_state):
    import random

    question_count = int(game_state.get("questions_asked", 0))

    should_add = (
        question_count <= 2
        or question_count in {4, 6, 8}
        or random.random() < 0.55
    )

    if not should_add:
        return message

    lowered = normalize_library_guessing_text(message)

    if lowered.startswith(("that's a good question", "that is a good question", "good question", "great question", "nice question")):
        return message

    prefixes = [
        "That's a good question.",
        "Good question.",
        "Great question.",
        "Nice question.",
        "That's a smart thing to ask."
    ]

    recent = list(game_state.get("recent_good_question_prefixes", []))[-3:]
    fresh = [prefix for prefix in prefixes if prefix not in recent]
    prefix = random.choice(fresh or prefixes)

    game_state["recent_good_question_prefixes"] = (recent + [prefix])[-3:]

    return f"{prefix} {message}"


def get_library_guessing_game_follow_up_after_answer(game_state):
    questions_asked = int(game_state.get("questions_asked", 0))
    wrong_guess_count = int(game_state.get("wrong_guess_count", 0))
    total_child_turns = questions_asked + wrong_guess_count
    last_hint_offer = int(game_state.get("last_hint_offer_question_count", 0))

    if total_child_turns >= 3 and total_child_turns - last_hint_offer >= 3:
        game_state["last_hint_offer_question_count"] = total_child_turns

        options = [
            "Let me know whenever you want a hint.",
            "Let me know if you want a clue.",
            "You can ask for a hint whenever you want.",
            "Whenever you want a clue, you can ask me."
        ]

        recent = list(game_state.get("recent_follow_ups", []))[-4:]
        follow_up = pick_non_repeating_line(options, recent)
        game_state["recent_follow_ups"] = (recent + [follow_up])[-4:]

        return follow_up

    return ""


def make_library_guessing_game_audio_response(
    message,
    stage,
    response_mode,
    expects_response,
    game_complete,
    game_state,
    history,
    event_type="server_response",
    child_response="",
    next_event=None,
    pause_before_next_ms=None,
    next_url=None,
    redirect_after_ms=None,
    session_done=False
):
    message = calm_library_guessing_game_line(message, game_complete=game_complete)

    history.append({
        "event_type": event_type,
        "child_response": child_response,
        "librarian": message,
        "stage": stage,
        "response_mode": response_mode,
        "game_complete": game_complete,
        "session_done": session_done
    })

    game_state["stage"] = stage
    game_state["last_response_mode"] = response_mode
    game_state["game_complete"] = game_complete

    session["library_guessing_game_history"] = history[-20:]
    session["library_guessing_game_state"] = game_state
    session.modified = True

    audio_bytes = generate_library_guessing_voice_elevenlabs(message, game_complete=game_complete)
    audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

    payload = {
        "success": True,
        "message": message,
        "audio": f"data:audio/mpeg;base64,{audio_base64}",
        "stage": stage,
        "expects_response": expects_response,
        "response_mode": response_mode,
        "game_complete": game_complete,
        "session_done": session_done,
        "offer_next_game": False,
        "game_state": game_state
    }

    if next_event:
        payload["next_event"] = next_event

    if pause_before_next_ms is not None:
        payload["pause_before_next_ms"] = pause_before_next_ms

    if next_url:
        payload["next_url"] = next_url

    if redirect_after_ms is not None:
        payload["redirect_after_ms"] = redirect_after_ms

    return jsonify(payload)


def unlock_library_guessing_game_next_activity_for_user():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT activity_id, scene_id, activity_order
            FROM activity
            WHERE activity_name = ?
              AND is_active = 1
            LIMIT 1
        """, ("library_guessing_game",))

        current_activity = cursor.fetchone()

        if not current_activity:
            conn.close()
            return False

        cursor.execute("""
            SELECT activity_id
            FROM activity
            WHERE is_active = 1
              AND (
                scene_id > ?
                OR (scene_id = ? AND activity_order > ?)
              )
            ORDER BY scene_id ASC, activity_order ASC
            LIMIT 1
        """, (
            current_activity["scene_id"],
            current_activity["scene_id"],
            current_activity["activity_order"]
        ))

        next_activity = cursor.fetchone()

        if not next_activity:
            conn.close()
            return False

        next_activity_id = next_activity["activity_id"]

        cursor.execute("""
            INSERT OR IGNORE INTO progress (
                user_id,
                activity_id,
                is_unlocked,
                is_completed,
                words_spoken,
                minutes_spoken,
                active_minutes,
                time_spent_on_activity
            )
            VALUES (?, ?, 1, 0, 0, 0, 0, 0)
        """, (session["user_id"], next_activity_id))

        cursor.execute("""
            UPDATE progress
            SET is_unlocked = 1
            WHERE user_id = ? AND activity_id = ?
        """, (session["user_id"], next_activity_id))

        cursor.execute("""
            UPDATE users
            SET current_activity_id = ?
            WHERE user_id = ?
        """, (next_activity_id, session["user_id"]))

        conn.commit()
        conn.close()

        return True

    except Exception as e:
        print("Could not unlock next Library Guessing Game activity:", repr(e))
        return False


def make_library_guessing_game_correct_round_response(
    profile,
    game_state,
    history,
    event_type,
    child_response,
    base_message
):
    rounds_completed = int(game_state.get("rounds_completed", 0)) + 1
    rounds_completed = save_guessing_game_progress_for_user(rounds_completed)
    game_state["rounds_completed"] = rounds_completed
    game_state["game_complete"] = True

    if rounds_completed >= LIBRARY_GUESSING_GAME_MAX_ROUNDS:
        unlock_library_guessing_game_next_activity_for_user()

        message = (
            f"{base_message} "
            "That was our last one for today. "
            "This was a fun call. I'll see you next time. Bye."
        )

        return make_library_guessing_game_audio_response(
            message=message,
            stage="session_done",
            response_mode="none",
            expects_response=False,
            game_complete=True,
            game_state=game_state,
            history=history,
            event_type=event_type,
            child_response=child_response,
            next_url=url_for("dashboard"),
            redirect_after_ms=1800,
            session_done=True
        )

    if rounds_completed == LIBRARY_GUESSING_GAME_MAX_ROUNDS - 1:
        message = f"{base_message} Do you want to play one last round before we end the call?"
    else:
        message = f"{base_message} Do you want to play another round?"

    return make_library_guessing_game_audio_response(
        message=message,
        stage="round_choice",
        response_mode="round_choice_voice",
        expects_response=True,
        game_complete=True,
        game_state=game_state,
        history=history,
        event_type=event_type,
        child_response=child_response
    )


@app.route("/api/library-guessing-game/thinking-audio", methods=["GET"])
@csrf.exempt
@login_required
@limiter.limit("50 per minute")
def library_guessing_game_thinking_audio():
    import hashlib
    import random

    thinking_lines = ["Hmm."]

    avoid_raw = request.args.get("avoid", "")
    avoid_lines = {
        re.sub(r"\s+", " ", item).strip().lower()
        for item in avoid_raw.split("|")
        if item.strip()
    }

    fresh_lines = [
        line for line in thinking_lines
        if re.sub(r"\s+", " ", line).strip().lower() not in avoid_lines
    ]

    if not fresh_lines:
        fresh_lines = thinking_lines

    line = random.choice(fresh_lines)
    cache_dir = os.path.join(BASE_DIR, "static", "audio", "library_guessing_thinking")
    os.makedirs(cache_dir, exist_ok=True)

    voice_id = os.getenv("LIBRARIAN_VOICE_ID") or os.getenv("ELEVENLABS_VOICE_ID", "piI8Kku0DcvcL6TTSeQt")
    cache_key = f"library-guessing-thinking-v1:{voice_id}:{line}"
    filename = hashlib.md5(cache_key.encode("utf-8")).hexdigest() + ".mp3"
    filepath = os.path.join(cache_dir, filename)

    try:
        if not os.path.exists(filepath):
            audio_bytes = generate_library_guessing_voice_elevenlabs(line, thinking=True)

            with open(filepath, "wb") as f:
                f.write(audio_bytes)

        return jsonify({
            "success": True,
            "line": line,
            "audio_url": url_for("static", filename=f"audio/library_guessing_thinking/{filename}")
        })

    except Exception as e:
        print("Library Guessing Game thinking audio error:", repr(e))
        return jsonify({
            "success": False,
            "error": "Could not generate thinking audio"
        }), 500


@app.route("/api/library-guessing-game/message", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("30 per minute")
def library_guessing_game_message():
    data = request.get_json(silent=True) or {}

    event_type = re.sub(r"\s+", " ", str(data.get("event_type", "intro") or "intro")).strip()
    child_response = re.sub(r"\s+", " ", str(data.get("child_response", "") or "")).strip()
    previous_response_mode = re.sub(r"\s+", " ", str(data.get("response_mode", "none") or "none")).strip()

    allowed_events = {"intro", "restart", "first_prompt", "child_answer", "no_response"}

    if event_type not in allowed_events:
        return jsonify({"success": False, "error": "Invalid event_type"}), 400

    if event_type in {"intro", "restart"}:
        session.pop("library_guessing_game_history", None)
        session.pop("library_guessing_game_state", None)
        history = []
        game_state = get_library_guessing_game_default_state(rounds_completed=0)
        child_response = ""
        previous_response_mode = "none"
    else:
        history = session.get("library_guessing_game_history", [])
        game_state = session.get(
            "library_guessing_game_state",
            get_library_guessing_game_default_state()
        )

    profile = get_library_guessing_game_profile(game_state)

    if event_type in {"intro", "restart"}:
        intro_options = [
            "Hi, I'm the librarian. Let's play a guessing game. I'm thinking of something you can find at school. Ask me questions so you can guess what it is.",
            "Hi, I'm the librarian. I picked something you can find at school. Ask me questions, and when you know it, make a guess.",
            "Hi, I'm the librarian. I'm thinking of something from school. Your job is to ask questions and guess what it is.",
            "Hi, I'm the librarian. I picked one school object. Ask me questions to get clues, then guess what it is."
        ]

        message = pick_non_repeating_line(
            intro_options,
            [item.get("librarian", "") for item in history[-8:] if isinstance(item, dict)]
        )

        try:
            return make_library_guessing_game_audio_response(
                message=message,
                stage="intro",
                response_mode="none",
                expects_response=False,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type=event_type,
                child_response="",
                next_event="first_prompt",
                pause_before_next_ms=2200
            )

        except Exception as e:
            print("Library Guessing Game intro TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate Librarian intro"
            }), 500

    if event_type == "first_prompt":
        rounds_completed = int(game_state.get("rounds_completed", 0))

        if rounds_completed == LIBRARY_GUESSING_GAME_MAX_ROUNDS - 1:
            prompts = [
                "I picked the last one for today. Ask me a question so you can figure out what it is.",
                "Okay, this is our last one for today. Ask me a question, then try to guess when you know it.",
                "I am thinking of the last one now. What question will help you guess it?",
                "Last one for today. Ask your first question so you can start guessing."
            ]
        else:
            prompts = [
                "I picked one. Ask me a question so you can guess what it is.",
                "I am thinking of it now. What question will help you guess it?",
                "You can ask me something about it, like what it looks like or what it is used for.",
                "Ask your first question so you can figure out what it is."
            ]

        recent_lines = [
            item.get("librarian", "")
            for item in history[-8:]
            if isinstance(item, dict)
        ]

        message = pick_non_repeating_line(prompts, recent_lines)

        try:
            return make_library_guessing_game_audio_response(
                message=message,
                stage="asking",
                response_mode="open_hint",
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type=event_type,
                child_response=child_response
            )

        except Exception as e:
            print("Library Guessing Game first prompt TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate first prompt"
            }), 500

    if previous_response_mode in {"round_choice", "round_choice_voice"} and event_type in {"child_answer", "no_response"}:
        rounds_completed = int(game_state.get("rounds_completed", 0))

        if event_type == "no_response":
            choice = "unclear"
        else:
            choice = classify_library_guessing_game_round_choice(child_response, offer_next_game=False)

        if choice == "same_game":
            previous_object = game_state.get("secret_object")
            used_objects = list(game_state.get("used_objects", []))

            if previous_object and previous_object not in used_objects:
                used_objects.append(previous_object)

            new_game_state = get_library_guessing_game_default_state(
                rounds_completed=rounds_completed,
                used_objects=used_objects
            )

            if rounds_completed == LIBRARY_GUESSING_GAME_MAX_ROUNDS - 1:
                replay_prompts = [
                    "Okay. Let's play one more round before we end our call today. I picked something new you can find at school.",
                    "Okay. One more round for today. I have a new one in mind.",
                    "Sure. This will be our last one today. I picked something new."
                ]
            else:
                replay_prompts = [
                    "Okay. I picked something new you can find at school.",
                    "Sure. I have a different one in mind now.",
                    "Okay. New one. Ask me questions so you can guess it.",
                    "Let's do another one. I picked something different."
                ]

            recent_prompts = game_state.get("recent_round_prompts", [])
            message = pick_non_repeating_line(replay_prompts, recent_prompts)
            new_game_state["recent_round_prompts"] = (recent_prompts + [message])[-4:]

            try:
                return make_library_guessing_game_audio_response(
                    message=message,
                    stage="intro",
                    response_mode="none",
                    expects_response=False,
                    game_complete=False,
                    game_state=new_game_state,
                    history=[],
                    event_type="replay",
                    child_response=child_response,
                    next_event="first_prompt",
                    pause_before_next_ms=1600
                )

            except Exception as e:
                print("Library Guessing Game replay TTS error:", repr(e))
                return jsonify({
                    "success": False,
                    "error": "Could not generate replay response"
                }), 500

        if choice == "stop":
            message = "Okay. We can stop here. Thanks for playing Library Guessing Game with me."

            try:
                return make_library_guessing_game_audio_response(
                    message=message,
                    stage="session_done",
                    response_mode="none",
                    expects_response=False,
                    game_complete=False,
                    game_state=game_state,
                    history=history,
                    event_type="stop",
                    child_response=child_response,
                    session_done=True
                )

            except Exception as e:
                print("Library Guessing Game stop TTS error:", repr(e))
                return jsonify({
                    "success": False,
                    "error": "Could not end the game"
                }), 500

        message = "That's okay. Do you want to play another round?"

        try:
            return make_library_guessing_game_audio_response(
                message=message,
                stage="round_choice",
                response_mode="round_choice_voice",
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type="choice_clarification",
                child_response=child_response
            )

        except Exception as e:
            print("Library Guessing Game choice clarification TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate choice response"
            }), 500

    if event_type == "no_response" or is_library_guessing_unclear_or_silent(child_response):
        game_state["unclear_or_silent_count"] = int(game_state.get("unclear_or_silent_count", 0)) + 1
        game_state["unclear_streak"] = int(game_state.get("unclear_streak", 0)) + 1

        options = [
            "That's okay. You can ask if it is big or small.",
            "No worries. You can ask what it is used for.",
            "That's okay. You can ask where you might find it in school.",
            "No problem. You can ask for a hint whenever you want."
        ]

        recent_lines = [item.get("librarian", "") for item in history[-8:] if isinstance(item, dict)]
        message = pick_non_repeating_line(options, recent_lines)

        try:
            return make_library_guessing_game_audio_response(
                message=message,
                stage="support",
                response_mode="open_hint",
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type=event_type,
                child_response=child_response
            )

        except Exception as e:
            print("Library Guessing Game no-response TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate support response"
            }), 500

    if is_library_guessing_hint_request(child_response):
        hint = get_library_guessing_game_hint(game_state)
        follow_up = get_library_guessing_game_follow_up_after_answer(game_state)
        message = f"Here's a hint. {hint} {follow_up}".strip()

        try:
            return make_library_guessing_game_audio_response(
                message=message,
                stage="hint",
                response_mode="open_hint",
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type="hint_request",
                child_response=child_response
            )

        except Exception as e:
            print("Library Guessing Game hint TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate hint"
            }), 500

    if is_library_guessing_direct_guess(child_response):
        guessed_object = get_library_guessing_named_object(child_response)

        if guessed_object:
            secret_object = game_state.get("secret_object")

            if guessed_object == secret_object:
                base_message = f"Yes, it is a {profile['display']}. You got it."

                try:
                    return make_library_guessing_game_correct_round_response(
                        profile=profile,
                        game_state=game_state,
                        history=history,
                        event_type="correct_guess",
                        child_response=child_response,
                        base_message=base_message
                    )

                except Exception as e:
                    print("Library Guessing Game direct correct TTS error:", repr(e))
                    return jsonify({
                        "success": False,
                        "error": "Could not generate correct response"
                    }), 500

            game_state.setdefault("wrong_guesses", []).append(guessed_object)
            game_state["wrong_guess_count"] = int(game_state.get("wrong_guess_count", 0)) + 1

            base_options = [
                f"Not quite, it is not a {LIBRARY_GUESSING_GAME_OBJECT_PROFILES[guessed_object]['display']}.",
                f"Good guess, but it is not a {LIBRARY_GUESSING_GAME_OBJECT_PROFILES[guessed_object]['display']}.",
                "Not that one.",
                f"It is not a {LIBRARY_GUESSING_GAME_OBJECT_PROFILES[guessed_object]['display']}."
            ]

            recent_lines = [item.get("librarian", "") for item in history[-8:] if isinstance(item, dict)]
            base_message = pick_non_repeating_line(base_options, recent_lines)
            follow_up = get_library_guessing_game_follow_up_after_answer(game_state)
            message = f"{base_message} {follow_up}".strip()

            try:
                return make_library_guessing_game_audio_response(
                    message=message,
                    stage="wrong_guess",
                    response_mode="open_hint",
                    expects_response=True,
                    game_complete=False,
                    game_state=game_state,
                    history=history,
                    event_type="wrong_guess",
                    child_response=child_response
                )

            except Exception as e:
                print("Library Guessing Game wrong guess TTS error:", repr(e))
                return jsonify({
                    "success": False,
                    "error": "Could not generate wrong guess response"
                }), 500

    if is_library_guessing_question(child_response):
        answer = answer_library_guessing_question(child_response, game_state)

        if answer["type"] == "correct_guess":
            base_message = answer["message"]

            try:
                return make_library_guessing_game_correct_round_response(
                    profile=profile,
                    game_state=game_state,
                    history=history,
                    event_type="correct_guess",
                    child_response=child_response,
                    base_message=base_message
                )

            except Exception as e:
                print("Library Guessing Game question correct TTS error:", repr(e))
                return jsonify({
                    "success": False,
                    "error": "Could not generate correct response"
                }), 500

        if answer["type"] == "wrong_guess":
            wrong_guess = answer.get("wrong_guess")

            if wrong_guess:
                game_state.setdefault("wrong_guesses", []).append(wrong_guess)

            game_state["wrong_guess_count"] = int(game_state.get("wrong_guess_count", 0)) + 1
            base_message = answer["message"]
            follow_up = get_library_guessing_game_follow_up_after_answer(game_state)
            message = f"{base_message} {follow_up}".strip()

            try:
                return make_library_guessing_game_audio_response(
                    message=message,
                    stage="wrong_guess",
                    response_mode="open_hint",
                    expects_response=True,
                    game_complete=False,
                    game_state=game_state,
                    history=history,
                    event_type="wrong_guess",
                    child_response=child_response
                )

            except Exception as e:
                print("Library Guessing Game question wrong TTS error:", repr(e))
                return jsonify({
                    "success": False,
                    "error": "Could not generate wrong guess response"
                }), 500

        if answer.get("question_answered"):
            game_state["questions_asked"] = int(game_state.get("questions_asked", 0)) + 1
            game_state["comfortable_question_count"] = int(game_state.get("comfortable_question_count", 0)) + 1
            game_state["unclear_streak"] = 0

            question_key = library_guessing_question_key(child_response)

            if question_key:
                game_state.setdefault("asked_questions", []).append(question_key)
                game_state["asked_questions"] = game_state["asked_questions"][-12:]

            remember_library_guessing_question_topic(child_response, game_state)
            answer_message = maybe_add_library_good_question_prefix(answer["message"], game_state)
            follow_up = get_library_guessing_game_follow_up_after_answer(game_state)
            message = f"{answer_message} {follow_up}".strip()

            try:
                return make_library_guessing_game_audio_response(
                    message=message,
                    stage="answering",
                    response_mode="open_hint",
                    expects_response=True,
                    game_complete=False,
                    game_state=game_state,
                    history=history,
                    event_type=event_type,
                    child_response=child_response
                )

            except Exception as e:
                print("Library Guessing Game answer TTS error:", repr(e))
                return jsonify({
                    "success": False,
                    "error": "Could not answer question"
                }), 500

        try:
            return make_library_guessing_game_audio_response(
                message=answer["message"],
                stage="support",
                response_mode="open_hint",
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type=event_type,
                child_response=child_response
            )

        except Exception as e:
            print("Library Guessing Game support answer TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate support"
            }), 500

    named_object = get_library_guessing_named_object(child_response)

    if named_object:
        secret_object = game_state.get("secret_object")

        if named_object == secret_object:
            base_message = f"Yes, it is a {profile['display']}. You got it."

            try:
                return make_library_guessing_game_correct_round_response(
                    profile=profile,
                    game_state=game_state,
                    history=history,
                    event_type="correct_guess",
                    child_response=child_response,
                    base_message=base_message
                )

            except Exception as e:
                print("Library Guessing Game named correct TTS error:", repr(e))
                return jsonify({
                    "success": False,
                    "error": "Could not generate correct response"
                }), 500

        game_state.setdefault("wrong_guesses", []).append(named_object)
        game_state["wrong_guess_count"] = int(game_state.get("wrong_guess_count", 0)) + 1
        base_message = f"Not quite, it is not a {LIBRARY_GUESSING_GAME_OBJECT_PROFILES[named_object]['display']}."
        follow_up = get_library_guessing_game_follow_up_after_answer(game_state)
        message = f"{base_message} {follow_up}".strip()

        try:
            return make_library_guessing_game_audio_response(
                message=message,
                stage="wrong_guess",
                response_mode="open_hint",
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type="wrong_guess",
                child_response=child_response
            )

        except Exception as e:
            print("Library Guessing Game named wrong TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate wrong guess response"
            }), 500

    game_state["comfortable_question_count"] = int(game_state.get("comfortable_question_count", 0)) + 1

    fallback_lines = [
        "You can ask me a yes or no question about it.",
        "You can ask about the thing I'm thinking of.",
        "You can ask for a hint whenever you want.",
        "You can make a guess whenever you're ready."
    ]

    recent_lines = [item.get("librarian", "") for item in history[-8:] if isinstance(item, dict)]
    message = pick_non_repeating_line(fallback_lines, recent_lines)

    try:
        return make_library_guessing_game_audio_response(
            message=message,
            stage="support",
            response_mode="open_hint",
            expects_response=True,
            game_complete=False,
            game_state=game_state,
            history=history,
            event_type=event_type,
            child_response=child_response
        )

    except Exception as e:
        print("Library Guessing Game fallback TTS error:", repr(e))
        return jsonify({
            "success": False,
            "error": "Could not generate fallback response"
        }), 500


@app.route("/api/library-guessing-game/transcribe", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("20 per minute")
def library_guessing_game_transcribe():
    if "audio" not in request.files:
        return jsonify({
            "success": False,
            "error": "Missing audio"
        }), 400

    audio_file = request.files["audio"]

    try:
        import io

        audio_bytes = audio_file.read()

        if not audio_bytes:
            return jsonify({
                "success": False,
                "error": "Empty audio file"
            }), 400

        file_obj = io.BytesIO(audio_bytes)
        file_obj.name = "library-guessing-response.webm"

        transcript = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=file_obj
        )

        text = transcript.text.strip()

        print("LIBRARY GUESSING GAME TRANSCRIPT:", text)

        return jsonify({
            "success": True,
            "text": text
        })

    except Exception as e:
        print("Library Guessing Game transcription error:", repr(e))
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/parent-academy")
@login_required
def parent_academy():
    return render_template(
        "parent_academy.html",
        active_page="parent_academy",
        parent=session["parent_name"],
        child=session["child_name"],
        profile_icon=session.get("profile_icon", "profileicon.png"),
        has_seen_tour=get_has_seen_tour_for_user(session["user_id"])
    )

def generate_gym_teacher_voice_elevenlabs(text):
    voice_id = os.getenv("GYM_TEACHER_VOICE_ID")

    if not voice_id:
        voice_id = os.getenv("ELEVENLABS_VOICE_ID", "piI8Kku0DcvcL6TTSeQt")

    response = eleven_client.text_to_speech.convert(
        voice_id=voice_id,
        text=text,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
        voice_settings={
            "stability": 0.84,
            "similarity_boost": 0.92,
            "style": 0.16,
            "use_speaker_boost": False
        }
    )

    return b"".join(response)


@app.route("/api/exercise-detective/message", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("30 per minute")
def exercise_detective_message():
    data = request.get_json(silent=True) or {}

    event_type = data.get("event_type", "intro")
    child_response = data.get("child_response", "").strip()
    response_mode = data.get("response_mode", "none")

    child_name = session.get("child_name", "there")

    if event_type == "restart":
        session.pop("exercise_detective_history", None)
        session.pop("exercise_detective_state", None)

    history = session.get("exercise_detective_history", [])

    game_state = session.get("exercise_detective_state", {
        "stage": "intro",
        "questions_asked": 0,
        "comfortable_answer_count": 0,
        "unclear_or_silent_count": 0,
        "question_history": [],
        "known_clues": [],
        "rejected_guesses": [],
        "possible_guess": None,
        "game_complete": False
    })

    system_prompt = """
You are a warm, friendly gym teacher on a video call with a young child.

You are playing Exercise Detective.

The child silently chooses or acts out one simple exercise or movement.
The gym teacher pretends to close his eyes, then asks gentle questions and uses clues to guess the exercise.

Core game:
The child thinks of or does an exercise.
The gym teacher asks questions.
The child answers or gives hints.
The gym teacher guesses the exercise when there are enough clues.

Exercise examples:
jumping jacks, running in place, hopping, stretching, toe touches, squats, arm circles, marching, balancing on one foot, dancing, push-ups, sit-ups, jumping, skipping, yoga pose.

Core goal:
Create a natural back-and-forth conversation around movement.
The child should feel like they are helping the gym teacher solve a fun mystery.

Hard rules:
- Never mention selective mutism, anxiety, therapy, treatment, exposure, stages, progress, confidence, or bravery.
- Never pressure the child to speak.
- Never say "use your words."
- Never sound disappointed.
- Never overpraise.
- Never make the child feel evaluated.
- Keep attention on the exercise detective game.
- Ask only one question at a time.
- Do not repeat previous questions or repeat the same question family inside one round.
- Use the clues already given as hard constraints. If the child says more than four legs, never guess a four-legged animal.
- If the child gives no answer, an unclear answer, or seems stuck, make the next question easier.
- If the child answers comfortably several times, you may gently increase verbal demand.
- Do not ask the child to do unsafe or intense exercise.
- Keep each spoken line to 1-3 short sentences.

Voice style:
Warm, playful, energetic but not hyper.
Friendly gym teacher.
Not babyish. Not too loud. Not teacher-scolding.

Intro:
For intro or restart, say something like:
"Okay, I'll close my eyes while you pick an exercise. You can do the move, answer my questions, or give me hints, and I'll try to guess it. Ready?"

Good question areas:
- Does it use your arms?
- Does it use your legs?
- Are you jumping?
- Are you standing still?
- Are you moving fast or slow?
- Does it happen on the floor?
- Is it a stretch?
- Is it something from gym class?
- Does it make your heart beat faster?
- Is it like running, jumping, or stretching?

Progression logic:
1. intro:
   Explain the premise simply.
2. yes_no:
   Ask concrete yes/no questions.
   Examples:
   "Do you use your arms?"
   "Are your feet leaving the floor?"
3. forced_choice:
   Ask two-option questions.
   Examples:
   "Is it more like jumping or stretching?"
   "Are you moving fast or slow?"
4. one_word:
   Ask for one simple word.
   Examples:
   "What body part moves most?"
   "What is one clue?"
5. short_phrase:
   Ask for a tiny hint.
   Examples:
   "Tell me one tiny clue."
   "What does the exercise look like?"
6. guess:
   Guess the exercise when there are enough clues.

Silence or stuck handling:
If the child says nothing or gives an unclear response:
- Do not say "I could not hear you."
- Do not call attention to silence.
- Offer an easier path.

Examples:
"Let's make it easy. Are you using your arms?"
"I'll ask a tiny question. Are you jumping?"
"You can say yes or no."
"Is it more like running or stretching?"

Output JSON only:
{
  "message": "the gym teacher's spoken line",
  "stage": "intro | yes_no | forced_choice | one_word | short_phrase | guess | support | complete",
  "expects_response": true,
  "response_mode": "none | yes_no | choice | one_word | short_phrase",
  "is_question": true,
  "question_text": "the question asked, or null",
  "game_complete": false,
  "state_update": {
    "comfortable_answer_delta": 0,
    "unclear_or_silent_delta": 0,
    "questions_asked_increment": 0,
    "known_clue": null,
    "possible_guess": null,
    "rejected_guess": null
  }
}
"""

    user_prompt = f"""
Child name:
{child_name}

Current game state:
{game_state}

Recent history:
{history[-12:]}

New event:
event_type: {event_type}
child_response: {child_response}
previous_response_mode: {response_mode}

Interpretation help:
- If event_type is intro or restart, start the game gently.
- If child_response is empty, unclear, "I don't know", or silence, count it as unclear_or_silent.
- If child_response is a clear answer to the gym teacher's last question, count it as comfortable.
- If the gym teacher guessed and the child says no, add the guess to rejected_guesses.
- If the gym teacher guessed and the child says yes, respond warmly and finish the round.
- Update the state based on the child response before choosing the next line.
- Ask a useful next question that narrows down the exercise.
- Do not repeat any question in question_history.
- If there are not enough clues, do not guess yet.
- If there are enough clues, make one playful guess.
- Keep exercises familiar and safe for young children.

Generate the next gym teacher line now.
"""

    try:
        text_response = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )

        raw = text_response.output_text.strip()

        import json

        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {
                "message": raw.replace('"', ""),
                "stage": game_state.get("stage", "yes_no"),
                "expects_response": True,
                "response_mode": "yes_no",
                "is_question": True,
                "question_text": raw.replace('"', ""),
                "game_complete": False,
                "state_update": {
                    "comfortable_answer_delta": 0,
                    "unclear_or_silent_delta": 0,
                    "questions_asked_increment": 1,
                    "known_clue": None,
                    "possible_guess": None,
                    "rejected_guess": None
                }
            }

        message = parsed.get("message", "").strip().replace('"', "")

        if not message:
            message = "I'm ready, exercise detective mode is on. Are you using your arms?"

        state_update = parsed.get("state_update", {}) or {}

        game_state["stage"] = parsed.get("stage", game_state.get("stage", "yes_no"))

        game_state["comfortable_answer_count"] = max(
            0,
            int(game_state.get("comfortable_answer_count", 0))
            + int(state_update.get("comfortable_answer_delta", 0))
        )

        game_state["unclear_or_silent_count"] = max(
            0,
            int(game_state.get("unclear_or_silent_count", 0))
            + int(state_update.get("unclear_or_silent_delta", 0))
        )

        game_state["questions_asked"] = int(game_state.get("questions_asked", 0)) + int(
            state_update.get("questions_asked_increment", 0)
        )

        if state_update.get("known_clue"):
            game_state.setdefault("known_clues", []).append(state_update["known_clue"])

        if state_update.get("possible_guess"):
            game_state["possible_guess"] = state_update["possible_guess"]

        if state_update.get("rejected_guess"):
            game_state.setdefault("rejected_guesses", []).append(state_update["rejected_guess"])

        question_text = parsed.get("question_text")
        if parsed.get("is_question") and question_text:
            game_state.setdefault("question_history", []).append({
                "question": question_text,
                "stage": parsed.get("stage"),
                "response_mode": parsed.get("response_mode")
            })

        game_complete = bool(parsed.get("game_complete", False))
        game_state["game_complete"] = game_complete

        history.append({
            "event_type": event_type,
            "child_response": child_response,
            "gym_teacher": message,
            "stage": parsed.get("stage"),
            "response_mode": parsed.get("response_mode"),
            "game_complete": game_complete
        })

        session["exercise_detective_history"] = history[-20:]
        session["exercise_detective_state"] = game_state
        session.modified = True

        audio_bytes = generate_gym_teacher_voice_elevenlabs(message)
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

        return jsonify({
            "success": True,
            "message": message,
            "audio": f"data:audio/mpeg;base64,{audio_base64}",
            "stage": parsed.get("stage"),
            "expects_response": parsed.get("expects_response", True) and not game_complete,
            "response_mode": parsed.get("response_mode", "yes_no"),
            "game_complete": game_complete,
            "game_state": game_state
        })

    except Exception as e:
        print("Exercise Detective AI error:", e)
        return jsonify({
            "success": False,
            "error": "Could not generate gym teacher response"
        }), 500


@app.route("/api/exercise-detective/transcribe", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("20 per minute")
def exercise_detective_transcribe():
    if "audio" not in request.files:
        return jsonify({
            "success": False,
            "error": "Missing audio"
        }), 400

    audio_file = request.files["audio"]

    try:
        import io

        audio_bytes = audio_file.read()

        if not audio_bytes:
            return jsonify({
                "success": False,
                "error": "Empty audio file"
            }), 400

        file_obj = io.BytesIO(audio_bytes)
        file_obj.name = "child-response.webm"

        transcript = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=file_obj
        )

        text = transcript.text.strip()

        print("EXERCISE DETECTIVE TRANSCRIPT:", text)

        return jsonify({
            "success": True,
            "text": text
        })

    except Exception as e:
        print("Exercise Detective transcription error:", repr(e))
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    
PARENT_ACADEMY_ARTICLES = {
    "what-is-selective-mutism": {
        "title": "What Is Selective Mutism?",
        "category": "Understanding Selective Mutism",
        "read_time": "7 min read",
        "evidence": "High",
        "sources_reviewed": "7",
        "summary": "Selective mutism is a childhood anxiety disorder where a child can speak comfortably in some situations but consistently cannot speak in others, usually because anxiety blocks access to speech in specific social settings.",
        "template": "parent_academy_articles/what_is_selective_mutism.html"
    },
    "is-selective-mutism-just-shyness": {
        "title": "Is Selective Mutism Just Shyness?",
        "category": "Understanding Selective Mutism",
        "read_time": "6 min read",
        "evidence": "High",
        "sources_reviewed": "4",
        "summary": "Selective mutism is not simply extreme shyness. Shyness is a temperament trait, while selective mutism is an anxiety disorder that can interfere with a child’s ability to speak in specific situations.",
        "template": "parent_academy_articles/is_selective_mutism_just_shyness.html"
    },
    "the-science-of-anxiety": {
        "title": "The Science of Anxiety",
        "category": "Understanding Selective Mutism",
        "read_time": "6 min read",
        "evidence": "High",
        "sources_reviewed": "5",
        "summary": "When speaking feels threatening, a child’s nervous system may activate a stress response. For some children, this leads to freezing, making speech feel temporarily inaccessible even when they know what they want to say.",
        "template": "parent_academy_articles/the_science_of_anxiety.html"
    },
    "what-causes-selective-mutism": {
        "title": "What Causes Selective Mutism?",
        "category": "Understanding Selective Mutism",
        "read_time": "6 min read",
        "evidence": "High",
        "sources_reviewed": "4",
        "summary": "Selective mutism is usually understood as an anxiety-related condition influenced by several factors, including temperament, genetics, environment, and learned avoidance patterns.",
        "template": "parent_academy_articles/what_causes_selective_mutism.html"
    },

    "why-does-my-child-freeze": {
        "title": "Why Does My Child Freeze?",
        "category": "Understanding Selective Mutism",
        "read_time": "6 min read",
        "evidence": "High",
        "sources_reviewed": "5",
        "summary": "Many children with selective mutism experience a freeze response where anxiety temporarily overwhelms their ability to communicate, even when they know exactly what they want to say.",
        "template": "parent_academy_articles/why_does_my_child_freeze.html"
    },

    "why-home-but-not-school": {
        "title": "Why Home but Not School?",
        "category": "Understanding Selective Mutism",
        "read_time": "6 min read",
        "evidence": "High",
        "sources_reviewed": "5",
        "summary": "Many children with selective mutism speak comfortably at home but become silent at school because different environments create very different levels of anxiety and perceived social pressure.",
        "template": "parent_academy_articles/why_home_but_not_school.html"
    },
    "why-does-my-child-whisper": {
        "title": "Why Does My Child Whisper?",
        "category": "Understanding Your Child",
        "read_time": "4 min read",
        "evidence": "Moderate",
        "sources_reviewed": "3",
        "summary": "Whispering can sometimes be a bridge between silence and full speech. It may show that communication is possible, but still feels safer at a lower intensity.",
        "template": "parent_academy_articles/why_does_my_child_whisper.html"
    },
    "should-i-answer-for-my-child": {
        "title": "Should I Answer For My Child?",
        "category": "Popular Questions",
        "read_time": "5 min read",
        "evidence": "Moderate",
        "sources_reviewed": "4",
        "summary": "Answering for your child can sometimes reduce immediate stress, but doing it automatically may also prevent small speaking opportunities. The goal is to support without taking over.",
        "template": "parent_academy_articles/should_i_answer_for_my_child.html"
    },
    "why-only-certain-people": {
    "title": "Why Only Certain People?",
    "category": "Understanding Your Child",
    "read_time": "6 min read",
    "evidence": "High",
    "sources_reviewed": "5",
    "summary": "Some children with selective mutism can speak to certain people but not others because speech becomes linked to safety, familiarity, predictability, and past speaking experiences.",
    "template": "parent_academy_articles/why_only_certain_people.html"
},

"why-one-teacher-but-not-another": {
    "title": "Why One Teacher But Not Another?",
    "category": "Understanding Your Child",
    "read_time": "6 min read",
    "evidence": "High",
    "sources_reviewed": "5",
    "summary": "A child may speak to one teacher but not another because subtle differences in predictability, pressure, relationship history, and classroom context can strongly affect anxiety.",
    "template": "parent_academy_articles/why_one_teacher_but_not_another.html"
},

"why-is-it-harder-around-other-children": {
    "title": "Why Is It Harder Around Other Children?",
    "category": "Understanding Your Child",
    "read_time": "6 min read",
    "evidence": "High",
    "sources_reviewed": "5",
    "summary": "Speaking around other children can be harder because peers add social attention, unpredictability, comparison, and fear of being judged or noticed.",
    "template": "parent_academy_articles/why_is_it_harder_around_other_children.html"
},

"why-avoid-eye-contact": {
    "title": "Why Avoid Eye Contact?",
    "category": "Understanding Your Child",
    "read_time": "5 min read",
    "evidence": "Moderate",
    "sources_reviewed": "5",
    "summary": "Avoiding eye contact can be a coping strategy that lowers the intensity of social interaction. For some children, looking away helps them listen, regulate anxiety, and communicate with less pressure.",
    "template": "parent_academy_articles/why_avoid_eye_contact.html"
},

"why-do-they-seem-comfortable-but-not-speak": {
    "title": "Why Do They Seem Comfortable But Not Speak?",
    "category": "Understanding Your Child",
    "read_time": "6 min read",
    "evidence": "High",
    "sources_reviewed": "5",
    "summary": "Some children with selective mutism look calm on the outside while still experiencing internal anxiety. The silence itself may be the symptom, even when distress is not obvious.",
    "template": "parent_academy_articles/why_do_they_seem_comfortable_but_not_speak.html"
},

"why-did-my-child-stop-speaking-again": {
    "title": "Why Did My Child Stop Speaking Again?",
    "category": "Understanding Your Child",
    "read_time": "6 min read",
    "evidence": "High",
    "sources_reviewed": "5",
    "summary": "Setbacks are common in selective mutism and do not necessarily mean progress is lost. Often, anxiety has increased and the child temporarily needs easier communication steps to regain access to speech.",
    "template": "parent_academy_articles/why_did_my_child_stop_speaking_again.html"
}, 

"why-speak-less-in-new-places": {
    "title": "Why Speak Less In New Places?",
    "category": "Understanding Your Child",
    "read_time": "6 min read",
    "evidence": "High",
    "sources_reviewed": "5",
    "summary": "Unfamiliar environments can make communication harder because new places increase uncertainty, reduce safety cues, and make speech feel less predictable.",
    "template": "parent_academy_articles/why_speak_less_in_new_places.html"
},

"why-use-gestures-instead-of-words": {
    "title": "Why Use Gestures Instead of Words?",
    "category": "Understanding Your Child",
    "read_time": "6 min read",
    "evidence": "High",
    "sources_reviewed": "5",
    "summary": "Gestures can be meaningful communication when speech feels too difficult. They often function as lower-pressure steps that can be shaped gradually toward speech.",
    "template": "parent_academy_articles/why_use_gestures_instead_of_words.html"
},

"why-do-they-speak-through-me": {
    "title": "Why Do They Speak Through Me?",
    "category": "Understanding Your Child",
    "read_time": "6 min read",
    "evidence": "High",
    "sources_reviewed": "5",
    "summary": "Some children rely on parents as a safe communication bridge. The goal is to support communication while gradually transferring small pieces back to the child.",
    "template": "parent_academy_articles/why_do_they_speak_through_me.html"
},

"why-do-they-shut-down-or-get-upset": {
    "title": "Why Do They Shut Down or Get Upset?",
    "category": "Understanding Your Child",
    "read_time": "6 min read",
    "evidence": "High",
    "sources_reviewed": "5",
    "summary": "Overwhelm can show up as silence, frustration, refusal, avoidance, tears, or shutdown when communication demands exceed what a child can manage in the moment.",
    "template": "parent_academy_articles/why_do_they_shut_down_or_get_upset.html"
},

"why-are-mornings-before-school-so-hard": {
    "title": "Why Are Mornings Before School So Hard?",
    "category": "Understanding Your Child",
    "read_time": "6 min read",
    "evidence": "High",
    "sources_reviewed": "5",
    "summary": "Mornings can be difficult because anticipatory anxiety may build before the child even reaches school, especially when they expect social or speaking demands.",
    "template": "parent_academy_articles/why_are_mornings_before_school_so_hard.html"
},
"how-can-i-help-my-child-at-school": {
    "title": "How Can I Help My Child at School?",
    "category": "Popular Questions",
    "read_time": "7 min read",
    "evidence": "High",
    "sources_reviewed": "5",
    "summary": "School support works best when parents and staff create a coordinated plan that lowers pressure while gradually building successful communication steps.",
    "template": "parent_academy_articles/how_can_i_help_my_child_at_school.html"
},

"is-it-okay-to-reward-my-child-for-speaking": {
    "title": "Is It Okay to Reward My Child for Speaking?",
    "category": "Popular Questions",
    "read_time": "6 min read",
    "evidence": "High",
    "sources_reviewed": "5",
    "summary": "Rewards can help when they reinforce small planned communication steps, but they can backfire when they feel like pressure, bribery, or performance.",
    "template": "parent_academy_articles/is_it_okay_to_reward_my_child_for_speaking.html"
},

"should-i-answer-for-my-child": {
    "title": "Should I Answer For My Child?",
    "category": "Popular Questions",
    "read_time": "6 min read",
    "evidence": "High",
    "sources_reviewed": "5",
    "summary": "Answering for your child can protect them when they are overwhelmed, but automatic answering can also reduce opportunities for small communication steps.",
    "template": "parent_academy_articles/should_i_answer_for_my_child.html"
},

"what-if-my-child-refuses-therapy": {
    "title": "What If My Child Refuses Therapy?",
    "category": "Popular Questions",
    "read_time": "7 min read",
    "evidence": "High",
    "sources_reviewed": "5",
    "summary": "Therapy refusal often means therapy feels like another speaking demand. Support can begin with parent coaching, school planning, and low-pressure participation.",
    "template": "parent_academy_articles/what_if_my_child_refuses_therapy.html"
},
"can-my-child-grow-out-of-selective-mutism": {
    "title": "Can My Child Grow Out of Selective Mutism?",
    "category": "Popular Questions",
    "read_time": "6 min read",
    "evidence": "High",
    "sources_reviewed": "5",
    "summary": "Some children improve over time, but selective mutism should not be treated as something a child will definitely outgrow without support.",
    "template": "parent_academy_articles/can_my_child_grow_out_of_selective_mutism.html"
},

"should-i-force-my-child-to-speak": {
    "title": "Should I Force My Child to Speak?",
    "category": "Popular Questions",
    "read_time": "6 min read",
    "evidence": "High",
    "sources_reviewed": "5",
    "summary": "Forcing speech usually increases anxiety. A better approach is using small, planned, low-pressure communication steps that help the child experience success.",
    "template": "parent_academy_articles/should_i_force_my_child_to_speak.html"
},

"is-whispering-a-good-sign": {
    "title": "Is Whispering a Good Sign?",
    "category": "Popular Questions",
    "read_time": "5 min read",
    "evidence": "Moderate",
    "sources_reviewed": "5",
    "summary": "Whispering can be a meaningful bridge between silence and full speech, but it should be gently shaped over time toward more flexible communication.",
    "template": "parent_academy_articles/is_whispering_a_good_sign.html"
},

"what-should-i-tell-relatives-about-sm": {
    "title": "What Should I Tell Relatives About SM?",
    "category": "Popular Questions",
    "read_time": "6 min read",
    "evidence": "High",
    "sources_reviewed": "5",
    "summary": "Relatives can support a child with selective mutism by understanding that silence is anxiety-based, not rude or defiant, and by reducing pressure while connection builds.",
    "template": "parent_academy_articles/what_should_i_tell_relatives_about_sm.html"
}, "how-to-reduce-speaking-pressure": {
    "title": "How to Reduce Speaking Pressure",
    "category": "Parent Strategies",
    "read_time": "6 min read",
    "evidence": "High",
    "sources_reviewed": "5",
    "summary": "Reducing speaking pressure means making communication feel safer, smaller, and less like a performance while still building toward gradual progress.",
    "template": "parent_academy_articles/how_to_reduce_speaking_pressure.html"
},

"what-parents-should-avoid": {
    "title": "What Parents Should Avoid",
    "category": "Parent Strategies",
    "read_time": "6 min read",
    "evidence": "High",
    "sources_reviewed": "5",
    "summary": "Certain well-meaning responses, like forcing speech, repeated prompting, over-rescuing, or public praise, can accidentally increase anxiety and maintain avoidance.",
    "template": "parent_academy_articles/what_parents_should_avoid.html"
},

"praise-vs-pressure": {
    "title": "Praise vs Pressure",
    "category": "Parent Strategies",
    "read_time": "6 min read",
    "evidence": "High",
    "sources_reviewed": "5",
    "summary": "Praise can support progress when it is calm and effort-focused, but it can become pressure when it puts a spotlight on the child’s speech.",
    "template": "parent_academy_articles/praise_vs_pressure.html"
}, 

"creating-speaking-opportunities": {
    "title": "Creating Speaking Opportunities",
    "category": "Parent Strategies",
    "read_time": "6 min read",
    "evidence": "High",
    "sources_reviewed": "5",
    "summary": "Low-pressure routines, games, and daily moments that support communication practice.",
    "template": "parent_academy_articles/creating_speaking_opportunities.html"
},

"handling-setbacks": {
    "title": "Handling Setbacks",
    "category": "Parent Strategies",
    "read_time": "5 min read",
    "evidence": "High",
    "sources_reviewed": "5",
    "summary": "How to respond when progress slows, stops, or temporarily reverses.",
    "template": "parent_academy_articles/handling_setbacks.html"
},

}

PARENT_ACADEMY_CATEGORIES = {
    "understanding-selective-mutism": {
        "title": "Understanding Selective Mutism",
        "subtitle": "Foundational guides to help parents understand what selective mutism is, why it happens, and why it changes across settings.",
        "articles": [
            {"slug": "what-is-selective-mutism", "image": "sm_brain_question.png", "art": "art-pink"},
            {"slug": "is-selective-mutism-just-shyness", "image": "sm_shyness.png", "art": "art-green"},
            {"slug": "what-causes-selective-mutism", "image": "sm_causes.png", "art": "art-peach"},
            {"slug": "the-science-of-anxiety", "image": "sm_anxiety.png", "art": "art-blue"},
            {"slug": "why-home-but-not-school", "image": "sm_home_school.png", "art": "art-rose"},
            {"slug": "why-does-my-child-freeze", "image": "sm_freeze.png", "art": "art-yellow"},
        ]
    },

    "understanding-your-child": {
        "title": "Understanding Your Child",
        "subtitle": "Answers to the confusing behaviors parents often notice: whispering, freezing, gestures, setbacks, and situation-specific speech.",
        "articles": [
            {"slug": "why-does-my-child-whisper", "image": "sm_whisper.png", "art": "art-lavender"},
            {"slug": "why-only-certain-people", "image": "sm_certain_people.png", "art": "art-mint"},
            {"slug": "why-one-teacher-but-not-another", "image": "sm_one_teacher.png", "art": "art-warm"},
            {"slug": "why-is-it-harder-around-other-children", "image": "sm_other_children.png", "art": "art-soft-blue"},
            {"slug": "why-avoid-eye-contact", "image": "sm_eye_contact.png", "art": "art-soft-purple"},
            {"slug": "why-do-they-seem-comfortable-but-not-speak", "image": "sm_seems_comfortable.png", "art": "art-pink"},
            {"slug": "why-did-my-child-stop-speaking-again", "image": "sm_regression.png", "art": "art-yellow"},
            {"slug": "why-speak-less-in-new-places", "image": "sm_new_places.png", "art": "art-green"},
            {"slug": "why-use-gestures-instead-of-words", "image": "sm_gestures.png", "art": "art-blue"},
            {"slug": "why-do-they-speak-through-me", "image": "sm_speaks_through_parent.png", "art": "art-peach"},
            {"slug": "why-do-they-shut-down-or-get-upset", "image": "sm_anger_shutdown.png", "art": "art-warm"},
            {"slug": "why-are-mornings-before-school-so-hard", "image": "sm_morning_school.png", "art": "art-soft-blue"},
        ]
    },

    "parent-strategies": {
        "title": "Parent Strategies",
        "subtitle": "Practical, evidence-aligned strategies for reducing pressure, creating speaking opportunities, and responding to setbacks.",
        "articles": [
            {"slug": "how-to-reduce-speaking-pressure", "image": "sm_reduce_pressure.png", "art": "art-green"},
            {"slug": "what-parents-should-avoid", "image": "sm_parent_avoid.png", "art": "art-blue"},
            {"slug": "praise-vs-pressure", "image": "sm_praise.png", "art": "art-yellow"},
            {"slug": "should-i-answer-for-my-child", "image": "sm_answering_for_child.png", "art": "art-peach"},
            {"slug": "creating-speaking-opportunities", "image": "sm_speaking_opportunities.png", "art": "art-lavender"},
            {"slug": "handling-setbacks", "image": "sm_setbacks.png", "art": "art-mint"},
        ]
    }
}

@app.route("/parent-academy/category/<category_slug>")
@login_required
def parent_academy_category(category_slug):
    category = PARENT_ACADEMY_CATEGORIES.get(category_slug)

    if not category:
        abort(404)

    articles = []

    for item in category["articles"]:
        article = PARENT_ACADEMY_ARTICLES.get(item["slug"])

        if article:
            articles.append({
                **article,
                "slug": item["slug"],
                "image": item["image"],
                "art": item["art"]
            })

    return render_template(
        "parent_academy_category.html",
        active_page="parent_academy",
        parent=session["parent_name"],
        child=session["child_name"],
        profile_icon=session.get("profile_icon", "profileicon.png"),
        category=category,
        articles=articles
    )

@app.route("/parent-academy/article/<slug>")
@login_required
def parent_academy_article(slug):
    article = PARENT_ACADEMY_ARTICLES.get(slug)

    if not article:
        abort(404)

    return render_template(
        "parent_academy_article.html",
        active_page="parent_academy",
        parent=session["parent_name"],
        child=session["child_name"],
        profile_icon=session.get("profile_icon", "profileicon.png"),
        article=article
    )

@app.route("/ask-bravesprouts")
@login_required
def ask_bravesprouts():
    return render_template(
        "ask_bravesprouts.html",
        active_page="ask_bravesprouts",
        parent=session["parent_name"],
        child=session["child_name"],
        profile_icon=session.get("profile_icon", "profileicon.png"),
        has_seen_tour=get_has_seen_tour_for_user(session["user_id"])
    )


@app.route("/api/ask-bravesprouts/conversations", methods=["GET"])
@login_required
def get_chat_conversations():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT conversation_id, title, updated_at
        FROM chat_conversations
        WHERE user_id = ?
        ORDER BY updated_at DESC
        LIMIT 20
    """, (session["user_id"],))

    rows = cursor.fetchall()
    conn.close()

    return jsonify({
        "success": True,
        "conversations": [dict(row) for row in rows]
    })


@app.route("/api/ask-bravesprouts/conversations", methods=["POST"])
@csrf.exempt
@login_required
def create_chat_conversation():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO chat_conversations (user_id, title)
        VALUES (?, ?)
    """, (session["user_id"], "New conversation"))

    conversation_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "conversation_id": conversation_id,
        "title": "New conversation"
    })


@app.route("/api/ask-bravesprouts/conversations/<int:conversation_id>", methods=["GET"])
@login_required
def get_chat_messages(conversation_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT conversation_id
        FROM chat_conversations
        WHERE conversation_id = ? AND user_id = ?
    """, (conversation_id, session["user_id"]))

    conversation = cursor.fetchone()

    if not conversation:
        conn.close()
        return jsonify({"success": False, "error": "Conversation not found"}), 404

    cursor.execute("""
        SELECT role, content, layout_type, created_at
        FROM chat_messages
        WHERE conversation_id = ? AND user_id = ?
        ORDER BY created_at ASC, message_id ASC
    """, (conversation_id, session["user_id"]))

    messages = cursor.fetchall()
    conn.close()

    return jsonify({
        "success": True,
        "messages": [dict(row) for row in messages]
    })


@app.route("/api/ask-bravesprouts/conversations/<int:conversation_id>", methods=["DELETE"])
@csrf.exempt
@login_required
def delete_chat_conversation(conversation_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM chat_messages
        WHERE conversation_id = ? AND user_id = ?
    """, (conversation_id, session["user_id"]))

    cursor.execute("""
        DELETE FROM chat_conversations
        WHERE conversation_id = ? AND user_id = ?
    """, (conversation_id, session["user_id"]))

    conn.commit()
    conn.close()

    return jsonify({"success": True})


def classify_ask_bravesprouts_message(user_message):
    message = user_message.lower().strip()

    courtesy_phrases = [
        "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
        "thanks", "thank you", "thank you so much", "thx", "appreciate it",
        "ok", "okay", "got it", "that helps", "makes sense", "cool",
        "yes", "no", "yeah", "yep", "nope", "sure"
    ]

    if message in courtesy_phrases:
        return "courtesy"

    if len(message.split()) <= 4 and any(phrase in message for phrase in courtesy_phrases):
        return "courtesy"

    allowed_keywords = [
        "selective mutism", "mutism", "sm",
        "speak", "speaking", "talk", "talking", "voice",
        "whisper", "freeze", "frozen", "silent", "silence",
        "anxiety", "anxious", "nervous", "shy", "shyness",
        "school", "teacher", "classroom", "student",
        "parent", "child", "kid", "daughter", "son",
        "therapy", "therapist", "doctor", "psychologist",
        "speech", "slp", "counselor",
        "reward", "pressure", "prompt", "avoid", "avoidance",
        "eye contact", "gestures", "setback", "progress",
        "relatives", "family", "friends",
        "communication", "bravesprouts", "practice", "support"
    ]

    blocked_keywords = [
        "html", "css", "javascript", "python", "code",
        "website", "essay", "homework", "math",
        "business plan", "marketing plan",
        "recipe", "travel", "movie", "song",
        "write me", "make me", "build me", "create me",
        "generate", "solve", "debug"
    ]

    has_allowed = any(keyword in message for keyword in allowed_keywords)
    has_blocked = any(keyword in message for keyword in blocked_keywords)

    if has_allowed and has_blocked:
        return "needs_context"

    if has_allowed:
        return "allowed"

    if has_blocked:
        return "blocked"

    if len(message.split()) <= 6:
        return "courtesy"

    return "blocked"


def save_simple_chat_response(cursor, conversation_id, user_id, user_message, bot_message):
    import json

    cursor.execute("""
        INSERT INTO chat_messages (conversation_id, user_id, role, content)
        VALUES (?, ?, 'user', ?)
    """, (conversation_id, user_id, user_message))

    cursor.execute("""
        INSERT INTO chat_messages (
            conversation_id,
            user_id,
            role,
            content,
            layout_type
        )
        VALUES (?, ?, 'assistant', ?, ?)
    """, (
        conversation_id,
        user_id,
        json.dumps(bot_message),
        bot_message.get("layout_type", "quick")
    ))

    cursor.execute("""
        UPDATE chat_conversations
        SET title = CASE
            WHEN title = 'New conversation' THEN ?
            ELSE title
        END,
        updated_at = CURRENT_TIMESTAMP
        WHERE conversation_id = ? AND user_id = ?
    """, (
        user_message[:42].strip(),
        conversation_id,
        user_id
    ))


@app.route("/api/ask-bravesprouts/message", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("20 per minute")
def ask_bravesprouts_message():
    data = request.get_json(silent=True) or {}

    conversation_id = data.get("conversation_id")
    user_message = (data.get("message") or "").strip()

    if not user_message:
        return jsonify({"success": False, "error": "Message is required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    if not conversation_id:
        cursor.execute("""
            INSERT INTO chat_conversations (user_id, title)
            VALUES (?, ?)
        """, (session["user_id"], "New conversation"))
        conversation_id = cursor.lastrowid
        conn.commit()

    cursor.execute("""
        SELECT conversation_id
        FROM chat_conversations
        WHERE conversation_id = ? AND user_id = ?
    """, (conversation_id, session["user_id"]))

    if not cursor.fetchone():
        conn.close()
        return jsonify({"success": False, "error": "Conversation not found"}), 404

    message_type = classify_ask_bravesprouts_message(user_message)

    if message_type == "courtesy":
        courtesy_message = {
            "layout_type": "quick",
            "title": "Hi, I’m here with you",
            "sections": [
                {
                    "heading": "How I can help",
                    "content": "You can ask me about selective mutism, speaking anxiety, school support, parent strategies, or communication practice.",
                    "items": [
                        "Why does my child freeze?",
                        "How can I reduce speaking pressure?",
                        "What should I tell my child’s teacher?"
                    ]
                }
            ],
            "gentle_reminder": ""
        }

        save_simple_chat_response(
            cursor,
            conversation_id,
            session["user_id"],
            user_message,
            courtesy_message
        )

        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "conversation_id": conversation_id,
            "message": courtesy_message
        })

    if message_type == "blocked":
        refusal_message = {
            "layout_type": "quick",
            "title": "I can only help with BraveSprouts-related questions",
            "sections": [
                {
                    "heading": "Try asking about communication support",
                    "content": "Ask BraveSprouts is designed to help with selective mutism, speaking anxiety, parent strategies, school support, and communication practice.",
                    "items": [
                        "Why does my child freeze when someone talks to them?",
                        "How can I reduce speaking pressure?",
                        "How should I talk to my child’s teacher?"
                    ]
                }
            ],
            "gentle_reminder": "For medical or treatment decisions, please work with a qualified professional."
        }

        save_simple_chat_response(
            cursor,
            conversation_id,
            session["user_id"],
            user_message,
            refusal_message
        )

        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "conversation_id": conversation_id,
            "message": refusal_message
        })
    
    if message_type == "needs_context":
        context_message = {
            "layout_type": "quick",
            "title": "That depends on what’s happening",
            "sections": [
                {
                    "heading": "A little more context would help",
                    "content": "I can help if this connects to speaking pressure, anxiety, avoidance, shutdowns, school communication, or parent support. I just don’t want to assume what is happening for your child.",
                    "items": [
                        "Is the challenge mainly about the homework itself?",
                        "Is your child getting overwhelmed or shutting down?",
                        "Is speaking, answering aloud, or pressure part of the situation?"
                    ]
                }
            ],
            "gentle_reminder": ""
        }

        save_simple_chat_response(
            cursor,
            conversation_id,
            session["user_id"],
            user_message,
            context_message
        )

        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "conversation_id": conversation_id,
            "message": context_message
        })

    cursor.execute("""
        INSERT INTO chat_messages (conversation_id, user_id, role, content)
        VALUES (?, ?, 'user', ?)
    """, (conversation_id, session["user_id"], user_message))

    cursor.execute("""
        SELECT role, content
        FROM chat_messages
        WHERE conversation_id = ? AND user_id = ?
        ORDER BY created_at DESC, message_id DESC
        LIMIT 12
    """, (conversation_id, session["user_id"]))

    recent_messages = list(reversed(cursor.fetchall()))

    message_history = [
        {
            "role": row["role"],
            "content": row["content"]
        }
        for row in recent_messages
    ]

    knowledge_context = get_relevant_parent_academy_context(user_message)
    research_context = get_relevant_research_context(user_message)

    system_prompt = f"""
You are Ask BraveSprouts, a warm educational AI guide for parents of children with selective mutism, speaking anxiety, or communication difficulties.

Core identity:
- You are not generic ChatGPT.
- You are a BraveSprouts parent-support guide.
- Your job is to give careful, honest, practical, research-informed support.
- You must never pretend to know more about the child than the parent has said.

Important safety rules:
- You are not a therapist, doctor, psychologist, speech-language pathologist, or legal advisor.
- Never diagnose a child.
- Never replace professional care.
- Encourage qualified professional support for treatment, diagnosis, school plans, severe anxiety, safety concerns, or major decisions.
- If the parent describes crisis, harm, abuse, or immediate danger, tell them to contact emergency services or a qualified crisis resource.

Scope rules:
- Only answer questions about selective mutism, child communication, parent strategies, school support, speaking anxiety, BraveSprouts activities, or closely related family support.
- If the user asks for unrelated help such as coding, homework answers, business advice, recipes, entertainment, travel, or unrelated schoolwork, politely redirect.
- If the message may be related but lacks context, ask for context instead of assuming.

No-assumption rules:
- You may assume the conversation is generally about selective mutism or speaking anxiety.
- Do not assume the child’s age, severity, comfort people, triggers, school situation, home behavior, speaking ability, treatment history, or progress level unless provided.
- Never assume the child cannot speak to a parent unless explicitly stated.
- Never assume the child struggles in a situation unless the parent describes that struggle.
- Never invent facts about the child or family.
- If several explanations are possible, present them as possibilities, not facts.

Clarifying-question rules:
- Ask clarifying questions only when missing context would significantly change the advice.
- Do not ask clarifying questions for every response.
- For broad plan requests, school plans, treatment-like questions, or questions where severity/context matters, ask 2-4 concise questions before giving a full plan.
- For simpler questions, give helpful general guidance immediately.
- Ask at most 4 questions at once.
- Do not make the parent feel interrogated.

Honesty and evidence rules:
- Be extremely honest about evidence strength.
- Do not say something is proven if evidence is limited.
- If research is strong, explain why.
- If research is limited, say so clearly.
- If a claim is based more on clinical consensus than direct trials, say that.
- When mentioning research, name the researcher/study when possible and briefly explain what the study showed.
- Do not invent citations.
- If you are unsure about a study, do not cite it.
- Prefer phrases like:
  - "One possibility is..."
  - "This can vary from child to child."
  - "The evidence is stronger for..."
  - "This is commonly recommended clinically, but direct research is limited."

Approach-comparison rules:
- When there are multiple reasonable approaches, present more than one.
- Explain pros, cons, and what to watch out for.
- Do not present one strategy as universally correct.
- Include risks of common advice, especially praise, rewards, prompting, answering for the child, and exposure practice.

Response design:
Return JSON only.

Use this JSON structure:
{{
  "layout_type": "comfort | quick | strategy | explainer | plan | professional | clarifying | comparison | research",
  "theme": "purple | green | blue | orange | pink | yellow",
  "confidence": "high | moderate | limited | unclear",
  "hero": {{
    "eyebrow": "Short label",
    "title": "Main response title",
    "summary": "Short 1-2 sentence summary"
  }},
  "sections": [
    {{
      "type": "why | do | avoid | research | approach | plan | question | note",
      "icon": "brain | check | x | flask | compass | calendar | question | heart",
      "heading": "Section heading",
      "content": "Short paragraph",
      "items": [
        {{
          "label": "Optional bold label",
          "text": "Item text"
        }}
      ],
      "pros": ["optional pro"],
      "cons": ["optional con"],
      "watch_out": ["optional caution"]
    }}
  ],
  "follow_up_questions": ["Only include when genuinely needed"],
  "gentle_reminder": "Short professional-support reminder when appropriate."
}}

BraveSprouts knowledge base:
{knowledge_context if knowledge_context else "No specific Parent Academy article matched. Answer using general educational guidance."}

When the knowledge base is relevant, use it.

Research context:
{research_context if research_context else "No specific research study matched this question. If research is discussed, speak generally and do not invent citations."}

Research use rules:
- When the user asks for strategies, plans, school support, treatment-like guidance, praise, rewards, pressure, avoidance, parent accommodation, or why selective mutism happens, include a research section when relevant.
- Mention specific studies from the research context when they directly support the answer.
- Explain what the study showed, what it implies, and what its limitations are.
- Be honest if evidence is limited, emerging, indirect, or based more on clinical consensus than direct trials.
- Never invent studies, author names, exact citations, or findings.
- If no specific research context is available, say the guidance is general or clinically informed rather than pretending it is backed by a named study.
- If you include a research section, end that section by telling the parent they can ask for a deeper explanation of any specific study, finding, limitation, or implication.

Parent name: {session.get("parent_name", "the parent")}
Child name: {session.get("child_name", "your child")}
"""


    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {"role": "system", "content": system_prompt},
                *message_history,
                {"role": "user", "content": user_message}
            ]
        )

        raw = response.output_text.strip()

        import json

        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {
                "layout_type": "quick",
                "theme": "purple",
                "confidence": "unclear",
                "hero": {
                    "eyebrow": "BraveSprouts Guide",
                    "title": "A gentle response",
                    "summary": raw
                },
                "sections": [],
                "follow_up_questions": [],
                "gentle_reminder": "This is educational support and does not replace guidance from a qualified professional."
            }

        assistant_content = json.dumps(parsed)

        cursor.execute("""
            INSERT INTO chat_messages (
                conversation_id,
                user_id,
                role,
                content,
                layout_type
            )
            VALUES (?, ?, 'assistant', ?, ?)
        """, (
            conversation_id,
            session["user_id"],
            assistant_content,
            parsed.get("layout_type", "quick")
        ))

        title = user_message[:42].strip()

        cursor.execute("""
            UPDATE chat_conversations
            SET title = CASE
                WHEN title = 'New conversation' THEN ?
                ELSE title
            END,
            updated_at = CURRENT_TIMESTAMP
            WHERE conversation_id = ? AND user_id = ?
        """, (title, conversation_id, session["user_id"]))

        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "conversation_id": conversation_id,
            "message": parsed
        })

    except Exception as e:
        print("Ask BraveSprouts error:", e)
        conn.rollback()
        conn.close()

        return jsonify({
            "success": False,
            "error": "Could not generate response"
        }), 500

def get_relevant_parent_academy_context(user_message):
    query = user_message.lower()
    matches = []

    for slug, article in PARENT_ACADEMY_ARTICLES.items():
        searchable = f"""
        {article.get("title", "")}
        {article.get("category", "")}
        {article.get("summary", "")}
        """.lower()

        score = 0
        for word in query.split():
            if len(word) > 3 and word in searchable:
                score += 1

        if score > 0:
            matches.append((score, slug, article))

    matches.sort(reverse=True, key=lambda x: x[0])
    matches = matches[:3]

    if not matches:
        return ""

    context = "Relevant BraveSprouts Parent Academy articles:\n\n"

    for score, slug, article in matches:
        context += f"""
Title: {article["title"]}
Category: {article["category"]}
Evidence level: {article["evidence"]}
Summary: {article["summary"]}
Article slug: {slug}
"""

    return context

def get_relevant_research_context(user_message, max_studies=6):
    query = user_message.lower()

    query_words = [
        word.strip(".,!?;:()[]{}").lower()
        for word in query.split()
        if len(word.strip(".,!?;:()[]{}")) > 3
    ]

    matches = []

    for study in RESEARCH_LIBRARY:
        searchable = " ".join([
            study.get("category", ""),
            " ".join(study.get("topics", [])),
            study.get("citation", ""),
            study.get("finding", ""),
            study.get("implication", "")
        ]).lower()

        score = 0

        for word in query_words:
            if word in searchable:
                score += 1

        if score > 0:
            matches.append((score, study))

    matches.sort(reverse=True, key=lambda x: x[0])
    matches = matches[:max_studies]

    if not matches:
        return ""

    context = "Relevant research context:\n\n"

    for score, study in matches:
        context += f"""
Study: {study.get("citation", "Unknown study")}
Category: {study.get("category", "uncategorized")}
Evidence level: {study.get("evidence_level", "unclear")}
Finding: {study.get("finding", "")}
Implication: {study.get("implication", "")}
Limitations: {study.get("limitations", "")}
"""

    return context

# =========================
# Drawing Game — Star + Librarian bridge activity
# Frontend routes:
#   /api/drawing-game/tts
#   /api/drawing-game/transcribe
#   /api/drawing-game/complete
#
# Put this block in app.py after your matching-game backend block.
# Requires:
#   templates/drawing_game.html
#   static/css/drawing_game.css
#   static/js/drawing_game.js
# =========================

def sanitize_drawing_game_line(text, fallback="Nice work.", max_len=260):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    text = text.replace('"', "")[:max_len]

    if not text:
        return fallback

    banned_terms = [
        "selective mutism",
        "anxiety",
        "therapy",
        "treatment",
        "exposure",
        "diagnosis",
        "progress",
        "bravery",
        "confidence",
        "use your words"
    ]

    lowered = text.lower()

    if any(term in lowered for term in banned_terms):
        return fallback

    return text


def generate_drawing_game_voice_elevenlabs(text, speaker="star", game_complete=False):
    speaker = str(speaker or "star").strip().lower()

    if speaker == "librarian":
        voice_id = (
            os.getenv("LIBRARIAN_VOICE_ID")
            or os.getenv("BOOK_GUESSING_VOICE_ID")
            or os.getenv("ELEVENLABS_VOICE_ID", "piI8Kku0DcvcL6TTSeQt")
        )
        voice_settings = {
            "stability": 0.94,
            "similarity_boost": 0.90,
            "style": 0.05,
            "use_speaker_boost": False
        }
    else:
        voice_id = os.getenv("ELEVENLABS_VOICE_ID", "piI8Kku0DcvcL6TTSeQt")
        voice_settings = {
            "stability": 0.99,
            "similarity_boost": 0.88,
            "style": 0.0,
            "use_speaker_boost": False
        }

    if game_complete:
        voice_settings["style"] = max(voice_settings.get("style", 0), 0.12)

    response = eleven_client.text_to_speech.convert(
        voice_id=voice_id,
        text=text,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
        voice_settings=voice_settings
    )

    return b"".join(response)


@app.route("/api/drawing-game/tts", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("60 per minute")
def drawing_game_tts():
    data = request.get_json(silent=True) or {}

    speaker = str(data.get("speaker", "star")).strip().lower()
    text = sanitize_drawing_game_line(data.get("text", ""), fallback="Nice work.")

    if speaker not in {"star", "librarian"}:
        speaker = "star"

    if not text:
        return jsonify({"success": False, "error": "Missing text"}), 400

    try:
        audio_bytes = generate_drawing_game_voice_elevenlabs(text, speaker=speaker)
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

        return jsonify({
            "success": True,
            "speaker": speaker,
            "message": text,
            "audio": f"data:audio/mpeg;base64,{audio_base64}"
        })

    except Exception as e:
        print("Drawing game TTS error:", repr(e))
        return jsonify({
            "success": False,
            "error": "Could not generate drawing game audio"
        }), 500


@app.route("/api/drawing-game/transcribe", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("30 per minute")
def drawing_game_transcribe():
    if "audio" not in request.files:
        return jsonify({
            "success": False,
            "error": "Missing audio"
        }), 400

    audio_file = request.files["audio"]

    try:
        import io

        audio_bytes = audio_file.read()

        if not audio_bytes:
            return jsonify({
                "success": False,
                "error": "Empty audio file"
            }), 400

        file_obj = io.BytesIO(audio_bytes)
        file_obj.name = "drawing-response.webm"

        transcript = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=file_obj
        )

        text = transcript.text.strip()
        print("DRAWING GAME TRANSCRIPT:", text)

        return jsonify({
            "success": True,
            "text": text
        })

    except Exception as e:
        print("Drawing game transcription error:", repr(e))
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/drawing-game/complete", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("20 per minute")
def drawing_game_complete():
    data = request.get_json(silent=True) or {}

    try:
        activity_id = int(data.get("activity_id") or 7)
        words_spoken = max(0, int(float(data.get("words_spoken", 0) or 0)))
        minutes_spoken = max(0.0, float(data.get("minutes_spoken", 0) or 0))
        active_minutes = max(0.0, float(data.get("active_minutes", 0) or 0))
        time_spent = max(
            0.0,
            float(data.get("time_spent_on_activity", active_minutes) or active_minutes)
        )
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "Invalid completion data"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT activity_id, scene_id, activity_order
            FROM activity
            WHERE activity_id = ? AND is_active = 1
        """, (activity_id,))

        activity = cursor.fetchone()

        if not activity:
            conn.close()
            return jsonify({"success": False, "error": "Activity not found"}), 404

        cursor.execute("""
            INSERT OR IGNORE INTO progress (
                user_id,
                activity_id,
                is_unlocked,
                is_completed,
                words_spoken,
                minutes_spoken,
                active_minutes,
                time_spent_on_activity
            )
            VALUES (?, ?, 1, 0, 0, 0, 0, 0)
        """, (session["user_id"], activity_id))

        cursor.execute("""
            UPDATE progress
            SET
                is_completed = 1,
                completed_at = CURRENT_TIMESTAMP,
                words_spoken = COALESCE(words_spoken, 0) + ?,
                minutes_spoken = COALESCE(minutes_spoken, 0) + ?,
                active_minutes = COALESCE(active_minutes, 0) + ?,
                time_spent_on_activity = COALESCE(time_spent_on_activity, 0) + ?
            WHERE user_id = ? AND activity_id = ?
        """, (
            words_spoken,
            minutes_spoken,
            active_minutes,
            time_spent,
            session["user_id"],
            activity_id
        ))

        cursor.execute("""
            INSERT INTO session_log (
                user_id,
                activity_id,
                words_spoken,
                minutes_spoken,
                active_minutes,
                completed_at
            )
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            session["user_id"],
            activity_id,
            words_spoken,
            minutes_spoken,
            active_minutes
        ))

        cursor.execute("""
            SELECT activity_id
            FROM activity
            WHERE is_active = 1
              AND (
                scene_id > ?
                OR (scene_id = ? AND activity_order > ?)
              )
            ORDER BY scene_id ASC, activity_order ASC
            LIMIT 1
        """, (
            activity["scene_id"],
            activity["scene_id"],
            activity["activity_order"]
        ))

        next_activity = cursor.fetchone()
        next_activity_id = None

        if next_activity:
            next_activity_id = next_activity["activity_id"]

            cursor.execute("""
                INSERT OR IGNORE INTO progress (
                    user_id,
                    activity_id,
                    is_unlocked,
                    is_completed,
                    words_spoken,
                    minutes_spoken,
                    active_minutes,
                    time_spent_on_activity
                )
                VALUES (?, ?, 1, 0, 0, 0, 0, 0)
            """, (session["user_id"], next_activity_id))

            cursor.execute("""
                UPDATE progress
                SET is_unlocked = 1
                WHERE user_id = ? AND activity_id = ?
            """, (session["user_id"], next_activity_id))

            cursor.execute("""
                UPDATE users
                SET current_activity_id = ?
                WHERE user_id = ?
            """, (next_activity_id, session["user_id"]))

        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "next_activity_id": next_activity_id
        })

    except Exception as e:
        conn.rollback()
        conn.close()
        print("Drawing game completion error:", repr(e))
        return jsonify({
            "success": False,
            "error": "Could not save drawing game completion"
        }), 500

# =========================
# Toy Sorting Game — Librarian + Toy Store Worker bridge activity
# Frontend routes:
#   /api/toy-sorting-game/tts
#   /api/toy-sorting-game/transcribe
#   /api/toy-sorting-game/complete
#
# Put this block in app.py near your other game backend blocks.
# Requires:
#   templates/toy_sorting_game.html
#   static/css/toy_sorting_game.css
#   static/js/toy_sorting_game.js
# =========================

def sanitize_toy_sorting_line(text, fallback="Nice sorting.", max_len=260):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    text = text.replace('"', "")[:max_len]

    if not text:
        return fallback

    banned_terms = [
        "selective mutism",
        "anxiety",
        "therapy",
        "treatment",
        "exposure",
        "diagnosis",
        "progress",
        "bravery",
        "confidence",
        "use your words"
    ]

    lowered = text.lower()

    if any(term in lowered for term in banned_terms):
        return fallback

    return text


def generate_toy_sorting_voice_elevenlabs(text, speaker="librarian", game_complete=False):
    speaker = str(speaker or "librarian").strip().lower()

    if speaker == "toyworker":
        voice_id = (
            os.getenv("TOY_WORKER_VOICE_ID")
            or os.getenv("TOY_TRIVIA_VOICE_ID")
            or os.getenv("ELEVENLABS_VOICE_ID", "piI8Kku0DcvcL6TTSeQt")
        )
        voice_settings = {
            "stability": 0.94,
            "similarity_boost": 0.90,
            "style": 0.06,
            "use_speaker_boost": False
        }
    else:
        voice_id = (
            os.getenv("LIBRARIAN_VOICE_ID")
            or os.getenv("BOOK_GUESSING_VOICE_ID")
            or os.getenv("ELEVENLABS_VOICE_ID", "piI8Kku0DcvcL6TTSeQt")
        )
        voice_settings = {
            "stability": 0.94,
            "similarity_boost": 0.90,
            "style": 0.04,
            "use_speaker_boost": False
        }

    if game_complete:
        voice_settings["style"] = max(voice_settings.get("style", 0), 0.12)

    response = eleven_client.text_to_speech.convert(
        voice_id=voice_id,
        text=text,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
        voice_settings=voice_settings
    )

    return b"".join(response)


@app.route("/api/toy-sorting-game/tts", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("60 per minute")
def toy_sorting_game_tts():
    data = request.get_json(silent=True) or {}

    speaker = str(data.get("speaker", "librarian")).strip().lower()
    text = sanitize_toy_sorting_line(data.get("text", ""), fallback="Nice sorting.")

    if speaker not in {"librarian", "toyworker"}:
        speaker = "librarian"

    if not text:
        return jsonify({"success": False, "error": "Missing text"}), 400

    try:
        audio_bytes = generate_toy_sorting_voice_elevenlabs(text, speaker=speaker)
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

        return jsonify({
            "success": True,
            "speaker": speaker,
            "message": text,
            "audio": f"data:audio/mpeg;base64,{audio_base64}"
        })

    except Exception as e:
        print("Toy sorting TTS error:", repr(e))
        return jsonify({
            "success": False,
            "error": "Could not generate toy sorting audio"
        }), 500


@app.route("/api/toy-sorting-game/transcribe", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("30 per minute")
def toy_sorting_game_transcribe():
    if "audio" not in request.files:
        return jsonify({
            "success": False,
            "error": "Missing audio"
        }), 400

    audio_file = request.files["audio"]

    try:
        import io

        audio_bytes = audio_file.read()

        if not audio_bytes:
            return jsonify({
                "success": False,
                "error": "Empty audio file"
            }), 400

        file_obj = io.BytesIO(audio_bytes)
        file_obj.name = "toy-sorting-response.webm"

        transcript = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=file_obj
        )

        text = transcript.text.strip()
        print("TOY SORTING TRANSCRIPT:", text)

        return jsonify({
            "success": True,
            "text": text
        })

    except Exception as e:
        print("Toy sorting transcription error:", repr(e))
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/toy-sorting-game/complete", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("20 per minute")
def toy_sorting_game_complete():
    data = request.get_json(silent=True) or {}

    try:
        activity_id = int(data.get("activity_id") or 4)
        words_spoken = max(0, int(float(data.get("words_spoken", 0) or 0)))
        minutes_spoken = max(0.0, float(data.get("minutes_spoken", 0) or 0))
        active_minutes = max(0.0, float(data.get("active_minutes", 0) or 0))
        time_spent = max(
            0.0,
            float(data.get("time_spent_on_activity", active_minutes) or active_minutes)
        )
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "Invalid completion data"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT activity_id, scene_id, activity_order
            FROM activity
            WHERE activity_id = ? AND is_active = 1
        """, (activity_id,))

        activity = cursor.fetchone()

        if not activity:
            conn.close()
            return jsonify({"success": False, "error": "Activity not found"}), 404

        cursor.execute("""
            INSERT OR IGNORE INTO progress (
                user_id,
                activity_id,
                is_unlocked,
                is_completed,
                words_spoken,
                minutes_spoken,
                active_minutes,
                time_spent_on_activity
            )
            VALUES (?, ?, 1, 0, 0, 0, 0, 0)
        """, (session["user_id"], activity_id))

        cursor.execute("""
            UPDATE progress
            SET
                is_completed = 1,
                completed_at = CURRENT_TIMESTAMP,
                words_spoken = COALESCE(words_spoken, 0) + ?,
                minutes_spoken = COALESCE(minutes_spoken, 0) + ?,
                active_minutes = COALESCE(active_minutes, 0) + ?,
                time_spent_on_activity = COALESCE(time_spent_on_activity, 0) + ?
            WHERE user_id = ? AND activity_id = ?
        """, (
            words_spoken,
            minutes_spoken,
            active_minutes,
            time_spent,
            session["user_id"],
            activity_id
        ))

        cursor.execute("""
            INSERT INTO session_log (
                user_id,
                activity_id,
                words_spoken,
                minutes_spoken,
                active_minutes,
                completed_at
            )
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            session["user_id"],
            activity_id,
            words_spoken,
            minutes_spoken,
            active_minutes
        ))

        cursor.execute("""
            SELECT activity_id
            FROM activity
            WHERE is_active = 1
              AND (
                scene_id > ?
                OR (scene_id = ? AND activity_order > ?)
              )
            ORDER BY scene_id ASC, activity_order ASC
            LIMIT 1
        """, (
            activity["scene_id"],
            activity["scene_id"],
            activity["activity_order"]
        ))

        next_activity = cursor.fetchone()
        next_activity_id = None

        if next_activity:
            next_activity_id = next_activity["activity_id"]

            cursor.execute("""
                INSERT OR IGNORE INTO progress (
                    user_id,
                    activity_id,
                    is_unlocked,
                    is_completed,
                    words_spoken,
                    minutes_spoken,
                    active_minutes,
                    time_spent_on_activity
                )
                VALUES (?, ?, 1, 0, 0, 0, 0, 0)
            """, (session["user_id"], next_activity_id))

            cursor.execute("""
                UPDATE progress
                SET is_unlocked = 1
                WHERE user_id = ? AND activity_id = ?
            """, (session["user_id"], next_activity_id))

            cursor.execute("""
                UPDATE users
                SET current_activity_id = ?
                WHERE user_id = ?
            """, (next_activity_id, session["user_id"]))

        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "next_activity_id": next_activity_id
        })

    except Exception as e:
        conn.rollback()
        conn.close()
        print("Toy sorting completion error:", repr(e))
        return jsonify({
            "success": False,
            "error": "Could not save toy sorting completion"
        }), 500

@app.route("/acknowledgments")
@login_required
def acknowledgments():
    return render_template(
        "acknowledgments.html",
        active_page="acknowledgments",
        parent=session["parent_name"],
        child=session.get("child_name", ""),
        profile_icon=session.get("profile_icon", "profileicon.png")
    )

@app.route("/forgot-password", methods=["GET", "POST"])
@csrf.exempt
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()
        conn.close()

        if not user:
            flash("We couldn't find a BraveSprouts account with that email. Please check the email or create a new account.")
            return redirect(url_for("forgot_password"))

        token = serializer.dumps(email, salt="password-reset-salt")
        reset_url = url_for("reset_password", token=token, _external=True)

        try:
            send_password_reset_email(email, reset_url)
            print("Password reset link:", reset_url)
        except Exception as e:
            print("EMAIL ERROR:", repr(e))
            print("Password reset link:", reset_url)

        return redirect(reset_url)

    return render_template("forgot_password.html")

@app.route("/reset-password/<token>", methods=["GET", "POST"])
@csrf.exempt
def reset_password(token):
    try:
        email = serializer.loads(
            token,
            salt="password-reset-salt",
            max_age=3600
        )
    except SignatureExpired:
        flash("This password reset link has expired.")
        return redirect(url_for("forgot_password"))
    except BadSignature:
        flash("Invalid password reset link.")
        return redirect(url_for("forgot_password"))

    conn = get_db_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE email = ?",
        (email,)
    ).fetchone()

    if not user:
        conn.close()
        flash("Invalid password reset link.")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        new_password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if new_password != confirm_password:
            conn.close()
            flash("Passwords do not match.")
            return redirect(request.url)

        password_error = validate_password(new_password)

        if password_error:
            conn.close()
            flash(password_error)
            return redirect(request.url)

        hashed_password = generate_password_hash(new_password)

        conn.execute(
            "UPDATE users SET password = ? WHERE email = ?",
            (hashed_password, email)
        )
        conn.commit()
        conn.close()

        flash("Your password has been reset. You can now log in.")
        return redirect(url_for("login"))

    conn.close()
    return render_template("reset_password.html")

def send_password_reset_email(to_email, reset_url):
    sender_email = os.getenv("MAIL_USERNAME")
    sender_password = os.getenv("MAIL_PASSWORD")

    subject = "Reset your BraveSprouts password"

    body = f"""
Hi,

We received a request to reset your BraveSprouts password.

Click the link below to reset your password:
{reset_url}

This link will expire in 1 hour.

If you did not request this, you can ignore this email.

Best,
BraveSprouts
"""

    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = to_email
    message["Subject"] = subject

    message.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_email, message.as_string())

if __name__ == "__main__":
    app.run(debug=app.config["DEBUG"])