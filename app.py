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

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

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
    "script-src": "'self' https://www.youtube.com https://www.youtube-nocookie.com",
    "style-src": "'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src": "'self' https://fonts.gstatic.com data:",
    "img-src": "'self' data: https:",
    "media-src": "'self' data: blob:",
    "frame-src": "'self' https://www.youtube.com https://www.youtube-nocookie.com",
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


def ensure_drawing_game_progress_columns():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(progress)")
    existing_columns = {row["name"] for row in cursor.fetchall()}

    columns_to_add = {
        "drawing_scene_index": "ALTER TABLE progress ADD COLUMN drawing_scene_index INTEGER DEFAULT 0",
        "drawing_stage_index": "ALTER TABLE progress ADD COLUMN drawing_stage_index INTEGER DEFAULT 0",
        "drawing_rounds_completed": "ALTER TABLE progress ADD COLUMN drawing_rounds_completed INTEGER DEFAULT 0",
        "drawing_stages_completed": "ALTER TABLE progress ADD COLUMN drawing_stages_completed INTEGER DEFAULT 0",
        "drawing_scenes_completed": "ALTER TABLE progress ADD COLUMN drawing_scenes_completed INTEGER DEFAULT 0",
        "drawing_spoken_responses": "ALTER TABLE progress ADD COLUMN drawing_spoken_responses INTEGER DEFAULT 0",
        "drawing_silent_windows": "ALTER TABLE progress ADD COLUMN drawing_silent_windows INTEGER DEFAULT 0",
        "drawing_total_color_selections": "ALTER TABLE progress ADD COLUMN drawing_total_color_selections INTEGER DEFAULT 0",
        "drawing_canvas_data": "ALTER TABLE progress ADD COLUMN drawing_canvas_data TEXT",
        "drawing_last_played_at": "ALTER TABLE progress ADD COLUMN drawing_last_played_at TEXT"
    }

    for column_name, alter_sql in columns_to_add.items():
        if column_name not in existing_columns:
            cursor.execute(alter_sql)

    conn.commit()
    conn.close()


def safe_drawing_int(value, default=0, max_value=999):
    try:
        parsed = int(float(value if value is not None else default))
    except (TypeError, ValueError):
        parsed = default

    return max(0, min(max_value, parsed))

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
    ensure_feedback_tables()

    if request.method == "GET" and session.get("user_id"):
        return redirect(url_for("dashboard"))

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
            bump_login_count(user[0])
            
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
    ensure_feedback_tables()
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
                terms_check,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
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

        cursor.execute("""
            UPDATE users
            SET login_count = 1
            WHERE user_id = ?
""",    (user_id,))

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

def clean_feedback_text(value, max_length=900):
    value = str(value or "").strip()
    value = re.sub(r"\s+", " ", value)
    return value[:max_length]


def ensure_feedback_tables():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(users)")
    existing_user_columns = {row["name"] for row in cursor.fetchall()}

    user_columns_to_add = {
        "login_count": "ALTER TABLE users ADD COLUMN login_count INTEGER DEFAULT 0",
        "has_seen_tour": "ALTER TABLE users ADD COLUMN has_seen_tour INTEGER DEFAULT 0",
        "feedback_prompt_dismissed_at": "ALTER TABLE users ADD COLUMN feedback_prompt_dismissed_at TEXT",
        "created_at": "ALTER TABLE users ADD COLUMN created_at TEXT"
    }

    for column_name, alter_sql in user_columns_to_add.items():
        if column_name not in existing_user_columns:
            cursor.execute(alter_sql)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parent_feedback (
            feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,

            what_child_enjoyed TEXT,
            what_didnt_work TEXT,
            what_would_make_better TEXT,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    conn.commit()
    conn.close()
@app.context_processor
def inject_feedback_globals():
    if "user_id" not in session:
        return {
            "show_feedback_widget": False,
            "show_feedback_prompt": False,
            "login_count": 0
        }

    ensure_feedback_tables()

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            COALESCE(u.login_count, 0) AS login_count,
            COALESCE(u.has_seen_tour, 0) AS has_seen_tour,
            CASE
                WHEN pf.feedback_id IS NULL THEN 0
                ELSE 1
            END AS has_submitted_feedback
        FROM users u
        LEFT JOIN parent_feedback pf
            ON pf.user_id = u.user_id
        WHERE u.user_id = ?
    """, (session["user_id"],))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return {
            "show_feedback_widget": False,
            "show_feedback_prompt": False,
            "login_count": 0
        }

    login_count = row["login_count"]
    has_seen_tour = bool(row["has_seen_tour"])
    has_submitted_feedback = bool(row["has_submitted_feedback"])

    return {
        "login_count": login_count,
        "show_feedback_widget": has_seen_tour and not has_submitted_feedback,
        "show_feedback_prompt": has_seen_tour and login_count >= 2 and not has_submitted_feedback
    }

def bump_login_count(user_id):
    ensure_feedback_tables()

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE users
        SET login_count = COALESCE(login_count, 0) + 1
        WHERE user_id = ?
    """, (user_id,))

    conn.commit()
    conn.close()

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
    ensure_feedback_tables()

    conn = get_db_connection()
    cursor = conn.cursor()

    now_et = datetime.now(ZoneInfo("America/New_York"))

    today_start_et = now_et.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start_et = today_start_et - timedelta(days=today_start_et.weekday())
    month_start_et = today_start_et.replace(day=1)

    def to_utc_sql(dt):
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    today_start = to_utc_sql(today_start_et)
    week_start = to_utc_sql(week_start_et)
    month_start = to_utc_sql(month_start_et)

    cursor.execute("""
        SELECT
            COUNT(*) AS total_users,

            COUNT(CASE
                WHEN created_at IS NOT NULL AND created_at >= ?
                THEN 1
            END) AS users_created_this_week,

            COUNT(CASE
                WHEN created_at IS NOT NULL AND created_at >= ?
                THEN 1
            END) AS users_created_today,

            COUNT(CASE
                WHEN created_at IS NOT NULL AND created_at >= ?
                THEN 1
            END) AS users_created_this_month
        FROM users
    """, (week_start, today_start, month_start))

    user_stats = cursor.fetchone()

    cursor.execute("""
        SELECT
            COUNT(DISTINCT CASE
                WHEN completed_at >= ?
                THEN user_id
            END) AS users_interacted_this_week,

            COUNT(DISTINCT CASE
                WHEN completed_at >= ?
                THEN user_id
            END) AS users_interacted_today,

            COUNT(DISTINCT CASE
                WHEN completed_at >= ?
                THEN user_id
            END) AS users_interacted_this_month
        FROM session_log
    """, (week_start, today_start, month_start))

    interaction_stats = cursor.fetchone()

    admin_stats = {
        "total_users": user_stats["total_users"] or 0,
        "users_created_this_week": user_stats["users_created_this_week"] or 0,
        "users_created_today": user_stats["users_created_today"] or 0,
        "users_created_this_month": user_stats["users_created_this_month"] or 0,
        "users_interacted_this_week": interaction_stats["users_interacted_this_week"] or 0,
        "users_interacted_today": interaction_stats["users_interacted_today"] or 0,
        "users_interacted_this_month": interaction_stats["users_interacted_this_month"] or 0
    }

    cursor.execute("""
        SELECT
            u.user_id,
            u.parent_name,
            u.email,
            u.child_name,
            u.child_age,
            COALESCE(u.login_count, 0) AS login_count,
            COALESCE(u.has_seen_tour, 0) AS has_seen_tour,

            COUNT(DISTINCT CASE
                WHEN a.is_active = 1 THEN a.activity_id
            END) AS total_levels,

            COUNT(DISTINCT CASE
                WHEN a.is_active = 1 AND p.is_unlocked = 1 THEN a.activity_id
            END) AS unlocked_levels,

            CASE
                WHEN pf.feedback_id IS NULL THEN 0
                ELSE 1
            END AS has_submitted_feedback,

            pf.created_at AS feedback_submitted_at,

            MAX(sl.completed_at) AS last_active

        FROM users u
        LEFT JOIN progress p
            ON u.user_id = p.user_id
        LEFT JOIN activity a
            ON p.activity_id = a.activity_id
        LEFT JOIN session_log sl
            ON u.user_id = sl.user_id
        LEFT JOIN parent_feedback pf
            ON pf.user_id = u.user_id
        GROUP BY u.user_id
        ORDER BY last_active DESC
    """)

    users = cursor.fetchall()
    conn.close()

    return render_template(
        "admin_user_overview.html",
        users=users,
        admin_stats=admin_stats,
        active_page="admin_user_overview"
    )

@app.route("/dashboard")
@login_required
def dashboard():
    ensure_feedback_tables()
    
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
    SELECT
        u.current_activity_id,
        COALESCE(u.has_seen_tour, 0) AS has_seen_tour,
        COALESCE(u.login_count, 0) AS login_count,
        u.feedback_prompt_dismissed_at,
        CASE
            WHEN pf.feedback_id IS NULL THEN 0
            ELSE 1
        END AS has_submitted_feedback
    FROM users u
    LEFT JOIN parent_feedback pf
        ON pf.user_id = u.user_id
    WHERE u.user_id = ?
    """, (session["user_id"],))

    user_row = cursor.fetchone()

    current_activity_id = user_row["current_activity_id"] if user_row else None
    has_seen_tour = user_row["has_seen_tour"] if user_row else 1

    login_count = user_row["login_count"] if user_row else 0
    has_submitted_feedback = bool(user_row["has_submitted_feedback"]) if user_row else True
    feedback_prompt_dismissed = bool(user_row["feedback_prompt_dismissed_at"]) if user_row else False

    show_feedback_prompt = has_seen_tour and login_count >= 2 and not has_submitted_feedback
    show_feedback_widget = has_seen_tour and not has_submitted_feedback

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
        recent_sessions=recent_sessions,
        show_feedback_prompt=show_feedback_prompt,
        feedback_prompt_dismissed=feedback_prompt_dismissed,
        login_count=login_count,
        show_feedback_widget=show_feedback_widget
    )

@app.route("/dismiss-feedback-prompt", methods=["POST"])
@csrf.exempt
@login_required
def dismiss_feedback_prompt():
    ensure_feedback_tables()

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE users
        SET feedback_prompt_dismissed_at = CURRENT_TIMESTAMP
        WHERE user_id = ?
    """, (session["user_id"],))

    conn.commit()
    conn.close()

    return jsonify({"success": True})

def has_real_child_name(value):
    child_name = clean_short_setting(value, 40).lower()
    return bool(child_name) and child_name not in {"child", "none", "null"}

@app.route("/submit-feedback", methods=["POST"])
@csrf.exempt
@login_required
def submit_feedback():
    ensure_feedback_tables()

    data = request.get_json(silent=True) or {}

    what_child_enjoyed = clean_feedback_text(data.get("what_child_enjoyed"))
    what_didnt_work = clean_feedback_text(data.get("what_didnt_work"))
    what_would_make_better = clean_feedback_text(data.get("what_would_make_better"))

    if not all([what_child_enjoyed, what_didnt_work, what_would_make_better]):
        return jsonify({
            "success": False,
            "error": "Please answer the 3 questions. Truly appreciate it!"
        }), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT feedback_id
        FROM parent_feedback
        WHERE user_id = ?
    """, (session["user_id"],))

    existing_feedback = cursor.fetchone()

    if existing_feedback:
        cursor.execute("""
            UPDATE parent_feedback
            SET
                what_child_enjoyed = ?,
                what_didnt_work = ?,
                what_would_make_better = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (
            what_child_enjoyed,
            what_didnt_work,
            what_would_make_better,
            session["user_id"]
        ))
    else:
        cursor.execute("""
            INSERT INTO parent_feedback (
                user_id,
                what_child_enjoyed,
                what_didnt_work,
                what_would_make_better
            )
            VALUES (?, ?, ?, ?)
        """, (
            session["user_id"],
            what_child_enjoyed,
            what_didnt_work,
            what_would_make_better
        ))

    conn.commit()
    conn.close()

    return jsonify({"success": True})

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

@app.route("/save-child-name-before-activity", methods=["POST"])
@csrf.exempt
@login_required
def save_child_name_before_activity():
    data = request.get_json(silent=True) or {}

    child_name = clean_short_setting(data.get("child_name"), 40)

    if not has_real_child_name(child_name):
        return jsonify({
            "success": False,
            "error": "Please enter your child's name before starting."
        }), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE users
        SET child_name = ?
        WHERE user_id = ?
    """, (child_name, session["user_id"]))

    conn.commit()
    conn.close()

    session["child_name"] = child_name

    return jsonify({
        "success": True,
        "child_name": child_name
    })

@app.route("/acknowledgments2")
def acknowledgments2():
    return render_template("acknowledgments2.html")

@app.route("/admin/feedback")
def admin_feedback():
    ensure_feedback_tables()

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            pf.feedback_id,
            pf.what_child_enjoyed,
            pf.what_didnt_work,
            pf.what_would_make_better,
            pf.created_at,
            pf.updated_at,

            u.user_id,
            u.parent_name,
            u.email,
            u.child_name,
            u.child_age
        FROM parent_feedback pf
        JOIN users u
            ON u.user_id = pf.user_id
        ORDER BY pf.updated_at DESC, pf.created_at DESC
    """)

    feedback_rows = cursor.fetchall()
    conn.close()

    return render_template(
        "admin_feedback.html",
        feedback_rows=feedback_rows,
        active_page="admin_feedback"
    )

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
    ensure_library_guessing_game_progress_columns()
    ensure_drawing_game_progress_columns()
    ensure_classroom_object_progress_columns()
    ensure_restaurant_game_progress_columns()

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

            mystery_classroom_object_rounds_completed = 0,
            mystery_classroom_object_last_played_at = NULL,

            guessing_game_rounds_completed = 0,
            guessing_game_last_played_at = NULL,

            library_guessing_game_rounds_completed = 0,
            library_guessing_game_last_played_at = NULL,

            drawing_scene_index = 0,
            drawing_stage_index = 0,
            drawing_rounds_completed = 0,
            drawing_stages_completed = 0,
            drawing_scenes_completed = 0,
            drawing_spoken_responses = 0,
            drawing_silent_windows = 0,
            drawing_total_color_selections = 0,
            drawing_canvas_data = NULL,
            drawing_last_played_at = NULL,

            restaurant_order_index = 0,
            restaurant_step_index = 0,
            restaurant_orders_completed = 0,
            restaurant_steps_completed = 0,
            restaurant_spoken_responses = 0,
            restaurant_silent_windows = 0,
            restaurant_worker_direct_responses = 0,
            restaurant_teacher_redirects = 0,
            restaurant_total_choices = 0,
            restaurant_last_pizza_json = NULL,
            restaurant_last_played_at = NULL
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
    session.pop("mystery_classroom_object_history", None)
    session.pop("mystery_classroom_object_state", None)
    session.pop("book_guessing_game_history", None)
    session.pop("book_guessing_game_state", None)
    session.pop("library_guessing_game_history", None)
    session.pop("library_guessing_game_state", None)
    session.pop("mystery_food_item_history", None)
    session.pop("mystery_food_item_state", None)
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

    activity_id_int = int(activity["activity_id"])

    if activity_id_int > 1:
        cursor.execute("""
            SELECT p.is_unlocked
            FROM progress p
            JOIN activity a ON p.activity_id = a.activity_id
            WHERE p.user_id = ?
            AND a.activity_id = ?
            AND a.is_active = 1
        """, (
            session["user_id"],
            activity_id_int - 1
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

    cursor.execute("""
        SELECT child_name
        FROM users
        WHERE user_id = ?
    """, (session["user_id"],))
    user_row = cursor.fetchone()

    conn.close()

    if not progress or not progress["is_unlocked"]:
        return redirect(url_for("dashboard"))

    child_name = user_row["child_name"] if user_row else session.get("child_name", "")

    if not has_real_child_name(child_name):
        session["child_name"] = ""
        return redirect(url_for(
            "dashboard",
            child_name_required=1,
            activity_id=activity_id
        ))

    session["child_name"] = child_name

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

@app.route("/getting-started")
def getting_started():
    return render_template(
        "getting_started.html",
        active_page="getting_started"
    )
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
                AND activity_id > ?
            ORDER BY activity_id ASC
            LIMIT 1
        """, (
            current_activity["activity_id"],
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
                 AND activity_id > ?
                ORDER BY activity_id ASC
                LIMIT 1
            """, (
                activity["activity_id"],
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
            AND activity_id > ?
            ORDER BY activity_id ASC
            LIMIT 1
        """, (
            current_activity["activity_id"],
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
        message = question_text

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
GUESSING_GAME_NEXT_ACTIVITY_ID = 4

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
        message = question_text

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
# =========================
# Mystery Classroom Object — Teacher version of Mystery Animal
# Replace the old Book Guessing Game backend block with this complete block.
# Frontend can keep using:
#   /api/book-guessing-game/thinking-audio
#   /api/book-guessing-game/message
#   /api/book-guessing-game/transcribe
# The block also supports /api/mystery-classroom-object/* aliases.
# =========================

CLASSROOM_OBJECT_REQUIRED_ROUNDS = 9
CLASSROOM_OBJECT_MAX_QUESTIONS_PER_ROUND = 9
CLASSROOM_OBJECT_SOFT_REVEAL_QUESTION_LIMIT = 9


def generate_book_guessing_voice_elevenlabs(text, game_complete=False, thinking=False):
    """Teacher voice for the classroom object game.

    Keep the function name so the old frontend/backend references do not break.
    Add TEACHER_VOICE_ID to your .env if you want a dedicated teacher voice.
    """
    voice_id = (
        os.getenv("TEACHER_VOICE_ID")
        or os.getenv("LIBRARIAN_VOICE_ID")
        or os.getenv("ELEVENLABS_VOICE_ID", "piI8Kku0DcvcL6TTSeQt")
    )

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


CLASSROOM_OBJECT_PROFILES = {
    "pencil": {
        "display": "pencil",
        "aliases": {"pencil", "lead pencil"},
        "tags": {"category_write_draw", "size_small", "material_wood", "material_graphite", "loc_desk", "loc_backpack", "feature_pointy", "feature_eraser", "writing", "drawing", "long", "yellow"},
        "colors": {"yellow", "black", "brown", "wood"},
        "hints": ["You can write with it.", "It is often yellow and pointy.", "It may have an eraser on the end."]
    },
    "pen": {
        "display": "pen",
        "aliases": {"pen", "ink pen"},
        "tags": {"category_write_draw", "size_small", "material_plastic", "material_metal", "loc_desk", "loc_backpack", "feature_cap", "feature_click", "writing", "ink", "long"},
        "colors": {"black", "blue", "red", "gray", "silver"},
        "hints": ["You can write with it.", "It uses ink.", "Some kinds click or have a cap."]
    },
    "eraser": {
        "display": "eraser",
        "aliases": {"eraser", "rubber"},
        "tags": {"category_erase", "size_small", "material_rubber", "loc_desk", "loc_backpack", "feature_soft", "erase", "school_supply"},
        "colors": {"pink", "white", "gray"},
        "hints": ["It helps fix pencil mistakes.", "It is small and often soft.", "You might keep it near a pencil."]
    },
    "crayon": {
        "display": "crayon",
        "aliases": {"crayon", "crayons"},
        "tags": {"category_write_draw", "category_art_craft", "size_small", "material_wax", "loc_desk", "loc_backpack", "coloring", "drawing", "art", "long"},
        "colors": {"red", "blue", "green", "yellow", "orange", "purple", "black"},
        "hints": ["You use it to color pictures.", "It can come in many colors.", "It is often used during art time."]
    },
    "marker": {
        "display": "marker",
        "aliases": {"marker", "markers"},
        "tags": {"category_write_draw", "category_art_craft", "size_small", "material_plastic", "loc_desk", "loc_backpack", "feature_cap", "writing", "drawing", "coloring", "ink", "long"},
        "colors": {"red", "blue", "green", "black", "purple", "yellow"},
        "hints": ["It can make bright lines.", "You can use it to write or draw.", "It usually has a cap."]
    },
    "colored pencil": {
        "display": "colored pencil",
        "aliases": {"colored pencil", "colour pencil", "color pencil", "colored pencils"},
        "tags": {"category_write_draw", "category_art_craft", "size_small", "material_wood", "loc_desk", "loc_backpack", "feature_pointy", "drawing", "coloring", "long"},
        "colors": {"red", "blue", "green", "yellow", "purple", "orange", "brown", "black"},
        "hints": ["You can draw or color with it.", "It is like a pencil, but colorful.", "It can be sharpened."]
    },
    "glue stick": {
        "display": "glue stick",
        "aliases": {"glue", "glue stick", "gluestick"},
        "tags": {"category_art_craft", "size_small", "material_plastic", "loc_desk", "loc_backpack", "feature_lid", "feature_sticky", "craft", "sticky"},
        "colors": {"white", "purple", "clear"},
        "hints": ["It helps paper stick together.", "You might use it for crafts.", "It can twist up from a tube."]
    },
    "scissors": {
        "display": "scissors",
        "aliases": {"scissors", "scissor"},
        "tags": {"category_cutting", "category_art_craft", "size_small", "material_metal", "material_plastic", "loc_desk", "loc_backpack", "feature_handles", "feature_sharp", "cutting"},
        "colors": {"blue", "red", "green", "silver", "black"},
        "hints": ["It is used for cutting paper.", "It has handles.", "A teacher might remind you to use it carefully."]
    },
    "ruler": {
        "display": "ruler",
        "aliases": {"ruler", "measuring stick"},
        "tags": {"category_measuring", "size_small", "material_wood", "material_plastic", "material_metal", "loc_desk", "loc_backpack", "feature_straight", "feature_flat", "measure", "long"},
        "colors": {"brown", "clear", "yellow", "blue", "silver"},
        "hints": ["It helps you measure.", "It is long and straight.", "It can help draw a straight line."]
    },
    "folder": {
        "display": "folder",
        "aliases": {"folder", "folders"},
        "tags": {"category_storage", "category_paper_book", "size_medium", "material_paper", "material_plastic", "loc_backpack", "loc_desk", "feature_flat", "organize", "papers"},
        "colors": {"red", "blue", "green", "yellow", "purple"},
        "hints": ["It can hold papers.", "It is flat and can go in a backpack.", "It helps keep schoolwork organized."]
    },
    "notebook": {
        "display": "notebook",
        "aliases": {"notebook", "notepad", "journal"},
        "tags": {"category_paper_book", "category_write_draw", "size_medium", "material_paper", "loc_desk", "loc_backpack", "feature_pages", "feature_flat", "writing", "notes"},
        "colors": {"red", "blue", "green", "black", "purple", "yellow"},
        "hints": ["It has pages inside.", "You can write notes in it.", "It might sit on a desk or go in a backpack."]
    },
    "textbook": {
        "display": "textbook",
        "aliases": {"textbook", "school book", "book"},
        "tags": {"category_paper_book", "size_medium", "material_paper", "loc_desk", "loc_backpack", "loc_shelf", "feature_pages", "reading", "learning"},
        "colors": {"blue", "red", "green", "black", "white", "yellow"},
        "hints": ["It has lots of pages.", "You might read it for class.", "It can be heavy in a backpack."]
    },
    "worksheet": {
        "display": "worksheet",
        "aliases": {"worksheet", "paper", "handout"},
        "tags": {"category_paper_book", "category_write_draw", "size_medium", "material_paper", "loc_desk", "loc_backpack", "feature_flat", "writing", "schoolwork"},
        "colors": {"white"},
        "hints": ["It is a piece of paper.", "A teacher might pass it out.", "Students write answers on it."]
    },
    "backpack": {
        "display": "backpack",
        "aliases": {"backpack", "bag", "school bag", "bookbag"},
        "tags": {"category_storage", "size_large", "material_fabric", "loc_floor", "feature_straps", "feature_zipper", "carry", "wear"},
        "colors": {"black", "blue", "red", "pink", "green", "purple", "gray"},
        "hints": ["You can carry school supplies in it.", "It often has straps.", "You might wear it on your back."]
    },
    "lunchbox": {
        "display": "lunchbox",
        "aliases": {"lunchbox", "lunch box"},
        "tags": {"category_storage", "size_medium", "material_plastic", "material_fabric", "loc_backpack", "loc_floor", "feature_handle", "carry", "food"},
        "colors": {"blue", "red", "pink", "black", "purple", "green"},
        "hints": ["It can hold food.", "You might bring it from home.", "It may have a handle."]
    },
    "water bottle": {
        "display": "water bottle",
        "aliases": {"water bottle", "bottle"},
        "tags": {"category_storage", "size_medium", "material_plastic", "material_metal", "loc_desk", "loc_backpack", "feature_lid", "drink"},
        "colors": {"blue", "clear", "silver", "black", "pink", "green"},
        "hints": ["It can hold a drink.", "It usually has a lid.", "It might sit on a desk."]
    },
    "pencil sharpener": {
        "display": "pencil sharpener",
        "aliases": {"pencil sharpener", "sharpener"},
        "tags": {"category_write_draw", "size_small", "material_plastic", "material_metal", "loc_desk", "loc_wall", "feature_hole", "feature_sharp", "sharpen"},
        "colors": {"blue", "black", "gray", "silver", "red"},
        "hints": ["It helps make a pencil pointy again.", "Some are small and some are on a wall.", "It has a little sharp part inside."]
    },
    "paper clip": {
        "display": "paper clip",
        "aliases": {"paper clip", "paperclip", "clip"},
        "tags": {"category_organize", "size_small", "material_metal", "loc_desk", "loc_backpack", "feature_bendy", "papers", "hold_together"},
        "colors": {"silver", "gray", "metal"},
        "hints": ["It can hold papers together.", "It is very small.", "It is often made of metal."]
    },
    "stapler": {
        "display": "stapler",
        "aliases": {"stapler"},
        "tags": {"category_organize", "size_medium", "material_plastic", "material_metal", "loc_desk", "feature_metal", "papers", "hold_together"},
        "colors": {"black", "gray", "red", "blue", "silver"},
        "hints": ["It fastens papers together.", "It uses staples.", "You might find it on a teacher's desk."]
    },
    "tape": {
        "display": "tape",
        "aliases": {"tape", "clear tape", "tape roll"},
        "tags": {"category_art_craft", "category_organize", "size_small", "material_plastic", "loc_desk", "feature_sticky", "feature_roll", "sticky"},
        "colors": {"clear", "white"},
        "hints": ["It is sticky.", "It can come on a roll.", "It helps attach things together."]
    },
    "calculator": {
        "display": "calculator",
        "aliases": {"calculator"},
        "tags": {"category_technology", "size_small", "material_plastic", "material_electronic", "loc_desk", "loc_backpack", "feature_buttons", "numbers", "math"},
        "colors": {"black", "gray", "blue", "silver"},
        "hints": ["It has number buttons.", "You might use it in math.", "It helps solve number problems."]
    },
    "computer": {
        "display": "computer",
        "aliases": {"computer", "laptop", "chromebook"},
        "tags": {"category_technology", "size_medium", "material_electronic", "material_metal", "material_plastic", "loc_desk", "feature_screen", "feature_keyboard", "typing", "learning"},
        "colors": {"black", "gray", "silver", "white"},
        "hints": ["It has a screen.", "You might type on it.", "It uses electricity."]
    },
    "keyboard": {
        "display": "keyboard",
        "aliases": {"keyboard"},
        "tags": {"category_technology", "size_medium", "material_plastic", "material_electronic", "loc_desk", "feature_buttons", "typing"},
        "colors": {"black", "white", "gray"},
        "hints": ["It has lots of keys.", "You type on it.", "It can be near a computer."]
    },
    "computer mouse": {
        "display": "computer mouse",
        "aliases": {"computer mouse", "mouse"},
        "tags": {"category_technology", "size_small", "material_plastic", "material_electronic", "loc_desk", "feature_buttons", "clicking"},
        "colors": {"black", "white", "gray"},
        "hints": ["You can click it.", "It helps control a computer.", "It sits near a keyboard."]
    },
    "headphones": {
        "display": "headphones",
        "aliases": {"headphones", "headset"},
        "tags": {"category_technology", "size_medium", "material_plastic", "material_electronic", "loc_desk", "loc_backpack", "feature_ear", "sound"},
        "colors": {"black", "white", "blue", "gray"},
        "hints": ["You wear them on your ears.", "They help you listen quietly.", "They may plug into a computer."]
    },
    "whiteboard": {
        "display": "whiteboard",
        "aliases": {"whiteboard", "dry erase board", "board"},
        "tags": {"category_wall_front", "size_large", "material_plastic", "material_metal", "loc_wall", "loc_front", "feature_flat", "writing", "teacher"},
        "colors": {"white"},
        "hints": ["A teacher might write on it.", "It is usually big and white.", "It is often at the front of a classroom."]
    },
    "chalkboard": {
        "display": "chalkboard",
        "aliases": {"chalkboard", "blackboard"},
        "tags": {"category_wall_front", "size_large", "material_wood", "loc_wall", "loc_front", "feature_flat", "writing", "teacher", "chalk"},
        "colors": {"green", "black"},
        "hints": ["A teacher might write on it with chalk.", "It is often at the front of a classroom.", "It is large and flat."]
    },
    "smartboard": {
        "display": "smartboard",
        "aliases": {"smartboard", "smart board", "projector board", "screen"},
        "tags": {"category_wall_front", "category_technology", "size_large", "material_electronic", "material_plastic", "loc_wall", "loc_front", "feature_screen", "feature_flat", "teacher"},
        "colors": {"white", "black", "gray"},
        "hints": ["It is a large screen or board.", "A teacher might use it for lessons.", "It is usually at the front of the room."]
    },
    "clock": {
        "display": "clock",
        "aliases": {"clock", "wall clock"},
        "tags": {"category_wall_front", "size_medium", "material_plastic", "material_metal", "loc_wall", "feature_round", "numbers", "time"},
        "colors": {"white", "black", "gray"},
        "hints": ["It tells time.", "It is often on the wall.", "It may have numbers around it."]
    },
    "calendar": {
        "display": "calendar",
        "aliases": {"calendar"},
        "tags": {"category_wall_front", "category_paper_book", "size_medium", "material_paper", "loc_wall", "feature_pages", "dates", "time"},
        "colors": {"white", "blue", "red", "black"},
        "hints": ["It shows days and months.", "It can hang on a wall.", "A teacher might use it to show the date."]
    },
    "bulletin board": {
        "display": "bulletin board",
        "aliases": {"bulletin board", "cork board"},
        "tags": {"category_wall_front", "size_large", "material_wood", "material_paper", "loc_wall", "feature_flat", "display", "papers"},
        "colors": {"brown", "tan", "colorful"},
        "hints": ["It can show papers or decorations.", "It is often on a classroom wall.", "Teachers might pin things to it."]
    },
    "poster": {
        "display": "poster",
        "aliases": {"poster", "classroom poster"},
        "tags": {"category_wall_front", "category_paper_book", "size_medium", "material_paper", "loc_wall", "feature_flat", "display", "colorful"},
        "colors": {"red", "blue", "green", "yellow", "white", "black"},
        "hints": ["It hangs on a wall.", "It may have words or pictures.", "It can decorate the classroom."]
    },
    "bookshelf": {
        "display": "bookshelf",
        "aliases": {"bookshelf", "book shelf", "shelf"},
        "tags": {"category_storage", "category_furniture", "size_large", "material_wood", "material_metal", "loc_floor", "loc_wall", "loc_shelf", "feature_shelves", "books"},
        "colors": {"brown", "white", "black", "gray"},
        "hints": ["It holds books.", "It is usually large.", "It may stand against a wall."]
    },
    "desk": {
        "display": "desk",
        "aliases": {"desk", "student desk"},
        "tags": {"category_furniture", "size_large", "material_wood", "material_metal", "loc_floor", "feature_flat_surface", "work", "sit"},
        "colors": {"brown", "tan", "gray", "black"},
        "hints": ["A student might sit at it.", "It has a flat top.", "You can work on it in class."]
    },
    "chair": {
        "display": "chair",
        "aliases": {"chair", "seat"},
        "tags": {"category_furniture", "size_large", "material_plastic", "material_wood", "material_metal", "loc_floor", "feature_legs", "sit"},
        "colors": {"blue", "brown", "gray", "black", "red"},
        "hints": ["You can sit on it.", "It is classroom furniture.", "It is often next to a desk."]
    },
    "teacher desk": {
        "display": "teacher desk",
        "aliases": {"teacher desk", "teacher's desk"},
        "tags": {"category_furniture", "size_large", "material_wood", "material_metal", "loc_front", "loc_floor", "feature_flat_surface", "teacher", "work"},
        "colors": {"brown", "tan", "gray", "black"},
        "hints": ["It is a desk for the teacher.", "It is often near the front of the room.", "It may have papers or supplies on it."]
    },
    "trash can": {
        "display": "trash can",
        "aliases": {"trash can", "garbage can", "bin"},
        "tags": {"category_other", "size_medium", "material_plastic", "material_metal", "loc_floor", "feature_opening", "trash"},
        "colors": {"black", "gray", "blue", "green"},
        "hints": ["It sits on the floor.", "People put trash in it.", "It may be near a desk or door."]
    },
    "cubby": {
        "display": "cubby",
        "aliases": {"cubby", "cubbies", "locker"},
        "tags": {"category_storage", "category_furniture", "size_large", "material_wood", "material_metal", "loc_wall", "loc_floor", "feature_compartments", "storage"},
        "colors": {"brown", "gray", "white"},
        "hints": ["Students can store things in it.", "It may have little spaces or compartments.", "It can be near the wall."]
    }
}


CLASSROOM_OBJECT_QUESTION_BANK = [
    {
        "key": "category_first",
        "question": "Is it something you write with, something you carry, or a different kind of classroom object?",
        "stage": "guided_choice",
        "response_mode": "choice",
        "option_tags": {
            "write": {"writing", "drawing", "coloring"},
            "writing": {"writing", "drawing", "coloring"},
            "draw": {"drawing", "coloring"},
            "drawing": {"drawing", "coloring"},
            "color": {"coloring", "drawing"},
            "carry": {"category_storage", "carry", "wear", "loc_backpack"},
            "store": {"category_storage"},
            "storage": {"category_storage"},
            "backpack": {"category_storage", "loc_backpack", "wear"}
        }
    },
    {
        "key": "write_tool_type",
        "question": "Does it use ink, color, or a different kind of mark?",
        "stage": "guided_choice",
        "response_mode": "choice",
        "option_tags": {
            "ink": {"ink"},
            "pen": {"ink"},
            "color": {"coloring", "drawing"},
            "colors": {"coloring", "drawing"},
            "colour": {"coloring", "drawing"},
            "draw": {"drawing"}
        }
    },
    {
        "key": "write_feature_followup",
        "question": "Does it have a cap, have an eraser, or neither?",
        "stage": "guided_choice",
        "response_mode": "choice",
        "option_tags": {
            "cap": {"feature_cap"},
            "lid": {"feature_cap", "feature_lid"},
            "eraser": {"feature_eraser", "erase"},
            "erase": {"feature_eraser", "erase"}
        }
    },
    {
        "key": "storage_detail_first",
        "question": "Do you wear it, drink from it, or use it another way?",
        "stage": "guided_choice",
        "response_mode": "choice",
        "option_tags": {
            "wear": {"wear", "feature_straps"},
            "straps": {"wear", "feature_straps"},
            "drink": {"drink"},
            "water": {"drink"},
            "food": {"food"}
        }
    },
    {
        "key": "wall_detail_first",
        "question": "Is it a board, a clock, or a different wall object?",
        "stage": "guided_choice",
        "response_mode": "choice",
        "option_tags": {
            "board": {"category_wall_front", "teacher", "feature_flat"},
            "whiteboard": {"category_wall_front", "teacher", "feature_flat"},
            "chalkboard": {"category_wall_front", "teacher", "feature_flat", "chalk"},
            "clock": {"time", "numbers"},
            "time": {"time", "numbers"}
        }
    },
    {
        "key": "furniture_detail_first",
        "question": "Do you sit on it, work on it, or use it another way?",
        "stage": "guided_choice",
        "response_mode": "choice",
        "option_tags": {
            "sit": {"sit"},
            "chair": {"sit"},
            "work": {"work", "feature_flat_surface"},
            "desk": {"work", "feature_flat_surface", "loc_desk"}
        }
    },
    {
        "key": "category_other_followup",
        "question": "Is it furniture, something on the wall, or a different kind of object?",
        "stage": "guided_choice",
        "response_mode": "choice",
        "option_tags": {
            "furniture": {"category_furniture"},
            "desk": {"category_furniture", "loc_desk"},
            "chair": {"category_furniture", "sit"},
            "sit": {"category_furniture", "sit"},
            "wall": {"category_wall_front", "loc_wall"},
            "front": {"category_wall_front", "loc_front"},
            "board": {"category_wall_front", "loc_front"}
        }
    },
    {
        "key": "size_first",
        "question": "Is it small, medium-sized, or big?",
        "stage": "guided_choice",
        "response_mode": "choice",
        "option_tags": {
            "small": {"size_small"},
            "hand": {"size_small"},
            "medium": {"size_medium"},
            "book": {"size_medium"},
            "lunchbox": {"size_medium"},
            "big": {"size_large"},
            "large": {"size_large"},
            "furniture": {"size_large"},
            "board": {"size_large"}
        }
    },
    {
        "key": "material_first",
        "question": "Is it made of paper, plastic, or another material?",
        "stage": "guided_choice",
        "response_mode": "choice",
        "option_tags": {
            "paper": {"material_paper"},
            "cardboard": {"material_paper"},
            "plastic": {"material_plastic"}
        }
    },
    {
        "key": "material_other_one",
        "question": "Is it made of metal, wood, or another material?",
        "stage": "guided_choice",
        "response_mode": "choice",
        "option_tags": {
            "metal": {"material_metal"},
            "silver": {"material_metal", "silver"},
            "wood": {"material_wood"},
            "wooden": {"material_wood"}
        }
    },
    {
        "key": "material_other_two",
        "question": "Is it fabric, electronic, or neither?",
        "stage": "guided_choice",
        "response_mode": "choice",
        "option_tags": {
            "fabric": {"material_fabric"},
            "cloth": {"material_fabric"},
            "electronic": {"material_electronic", "category_technology"},
            "electric": {"material_electronic", "category_technology"},
            "technology": {"material_electronic", "category_technology"}
        }
    },
    {
        "key": "where_first",
        "question": "Is it usually on a desk, in a backpack, or somewhere different?",
        "stage": "guided_choice",
        "response_mode": "choice",
        "option_tags": {
            "desk": {"loc_desk"},
            "table": {"loc_desk"},
            "backpack": {"loc_backpack"},
            "bag": {"loc_backpack"}
        }
    },
    {
        "key": "where_other",
        "question": "Is it on the wall, on a shelf, or somewhere different?",
        "stage": "guided_choice",
        "response_mode": "choice",
        "option_tags": {
            "wall": {"loc_wall"},
            "front": {"loc_front"},
            "board": {"loc_front", "category_wall_front"},
            "shelf": {"loc_shelf"},
            "bookshelf": {"loc_shelf"},
            "floor": {"loc_floor"}
        }
    },
    {
        "key": "use_first",
        "question": "Do people use it to write, cut things, or something else?",
        "stage": "guided_choice",
        "response_mode": "choice",
        "option_tags": {
            "write": {"category_write_draw", "writing"},
            "draw": {"category_write_draw", "drawing"},
            "color": {"category_art_craft", "coloring"},
            "cut": {"category_cutting", "cutting"},
            "scissor": {"category_cutting", "cutting"},
            "scissors": {"category_cutting", "cutting"}
        }
    },
    {
        "key": "use_other",
        "question": "Does it organize papers, use technology, or something else?",
        "stage": "guided_choice",
        "response_mode": "choice",
        "option_tags": {
            "organize": {"category_organize"},
            "papers": {"category_paper_book", "papers"},
            "paper": {"category_paper_book", "papers"},
            "technology": {"category_technology", "material_electronic"},
            "screen": {"category_technology", "feature_screen"},
            "computer": {"category_technology", "material_electronic"}
        }
    },
    {
        "key": "feature_first",
        "question": "Does it have pages, a cap, or something else?",
        "stage": "guided_choice",
        "response_mode": "choice",
        "option_tags": {
            "pages": {"feature_pages", "category_paper_book"},
            "page": {"feature_pages", "category_paper_book"},
            "cap": {"feature_cap"},
            "lid": {"feature_lid"}
        }
    },
    {
        "key": "feature_other",
        "question": "Does it have handles, a screen, or something else?",
        "stage": "guided_choice",
        "response_mode": "choice",
        "option_tags": {
            "handle": {"feature_handle", "feature_handles"},
            "handles": {"feature_handle", "feature_handles"},
            "strap": {"feature_straps"},
            "straps": {"feature_straps"},
            "screen": {"feature_screen"},
            "buttons": {"feature_buttons"},
            "button": {"feature_buttons"}
        }
    },
    {
        "key": "color_choice",
        "question": "Is it mostly white, black, or another color?",
        "stage": "one_word",
        "response_mode": "one_word",
        "option_tags": {
            "white": {"white"},
            "black": {"black"},
            "blue": {"blue"},
            "red": {"red"},
            "green": {"green"},
            "yellow": {"yellow"},
            "pink": {"pink"},
            "purple": {"purple"},
            "brown": {"brown"},
            "gray": {"gray"},
            "grey": {"gray"},
            "silver": {"silver"},
            "clear": {"clear"},
            "orange": {"orange"}
        }
    },
    {
        "key": "extra_hint",
        "question": "Can you give me one hint about what people do with it?",
        "stage": "open_hint",
        "response_mode": "open_hint",
        "option_tags": {}
    },
    {
        "key": "last_hint",
        "question": "One last clue. What makes it special?",
        "stage": "open_hint",
        "response_mode": "open_hint",
        "option_tags": {}
    }
]


def normalize_classroom_object_text(text):
    text = re.sub(r"\s+", " ", str(text or "")).strip().lower()
    text = text.replace("’", "'")
    text = re.sub(r"[^a-z0-9' -]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def classroom_object_words(text):
    return set(re.findall(r"[a-z']+", normalize_classroom_object_text(text)))


def clean_classroom_child_name(child_name):
    name = re.sub(r"[^A-Za-z' -]", "", str(child_name or "")).strip()
    name = re.sub(r"\s+", " ", name)
    if not name or name.lower() in {"none", "child"}:
        return ""
    return name[:28]


def get_classroom_object_default_state(rounds_completed=0):
    try:
        rounds_completed_int = max(0, int(float(rounds_completed or 0)))
    except (TypeError, ValueError):
        rounds_completed_int = 0

    return {
        "stage": "intro",
        "rounds_completed": rounds_completed_int,
        "questions_asked": 0,
        "comfortable_answer_count": 0,
        "unclear_or_silent_count": 0,
        "comfortable_streak": 0,
        "unclear_streak": 0,
        "question_history": [],
        "known_clues": [],
        "clue_tags": [],
        "answers_by_key": {},
        "rejected_guesses": [],
        "possible_guess": None,
        "last_question": None,
        "last_question_key": None,
        "last_response_mode": "none",
        "game_complete": False,
        "skip_guess_once": False,
        "guess_cooldown_questions": 0,
        "recent_guesses": [],
        "recent_acknowledgments": [],
        "soft_reveal_used": False,
        # Active candidate pool for the current object attempt. The first three
        # choice answers filter this list. "I don't know" / unclear answers do not.
        "candidate_keys": list(CLASSROOM_OBJECT_PROFILES.keys()),
        "candidate_filter_notes": [],
        "void_question_keys": []
    }


def ensure_classroom_object_progress_columns():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(progress)")
    existing_columns = {row["name"] for row in cursor.fetchall()}

    columns_to_add = {
        "mystery_classroom_object_rounds_completed": "ALTER TABLE progress ADD COLUMN mystery_classroom_object_rounds_completed INTEGER DEFAULT 0",
        "mystery_classroom_object_last_played_at": "ALTER TABLE progress ADD COLUMN mystery_classroom_object_last_played_at TEXT"
    }

    for column_name, alter_sql in columns_to_add.items():
        if column_name not in existing_columns:
            cursor.execute(alter_sql)

    conn.commit()
    conn.close()


def get_classroom_object_activity(cursor):
    cursor.execute("""
        SELECT activity_id, scene_id, activity_order
        FROM activity
        WHERE is_active = 1
          AND activity_name IN (
            'mystery_classroom_object',
            'book_guessing_game',
            'classroom_object_game'
          )
        ORDER BY CASE activity_name
            WHEN 'mystery_classroom_object' THEN 1
            WHEN 'book_guessing_game' THEN 2
            ELSE 3
        END
        LIMIT 1
    """)
    return cursor.fetchone()


def get_saved_classroom_object_rounds():
    ensure_classroom_object_progress_columns()

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        activity = get_classroom_object_activity(cursor)

        if not activity:
            conn.close()
            return 0

        cursor.execute("""
            SELECT COALESCE(mystery_classroom_object_rounds_completed, 0) AS rounds_completed
            FROM progress
            WHERE user_id = ? AND activity_id = ?
        """, (session["user_id"], activity["activity_id"]))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return 0

        return max(0, int(row["rounds_completed"] or 0))

    except Exception as e:
        print("Could not load Mystery Classroom Object progress:", repr(e))
        return 0


def save_classroom_object_round_progress(rounds_completed):
    ensure_classroom_object_progress_columns()

    try:
        rounds_completed = max(0, int(rounds_completed or 0))
        conn = get_db_connection()
        cursor = conn.cursor()
        activity = get_classroom_object_activity(cursor)

        if not activity:
            conn.close()
            return None

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
        """, (session["user_id"], activity["activity_id"]))

        cursor.execute("""
            UPDATE progress
            SET
                mystery_classroom_object_rounds_completed = MAX(
                    COALESCE(mystery_classroom_object_rounds_completed, 0),
                    ?
                ),
                mystery_classroom_object_last_played_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND activity_id = ?
        """, (rounds_completed, session["user_id"], activity["activity_id"]))

        conn.commit()
        conn.close()
        return activity["activity_id"]

    except Exception as e:
        print("Could not save Mystery Classroom Object progress:", repr(e))
        return None


def complete_classroom_object_and_unlock_next_for_user(rounds_completed=None):
    ensure_classroom_object_progress_columns()

    try:
        completed_rounds = max(0, int(rounds_completed or CLASSROOM_OBJECT_REQUIRED_ROUNDS))
        conn = get_db_connection()
        cursor = conn.cursor()
        current_activity = get_classroom_object_activity(cursor)

        if not current_activity:
            conn.close()
            return None

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
        """, (session["user_id"], current_activity["activity_id"]))

        cursor.execute("""
            UPDATE progress
            SET
                is_completed = 1,
                mystery_classroom_object_rounds_completed = MAX(
                    COALESCE(mystery_classroom_object_rounds_completed, 0),
                    ?
                ),
                mystery_classroom_object_last_played_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND activity_id = ?
        """, (
            max(completed_rounds, CLASSROOM_OBJECT_REQUIRED_ROUNDS),
            session["user_id"],
            current_activity["activity_id"]
        ))

        cursor.execute("""
            SELECT activity_id
            FROM activity
            WHERE is_active = 1
            AND activity_id > ?
            ORDER BY activity_id ASC
            LIMIT 1
        """, (
            current_activity["activity_id"],
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
        print("Could not complete Mystery Classroom Object and unlock next activity:", repr(e))
        return None


def should_classroom_object_ask_round_choice(rounds_completed):
    completed = int(rounds_completed or 0)

    if completed >= CLASSROOM_OBJECT_REQUIRED_ROUNDS:
        return True

    # Pause after every two completed activity rounds so the child can choose
    # whether to continue playing or take a break for now.
    return completed > 0 and completed % 2 == 0


def is_classroom_object_final_round_choice(rounds_completed):
    return int(rounds_completed or 0) >= CLASSROOM_OBJECT_REQUIRED_ROUNDS


def is_classroom_object_break_checkpoint(rounds_completed):
    completed = int(rounds_completed or 0)
    return 0 < completed < CLASSROOM_OBJECT_REQUIRED_ROUNDS and completed % 2 == 0


def is_classroom_object_unclear_or_silent(text):
    lowered = normalize_classroom_object_text(text)

    if not lowered:
        return True

    unclear_phrases = {
        "i don't know", "i dont know", "i do not know", "don't know", "dont know",
        "idk", "not sure", "i'm not sure", "im not sure", "maybe", "hmm", "hm",
        "mm", "mmm", "uh", "um", "wait", "hold on"
    }

    if lowered in unclear_phrases:
        return True

    words = re.findall(r"[a-z']+", lowered)
    filler_words = {"hmm", "hm", "mm", "mmm", "uh", "um", "like", "wait"}
    return bool(words) and all(word in filler_words for word in words)


def classroom_object_is_yes(text):
    words = classroom_object_words(text)
    return bool(words & {"yes", "yeah", "yep", "yup", "sure", "correct", "right"})


def classroom_object_is_no(text):
    words = classroom_object_words(text)
    return bool(words & {"no", "nope", "nah", "not", "wrong"})


def is_clear_classroom_object_response(text, response_mode):
    if is_classroom_object_unclear_or_silent(text):
        return False

    if response_mode in {"yes_no", "guess_confirmation"}:
        return classroom_object_is_yes(text) or classroom_object_is_no(text)

    return len(re.findall(r"[A-Za-z']+", str(text or ""))) >= 1


def get_classroom_object_named_object(text):
    lowered = normalize_classroom_object_text(text)
    words = classroom_object_words(lowered)

    for object_key, profile in CLASSROOM_OBJECT_PROFILES.items():
        for alias in profile.get("aliases", set()):
            alias_clean = normalize_classroom_object_text(alias)
            alias_words = classroom_object_words(alias_clean)

            if not alias_clean:
                continue

            if " " in alias_clean and alias_clean in lowered:
                return profile["display"]

            if alias_clean in words:
                return profile["display"]

            if alias_words and alias_words.issubset(words):
                return profile["display"]

    return None


def classroom_object_article(noun):
    noun = normalize_classroom_object_text(noun)
    if noun[:1] in {"a", "e", "i", "o", "u"}:
        return "an"
    return "a"


def parse_child_told_classroom_object(text):
    lowered = normalize_classroom_object_text(text)

    if not lowered:
        return None

    reveal_phrases = [
        "it's", "it is", "my object is", "the object is", "my thing is", "the thing is",
        "i picked", "i chose", "i was thinking of", "i am thinking of", "i'm thinking of",
        "it was", "it's a", "it is a"
    ]

    named = get_classroom_object_named_object(lowered)
    if named and (any(phrase in lowered for phrase in reveal_phrases) or len(classroom_object_words(lowered)) <= 5):
        return named

    return None


def classify_classroom_object_round_choice(text, offer_next_game=False):
    lowered = normalize_classroom_object_text(text)
    words = classroom_object_words(lowered)

    if not lowered:
        return "unclear"

    stop_words = {"stop", "done", "finish", "finished", "end", "quit", "leave", "dashboard", "break", "pause", "rest", "no", "nope", "nah"}
    same_game_words = {"again", "same", "replay", "more", "continue", "keep", "yes", "yeah", "yep", "yup", "sure", "okay", "ok", "alright"}
    next_game_words = {"different", "new", "next", "other"}

    if words & stop_words:
        return "stop"

    if offer_next_game and words & next_game_words:
        return "next_game"

    if words & same_game_words:
        return "same_game"

    if any(phrase in lowered for phrase in ["take a break", "break for now", "pause for now", "stop for now", "end for now"]):
        return "stop"

    if any(phrase in lowered for phrase in ["continue playing", "keep playing", "play more", "play again", "another round", "one more", "same game"]):
        return "same_game"

    if offer_next_game and any(phrase in lowered for phrase in ["next game", "different game", "new game", "other game"]):
        return "next_game"

    return "unclear"


def calm_classroom_object_line(text, game_complete=False):
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

    return text[:300].strip()


def get_classroom_latest_clue_answer(game_state, key):
    for item in reversed(game_state.get("known_clues", [])):
        if isinstance(item, dict) and item.get("question_key") == key:
            return normalize_classroom_object_text(item.get("answer", ""))
    return ""


def classroom_answer_was_other(answer):
    lowered = normalize_classroom_object_text(answer)
    if not lowered:
        return False

    other_phrases = {
        "something else", "somewhere else", "someone else", "other", "another",
        "neither", "none", "none of those", "not those", "not that",
        "not any of those", "no", "nope"
    }

    if lowered in other_phrases:
        return True

    return any(phrase in lowered for phrase in [
        "something else",
        "somewhere else",
        "none of",
        "not those",
        "not any",
        "neither"
    ])


def classroom_chose_other_for_key(game_state, key):
    return classroom_answer_was_other(get_classroom_latest_clue_answer(game_state, key))


def classroom_has_any_tag(game_state, tags):
    clue_tags = set(game_state.get("clue_tags", []))
    return any(tag in clue_tags for tag in tags)


def classroom_has_tag_prefix(game_state, prefix):
    return any(str(tag).startswith(prefix) for tag in game_state.get("clue_tags", []))


def get_classroom_question_by_key_copy(key):
    question = get_classroom_object_question_by_key(key)
    if question:
        return question.copy()
    return CLASSROOM_OBJECT_QUESTION_BANK[-1].copy()


def classroom_clean_answer_fragment(child_response):
    cleaned = normalize_classroom_object_text(child_response)

    if not cleaned or classroom_answer_was_other(cleaned):
        return ""

    remove_prefixes = [
        "it is made of ",
        "it's made of ",
        "its made of ",
        "it is mostly ",
        "it's mostly ",
        "its mostly ",
        "it is ",
        "it's ",
        "its ",
        "made of ",
        "mostly "
    ]

    for prefix in remove_prefixes:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
            break

    words = cleaned.split()
    if len(words) > 4:
        return ""

    return cleaned[:45]


def maybe_add_classroom_acknowledgment(message, event_type, child_response, previous_response_mode, game_state):
    import random

    if event_type != "child_answer":
        return message

    if previous_response_mode in {"none", "guess_confirmation", "round_choice", "object_reveal"}:
        return message

    if not is_clear_classroom_object_response(child_response, previous_response_mode):
        return message

    lowered_message = normalize_classroom_object_text(message)
    existing = ["thank", "that helps", "helpful", "good clue", "that gives me", "i can use", "okay"]
    if any(phrase in lowered_message for phrase in existing):
        return message

    fragment = classroom_clean_answer_fragment(child_response)
    recent = list(game_state.get("recent_acknowledgments", []))[-4:]

    if fragment:
        acknowledgment_options = [
            f"Okay, {fragment}. Hmm.",
            f"Got it, {fragment}. Hmm.",
            f"Okay, {fragment}. That helps."
        ]
    else:
        acknowledgment_options = [
            "That helps. Hmm.",
            "Okay, that helps.",
            "Got it. Hmm.",
            "That narrows it down."
        ]

    fresh = [line for line in acknowledgment_options if line not in recent]
    acknowledgment = random.choice(fresh or acknowledgment_options)
    game_state["recent_acknowledgments"] = (recent + [acknowledgment])[-4:]

    return f"{acknowledgment} {message}"


def get_classroom_question_round_band(game_state):
    """Question style is based on question number inside the current object attempt."""
    questions_asked = int(game_state.get("questions_asked", 0) or 0)
    if questions_asked < 3:
        return "required_choice"
    if questions_asked < 7:
        return "guided_detail"
    return "late_hint"



def get_classroom_profile_all_tags(profile):
    return set(profile.get("tags", set())) | set(profile.get("colors", set()))


def get_classroom_candidate_keys(game_state):
    keys = [
        key for key in game_state.get("candidate_keys", [])
        if key in CLASSROOM_OBJECT_PROFILES
    ]
    if not keys:
        keys = list(CLASSROOM_OBJECT_PROFILES.keys())
        game_state["candidate_keys"] = keys
    return keys


def set_classroom_candidate_keys(game_state, keys):
    clean_keys = [key for key in keys if key in CLASSROOM_OBJECT_PROFILES]
    if clean_keys:
        game_state["candidate_keys"] = clean_keys


def get_classroom_question_offered_tags(question_item):
    offered = set()
    for tag_set in (question_item or {}).get("option_tags", {}).values():
        offered.update(tag_set)
    return offered


def classroom_filter_candidates_from_answer(game_state, question_item, child_response):
    """Filter the active classroom-object candidate pool from a choice answer.

    This is intentionally conservative:
    - Clear option answers narrow the pool.
    - "Something else" removes the offered option groups.
    - "I don't know" / unclear answers are void and do not eliminate anything.
    - If a filter would eliminate every object, we keep the old pool.
    """
    question_key = (question_item or {}).get("key")

    if is_classroom_object_unclear_or_silent(child_response):
        if question_key:
            game_state.setdefault("void_question_keys", []).append(question_key)
        return

    current_keys = get_classroom_candidate_keys(game_state)
    offered_tags = get_classroom_question_offered_tags(question_item)
    answer_tags = extract_classroom_tags_from_answer(question_item, child_response)

    if classroom_answer_was_other(child_response) and offered_tags:
        filtered = [
            key for key in current_keys
            if not (get_classroom_profile_all_tags(CLASSROOM_OBJECT_PROFILES[key]) & offered_tags)
        ]
        action = "excluded_offered_options"
    elif answer_tags:
        filtered = [
            key for key in current_keys
            if get_classroom_profile_all_tags(CLASSROOM_OBJECT_PROFILES[key]) & answer_tags
        ]
        action = "matched_answer_tags"
    else:
        return

    if filtered:
        set_classroom_candidate_keys(game_state, filtered)
        game_state.setdefault("candidate_filter_notes", []).append({
            "question_key": question_key,
            "answer": str(child_response or "")[:80],
            "action": action,
            "remaining": len(filtered)
        })


def classroom_question_split_score(question_item, game_state):
    """Prefer questions that actually split the current candidate pool."""
    option_tags = (question_item or {}).get("option_tags", {})
    if not option_tags:
        return -999

    candidate_keys = get_classroom_candidate_keys(game_state)
    if len(candidate_keys) <= 1:
        return -999

    unique_groups = []
    seen = set()
    for raw_tags in option_tags.values():
        frozen = frozenset(raw_tags)
        if frozen and frozen not in seen:
            unique_groups.append(set(raw_tags))
            seen.add(frozen)

    if not unique_groups:
        return -999

    counts = []
    offered_union = set()
    for tag_group in unique_groups:
        offered_union.update(tag_group)
        count = sum(
            1 for key in candidate_keys
            if get_classroom_profile_all_tags(CLASSROOM_OBJECT_PROFILES[key]) & tag_group
        )
        if count > 0:
            counts.append(count)

    other_count = sum(
        1 for key in candidate_keys
        if not (get_classroom_profile_all_tags(CLASSROOM_OBJECT_PROFILES[key]) & offered_union)
    )
    if other_count > 0:
        counts.append(other_count)

    if len(counts) < 2:
        return -999

    balance_penalty = max(counts) - min(counts)
    return len(counts) * 20 - balance_penalty


FIRST_THREE_CLASSROOM_QUESTION_KEYS = [
    "write_tool_type",
    "write_feature_followup",
    "storage_detail_first",
    "wall_detail_first",
    "furniture_detail_first",
    "category_other_followup",
    "size_first",
    "material_first",
    "material_other_one",
    "where_first",
    "feature_first"
]


def choose_first_three_classroom_question(game_state, asked_keys, questions_asked):
    if questions_asked == 0:
        return get_classroom_question_by_key_copy("category_first")

    if questions_asked == 1 and classroom_chose_other_for_key(game_state, "category_first"):
        if "category_other_followup" not in asked_keys:
            return get_classroom_question_by_key_copy("category_other_followup")

    best_question = None
    best_score = -999

    for key in FIRST_THREE_CLASSROOM_QUESTION_KEYS:
        if key in asked_keys:
            continue
        item = get_classroom_object_question_by_key(key)
        if not item or item.get("response_mode") != "choice":
            continue
        score = classroom_question_split_score(item, game_state)
        if score > best_score:
            best_score = score
            best_question = item

    if best_question and best_score > -999:
        return best_question.copy()

    for key in ["size_first", "material_first", "where_first"]:
        if key not in asked_keys:
            return get_classroom_question_by_key_copy(key)

    return get_classroom_question_by_key_copy("material_first")


def choose_classroom_object_question(game_state, event_type="child_answer"):
    asked_keys = {
        item.get("key")
        for item in game_state.get("question_history", [])
        if isinstance(item, dict)
    }

    questions_asked = int(game_state.get("questions_asked", 0) or 0)

    # First three spoken questions are always short, choice-based, and candidate-aware.
    if questions_asked < 3:
        return choose_first_three_classroom_question(game_state, asked_keys, questions_asked)

    # Rounds 4-6 and 7-9 keep the Mystery Animal-style structure, but use
    # the candidate pool created by the first three answers.
    adaptive_keys = []

    if classroom_chose_other_for_key(game_state, "material_first"):
        adaptive_keys.append("material_other_one")

    if classroom_chose_other_for_key(game_state, "material_other_one"):
        adaptive_keys.append("material_other_two")

    if not classroom_has_tag_prefix(game_state, "loc_"):
        adaptive_keys.append("where_first")

    if classroom_chose_other_for_key(game_state, "where_first"):
        adaptive_keys.append("where_other")

    if not (
        classroom_has_any_tag(game_state, {"writing", "drawing", "coloring", "cutting", "sticky", "sit", "work", "math", "time", "dates"}) or
        classroom_has_tag_prefix(game_state, "category_")
    ):
        adaptive_keys.append("use_first")

    if classroom_chose_other_for_key(game_state, "use_first"):
        adaptive_keys.append("use_other")

    if questions_asked >= 5:
        adaptive_keys.append("feature_first")

    if classroom_chose_other_for_key(game_state, "feature_first"):
        adaptive_keys.append("feature_other")

    if questions_asked >= 6:
        adaptive_keys.append("color_choice")

    best_adaptive = None
    best_adaptive_score = -999
    for key in adaptive_keys:
        if key in asked_keys:
            continue
        item = get_classroom_object_question_by_key(key)
        if not item:
            continue
        score = classroom_question_split_score(item, game_state)
        if item.get("response_mode") in {"open_hint", "one_word"}:
            score = max(score, 0)
        if score > best_adaptive_score:
            best_adaptive = item
            best_adaptive_score = score

    if best_adaptive and best_adaptive_score > -999:
        return best_adaptive.copy()

    if event_type == "no_response":
        fallback_keys = ["where_first", "use_first", "feature_first", "color_choice", "extra_hint"]
    elif questions_asked < 6:
        fallback_keys = ["where_first", "use_first", "feature_first", "color_choice"]
    elif questions_asked < 8:
        fallback_keys = ["extra_hint", "color_choice"]
    else:
        fallback_keys = ["last_hint"]

    for key in fallback_keys:
        if key not in asked_keys:
            return get_classroom_question_by_key_copy(key)

    for question in CLASSROOM_OBJECT_QUESTION_BANK:
        if question["key"] not in asked_keys:
            return question.copy()

    return get_classroom_question_by_key_copy("last_hint")

def extract_classroom_tags_from_answer(question_item, answer):
    lowered = normalize_classroom_object_text(answer)
    words = classroom_object_words(lowered)
    tags = set()

    if not question_item:
        question_item = {}

    option_tags = question_item.get("option_tags") or {}
    for raw_option, option_tag_set in option_tags.items():
        option = normalize_classroom_object_text(raw_option)
        option_words = classroom_object_words(option)

        if not option:
            continue

        if option in lowered or option in words or (option_words and option_words.issubset(words)):
            tags.update(option_tag_set)

    keyword_map = {
        "write": "writing", "writing": "writing", "draw": "drawing", "drawing": "drawing",
        "color": "coloring", "colour": "coloring", "erase": "erase", "mistake": "erase",
        "cut": "cutting", "scissor": "cutting", "scissors": "cutting",
        "measure": "measure", "straight": "feature_straight", "paper": "material_paper",
        "page": "feature_pages", "pages": "feature_pages", "sticky": "feature_sticky", "glue": "feature_sticky",
        "sit": "sit", "chair": "category_furniture", "desk": "loc_desk", "backpack": "loc_backpack", "bag": "loc_backpack",
        "wall": "loc_wall", "front": "loc_front", "shelf": "loc_shelf", "floor": "loc_floor",
        "screen": "feature_screen", "keyboard": "feature_keyboard", "button": "feature_buttons", "buttons": "feature_buttons",
        "number": "numbers", "numbers": "numbers", "math": "math", "paint": "painting", "brush": "bristles",
        "metal": "material_metal", "plastic": "material_plastic", "wood": "material_wood", "wooden": "material_wood",
        "fabric": "material_fabric", "cloth": "material_fabric", "electronic": "material_electronic", "electric": "material_electronic",
        "soft": "feature_soft", "flat": "feature_flat", "long": "long", "pointy": "feature_pointy", "sharp": "feature_sharp",
        "small": "size_small", "medium": "size_medium", "big": "size_large", "large": "size_large",
        "white": "white", "yellow": "yellow", "blue": "blue", "red": "red", "green": "green",
        "black": "black", "pink": "pink", "purple": "purple", "brown": "brown", "gray": "gray", "grey": "gray", "silver": "silver", "clear": "clear", "orange": "orange"
    }

    for word in words:
        mapped = keyword_map.get(word)
        if mapped:
            tags.add(mapped)

    return tags


def get_classroom_object_question_by_key(key):
    for item in CLASSROOM_OBJECT_QUESTION_BANK:
        if item.get("key") == key:
            return item
    return None


def get_classroom_tag_group(tag):
    for prefix in ["category_", "size_", "material_", "loc_"]:
        if str(tag).startswith(prefix):
            return prefix
    return None


def get_classroom_object_score(profile, clue_answer_text, clue_tags):
    score = 0
    tags = set(profile.get("tags", set())) | set(profile.get("colors", set()))
    aliases = set(profile.get("aliases", set()))
    display = normalize_classroom_object_text(profile.get("display", ""))

    for alias in aliases:
        alias_clean = normalize_classroom_object_text(alias)
        if alias_clean and alias_clean in clue_answer_text:
            score += 35

    if display and display in clue_answer_text:
        score += 35

    # Treat major clue groups as constraints instead of loose suggestions.
    group_weights = {
        "category_": (10, -12),
        "size_": (9, -12),
        "material_": (16, -30),
        "loc_": (7, -6)
    }

    for prefix, (match_points, miss_penalty) in group_weights.items():
        clue_group = {tag for tag in clue_tags if str(tag).startswith(prefix)}
        if not clue_group:
            continue

        profile_group = {tag for tag in tags if str(tag).startswith(prefix)}
        if profile_group & clue_group:
            score += match_points * len(profile_group & clue_group)
        else:
            score += miss_penalty

    for tag in clue_tags:
        if str(tag).startswith(("category_", "size_", "material_", "loc_")):
            continue

        if tag in tags:
            score += 4

    for tag in tags:
        tag_text = normalize_classroom_object_text(tag.replace("_", " "))
        if tag_text and tag_text in clue_answer_text:
            score += 2

    for hint in profile.get("hints", []):
        for word in classroom_object_words(hint):
            if len(word) > 3 and word in classroom_object_words(clue_answer_text):
                score += 1

    return score


def get_ranked_classroom_object_candidates(game_state):
    rejected = {
        normalize_classroom_object_text(item)
        for item in game_state.get("rejected_guesses", [])
        if item
    }

    recent = {
        normalize_classroom_object_text(item)
        for item in game_state.get("recent_guesses", [])[-4:]
        if item
    }

    clue_answer_text = " ".join(
        str(item.get('answer', ''))
        for item in game_state.get("known_clues", [])
        if isinstance(item, dict)
    ).lower()

    clue_tags = set(game_state.get("clue_tags", []))
    candidate_keys = get_classroom_candidate_keys(game_state)
    candidates = []

    for object_key in candidate_keys:
        profile = CLASSROOM_OBJECT_PROFILES.get(object_key)
        if not profile:
            continue

        display = profile["display"]
        display_key = normalize_classroom_object_text(display)
        if display_key in rejected:
            continue

        score = get_classroom_object_score(profile, clue_answer_text, clue_tags)
        score += 8

        if display_key in recent:
            score -= 6

        candidates.append((score, display))

    if not candidates:
        for object_key, profile in CLASSROOM_OBJECT_PROFILES.items():
            display = profile["display"]
            display_key = normalize_classroom_object_text(display)
            if display_key in rejected:
                continue
            score = get_classroom_object_score(profile, clue_answer_text, clue_tags)
            candidates.append((score, display))

    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates

def get_classroom_object_guess_confidence(game_state):
    ranked = get_ranked_classroom_object_candidates(game_state)
    if not ranked:
        return None, -999, 0

    best_score, best_display = ranked[0]
    second_score = ranked[1][0] if len(ranked) > 1 else -999
    margin = best_score - second_score
    return best_display, best_score, margin


def get_best_classroom_object_guess(game_state):
    guess, score, margin = get_classroom_object_guess_confidence(game_state)
    if not guess:
        guess = "pencil"

    game_state["recent_guesses"] = (list(game_state.get("recent_guesses", [])) + [guess])[-5:]
    return guess


def is_classroom_object_guess_ready(game_state, previous_response_mode="none", child_response=""):
    questions_asked = int(game_state.get("questions_asked", 0) or 0)
    known_clues = game_state.get("known_clues", [])
    guess_cooldown = int(game_state.get("guess_cooldown_questions", 0) or 0)

    if game_state.get("skip_guess_once") or guess_cooldown > 0:
        return False

    if questions_asked < 3 or len(known_clues) < 3:
        return False

    active_candidates = get_classroom_candidate_keys(game_state)
    if len(active_candidates) == 1:
        return True

    guess, score, margin = get_classroom_object_guess_confidence(game_state)

    if not guess:
        return False

    if questions_asked >= CLASSROOM_OBJECT_MAX_QUESTIONS_PER_ROUND:
        return score >= 16 and margin >= 2

    if score >= 38 and margin >= 8:
        return True

    if questions_asked >= 6 and score >= 30 and margin >= 6:
        return True

    if questions_asked >= 8 and score >= 23 and margin >= 4:
        return True

    return False

def get_classroom_object_cached_audio_url(text, namespace="mystery-classroom-object-main-v1"):
    text = sanitize_short_line(text, fallback="Hmm, let me think.", max_len=320)

    cache_dir = os.path.join(BASE_DIR, "static", "audio", "mystery_classroom_object")
    os.makedirs(cache_dir, exist_ok=True)

    voice_id = (
        os.getenv("TEACHER_VOICE_ID")
        or os.getenv("LIBRARIAN_VOICE_ID")
        or os.getenv("ELEVENLABS_VOICE_ID", "piI8Kku0DcvcL6TTSeQt")
    )
    cache_key = f"{namespace}:{voice_id}:{text}"
    filename = hashlib.md5(cache_key.encode("utf-8")).hexdigest() + ".mp3"
    filepath = os.path.join(cache_dir, filename)

    if not os.path.exists(filepath):
        audio_bytes = generate_book_guessing_voice_elevenlabs(text)
        with open(filepath, "wb") as f:
            f.write(audio_bytes)

    return url_for("static", filename=f"audio/mystery_classroom_object/{filename}")


def split_classroom_line_for_child_name(text, child_name):
    # Keep this simple: the frontend can play one audio file, but the payload still
    # supports audio_parts just like Mystery Animal.
    return [re.sub(r"\s+", " ", str(text or "")).strip()]


def add_classroom_audio_to_payload(payload, message):
    child_name = clean_classroom_child_name(session.get("child_name", ""))
    audio_text_parts = split_classroom_line_for_child_name(message, child_name)
    audio_parts = [
        get_classroom_object_cached_audio_url(part)
        for part in audio_text_parts
        if part and str(part).strip()
    ]

    payload["audio_parts"] = audio_parts
    payload["audio_part_texts"] = audio_text_parts

    if audio_parts:
        payload["audio_url"] = audio_parts[0]

    return payload


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
    message = calm_classroom_object_line(message, game_complete=game_complete)

    history.append({
        "event_type": event_type,
        "child_response": child_response,
        "teacher": message,
        "stage": stage,
        "response_mode": response_mode,
        "game_complete": game_complete,
        "session_done": session_done
    })

    game_state["stage"] = stage
    game_state["last_response_mode"] = response_mode
    game_state["game_complete"] = game_complete

    session["mystery_classroom_object_history"] = history[-20:]
    session["mystery_classroom_object_state"] = game_state

    # Backwards-compatible session keys in case older code reads them.
    session["book_guessing_game_history"] = history[-20:]
    session["book_guessing_game_state"] = game_state
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

    payload = add_classroom_audio_to_payload(payload, message)

    if next_event:
        payload["next_event"] = next_event

    if pause_before_next_ms is not None:
        payload["pause_before_next_ms"] = pause_before_next_ms

    if next_url:
        payload["next_url"] = next_url

    if redirect_after_ms is not None:
        payload["redirect_after_ms"] = redirect_after_ms

    return jsonify(payload)


def start_new_classroom_object_round(rounds_completed, message, event_label="replay", pause_ms=1800):
    game_state = get_classroom_object_default_state(rounds_completed=rounds_completed)
    history = []

    return make_book_guessing_game_audio_response(
        message=message,
        stage="intro",
        response_mode="none",
        expects_response=False,
        game_complete=False,
        game_state=game_state,
        history=history,
        event_type=event_label,
        child_response="",
        next_event="first_question",
        pause_before_next_ms=pause_ms
    )


def end_classroom_object_call(message, game_state, history, event_label, unlock_next=False, redirect_to_dashboard=False):
    rounds_completed = int(game_state.get("rounds_completed", 0) or 0)

    next_url = None
    if unlock_next:
        next_activity_id = complete_classroom_object_and_unlock_next_for_user(rounds_completed)
        if next_activity_id:
            next_url = url_for("open_activity", activity_id=next_activity_id)
    else:
        save_classroom_object_round_progress(rounds_completed)

        if redirect_to_dashboard:
            next_url = url_for("dashboard")

    return make_book_guessing_game_audio_response(
        message=message,
        stage="session_done",
        response_mode="none",
        expects_response=False,
        game_complete=unlock_next,
        game_state=game_state,
        history=history,
        event_type=event_label,
        child_response="",
        next_url=next_url,
        redirect_after_ms=1700 if next_url else None,
        session_done=True
    )


def finish_classroom_object_round(base_message, game_state, history, event_label, child_name=""):
    rounds_completed = int(game_state.get("rounds_completed", 0) or 0)
    save_classroom_object_round_progress(rounds_completed)

    if not should_classroom_object_ask_round_choice(rounds_completed):
        message = (
            f"{base_message} "
            "Let's play another round. Think of a new classroom object, like a pencil, backpack, or desk."
        )

        return start_new_classroom_object_round(
            rounds_completed=rounds_completed,
            message=message,
            event_label=event_label,
            pause_ms=1900
        )

    child_name = clean_classroom_child_name(child_name)
    name_part = f" {child_name}," if child_name else ""

    if is_classroom_object_break_checkpoint(rounds_completed):
        message = (
            f"{base_message} "
            "Do you want to continue playing, or do you want to take a break for now?"
        )
    else:
        message = (
            f"{base_message} "
            f"That finishes our nine Mystery Classroom Object rounds for today.{name_part} "
            "Do you want to play again, or do you want to end here?"
        )

    return make_book_guessing_game_audio_response(
        message=message,
        stage="round_choice",
        response_mode="round_choice",
        expects_response=True,
        game_complete=False,
        game_state=game_state,
        history=history,
        event_type=event_label,
        child_response=""
    )


def update_classroom_object_state_from_response(game_state, event_type, child_response, previous_response_mode):
    if event_type in {"intro", "restart", "first_question"}:
        return

    if game_state.get("game_complete"):
        return

    child_response = re.sub(r"\s+", " ", str(child_response or "")).strip()
    previous_stage = game_state.get("stage", "")

    if previous_stage == "guess":
        if classroom_object_is_yes(child_response):
            game_state["rounds_completed"] = int(game_state.get("rounds_completed", 0) or 0) + 1
            game_state["stage"] = "round_choice"
            game_state["last_response_mode"] = "round_choice"
            game_state["game_complete"] = False
            return

        possible_guess = game_state.get("possible_guess")

        if classroom_object_is_no(child_response):
            if possible_guess:
                game_state.setdefault("rejected_guesses", []).append(possible_guess)

            game_state["possible_guess"] = None
            game_state["skip_guess_once"] = True
            game_state["guess_cooldown_questions"] = 2

        elif event_type == "no_response":
            game_state["possible_guess"] = None
            game_state["skip_guess_once"] = True
            game_state["guess_cooldown_questions"] = 2

    clear_response = (
        event_type == "child_answer" and
        is_clear_classroom_object_response(child_response, previous_response_mode)
    )

    if clear_response:
        game_state["comfortable_answer_count"] = int(game_state.get("comfortable_answer_count", 0) or 0) + 1
        game_state["comfortable_streak"] = int(game_state.get("comfortable_streak", 0) or 0) + 1
        game_state["unclear_streak"] = 0

        last_question = game_state.get("last_question")
        last_question_key = game_state.get("last_question_key")
        question_item = get_classroom_object_question_by_key(last_question_key)

        if last_question and previous_stage != "guess":
            clue_tags = extract_classroom_tags_from_answer(question_item, child_response)
            existing_tags = set(game_state.get("clue_tags", []))
            game_state["clue_tags"] = sorted(list(existing_tags | clue_tags))

            game_state.setdefault("known_clues", []).append({
                "question": last_question,
                "question_key": last_question_key,
                "answer": child_response[:120],
                "tags": sorted(list(clue_tags))
            })

            if previous_response_mode == "choice":
                classroom_filter_candidates_from_answer(game_state, question_item, child_response)
    else:
        last_question_key = game_state.get("last_question_key")
        if last_question_key:
            game_state.setdefault("void_question_keys", []).append(last_question_key)

        game_state["unclear_or_silent_count"] = int(game_state.get("unclear_or_silent_count", 0) or 0) + 1
        game_state["unclear_streak"] = int(game_state.get("unclear_streak", 0) or 0) + 1
        game_state["comfortable_streak"] = 0





# =========================
# Final Mystery Classroom Object refinements
# - 50-object tree
# - locked candidate pool for early choices
# - category-specific follow-ups
# - child-answer echo without duplicate "Hmm"
# =========================

FINAL_CLASSROOM_EXTRA_PROFILES = {
    "highlighter": {
        "display": "highlighter",
        "aliases": {"highlighter", "highlight marker"},
        "tags": {"category_write_draw", "tool_write_draw", "category_art_craft", "size_small", "material_plastic", "loc_desk", "loc_backpack", "feature_cap", "ink", "coloring", "drawing", "long", "yellow"},
        "colors": {"yellow", "pink", "green", "orange", "blue"},
        "hints": ["It can mark important words.", "It often uses bright ink.", "It usually has a cap."]
    },
    "dry erase marker": {
        "display": "dry erase marker",
        "aliases": {"dry erase marker", "whiteboard marker", "expo marker", "board marker"},
        "tags": {"category_write_draw", "tool_write_draw", "category_wall_front", "size_small", "material_plastic", "loc_desk", "loc_front", "feature_cap", "ink", "writing", "drawing", "board_tool", "long"},
        "colors": {"black", "blue", "red", "green", "purple"},
        "hints": ["Teachers use it on a whiteboard.", "It has ink and a cap.", "It can be erased from a board."]
    },
    "chalk": {
        "display": "chalk",
        "aliases": {"chalk", "piece of chalk"},
        "tags": {"category_write_draw", "tool_write_draw", "category_wall_front", "size_small", "material_chalk", "loc_desk", "loc_front", "writing", "drawing", "board_tool", "chalk", "dusty"},
        "colors": {"white", "yellow", "pink", "blue"},
        "hints": ["It writes on a chalkboard.", "It can feel dusty.", "It is usually small."]
    },
    "paintbrush": {
        "display": "paintbrush",
        "aliases": {"paintbrush", "paint brush", "brush"},
        "tags": {"category_art_craft", "tool_art", "size_small", "material_wood", "material_plastic", "loc_desk", "feature_bristles", "painting", "drawing", "long"},
        "colors": {"brown", "black", "red", "blue"},
        "hints": ["It is used with paint.", "It has bristles.", "You might use it during art."]
    },
    "pencil case": {
        "display": "pencil case",
        "aliases": {"pencil case", "pencil pouch", "pouch", "case"},
        "tags": {"category_storage", "size_medium", "material_fabric", "material_plastic", "loc_backpack", "loc_desk", "feature_zipper", "carry", "storage", "school_supply"},
        "colors": {"black", "blue", "pink", "purple", "gray", "red"},
        "hints": ["It holds pencils or pens.", "It can go in a backpack.", "It may have a zipper."]
    },
    "projector": {
        "display": "projector",
        "aliases": {"projector", "classroom projector"},
        "tags": {"category_technology", "category_wall_front", "size_medium", "material_electronic", "material_plastic", "material_metal", "loc_front", "loc_ceiling", "feature_lens", "light", "screen", "teacher"},
        "colors": {"white", "black", "gray", "silver"},
        "hints": ["It can show an image on a screen.", "It uses light.", "It may be near the ceiling or front of the room."]
    },
    "projector remote": {
        "display": "projector remote",
        "aliases": {"projector remote", "remote", "remote control"},
        "tags": {"category_technology", "size_small", "material_plastic", "material_electronic", "loc_desk", "loc_front", "feature_buttons", "remote", "teacher"},
        "colors": {"black", "gray", "white"},
        "hints": ["It has buttons.", "It can control a projector.", "A teacher might keep it near the front."]
    },
    "carpet": {
        "display": "carpet",
        "aliases": {"carpet", "rug", "classroom rug"},
        "tags": {"category_floor", "category_room_part", "size_large", "material_fabric", "loc_floor", "feature_soft", "sit", "rug"},
        "colors": {"blue", "green", "gray", "red", "brown", "colorful"},
        "hints": ["It is on the floor.", "Students might sit on it.", "It can be soft."]
    },
    "door": {
        "display": "door",
        "aliases": {"door", "classroom door"},
        "tags": {"category_room_part", "size_large", "material_wood", "material_metal", "loc_wall", "feature_handle", "entrance"},
        "colors": {"brown", "white", "gray", "tan"},
        "hints": ["People use it to enter the room.", "It has a handle.", "It is part of the classroom."]
    },
    "window": {
        "display": "window",
        "aliases": {"window", "classroom window"},
        "tags": {"category_room_part", "size_large", "material_glass", "loc_wall", "feature_clear", "light", "outside"},
        "colors": {"clear", "white", "gray"},
        "hints": ["You can look outside through it.", "It lets in light.", "It is usually on a wall."]
    },
    "map": {
        "display": "map",
        "aliases": {"map", "classroom map", "world map"},
        "tags": {"category_wall_front", "category_paper_book", "category_learning_tool", "size_medium", "material_paper", "loc_wall", "feature_flat", "display", "geography"},
        "colors": {"blue", "green", "white", "colorful"},
        "hints": ["It shows places.", "It may hang on a wall.", "It can help with geography."]
    },
    "globe": {
        "display": "globe",
        "aliases": {"globe", "world globe"},
        "tags": {"category_learning_tool", "size_medium", "material_plastic", "loc_desk", "loc_shelf", "feature_round", "geography", "spin"},
        "colors": {"blue", "green", "brown", "white"},
        "hints": ["It shows the world.", "It is round.", "It can sit on a desk or shelf."]
    }
}

CLASSROOM_OBJECT_PROFILES.update(FINAL_CLASSROOM_EXTRA_PROFILES)

# Mark actual write/color tools separately from objects you write ON or IN.
for _key in ["pencil", "pen", "crayon", "marker", "colored pencil", "highlighter", "dry erase marker", "chalk"]:
    if _key in CLASSROOM_OBJECT_PROFILES:
        CLASSROOM_OBJECT_PROFILES[_key].setdefault("tags", set()).add("tool_write_draw")

# A few existing items need extra tags so the filtered tree asks smarter questions.
if "crayon" in CLASSROOM_OBJECT_PROFILES:
    CLASSROOM_OBJECT_PROFILES["crayon"].setdefault("tags", set()).update({"material_wax", "waxy", "tool_art"})
if "colored pencil" in CLASSROOM_OBJECT_PROFILES:
    CLASSROOM_OBJECT_PROFILES["colored pencil"].setdefault("tags", set()).update({"sharpen", "tool_art"})
if "marker" in CLASSROOM_OBJECT_PROFILES:
    CLASSROOM_OBJECT_PROFILES["marker"].setdefault("tags", set()).update({"ink", "tool_art"})
if "pen" in CLASSROOM_OBJECT_PROFILES:
    CLASSROOM_OBJECT_PROFILES["pen"].setdefault("tags", set()).update({"ink"})
if "pencil" in CLASSROOM_OBJECT_PROFILES:
    CLASSROOM_OBJECT_PROFILES["pencil"].setdefault("tags", set()).update({"sharpen"})


def classroom_upsert_question(question):
    for i, item in enumerate(CLASSROOM_OBJECT_QUESTION_BANK):
        if item.get("key") == question.get("key"):
            CLASSROOM_OBJECT_QUESTION_BANK[i] = question
            return
    CLASSROOM_OBJECT_QUESTION_BANK.append(question)


classroom_upsert_question({
    "key": "category_first",
    "question": "Is it something you write or color with, something you carry, or something else?",
    "stage": "guided_choice",
    "response_mode": "choice",
    "option_tags": {
        "write": {"tool_write_draw"},
        "writing": {"tool_write_draw"},
        "draw": {"tool_write_draw"},
        "drawing": {"tool_write_draw"},
        "color": {"tool_write_draw"},
        "coloring": {"tool_write_draw"},
        "colour": {"tool_write_draw"},
        "carry": {"category_storage", "carry", "wear", "loc_backpack"},
        "store": {"category_storage"},
        "storage": {"category_storage"},
        "backpack": {"category_storage", "loc_backpack", "wear"}
    }
})

classroom_upsert_question({
    "key": "write_tool_type",
    "question": "Does it use ink, color, or a different kind of mark?",
    "stage": "guided_choice",
    "response_mode": "choice",
    "option_tags": {
        "ink": {"ink"},
        "pen": {"ink"},
        "color": {"coloring"},
        "colors": {"coloring"},
        "colour": {"coloring"},
        "draw": {"drawing"},
        "drawing": {"drawing"}
    }
})

classroom_upsert_question({
    "key": "write_feature_followup",
    "question": "Does it have a cap, have an eraser, or neither?",
    "stage": "guided_choice",
    "response_mode": "choice",
    "option_tags": {
        "cap": {"feature_cap"},
        "lid": {"feature_cap", "feature_lid"},
        "eraser": {"feature_eraser", "erase"},
        "erase": {"feature_eraser", "erase"}
    }
})

classroom_upsert_question({
    "key": "write_texture_followup",
    "question": "Is it waxy, does it need sharpening, or something else?",
    "stage": "guided_choice",
    "response_mode": "choice",
    "option_tags": {
        "waxy": {"material_wax", "waxy"},
        "wax": {"material_wax", "waxy"},
        "crayon": {"material_wax", "waxy"},
        "sharpen": {"sharpen", "feature_pointy", "material_wood"},
        "sharpening": {"sharpen", "feature_pointy", "material_wood"},
        "pointy": {"feature_pointy"}
    }
})

classroom_upsert_question({
    "key": "write_surface_followup",
    "question": "Is it used on paper, on a board, or something else?",
    "stage": "guided_choice",
    "response_mode": "choice",
    "option_tags": {
        "paper": {"paper_use", "loc_desk"},
        "board": {"board_tool", "category_wall_front"},
        "whiteboard": {"board_tool", "category_wall_front"},
        "chalkboard": {"board_tool", "chalk"}
    }
})

classroom_upsert_question({
    "key": "tech_detail_first",
    "question": "Does it show a picture, have buttons, or something else?",
    "stage": "guided_choice",
    "response_mode": "choice",
    "option_tags": {
        "picture": {"screen", "feature_screen", "light"},
        "image": {"screen", "feature_screen", "light"},
        "screen": {"screen", "feature_screen"},
        "buttons": {"feature_buttons"},
        "button": {"feature_buttons"},
        "remote": {"remote", "feature_buttons"}
    }
})

classroom_upsert_question({
    "key": "room_part_detail_first",
    "question": "Is it on the floor, on the wall, or somewhere else?",
    "stage": "guided_choice",
    "response_mode": "choice",
    "option_tags": {
        "floor": {"loc_floor", "category_floor"},
        "carpet": {"loc_floor", "category_floor", "rug"},
        "rug": {"loc_floor", "category_floor", "rug"},
        "wall": {"loc_wall", "category_room_part", "category_wall_front"},
        "door": {"category_room_part", "feature_handle"},
        "window": {"category_room_part", "material_glass"}
    }
})


def extract_classroom_tags_from_answer(question_item, answer):
    lowered = normalize_classroom_object_text(answer)
    words = classroom_object_words(lowered)
    tags = set()

    if not question_item:
        question_item = {}

    option_tags = question_item.get("option_tags") or {}
    for raw_option, option_tag_set in option_tags.items():
        option = normalize_classroom_object_text(raw_option)
        option_words = classroom_object_words(option)

        if not option:
            continue

        if option in lowered or option in words or (option_words and option_words.issubset(words)):
            tags.update(option_tag_set)

    keyword_map = {
        "write": "writing", "writing": "writing", "draw": "drawing", "drawing": "drawing",
        "color": "coloring", "colors": "coloring", "colour": "coloring", "erase": "erase", "mistake": "erase",
        "cut": "cutting", "scissor": "cutting", "scissors": "cutting", "measure": "measure", "straight": "feature_straight",
        "paper": "material_paper", "cardboard": "material_paper", "page": "feature_pages", "pages": "feature_pages",
        "sticky": "feature_sticky", "glue": "feature_sticky", "sit": "sit", "chair": "category_furniture", "desk": "loc_desk",
        "backpack": "loc_backpack", "bag": "loc_backpack", "wall": "loc_wall", "front": "loc_front", "shelf": "loc_shelf",
        "floor": "loc_floor", "screen": "feature_screen", "keyboard": "feature_keyboard", "button": "feature_buttons", "buttons": "feature_buttons",
        "number": "numbers", "numbers": "numbers", "math": "math", "paint": "painting", "brush": "feature_bristles",
        "metal": "material_metal", "plastic": "material_plastic", "wood": "material_wood", "wooden": "material_wood",
        "fabric": "material_fabric", "cloth": "material_fabric", "electronic": "material_electronic", "electric": "material_electronic",
        "soft": "feature_soft", "flat": "feature_flat", "long": "long", "pointy": "feature_pointy", "sharp": "feature_sharp",
        "small": "size_small", "medium": "size_medium", "big": "size_large", "large": "size_large",
        "white": "white", "yellow": "yellow", "blue": "blue", "red": "red", "green": "green",
        "black": "black", "pink": "pink", "purple": "purple", "brown": "brown", "gray": "gray", "grey": "gray", "silver": "silver", "clear": "clear", "orange": "orange",
        "ink": "ink", "cap": "feature_cap", "lid": "feature_lid", "waxy": "material_wax", "wax": "material_wax", "crayon": "material_wax",
        "sharpen": "sharpen", "sharpening": "sharpen", "chalk": "chalk", "board": "board_tool", "whiteboard": "board_tool", "marker": "tool_write_draw",
        "projector": "category_technology", "remote": "remote", "carpet": "category_floor", "rug": "category_floor", "door": "category_room_part",
        "window": "category_room_part", "map": "geography", "globe": "geography", "glass": "material_glass"
    }

    for word in words:
        mapped = keyword_map.get(word)
        if mapped:
            tags.add(mapped)

    return tags


def classroom_clean_answer_fragment(child_response):
    cleaned = normalize_classroom_object_text(child_response)

    if not cleaned:
        return ""

    if classroom_answer_was_other(cleaned):
        return "something else"

    remove_prefixes = [
        "yes it is ", "yeah it is ", "yep it is ", "yes it's ", "yeah it's ",
        "it is made of ", "it's made of ", "its made of ",
        "it is mostly ", "it's mostly ", "its mostly ",
        "it is something you ", "it's something you ", "it is something i ", "it's something i ",
        "it is ", "it's ", "its ", "made of ", "mostly "
    ]

    for prefix in remove_prefixes:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
            break

    phrase_labels = {
        "write with": "something you write with",
        "writing": "something you write with",
        "draw with": "something you draw with",
        "color with": "something you color with",
        "colour with": "something you color with",
        "ink": "ink",
        "color": "color",
        "colour": "color",
        "waxy": "waxy",
        "wax": "waxy",
        "sharpen": "needs sharpening",
        "sharpening": "needs sharpening",
        "cap": "has a cap",
        "eraser": "has an eraser",
        "paper": "paper",
        "plastic": "plastic",
        "metal": "metal",
        "wood": "wood",
        "fabric": "fabric",
        "electronic": "electronic"
    }

    for key, label in phrase_labels.items():
        if key in cleaned:
            return label

    words = cleaned.split()
    if len(words) > 5:
        return ""

    return cleaned[:45]


def maybe_add_classroom_acknowledgment(message, event_type, child_response, previous_response_mode, game_state):
    if event_type != "child_answer":
        return message

    if previous_response_mode in {"none", "guess_confirmation", "round_choice", "object_reveal"}:
        return message

    if not is_clear_classroom_object_response(child_response, previous_response_mode):
        return message

    lowered_message = normalize_classroom_object_text(message)
    # Do not double-acknowledge if the response already starts that way.
    if lowered_message.startswith(("okay", "got it", "that helps", "thank")):
        return message

    fragment = classroom_clean_answer_fragment(child_response)
    if fragment:
        acknowledgment = f"Okay, {fragment}. That helps."
    else:
        acknowledgment = "Okay, that helps."

    return f"{acknowledgment} {message}"


def classroom_candidate_family(game_state):
    candidate_keys = get_classroom_candidate_keys(game_state)
    if not candidate_keys:
        return "general"

    counts = {
        "write_tool": 0,
        "storage": 0,
        "technology": 0,
        "wall_front": 0,
        "furniture": 0,
        "room_part": 0,
        "art_craft": 0
    }

    for key in candidate_keys:
        tags = get_classroom_profile_all_tags(CLASSROOM_OBJECT_PROFILES[key])
        if "tool_write_draw" in tags:
            counts["write_tool"] += 1
        if "category_storage" in tags:
            counts["storage"] += 1
        if "category_technology" in tags:
            counts["technology"] += 1
        if "category_wall_front" in tags:
            counts["wall_front"] += 1
        if "category_furniture" in tags:
            counts["furniture"] += 1
        if "category_room_part" in tags or "category_floor" in tags:
            counts["room_part"] += 1
        if "category_art_craft" in tags:
            counts["art_craft"] += 1

    total = len(candidate_keys)
    best_family, best_count = max(counts.items(), key=lambda item: item[1])
    if best_count / max(total, 1) >= 0.60:
        return best_family
    return "general"


def choose_best_unasked_from_keys(keys, asked_keys, game_state, allow_zero_score=False):
    best_item = None
    best_score = -999

    for key in keys:
        if key in asked_keys:
            continue
        item = get_classroom_object_question_by_key(key)
        if not item:
            continue
        score = classroom_question_split_score(item, game_state)
        if allow_zero_score and item.get("response_mode") in {"open_hint", "one_word"}:
            score = max(score, 0)
        if score > best_score:
            best_item = item
            best_score = score

    if best_item and (best_score > -999 or allow_zero_score):
        return best_item.copy()
    return None


FINAL_FIRST_THREE_CLASSROOM_QUESTION_KEYS = [
    "write_tool_type",
    "write_feature_followup",
    "write_texture_followup",
    "write_surface_followup",
    "storage_detail_first",
    "tech_detail_first",
    "wall_detail_first",
    "furniture_detail_first",
    "room_part_detail_first",
    "category_other_followup",
    "size_first",
    "material_first",
    "material_other_one",
    "where_first",
    "feature_first"
]


def choose_first_three_classroom_question(game_state, asked_keys, questions_asked):
    if questions_asked == 0:
        return get_classroom_question_by_key_copy("category_first")

    family = classroom_candidate_family(game_state)

    if family == "write_tool":
        item = choose_best_unasked_from_keys(
            ["write_tool_type", "write_feature_followup", "write_texture_followup", "write_surface_followup", "material_first", "color_choice"],
            asked_keys,
            game_state,
            allow_zero_score=True
        )
        if item:
            return item

    if family == "technology":
        item = choose_best_unasked_from_keys(["tech_detail_first", "size_first", "material_other_two", "feature_other"], asked_keys, game_state, allow_zero_score=True)
        if item:
            return item

    if family == "storage":
        item = choose_best_unasked_from_keys(["storage_detail_first", "size_first", "material_first", "feature_other"], asked_keys, game_state, allow_zero_score=True)
        if item:
            return item

    if family in {"room_part", "wall_front"}:
        item = choose_best_unasked_from_keys(["room_part_detail_first", "wall_detail_first", "size_first", "material_first"], asked_keys, game_state, allow_zero_score=True)
        if item:
            return item

    if family == "furniture":
        item = choose_best_unasked_from_keys(["furniture_detail_first", "size_first", "material_first"], asked_keys, game_state, allow_zero_score=True)
        if item:
            return item

    if questions_asked == 1 and classroom_chose_other_for_key(game_state, "category_first"):
        if "category_other_followup" not in asked_keys:
            return get_classroom_question_by_key_copy("category_other_followup")

    item = choose_best_unasked_from_keys(FINAL_FIRST_THREE_CLASSROOM_QUESTION_KEYS, asked_keys, game_state, allow_zero_score=True)
    if item:
        return item

    for key in ["size_first", "material_first", "where_first"]:
        if key not in asked_keys:
            return get_classroom_question_by_key_copy(key)

    return get_classroom_question_by_key_copy("material_first")


def choose_classroom_object_question(game_state, event_type="child_answer"):
    asked_keys = {
        item.get("key")
        for item in game_state.get("question_history", [])
        if isinstance(item, dict)
    }

    questions_asked = int(game_state.get("questions_asked", 0) or 0)

    # First three spoken questions are short, choice-based, and candidate-aware.
    if questions_asked < 3:
        return choose_first_three_classroom_question(game_state, asked_keys, questions_asked)

    family = classroom_candidate_family(game_state)

    if family == "write_tool":
        item = choose_best_unasked_from_keys(
            ["write_texture_followup", "write_surface_followup", "write_feature_followup", "write_tool_type", "color_choice", "extra_hint", "last_hint"],
            asked_keys,
            game_state,
            allow_zero_score=True
        )
        if item:
            return item
        return get_classroom_question_by_key_copy("extra_hint")

    if family == "technology":
        item = choose_best_unasked_from_keys(["tech_detail_first", "feature_other", "where_first", "color_choice", "extra_hint"], asked_keys, game_state, allow_zero_score=True)
        if item:
            return item

    if family == "storage":
        item = choose_best_unasked_from_keys(["storage_detail_first", "feature_other", "material_first", "where_first", "color_choice", "extra_hint"], asked_keys, game_state, allow_zero_score=True)
        if item:
            return item

    if family in {"room_part", "wall_front"}:
        item = choose_best_unasked_from_keys(["room_part_detail_first", "wall_detail_first", "material_first", "feature_other", "color_choice", "extra_hint"], asked_keys, game_state, allow_zero_score=True)
        if item:
            return item

    if family == "furniture":
        item = choose_best_unasked_from_keys(["furniture_detail_first", "material_first", "where_first", "color_choice", "extra_hint"], asked_keys, game_state, allow_zero_score=True)
        if item:
            return item

    adaptive_keys = []

    if classroom_chose_other_for_key(game_state, "material_first"):
        adaptive_keys.append("material_other_one")

    if classroom_chose_other_for_key(game_state, "material_other_one"):
        adaptive_keys.append("material_other_two")

    if not classroom_has_tag_prefix(game_state, "loc_"):
        adaptive_keys.append("where_first")

    if classroom_chose_other_for_key(game_state, "where_first"):
        adaptive_keys.append("where_other")

    if not (
        classroom_has_any_tag(game_state, {"writing", "drawing", "coloring", "cutting", "sticky", "sit", "work", "math", "time", "dates"}) or
        classroom_has_tag_prefix(game_state, "category_")
    ):
        adaptive_keys.append("use_first")

    if classroom_chose_other_for_key(game_state, "use_first"):
        adaptive_keys.append("use_other")

    if questions_asked >= 5:
        adaptive_keys.append("feature_first")

    if classroom_chose_other_for_key(game_state, "feature_first"):
        adaptive_keys.append("feature_other")

    if questions_asked >= 6:
        adaptive_keys.append("color_choice")

    item = choose_best_unasked_from_keys(adaptive_keys, asked_keys, game_state, allow_zero_score=True)
    if item:
        return item

    if event_type == "no_response":
        fallback_keys = ["use_first", "feature_first", "where_first", "color_choice", "extra_hint"]
    elif questions_asked < 6:
        fallback_keys = ["use_first", "feature_first", "where_first", "color_choice"]
    elif questions_asked < 8:
        fallback_keys = ["extra_hint", "color_choice"]
    else:
        fallback_keys = ["last_hint"]

    for key in fallback_keys:
        if key not in asked_keys:
            return get_classroom_question_by_key_copy(key)

    for question in CLASSROOM_OBJECT_QUESTION_BANK:
        if question["key"] not in asked_keys:
            return question.copy()

    return get_classroom_question_by_key_copy("last_hint")


def is_classroom_object_guess_ready(game_state, previous_response_mode="none", child_response=""):
    questions_asked = int(game_state.get("questions_asked", 0) or 0)
    known_clues = game_state.get("known_clues", [])
    guess_cooldown = int(game_state.get("guess_cooldown_questions", 0) or 0)

    if game_state.get("skip_guess_once") or guess_cooldown > 0:
        return False

    if questions_asked < 3 or len(known_clues) < 3:
        return False

    active_candidates = get_classroom_candidate_keys(game_state)
    if len(active_candidates) == 1:
        return True

    # Once the pool is tiny, ask one more family-specific question instead of drifting.
    if len(active_candidates) <= 2 and questions_asked >= 4:
        return True

    guess, score, margin = get_classroom_object_guess_confidence(game_state)

    if not guess:
        return False

    if questions_asked >= CLASSROOM_OBJECT_MAX_QUESTIONS_PER_ROUND:
        return score >= 16 and margin >= 2

    if score >= 38 and margin >= 8:
        return True

    if questions_asked >= 6 and score >= 30 and margin >= 6:
        return True

    if questions_asked >= 8 and score >= 23 and margin >= 4:
        return True

    return False




# Final hotfix: use strict option tags for candidate filtering and keep category paths ordered.
def extract_classroom_option_tags_only(question_item, answer):
    lowered = normalize_classroom_object_text(answer)
    words = classroom_object_words(lowered)
    tags = set()

    option_tags = (question_item or {}).get("option_tags") or {}
    for raw_option, option_tag_set in option_tags.items():
        option = normalize_classroom_object_text(raw_option)
        option_words = classroom_object_words(option)
        if not option:
            continue
        if option in lowered or option in words or (option_words and option_words.issubset(words)):
            tags.update(option_tag_set)
    return tags


def classroom_filter_candidates_from_answer(game_state, question_item, child_response):
    question_key = (question_item or {}).get("key")

    if is_classroom_object_unclear_or_silent(child_response):
        if question_key:
            game_state.setdefault("void_question_keys", []).append(question_key)
        return

    current_keys = get_classroom_candidate_keys(game_state)
    offered_tags = get_classroom_question_offered_tags(question_item)
    strict_answer_tags = extract_classroom_option_tags_only(question_item, child_response)
    answer_tags = strict_answer_tags or extract_classroom_tags_from_answer(question_item, child_response)

    if classroom_answer_was_other(child_response) and offered_tags:
        filtered = [
            key for key in current_keys
            if not (get_classroom_profile_all_tags(CLASSROOM_OBJECT_PROFILES[key]) & offered_tags)
        ]
        action = "excluded_offered_options"
    elif answer_tags:
        filtered = [
            key for key in current_keys
            if get_classroom_profile_all_tags(CLASSROOM_OBJECT_PROFILES[key]) & answer_tags
        ]
        action = "matched_answer_tags"
    else:
        return

    if filtered:
        set_classroom_candidate_keys(game_state, filtered)
        game_state.setdefault("candidate_filter_notes", []).append({
            "question_key": question_key,
            "answer": str(child_response or "")[:80],
            "action": action,
            "remaining": len(filtered)
        })


def choose_first_available_split_question(keys, asked_keys, game_state, allow_zero_score=True):
    for key in keys:
        if key in asked_keys:
            continue
        item = get_classroom_object_question_by_key(key)
        if not item:
            continue
        score = classroom_question_split_score(item, game_state)
        if score > -999 or allow_zero_score:
            return item.copy()
    return None


def choose_first_three_classroom_question(game_state, asked_keys, questions_asked):
    if questions_asked == 0:
        return get_classroom_question_by_key_copy("category_first")

    family = classroom_candidate_family(game_state)

    if family == "write_tool":
        item = choose_first_available_split_question(
            ["write_tool_type", "write_feature_followup", "write_texture_followup", "write_surface_followup", "color_choice"],
            asked_keys,
            game_state
        )
        if item:
            return item

    if family == "technology":
        item = choose_first_available_split_question(["tech_detail_first", "size_first", "material_other_two", "feature_other"], asked_keys, game_state)
        if item:
            return item

    if family == "storage":
        item = choose_first_available_split_question(["storage_detail_first", "size_first", "material_first", "feature_other"], asked_keys, game_state)
        if item:
            return item

    if family in {"room_part", "wall_front"}:
        item = choose_first_available_split_question(["room_part_detail_first", "wall_detail_first", "size_first", "material_first"], asked_keys, game_state)
        if item:
            return item

    if family == "furniture":
        item = choose_first_available_split_question(["furniture_detail_first", "size_first", "material_first"], asked_keys, game_state)
        if item:
            return item

    if questions_asked == 1 and classroom_chose_other_for_key(game_state, "category_first"):
        if "category_other_followup" not in asked_keys:
            return get_classroom_question_by_key_copy("category_other_followup")

    item = choose_first_available_split_question(FINAL_FIRST_THREE_CLASSROOM_QUESTION_KEYS, asked_keys, game_state)
    if item:
        return item

    for key in ["size_first", "material_first", "where_first"]:
        if key not in asked_keys:
            return get_classroom_question_by_key_copy(key)
    return get_classroom_question_by_key_copy("material_first")


def choose_classroom_object_question(game_state, event_type="child_answer"):
    asked_keys = {
        item.get("key")
        for item in game_state.get("question_history", [])
        if isinstance(item, dict)
    }
    questions_asked = int(game_state.get("questions_asked", 0) or 0)

    if questions_asked < 3:
        return choose_first_three_classroom_question(game_state, asked_keys, questions_asked)

    family = classroom_candidate_family(game_state)

    if family == "write_tool":
        item = choose_first_available_split_question(
            ["write_texture_followup", "write_surface_followup", "write_feature_followup", "write_tool_type", "color_choice", "extra_hint", "last_hint"],
            asked_keys,
            game_state
        )
        if item:
            return item
        return get_classroom_question_by_key_copy("extra_hint")

    if family == "technology":
        item = choose_first_available_split_question(["tech_detail_first", "feature_other", "where_first", "color_choice", "extra_hint"], asked_keys, game_state)
        if item:
            return item

    if family == "storage":
        item = choose_first_available_split_question(["storage_detail_first", "feature_other", "material_first", "where_first", "color_choice", "extra_hint"], asked_keys, game_state)
        if item:
            return item

    if family in {"room_part", "wall_front"}:
        item = choose_first_available_split_question(["room_part_detail_first", "wall_detail_first", "material_first", "feature_other", "color_choice", "extra_hint"], asked_keys, game_state)
        if item:
            return item

    if family == "furniture":
        item = choose_first_available_split_question(["furniture_detail_first", "material_first", "where_first", "color_choice", "extra_hint"], asked_keys, game_state)
        if item:
            return item

    adaptive_keys = []
    if classroom_chose_other_for_key(game_state, "material_first"):
        adaptive_keys.append("material_other_one")
    if classroom_chose_other_for_key(game_state, "material_other_one"):
        adaptive_keys.append("material_other_two")
    if not classroom_has_tag_prefix(game_state, "loc_"):
        adaptive_keys.append("where_first")
    if classroom_chose_other_for_key(game_state, "where_first"):
        adaptive_keys.append("where_other")
    if not (
        classroom_has_any_tag(game_state, {"writing", "drawing", "coloring", "cutting", "sticky", "sit", "work", "math", "time", "dates"}) or
        classroom_has_tag_prefix(game_state, "category_")
    ):
        adaptive_keys.append("use_first")
    if classroom_chose_other_for_key(game_state, "use_first"):
        adaptive_keys.append("use_other")
    if questions_asked >= 5:
        adaptive_keys.append("feature_first")
    if classroom_chose_other_for_key(game_state, "feature_first"):
        adaptive_keys.append("feature_other")
    if questions_asked >= 6:
        adaptive_keys.append("color_choice")

    item = choose_best_unasked_from_keys(adaptive_keys, asked_keys, game_state, allow_zero_score=True)
    if item:
        return item

    fallback_keys = ["use_first", "feature_first", "where_first", "color_choice", "extra_hint"] if questions_asked < 8 else ["last_hint"]
    for key in fallback_keys:
        if key not in asked_keys:
            return get_classroom_question_by_key_copy(key)

    for question in CLASSROOM_OBJECT_QUESTION_BANK:
        if question["key"] not in asked_keys:
            return question.copy()
    return get_classroom_question_by_key_copy("last_hint")




# Final round-style patch: keep rounds 1-3 strict and candidate-aware, then restore
# Mystery Animal-style guided/open questions for questions 4-9.
# This intentionally overrides choose_classroom_object_question and guess timing below.

def classroom_upsert_open_round_question(key, question, stage, response_mode):
    classroom_upsert_question({
        "key": key,
        "question": question,
        "stage": stage,
        "response_mode": response_mode,
        "option_tags": {}
    })


# Questions 4-6: short, a little more open-ended, modeled after Mystery Animal's
# detail questions like color/place/food/movement/body-part. These still feed the
# scoring system through the keyword extractor, but they do not feel like more
# forced choice questions.
classroom_upsert_open_round_question(
    "detail_color_open",
    "What color is it usually?",
    "guided_clue",
    "one_word"
)
classroom_upsert_open_round_question(
    "detail_where_open",
    "Where would I usually find it?",
    "guided_clue",
    "short_phrase"
)
classroom_upsert_open_round_question(
    "detail_use_open",
    "What do people use it for?",
    "guided_clue",
    "short_phrase"
)
classroom_upsert_open_round_question(
    "detail_notice_open",
    "What part should I notice first?",
    "tiny_hint",
    "short_phrase"
)
classroom_upsert_open_round_question(
    "detail_look_open",
    "What does it look like?",
    "guided_clue",
    "short_phrase"
)
classroom_upsert_open_round_question(
    "detail_special_open",
    "What makes it different from other classroom objects like it?",
    "tiny_hint",
    "short_phrase"
)

# Family-specific detail questions for questions 4-6.
classroom_upsert_open_round_question(
    "write_detail_mark",
    "What kind of mark does it make?",
    "guided_clue",
    "short_phrase"
)
classroom_upsert_open_round_question(
    "write_detail_look",
    "What does the outside of it look like?",
    "guided_clue",
    "short_phrase"
)
classroom_upsert_open_round_question(
    "write_detail_difference",
    "What makes it different from other things you write or color with?",
    "tiny_hint",
    "short_phrase"
)
classroom_upsert_open_round_question(
    "storage_detail_contents_open",
    "What do people put inside it?",
    "guided_clue",
    "short_phrase"
)
classroom_upsert_open_round_question(
    "storage_detail_carry_open",
    "How do people carry it or open it?",
    "guided_clue",
    "short_phrase"
)
classroom_upsert_open_round_question(
    "tech_detail_use_open",
    "What does it help people do?",
    "guided_clue",
    "short_phrase"
)
classroom_upsert_open_round_question(
    "tech_detail_notice_open",
    "What part of it should I notice first?",
    "guided_clue",
    "short_phrase"
)
classroom_upsert_open_round_question(
    "wall_detail_place_open",
    "Where is it in the classroom?",
    "guided_clue",
    "short_phrase"
)
classroom_upsert_open_round_question(
    "wall_detail_purpose_open",
    "What does it help the class see or do?",
    "guided_clue",
    "short_phrase"
)
classroom_upsert_open_round_question(
    "furniture_detail_use_open",
    "What do people do with it?",
    "guided_clue",
    "short_phrase"
)
classroom_upsert_open_round_question(
    "furniture_detail_shape_open",
    "What shape or part should I notice first?",
    "guided_clue",
    "short_phrase"
)
classroom_upsert_open_round_question(
    "room_part_detail_open",
    "What part of the room is it near?",
    "guided_clue",
    "short_phrase"
)

# Questions 7-9: open hints, modeled after Mystery Animal's later hint section.
classroom_upsert_open_round_question(
    "hint_look_open",
    "What does it look like?",
    "open_hint",
    "open_hint"
)
classroom_upsert_open_round_question(
    "hint_action_open",
    "What do people do with it?",
    "open_hint",
    "open_hint"
)
classroom_upsert_open_round_question(
    "hint_place_open",
    "Where might I see it in the classroom?",
    "open_hint",
    "open_hint"
)
classroom_upsert_open_round_question(
    "hint_best_open",
    "Can I get a hint?",
    "open_hint",
    "open_hint"
)
classroom_upsert_open_round_question(
    "write_hint_difference_open",
    "What makes it different from other things you write or color with?",
    "open_hint",
    "open_hint"
)
classroom_upsert_open_round_question(
    "tech_hint_difference_open",
    "What makes it different from other classroom technology?",
    "open_hint",
    "open_hint"
)
classroom_upsert_open_round_question(
    "storage_hint_difference_open",
    "What makes it different from other things that hold supplies?",
    "open_hint",
    "open_hint"
)
classroom_upsert_open_round_question(
    "wall_hint_difference_open",
    "What makes it different from other things on the wall or front of the room?",
    "open_hint",
    "open_hint"
)
classroom_upsert_open_round_question(
    "furniture_hint_difference_open",
    "What makes it different from other classroom furniture?",
    "open_hint",
    "open_hint"
)


def classroom_first_available_question(keys, asked_keys):
    for key in keys:
        if key in asked_keys:
            continue
        item = get_classroom_question_by_key_copy(key)
        if item:
            return item
    return None


def classroom_mid_detail_keys_for_family(family):
    # Questions 4-6. Keep them short and child-friendly, not giant option lists.
    if family == "write_tool":
        return [
            "write_detail_mark",
            "write_detail_look",
            "write_detail_difference",
            "detail_color_open",
            "detail_notice_open"
        ]
    if family == "technology":
        return [
            "tech_detail_use_open",
            "tech_detail_notice_open",
            "detail_where_open",
            "detail_color_open"
        ]
    if family == "storage":
        return [
            "storage_detail_contents_open",
            "storage_detail_carry_open",
            "detail_where_open",
            "detail_color_open"
        ]
    if family in {"room_part", "wall_front"}:
        return [
            "wall_detail_place_open",
            "wall_detail_purpose_open",
            "detail_notice_open",
            "detail_color_open"
        ]
    if family == "furniture":
        return [
            "furniture_detail_use_open",
            "furniture_detail_shape_open",
            "detail_color_open",
            "detail_where_open"
        ]
    return [
        "detail_use_open",
        "detail_look_open",
        "detail_where_open",
        "detail_color_open",
        "detail_notice_open",
        "detail_special_open"
    ]


def classroom_late_hint_keys_for_family(family):
    # Questions 7-9. These are intentionally more open, just like Mystery Animal's
    # later hint rounds.
    if family == "write_tool":
        return ["write_hint_difference_open", "hint_look_open", "hint_action_open", "hint_best_open"]
    if family == "technology":
        return ["tech_hint_difference_open", "hint_action_open", "hint_look_open", "hint_best_open"]
    if family == "storage":
        return ["storage_hint_difference_open", "hint_action_open", "hint_look_open", "hint_best_open"]
    if family in {"room_part", "wall_front"}:
        return ["wall_hint_difference_open", "hint_place_open", "hint_look_open", "hint_best_open"]
    if family == "furniture":
        return ["furniture_hint_difference_open", "hint_action_open", "hint_look_open", "hint_best_open"]
    return ["hint_look_open", "hint_action_open", "hint_place_open", "hint_best_open"]


def choose_classroom_object_question(game_state, event_type="child_answer"):
    asked_keys = {
        item.get("key")
        for item in game_state.get("question_history", [])
        if isinstance(item, dict)
    }

    questions_asked = int(game_state.get("questions_asked", 0) or 0)
    rounds_completed = int(game_state.get("rounds_completed", 0) or 0)
    activity_round_number = rounds_completed + 1
    family = classroom_candidate_family(game_state)

    # Activity rounds 1-3:
    # keep the working decision-tree flow. These rounds are intentionally more
    # guided, with the first three spoken questions doing most of the narrowing.
    if activity_round_number <= 3:
        if questions_asked < 3:
            return choose_first_three_classroom_question(game_state, asked_keys, questions_asked)

        if questions_asked < 6:
            item = classroom_first_available_question(
                classroom_mid_detail_keys_for_family(family),
                asked_keys
            )
            if item:
                return item

        item = classroom_first_available_question(
            classroom_late_hint_keys_for_family(family),
            asked_keys
        )
        if item:
            return item

        return get_classroom_question_by_key_copy("hint_best_open") or get_classroom_question_by_key_copy("last_hint")

    # Activity rounds 4-6:
    # do NOT start with another "this, this, or something else" question.
    # Start with short guided clue questions, like Mystery Animal's middle rounds.
    if activity_round_number <= 6:
        item = classroom_first_available_question(
            classroom_mid_detail_keys_for_family(family),
            asked_keys
        )
        if item:
            return item

        item = classroom_first_available_question(
            classroom_late_hint_keys_for_family(family),
            asked_keys
        )
        if item:
            return item

        return get_classroom_question_by_key_copy("hint_best_open") or get_classroom_question_by_key_copy("last_hint")

    # Activity rounds 7-9:
    # start even more openly, matching Mystery Animal's late hint rounds.
    item = classroom_first_available_question(
        classroom_late_hint_keys_for_family(family),
        asked_keys
    )
    if item:
        return item

    item = classroom_first_available_question(
        classroom_mid_detail_keys_for_family(family),
        asked_keys
    )
    if item:
        return item

    return get_classroom_question_by_key_copy("hint_best_open") or get_classroom_question_by_key_copy("last_hint")

def is_classroom_object_guess_ready(game_state, previous_response_mode="none", child_response=""):
    questions_asked = int(game_state.get("questions_asked", 0) or 0)
    known_clues = game_state.get("known_clues", [])
    guess_cooldown = int(game_state.get("guess_cooldown_questions", 0) or 0)

    if game_state.get("skip_guess_once") or guess_cooldown > 0:
        return False

    # Do not guess immediately after the three strict decision-tree questions.
    # Ask at least one more Mystery Animal-style detail question first.
    if questions_asked < 4 or len(known_clues) < 4:
        return False

    active_candidates = get_classroom_candidate_keys(game_state)
    if len(active_candidates) == 1 and questions_asked >= 4:
        return True

    if len(active_candidates) <= 2 and questions_asked >= 5:
        return True

    guess, score, margin = get_classroom_object_guess_confidence(game_state)

    if not guess:
        return False

    if questions_asked >= CLASSROOM_OBJECT_MAX_QUESTIONS_PER_ROUND:
        return score >= 16 and margin >= 2

    if questions_asked >= 5 and score >= 38 and margin >= 8:
        return True

    if questions_asked >= 6 and score >= 30 and margin >= 6:
        return True

    if questions_asked >= 8 and score >= 23 and margin >= 4:
        return True

    return False

@app.route("/api/mystery-classroom-object/thinking-audio", methods=["GET"])
@app.route("/api/book-guessing-game/thinking-audio", methods=["GET"])
@csrf.exempt
@login_required
@limiter.limit("50 per minute")
def book_guessing_game_thinking_audio():
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

    cache_dir = os.path.join(BASE_DIR, "static", "audio", "mystery_classroom_object_thinking")
    os.makedirs(cache_dir, exist_ok=True)

    voice_id = (
        os.getenv("TEACHER_VOICE_ID")
        or os.getenv("LIBRARIAN_VOICE_ID")
        or os.getenv("ELEVENLABS_VOICE_ID", "piI8Kku0DcvcL6TTSeQt")
    )
    cache_key = f"mystery-classroom-object-thinking-v1:{voice_id}:{line}"
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
            "audio_url": url_for("static", filename=f"audio/mystery_classroom_object_thinking/{filename}")
        })

    except Exception as e:
        print("Mystery Classroom Object thinking audio error:", repr(e))
        return jsonify({"success": False, "error": "Could not generate thinking audio"}), 500



# =========================
# Mystery Classroom Object — OpenAI-driven rounds 4-9
# Rounds 1-3 remain deterministic decision-tree rounds.
# Rounds 4-9 use OpenAI to decide whether to ask, guess, or give up.
# =========================

CLASSROOM_OBJECT_AI_MODEL = os.getenv("CLASSROOM_OBJECT_AI_MODEL", "gpt-4o-mini")
CLASSROOM_OBJECT_AI_GIVE_UP_AFTER_QUESTIONS = 7
CLASSROOM_OBJECT_AI_FIRST_GUESS_AFTER_QUESTIONS = 2

# Rounds 4-6: short, easy, straightforward short-answer questions.
# No "give me a clue" / "what is special" style prompts here.
CLASSROOM_OBJECT_AI_MID_QUESTIONS = [
    {
        "key": "ai_use_open",
        "question": "What do people use it for?",
        "stage": "guided_clue",
        "response_mode": "short_phrase"
    },
    {
        "key": "ai_color_open",
        "question": "What color is it usually?",
        "stage": "guided_clue",
        "response_mode": "short_phrase"
    },
    {
        "key": "ai_look_open",
        "question": "What does it look like?",
        "stage": "guided_clue",
        "response_mode": "short_phrase"
    },
    {
        "key": "ai_made_of_open",
        "question": "What is it made of?",
        "stage": "guided_clue",
        "response_mode": "short_phrase"
    },
    {
        "key": "ai_where_open",
        "question": "Where do you usually see it?",
        "stage": "guided_clue",
        "response_mode": "short_phrase"
    },
    {
        "key": "ai_touch_open",
        "question": "What part do people use or touch?",
        "stage": "guided_clue",
        "response_mode": "short_phrase"
    }
]

# Rounds 7-9: later rounds may ask broader hint/clue questions, while still
# mixing in simple open-ended questions when helpful.
CLASSROOM_OBJECT_AI_LATE_QUESTIONS = [
    {
        "key": "ai_look_hint_open",
        "question": "What does it look like?",
        "stage": "open_hint",
        "response_mode": "open_hint"
    },
    {
        "key": "ai_action_hint_open",
        "question": "What do people do with it?",
        "stage": "open_hint",
        "response_mode": "open_hint"
    },
    {
        "key": "ai_place_hint_open",
        "question": "Where might I find it?",
        "stage": "open_hint",
        "response_mode": "open_hint"
    },
    {
        "key": "ai_best_clue_open",
        "question": "Can I get a hint?",
        "stage": "open_hint",
        "response_mode": "open_hint"
    },
    {
        "key": "ai_difference_hint_open",
        "question": "Can you give me a hint about what makes it different?",
        "stage": "open_hint",
        "response_mode": "open_hint"
    },
    {
        "key": "ai_final_hint_open",
        "question": "Can you give me one more hint?",
        "stage": "open_hint",
        "response_mode": "open_hint"
    }
]


def classroom_activity_round_number(game_state):
    return int(game_state.get("rounds_completed", 0) or 0) + 1


def classroom_use_openai_round(game_state):
    return classroom_activity_round_number(game_state) >= 4


def classroom_ai_question_bank_for_round(game_state):
    round_number = classroom_activity_round_number(game_state)

    if round_number <= 6:
        return list(CLASSROOM_OBJECT_AI_MID_QUESTIONS)

    # Late rounds can use both late hint questions and the simpler short-answer
    # questions, but prioritize the late hint questions first.
    return list(CLASSROOM_OBJECT_AI_LATE_QUESTIONS) + list(CLASSROOM_OBJECT_AI_MID_QUESTIONS)


def classroom_ai_question_by_key(key, game_state=None):
    banks = []
    if game_state is not None:
        banks.extend(classroom_ai_question_bank_for_round(game_state))
    banks.extend(CLASSROOM_OBJECT_AI_MID_QUESTIONS)
    banks.extend(CLASSROOM_OBJECT_AI_LATE_QUESTIONS)

    seen = set()
    for item in banks:
        item_key = item.get("key")
        if item_key in seen:
            continue
        seen.add(item_key)
        if item_key == key:
            return item.copy()
    return None


def classroom_ai_available_questions(game_state):
    asked_keys = {
        item.get("key")
        for item in game_state.get("question_history", [])
        if isinstance(item, dict)
    }

    questions = []
    seen = set()
    for item in classroom_ai_question_bank_for_round(game_state):
        key = item.get("key")
        if key in asked_keys or key in seen:
            continue
        seen.add(key)
        questions.append(item.copy())

    if not questions:
        backup = CLASSROOM_OBJECT_AI_LATE_QUESTIONS + CLASSROOM_OBJECT_AI_MID_QUESTIONS
        for item in backup:
            key = item.get("key")
            if key in asked_keys or key in seen:
                continue
            seen.add(key)
            questions.append(item.copy())

    if not questions:
        questions = [CLASSROOM_OBJECT_AI_LATE_QUESTIONS[-1].copy()]

    return questions


def classroom_ai_clues_for_prompt(game_state):
    clues = []
    for item in game_state.get("known_clues", [])[-8:]:
        if not isinstance(item, dict):
            continue
        q = re.sub(r"\s+", " ", str(item.get("question", "") or "")).strip()
        a = re.sub(r"\s+", " ", str(item.get("answer", "") or "")).strip()
        if q and a:
            clues.append({"question": q[:120], "answer": a[:120]})
    return clues


def classroom_common_objects_for_prompt():
    objects = []
    try:
        for profile in CLASSROOM_OBJECT_PROFILES.values():
            display = str(profile.get("display", "")).strip()
            if display and display not in objects:
                objects.append(display)
    except Exception:
        pass
    return objects[:60]


def fallback_classroom_ai_question(game_state):
    return classroom_ai_available_questions(game_state)[0]


def classroom_ai_guess_pressure(game_state):
    questions_asked = int(game_state.get("questions_asked", 0) or 0)
    clues = classroom_ai_clues_for_prompt(game_state)
    rejected = [g for g in game_state.get("rejected_guesses", []) if str(g or "").strip()]
    recent_guesses = [g for g in game_state.get("recent_guesses", []) if str(g or "").strip()]

    if questions_asked >= CLASSROOM_OBJECT_AI_GIVE_UP_AFTER_QUESTIONS:
        return "give_up"

    # After a rejected guess, let GPT try another likely option before asking again
    # unless it truly needs one more clue.
    if rejected and questions_asked >= CLASSROOM_OBJECT_AI_FIRST_GUESS_AFTER_QUESTIONS:
        return "guess_preferred"

    # Do not wait for certainty. Once there are a couple of useful answers in
    # rounds 4-9, GPT should start testing guesses.
    if len(clues) >= 3 or questions_asked >= 3:
        return "guess_preferred"

    if len(clues) >= 2 or questions_asked >= CLASSROOM_OBJECT_AI_FIRST_GUESS_AFTER_QUESTIONS:
        return "guess_allowed"

    return "ask"


def get_classroom_openai_decision(game_state, force_ask=False):
    """Return a small JSON-compatible dict:
    {"action": "ask"|"guess"|"give_up", "question_key": "...", "guess": "..."}

    Rounds 4-9 use this instead of the deterministic decision-tree selector.
    The backend supplies the approved questions; OpenAI chooses whether to ask,
    guess, or give up.
    """
    questions_asked = int(game_state.get("questions_asked", 0) or 0)
    clues = classroom_ai_clues_for_prompt(game_state)
    available_questions = classroom_ai_available_questions(game_state)
    guess_pressure = classroom_ai_guess_pressure(game_state)

    if not force_ask and guess_pressure == "give_up":
        return {"action": "give_up", "question_key": "", "guess": ""}

    if force_ask or not clues:
        return {"action": "ask", "question_key": available_questions[0]["key"], "guess": ""}

    prompt_payload = {
        "activity_round": classroom_activity_round_number(game_state),
        "questions_asked_this_object": questions_asked,
        "guess_pressure": guess_pressure,
        "rules": {
            "rounds_4_to_6": "Ask short, easy, straightforward short-answer questions. Avoid hard hint questions like 'what clue would help' or 'what makes it special'.",
            "rounds_7_to_9": "You may ask broader hint questions, but simple open-ended questions are still okay.",
            "guessing": "Do not wait until you are certain. Once there are 2-3 useful clues, make a reasonable guess. After one wrong guess, you may make a second likely guess before asking another question.",
            "give_up": "If the object is still unclear after about 7 questions, choose give_up."
        },
        "clues": clues,
        "already_guessed": list(game_state.get("rejected_guesses", []))[-6:],
        "recent_guesses": list(game_state.get("recent_guesses", []))[-6:],
        "common_classroom_objects": classroom_common_objects_for_prompt(),
        "allowed_questions": [
            {"key": q["key"], "question": q["question"]}
            for q in available_questions
        ]
    }

    try:
        response = client.chat.completions.create(
            model=CLASSROOM_OBJECT_AI_MODEL,
            temperature=0.2,
            max_tokens=110,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are the reasoning engine for a child's classroom-object guessing game. "
                        "Use the child's clues to decide the next move. Return ONLY JSON with keys: "
                        "action, question_key, guess. action must be ask, guess, or give_up. "
                        "If asking, question_key must be one of the allowed question keys. "
                        "If guessing, guess should be a concise classroom object name. "
                        "Never repeat or summarize the child's last answer in your output. "
                        "Do not invent question text. Use only the approved question_key. "
                        "If guess_pressure is guess_preferred, strongly prefer action='guess' unless the clues are truly too weak. "
                        "If you already made a wrong guess, try another likely guess when reasonable. "
                        "Do not wait for perfect certainty; reasonable guesses are encouraged. "
                        "If the clues are still too weak after many questions, choose give_up."
                    )
                },
                {
                    "role": "user",
                    "content": json.dumps(prompt_payload, ensure_ascii=False)
                }
            ]
        )

        content = response.choices[0].message.content or "{}"
        decision = json.loads(content)
    except Exception as e:
        print("Mystery Classroom Object OpenAI decision error:", repr(e))
        return {"action": "ask", "question_key": available_questions[0]["key"], "guess": ""}

    action = normalize_classroom_object_text(decision.get("action", "ask"))
    if action not in {"ask", "guess", "give_up"}:
        action = "ask"

    question_key = normalize_classroom_object_text(decision.get("question_key", ""))
    allowed_keys = {q["key"] for q in available_questions}
    if action == "ask" and question_key not in allowed_keys:
        question_key = available_questions[0]["key"]

    guess = re.sub(r"\s+", " ", str(decision.get("guess", "") or "")).strip()[:60]
    if action == "guess" and not guess:
        action = "ask"
        question_key = available_questions[0]["key"]

    # If GPT keeps asking even after enough clues, still keep the game moving.
    # This fallback is only a safety net; the normal guess is chosen by OpenAI.
    if action == "ask" and guess_pressure == "guess_preferred" and guess:
        action = "guess"

    return {"action": action, "question_key": question_key, "guess": guess}


def classroom_record_question_item(game_state, question_item):
    question_text = question_item["question"]
    game_state["stage"] = question_item["stage"]
    game_state["last_response_mode"] = question_item["response_mode"]
    game_state["last_question"] = question_text
    game_state["last_question_key"] = question_item["key"]
    game_state.setdefault("question_history", []).append({
        "key": question_item["key"],
        "question": question_text,
        "stage": question_item["stage"],
        "response_mode": question_item["response_mode"]
    })
    game_state["questions_asked"] = int(game_state.get("questions_asked", 0) or 0) + 1


def classroom_build_ai_followup_response(game_state, history, event_type, child_response, previous_response_mode, child_name="there", force_ask=False):
    decision = get_classroom_openai_decision(game_state, force_ask=force_ask)
    action = decision.get("action", "ask")

    if action == "give_up":
        game_state["soft_reveal_used"] = True
        return make_book_guessing_game_audio_response(
            message="This is a tricky one. I don't know what it is yet. Can you tell me the classroom object?",
            stage="give_up_reveal",
            response_mode="object_reveal",
            expects_response=True,
            game_complete=False,
            game_state=game_state,
            history=history,
            event_type="openai_give_up",
            child_response=child_response
        )

    if action == "guess":
        guess = re.sub(r"\s+", " ", str(decision.get("guess", "") or "")).strip()
        if guess:
            game_state["possible_guess"] = guess
            game_state["stage"] = "guess"
            game_state["last_response_mode"] = "guess_confirmation"
            game_state["recent_guesses"] = (list(game_state.get("recent_guesses", [])) + [guess])[-6:]
            article = classroom_object_article(guess)
            return make_book_guessing_game_audio_response(
                message=f"I have a guess. Is it {article} {guess}?",
                stage="guess",
                response_mode="guess_confirmation",
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type="openai_guess",
                child_response=child_response
            )

    question_item = classroom_ai_question_by_key(decision.get("question_key", ""), game_state) or fallback_classroom_ai_question(game_state)
    question_text = question_item["question"]

    # For OpenAI-driven rounds 4-9, do not reiterate the child's response.
    # Just ask the next question or give the guess.
    message = question_text
    if event_type == "no_response":
        message = f"That's okay. {question_text}"

    classroom_record_question_item(game_state, question_item)

    return make_book_guessing_game_audio_response(
        message=message,
        stage=question_item["stage"],
        response_mode=question_item["response_mode"],
        expects_response=True,
        game_complete=False,
        game_state=game_state,
        history=history,
        event_type="openai_question",
        child_response=child_response
    )




# Final polish override: make early-round acknowledgments occasional instead of repetitive.
def maybe_add_classroom_acknowledgment(message, event_type, child_response, previous_response_mode, game_state):
    import random

    if event_type != "child_answer":
        return message

    if previous_response_mode in {"none", "guess_confirmation", "round_choice", "object_reveal"}:
        return message

    if not is_clear_classroom_object_response(child_response, previous_response_mode):
        return message

    # Rounds 4-9 are OpenAI-driven and should not reiterate the child's answer.
    if classroom_use_openai_round(game_state):
        return message

    lowered_message = normalize_classroom_object_text(message)
    if lowered_message.startswith(("okay", "got it", "that helps", "thank")):
        return message

    count = int(game_state.get("early_acknowledgment_count", 0) or 0) + 1
    game_state["early_acknowledgment_count"] = count

    fragment = classroom_clean_answer_fragment(child_response)
    recent = list(game_state.get("recent_acknowledgments", []))[-4:]

    # Echo the actual child answer only once in a while, not every turn.
    should_echo = bool(fragment) and count % 3 == 1

    if should_echo:
        options = [
            f"Okay, {fragment}.",
            f"Got it, {fragment}.",
            f"That helps, {fragment}."
        ]
    else:
        options = [
            "Okay.",
            "Got it.",
            "That helps.",
            "Thanks."
        ]

    fresh = [line for line in options if line not in recent]
    acknowledgment = random.choice(fresh or options)
    game_state["recent_acknowledgments"] = (recent + [acknowledgment])[-4:]

    return f"{acknowledgment} {message}"


@app.route("/api/mystery-classroom-object/message", methods=["POST"])
@app.route("/api/book-guessing-game/message", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("30 per minute")
def book_guessing_game_message():
    data = request.get_json(silent=True) or {}

    event_type = re.sub(r"\s+", " ", str(data.get("event_type", "intro") or "intro")).strip()
    child_response = re.sub(r"\s+", " ", str(data.get("child_response", "") or "")).strip()
    previous_response_mode = re.sub(r"\s+", " ", str(data.get("response_mode", "none") or "none")).strip()

    allowed_events = {"intro", "restart", "first_question", "round_choice_prompt", "child_answer", "no_response"}

    if event_type not in allowed_events:
        return jsonify({"success": False, "error": "Invalid event_type"}), 400

    child_name = clean_classroom_child_name(session.get("child_name", "")) or "there"

    if event_type in {"intro", "restart"}:
        session.pop("mystery_classroom_object_history", None)
        session.pop("mystery_classroom_object_state", None)
        session.pop("book_guessing_game_history", None)
        session.pop("book_guessing_game_state", None)

        saved_rounds = get_saved_classroom_object_rounds()
        history = []
        game_state = get_classroom_object_default_state(rounds_completed=saved_rounds)
        child_response = ""
        previous_response_mode = "none"

        if saved_rounds >= CLASSROOM_OBJECT_REQUIRED_ROUNDS:
            message = (
                "Hi, I'm your teacher. Welcome back to Mystery Classroom Object. "
                "We finished our main rounds, but we can still play again if you want. "
                "Think of a classroom object, like a pencil, backpack, or desk. It can be something else too."
            )
        elif saved_rounds > 0:
            message = (
                "Hi, I'm your teacher. Welcome back to Mystery Classroom Object. "
                "We'll keep going from where you left off. "
                "Think of a classroom object, like a pencil, backpack, or desk. It can be something else too."
            )
        else:
            message = (
                "Hi, I'm your teacher. We're going to play Mystery Classroom Object. "
                "Think of a classroom object, like a pencil, backpack, or desk. It can be something else too. "
                "I'll start with three this-or-that questions to help me narrow it down."
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
            print("Mystery Classroom Object intro TTS error:", repr(e))
            return jsonify({"success": False, "error": "Could not generate Teacher intro"}), 500

    history = session.get(
        "mystery_classroom_object_history",
        session.get("book_guessing_game_history", [])
    )
    game_state = session.get(
        "mystery_classroom_object_state",
        session.get("book_guessing_game_state", get_classroom_object_default_state())
    )

    if previous_response_mode == "round_choice" and event_type in {"child_answer", "no_response"}:
        rounds_completed = int(game_state.get("rounds_completed", 0) or 0)
        ready_to_unlock_next = rounds_completed >= CLASSROOM_OBJECT_REQUIRED_ROUNDS
        is_break_checkpoint = is_classroom_object_break_checkpoint(rounds_completed)

        if event_type == "no_response":
            choice = "stop" if ready_to_unlock_next else "unclear"
        else:
            choice = classify_classroom_object_round_choice(
                child_response,
                offer_next_game=ready_to_unlock_next
            )

        if choice == "same_game":
            message = "Okay. Let's play another round. Think of a new classroom object, like a pencil, backpack, or desk."
            try:
                return start_new_classroom_object_round(
                    rounds_completed=rounds_completed,
                    message=message,
                    event_label="replay",
                    pause_ms=1800
                )
            except Exception as e:
                print("Mystery Classroom Object replay TTS error:", repr(e))
                return jsonify({"success": False, "error": "Could not generate replay intro"}), 500

        if choice in {"stop", "next_game"}:
            if ready_to_unlock_next:
                message = "Okay. Great work today. We can end here. Bye-bye. See you later."
                try:
                    return end_classroom_object_call(
                        message=message,
                        game_state=game_state,
                        history=history,
                        event_label="complete_and_stop",
                        unlock_next=True
                    )
                except Exception as e:
                    print("Mystery Classroom Object complete-and-stop TTS error:", repr(e))
                    return jsonify({"success": False, "error": "Could not finish Mystery Classroom Object"}), 500

            message = "Okay. We can take a break for now. Your spot is saved. Bye-bye. See you later."
            try:
                return end_classroom_object_call(
                    message=message,
                    game_state=game_state,
                    history=history,
                    event_label="break_for_now",
                    unlock_next=False,
                    redirect_to_dashboard=True
                )
            except Exception as e:
                print("Mystery Classroom Object break TTS error:", repr(e))
                return jsonify({"success": False, "error": "Could not take a break"}), 500

        if ready_to_unlock_next:
            message = "That's okay. You can say play again, or you can say end here."
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
                print("Mystery Classroom Object choice clarification TTS error:", repr(e))
                return jsonify({"success": False, "error": "Could not generate choice response"}), 500

        if is_break_checkpoint:
            message = "That's okay. You can say continue playing, or take a break for now."
            try:
                return make_book_guessing_game_audio_response(
                    message=message,
                    stage="round_choice",
                    response_mode="round_choice",
                    expects_response=True,
                    game_complete=False,
                    game_state=game_state,
                    history=history,
                    event_type="break_choice_clarification",
                    child_response=child_response
                )
            except Exception as e:
                print("Mystery Classroom Object break clarification TTS error:", repr(e))
                return jsonify({"success": False, "error": "Could not generate break choice response"}), 500

        message = "That's okay. We can play another round together."
        try:
            return start_new_classroom_object_round(
                rounds_completed=rounds_completed,
                message=message,
                event_label="choice_unclear_continue",
                pause_ms=1500
            )
        except Exception as e:
            print("Mystery Classroom Object unclear-choice replay error:", repr(e))
            return jsonify({"success": False, "error": "Could not continue the game"}), 500

    if event_type == "first_question":
        if classroom_use_openai_round(game_state):
            try:
                return classroom_build_ai_followup_response(
                    game_state=game_state,
                    history=history,
                    event_type="first_question",
                    child_response="",
                    previous_response_mode="none",
                    child_name=child_name,
                    force_ask=True
                )
            except Exception as e:
                print("Mystery Classroom Object OpenAI first-question error:", repr(e))
                return jsonify({"success": False, "error": "Could not generate Teacher question"}), 500

        question_item = choose_classroom_object_question(game_state, event_type="first_question")
        question_text = question_item["question"]
        message = f"Okay. {question_text}"

        game_state["stage"] = question_item["stage"]
        game_state["last_response_mode"] = question_item["response_mode"]
        game_state["game_complete"] = False
        game_state["last_question"] = question_text
        game_state["last_question_key"] = question_item["key"]
        game_state.setdefault("question_history", []).append({
            "key": question_item["key"],
            "question": question_text,
            "stage": question_item["stage"],
            "response_mode": question_item["response_mode"]
        })
        game_state["questions_asked"] = int(game_state.get("questions_asked", 0) or 0) + 1

        try:
            return make_book_guessing_game_audio_response(
                message=message,
                stage=question_item["stage"],
                response_mode=question_item["response_mode"],
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type="first_question",
                child_response=""
            )
        except Exception as e:
            print("Mystery Classroom Object first question TTS error:", repr(e))
            return jsonify({"success": False, "error": "Could not generate first question"}), 500

    if (
        event_type == "child_answer"
        and (game_state.get("stage") == "give_up_reveal" or previous_response_mode == "object_reveal")
    ):
        told_object = parse_child_told_classroom_object(child_response) or get_classroom_object_named_object(child_response)

        if told_object:
            game_state["possible_guess"] = told_object
            game_state["rounds_completed"] = int(game_state.get("rounds_completed", 0) or 0) + 1
            article = classroom_object_article(told_object)
            base_message = f"Oh, it was {article} {told_object}. I got it now."

            try:
                return finish_classroom_object_round(
                    base_message=base_message,
                    game_state=game_state,
                    history=history,
                    event_label="child_revealed_after_give_up",
                    child_name=child_name
                )
            except Exception as e:
                print("Mystery Classroom Object reveal finish TTS error:", repr(e))
                return jsonify({"success": False, "error": "Could not finish the round"}), 500

        try:
            return make_book_guessing_game_audio_response(
                message="That's okay. What object were you thinking of? You can say just the object.",
                stage="give_up_reveal",
                response_mode="object_reveal",
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type="give_up_reveal_clarification",
                child_response=child_response
            )
        except Exception as e:
            print("Mystery Classroom Object reveal clarification TTS error:", repr(e))
            return jsonify({"success": False, "error": "Could not generate reveal clarification"}), 500

    revealed_object = parse_child_told_classroom_object(child_response)
    if event_type == "child_answer" and revealed_object and previous_response_mode != "guess_confirmation":
        game_state["stage"] = "guess"
        game_state["last_response_mode"] = "guess_confirmation"
        game_state["possible_guess"] = revealed_object

        article = classroom_object_article(revealed_object)
        message = f"That gives me a guess. Is it {article} {revealed_object}?"

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
            print("Mystery Classroom Object direct reveal TTS error:", repr(e))
            return jsonify({"success": False, "error": "Could not generate Teacher response"}), 500

    update_classroom_object_state_from_response(
        game_state,
        event_type,
        child_response,
        previous_response_mode
    )

    if game_state.get("stage") == "round_choice":
        import random
        success_options = [
            "Yes! I got it.",
            "Aha, I got it!",
            "Yes, that was it!",
            "I found it!",
            "Okay, I got it."
        ]
        base_message = random.choice(success_options)

        try:
            return finish_classroom_object_round(
                base_message=base_message,
                game_state=game_state,
                history=history,
                event_label="correct_guess_confirmed",
                child_name=child_name
            )
        except Exception as e:
            print("Mystery Classroom Object correct guess TTS error:", repr(e))
            return jsonify({"success": False, "error": "Could not generate round finish response"}), 500

    if classroom_use_openai_round(game_state):
        try:
            return classroom_build_ai_followup_response(
                game_state=game_state,
                history=history,
                event_type=event_type,
                child_response=child_response,
                previous_response_mode=previous_response_mode,
                child_name=child_name,
                force_ask=(event_type == "no_response" or is_classroom_object_unclear_or_silent(child_response))
            )
        except Exception as e:
            print("Mystery Classroom Object OpenAI follow-up error:", repr(e))
            return jsonify({"success": False, "error": "Could not generate Teacher response"}), 500

    if event_type == "no_response" or is_classroom_object_unclear_or_silent(child_response):
        question_item = choose_classroom_object_question(game_state, event_type="no_response")
        question_text = question_item["question"]

        calm_prefixes = [
            "That's okay.",
            "No problem.",
            "No worries.",
            "That's okay. We can try a different question."
        ]
        prefix_index = int(game_state.get("unclear_or_silent_count", 0) or 0) % len(calm_prefixes)
        message = f"{calm_prefixes[prefix_index]} {question_text}"

        game_state["stage"] = question_item["stage"]
        game_state["last_response_mode"] = question_item["response_mode"]
        game_state["last_question"] = question_text
        game_state["last_question_key"] = question_item["key"]
        game_state.setdefault("question_history", []).append({
            "key": question_item["key"],
            "question": question_text,
            "stage": question_item["stage"],
            "response_mode": question_item["response_mode"]
        })
        game_state["questions_asked"] = int(game_state.get("questions_asked", 0) or 0) + 1

        try:
            return make_book_guessing_game_audio_response(
                message=message,
                stage=question_item["stage"],
                response_mode=question_item["response_mode"],
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type=event_type,
                child_response=child_response
            )
        except Exception as e:
            print("Mystery Classroom Object no-response TTS error:", repr(e))
            return jsonify({"success": False, "error": "Could not generate no-response"}), 500

    if (
        not bool(game_state.get("soft_reveal_used", False))
        and not classroom_use_openai_round(game_state)
        and int(game_state.get("questions_asked", 0) or 0) >= CLASSROOM_OBJECT_SOFT_REVEAL_QUESTION_LIMIT
        and not is_classroom_object_guess_ready(game_state, previous_response_mode, child_response)
    ):
        game_state["soft_reveal_used"] = True
        try:
            return make_book_guessing_game_audio_response(
                message="Hmm, this is a tricky one. I don't know what it is yet. Can you tell me the classroom object?",
                stage="give_up_reveal",
                response_mode="object_reveal",
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type="soft_reveal",
                child_response=child_response
            )
        except Exception as e:
            print("Mystery Classroom Object soft reveal TTS error:", repr(e))
            return jsonify({"success": False, "error": "Could not generate soft reveal"}), 500

    if (not classroom_use_openai_round(game_state)) and is_classroom_object_guess_ready(game_state, previous_response_mode, child_response):
        guess = get_best_classroom_object_guess(game_state)
        game_state["possible_guess"] = guess
        game_state["stage"] = "guess"
        game_state["last_response_mode"] = "guess_confirmation"
        article = classroom_object_article(guess)
        message = f"I have a guess. Is it {article} {guess}?"

        try:
            return make_book_guessing_game_audio_response(
                message=message,
                stage="guess",
                response_mode="guess_confirmation",
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type="guess",
                child_response=child_response
            )
        except Exception as e:
            print("Mystery Classroom Object guess TTS error:", repr(e))
            return jsonify({"success": False, "error": "Could not generate guess"}), 500

    question_item = choose_classroom_object_question(game_state, event_type=event_type)
    question_text = question_item["question"]
    message = question_text

    message = maybe_add_classroom_acknowledgment(
        message=message,
        event_type=event_type,
        child_response=child_response,
        previous_response_mode=previous_response_mode,
        game_state=game_state
    )

    game_state["stage"] = question_item["stage"]
    game_state["last_response_mode"] = question_item["response_mode"]
    game_state["last_question"] = question_text
    game_state["last_question_key"] = question_item["key"]
    game_state.setdefault("question_history", []).append({
        "key": question_item["key"],
        "question": question_text,
        "stage": question_item["stage"],
        "response_mode": question_item["response_mode"]
    })
    game_state["questions_asked"] = int(game_state.get("questions_asked", 0) or 0) + 1

    if game_state.get("skip_guess_once"):
        game_state["skip_guess_once"] = False

    if int(game_state.get("guess_cooldown_questions", 0) or 0) > 0:
        game_state["guess_cooldown_questions"] = max(0, int(game_state.get("guess_cooldown_questions", 0) or 0) - 1)

    try:
        return make_book_guessing_game_audio_response(
            message=message,
            stage=question_item["stage"],
            response_mode=question_item["response_mode"],
            expects_response=True,
            game_complete=False,
            game_state=game_state,
            history=history,
            event_type=event_type,
            child_response=child_response
        )
    except Exception as e:
        print("Mystery Classroom Object response TTS error:", repr(e))
        return jsonify({"success": False, "error": "Could not generate Teacher response"}), 500


@app.route("/api/mystery-classroom-object/transcribe", methods=["POST"])
@app.route("/api/book-guessing-game/transcribe", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("30 per minute")
def book_guessing_game_transcribe():
    if "audio" not in request.files:
        return jsonify({"success": False, "error": "Missing audio"}), 400

    audio_file = request.files["audio"]

    try:
        import io
        audio_bytes = audio_file.read()

        if not audio_bytes:
            return jsonify({"success": False, "error": "Empty audio file"}), 400

        file_obj = io.BytesIO(audio_bytes)
        file_obj.name = "mystery-classroom-object-response.webm"

        transcript = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=file_obj
        )

        text = transcript.text.strip()
        print("MYSTERY CLASSROOM OBJECT TRANSCRIPT:", text)

        return jsonify({"success": True, "text": text})

    except Exception as e:
        print("Mystery Classroom Object transcription error:", repr(e))
        return jsonify({"success": False, "error": str(e)}), 500


# =========================
# Classroom Guessing Game — Teacher thinks of a classroom object
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
LIBRARY_GUESSING_GAME_PRESET_OBJECT_ORDER = [
    "pencil",
    "backpack",
    "glue_stick"
]
LIBRARY_GUESSING_GAME_NEXT_ACTIVITY_ID = 7
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
    try:
        rounds_completed_int = max(0, int(rounds_completed or 0))
    except (TypeError, ValueError):
        rounds_completed_int = 0

    rounds_completed_int = min(rounds_completed_int, LIBRARY_GUESSING_GAME_MAX_ROUNDS)
    preset_index = min(rounds_completed_int, len(LIBRARY_GUESSING_GAME_PRESET_OBJECT_ORDER) - 1)
    secret_object = LIBRARY_GUESSING_GAME_PRESET_OBJECT_ORDER[preset_index]

    if secret_object not in LIBRARY_GUESSING_GAME_OBJECT_PROFILES:
        secret_object = "pencil"

    used_so_far = [
        obj for obj in list(used_objects or [])
        if obj in LIBRARY_GUESSING_GAME_OBJECT_PROFILES
    ]

    if secret_object not in used_so_far:
        used_so_far.append(secret_object)

    used_objects_for_session = used_so_far[-LIBRARY_GUESSING_GAME_MAX_ROUNDS:]

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
You are a warm cartoon teacher playing Classroom Guessing Game.

The teacher is thinking of one secret classroom object.
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
  "message": "Teacher's spoken line",
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


def ensure_library_guessing_game_progress_columns():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(progress)")
    existing_columns = {row["name"] for row in cursor.fetchall()}

    columns_to_add = {
        "library_guessing_game_rounds_completed": "ALTER TABLE progress ADD COLUMN library_guessing_game_rounds_completed INTEGER DEFAULT 0",
        "library_guessing_game_last_played_at": "ALTER TABLE progress ADD COLUMN library_guessing_game_last_played_at TEXT"
    }

    for column_name, alter_sql in columns_to_add.items():
        if column_name not in existing_columns:
            cursor.execute(alter_sql)

    conn.commit()
    conn.close()


def get_library_guessing_game_saved_rounds_for_user():
    ensure_library_guessing_game_progress_columns()

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COALESCE(p.library_guessing_game_rounds_completed, 0) AS rounds_completed
        FROM progress p
        JOIN activity a ON p.activity_id = a.activity_id
        WHERE p.user_id = ?
          AND a.activity_name = 'library_guessing_game'
        LIMIT 1
    """, (session["user_id"],))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return 0

    try:
        return max(0, min(LIBRARY_GUESSING_GAME_MAX_ROUNDS, int(row["rounds_completed"] or 0)))
    except (TypeError, ValueError):
        return 0


def save_library_guessing_game_progress_for_user(rounds_completed):
    ensure_library_guessing_game_progress_columns()

    try:
        rounds_completed = max(0, min(LIBRARY_GUESSING_GAME_MAX_ROUNDS, int(rounds_completed or 0)))
    except (TypeError, ValueError):
        rounds_completed = 0

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE progress
        SET
            library_guessing_game_rounds_completed = MAX(COALESCE(library_guessing_game_rounds_completed, 0), ?),
            library_guessing_game_last_played_at = ?,
            is_completed = CASE
                WHEN ? >= ? THEN 1
                ELSE is_completed
            END
        WHERE user_id = ?
          AND activity_id = (
              SELECT activity_id
              FROM activity
              WHERE activity_name = 'library_guessing_game'
              LIMIT 1
          )
    """, (
        rounds_completed,
        datetime.utcnow().isoformat(),
        rounds_completed,
        LIBRARY_GUESSING_GAME_MAX_ROUNDS,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    return rounds_completed


def reset_library_guessing_game_progress_for_user():
    ensure_library_guessing_game_progress_columns()

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE progress
        SET
            library_guessing_game_rounds_completed = 0,
            library_guessing_game_last_played_at = NULL,
            is_completed = 0
        WHERE user_id = ?
          AND activity_id = (
              SELECT activity_id
              FROM activity
              WHERE activity_name = 'library_guessing_game'
              LIMIT 1
          )
    """, (session["user_id"],))

    conn.commit()
    conn.close()

    return 0


def unlock_library_guessing_game_next_activity_for_user():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT activity_id
            FROM activity
            WHERE activity_id = ?
              AND is_active = 1
        """, (LIBRARY_GUESSING_GAME_NEXT_ACTIVITY_ID,))

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
        """, (session["user_id"], LIBRARY_GUESSING_GAME_NEXT_ACTIVITY_ID))

        cursor.execute("""
            UPDATE progress
            SET is_unlocked = 1
            WHERE user_id = ? AND activity_id = ?
        """, (session["user_id"], LIBRARY_GUESSING_GAME_NEXT_ACTIVITY_ID))

        cursor.execute("""
            UPDATE users
            SET current_activity_id = ?
            WHERE user_id = ?
        """, (LIBRARY_GUESSING_GAME_NEXT_ACTIVITY_ID, session["user_id"]))

        conn.commit()
        conn.close()

        return True

    except Exception as e:
        print("Could not unlock next Classroom Guessing Game activity:", repr(e))
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
    rounds_completed = save_library_guessing_game_progress_for_user(rounds_completed)
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
        message = f"{base_message} Would you like to play the last round, or be done with the game for now?"
    else:
        message = f"{base_message} Would you like to play another round, or be done with the game for now?"

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

    allowed_events = {"intro", "restart", "first_prompt", "round_guidance", "child_answer", "no_response"}

    if event_type not in allowed_events:
        return jsonify({"success": False, "error": "Invalid event_type"}), 400

    if event_type in {"intro", "restart"}:
        ensure_library_guessing_game_progress_columns()
        session.pop("library_guessing_game_history", None)
        session.pop("library_guessing_game_state", None)
        history = []

        if event_type == "restart":
            saved_rounds_completed = reset_library_guessing_game_progress_for_user()
        else:
            saved_rounds_completed = get_library_guessing_game_saved_rounds_for_user()

        game_state = get_library_guessing_game_default_state(rounds_completed=saved_rounds_completed)
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
            "Hi, I'm your teacher. Let's play Classroom Guessing Game. In this game, I'm thinking of an object that you can find in a classroom.",
            "Hi, I'm your teacher. I have a classroom guessing game for us. I'm thinking of an object that you can find in a classroom.",
            "Hi, I'm your teacher. Let's try Classroom Guessing Game. I'll think of an object that you can find in a classroom."
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
            print("Classroom Guessing Game intro TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate Teacher intro"
            }), 500

    if event_type == "first_prompt":
        rounds_completed = int(game_state.get("rounds_completed", 0))

        if rounds_completed == 0:
            prompts = [
                "Okay. I thought of an object.",
                "Okay. I have my object in mind.",
                "Okay. I picked one classroom object."
            ]
        elif rounds_completed == 1:
            prompts = [
                "Okay. I thought of a new object.",
                "Okay. I have a different object in mind.",
                "Okay. I picked a new classroom object."
            ]
        else:
            prompts = [
                "Okay. I thought of our last object.",
                "Okay. I have our final object in mind.",
                "Okay. This is our last classroom object."
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
                stage="setup",
                response_mode="none",
                expects_response=False,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type=event_type,
                child_response=child_response,
                next_event="round_guidance",
                pause_before_next_ms=1200
            )

        except Exception as e:
            print("Library Guessing Game first prompt TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate first prompt"
            }), 500

    if event_type == "round_guidance":
        rounds_completed = int(game_state.get("rounds_completed", 0))

        if rounds_completed == 0:
            prompts = [
                "You can try asking me questions to figure out what it is. If you need help, you can ask me for example questions, or ask for a hint. You could ask questions like, is it used for writing, can you carry it, or is it sticky. You can also guess whenever you're ready.",
                "You can ask me questions to figure out what it is. If you want help, ask me for example questions, or ask for a hint. For example, you might ask, is it used for writing, can you carry it, or is it sticky. You can also guess when you're ready."
            ]
        elif rounds_completed == 1:
            prompts = [
                "If you need help thinking of questions, you can ask me for example questions. You can also ask for a hint whenever you need it, or you can just guess what it is.",
                "You can ask your own questions now. If you need help, you can ask me for example questions. You can also ask for a hint whenever you need it, or just make a guess."
            ]
        else:
            prompts = [
                "You can ask me questions whenever you're ready, or ask for a hint whenever you need it.",
                "Whenever you're ready, you can ask me questions, ask for a hint, or make your guess."
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
            print("Library Guessing Game round guidance TTS error:", repr(e))
            return jsonify({
                "success": False,
                "error": "Could not generate round guidance"
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
                    "Okay. Let's do the last round.",
                    "Okay. One more round for today.",
                    "Sure. This will be our last one today."
                ]
            else:
                replay_prompts = [
                    "Okay. Let's keep going.",
                    "Sure. Let's do another one.",
                    "Okay. We'll try a new one."
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
            message = "Okay. We can stop here. Thanks for playing Classroom Guessing Game with me."

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

        message = "That's okay. Would you like to play another round, or be done with the game for now?"

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

    if speaker in {"librarian", "teacher"}:
        voice_id = (
            os.getenv("LIBRARIAN_VOICE_ID")
            or os.getenv("BOOK_GUESSING_VOICE_ID")
            or os.getenv("ELEVENLABS_VOICE_ID", "piI8Kku0DcvcL6TTSeQt")
        )
        voice_settings = {
            "stability": 0.99,
            "similarity_boost": 0.90,
            "style": 0.0,
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

    if speaker not in {"star", "librarian", "teacher"}:
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


@app.route("/api/drawing-game/state", methods=["GET"])
@csrf.exempt
@login_required
def drawing_game_state():
    ensure_drawing_game_progress_columns()

    try:
        activity_id = int(request.args.get("activity_id") or 7)
    except (TypeError, ValueError):
        activity_id = 7

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            COALESCE(drawing_scene_index, 0) AS scene_index,
            COALESCE(drawing_stage_index, 0) AS stage_index,
            COALESCE(drawing_rounds_completed, 0) AS rounds_completed,
            COALESCE(drawing_stages_completed, 0) AS stages_completed,
            COALESCE(drawing_scenes_completed, 0) AS scenes_completed,
            COALESCE(drawing_spoken_responses, 0) AS spoken_responses,
            COALESCE(drawing_silent_windows, 0) AS silent_windows,
            COALESCE(drawing_total_color_selections, 0) AS total_color_selections,
            COALESCE(drawing_canvas_data, '') AS canvas_data,
            COALESCE(is_completed, 0) AS is_completed
        FROM progress
        WHERE user_id = ? AND activity_id = ?
    """, (session["user_id"], activity_id))

    row = cursor.fetchone()
    conn.close()

    if not row:
        state = {
            "scene_index": 0,
            "stage_index": 0,
            "rounds_completed": 0,
            "stages_completed": 0,
            "scenes_completed": 0,
            "spoken_responses": 0,
            "silent_windows": 0,
            "total_color_selections": 0,
            "canvas_data": "",
            "is_completed": 0
        }
    else:
        state = {
            "scene_index": row["scene_index"],
            "stage_index": row["stage_index"],
            "rounds_completed": row["rounds_completed"],
            "stages_completed": row["stages_completed"],
            "scenes_completed": row["scenes_completed"],
            "spoken_responses": row["spoken_responses"],
            "silent_windows": row["silent_windows"],
            "total_color_selections": row["total_color_selections"],
            "canvas_data": row["canvas_data"],
            "is_completed": row["is_completed"]
        }

    return jsonify({"success": True, "state": state})


@app.route("/api/drawing-game/save-progress", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("60 per minute")
def drawing_game_save_progress():
    ensure_drawing_game_progress_columns()

    data = request.get_json(silent=True) or {}

    activity_id = safe_drawing_int(data.get("activity_id"), 7, 9999)
    scene_index = safe_drawing_int(data.get("scene_index"), 0, 3)
    stage_index = safe_drawing_int(data.get("stage_index"), 0, 3)
    rounds_completed = safe_drawing_int(data.get("rounds_completed"), 0, 4)
    stages_completed = safe_drawing_int(data.get("stages_completed"), 0, 16)
    scenes_completed = safe_drawing_int(data.get("scenes_completed"), 0, 4)
    spoken_responses = safe_drawing_int(data.get("spoken_responses"), 0, 9999)
    silent_windows = safe_drawing_int(data.get("silent_windows"), 0, 9999)
    total_color_selections = safe_drawing_int(data.get("total_color_selections"), 0, 9999)
    canvas_data = str(data.get("canvas_data", "") or "")

    if canvas_data and not canvas_data.startswith("data:image/"):
        canvas_data = ""

    # Keep the database from growing without bound if something goes wrong client-side.
    if len(canvas_data) > 2500000:
        canvas_data = ""

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
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
                drawing_scene_index = ?,
                drawing_stage_index = ?,
                drawing_rounds_completed = MAX(COALESCE(drawing_rounds_completed, 0), ?),
                drawing_stages_completed = MAX(COALESCE(drawing_stages_completed, 0), ?),
                drawing_scenes_completed = MAX(COALESCE(drawing_scenes_completed, 0), ?),
                drawing_spoken_responses = MAX(COALESCE(drawing_spoken_responses, 0), ?),
                drawing_silent_windows = MAX(COALESCE(drawing_silent_windows, 0), ?),
                drawing_total_color_selections = MAX(COALESCE(drawing_total_color_selections, 0), ?),
                drawing_canvas_data = ?,
                drawing_last_played_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND activity_id = ?
        """, (
            scene_index,
            stage_index,
            rounds_completed,
            stages_completed,
            scenes_completed,
            spoken_responses,
            silent_windows,
            total_color_selections,
            canvas_data,
            session["user_id"],
            activity_id
        ))

        cursor.execute("""
            UPDATE users
            SET current_activity_id = ?
            WHERE user_id = ?
        """, (activity_id, session["user_id"]))

        conn.commit()
        conn.close()

        return jsonify({"success": True})

    except Exception as e:
        conn.rollback()
        conn.close()
        print("Drawing game save progress error:", repr(e))
        return jsonify({"success": False, "error": "Could not save drawing progress"}), 500


@app.route("/api/drawing-game/complete", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("20 per minute")
def drawing_game_complete():
    ensure_drawing_game_progress_columns()

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
                time_spent_on_activity = COALESCE(time_spent_on_activity, 0) + ?,
                drawing_scene_index = 0,
                drawing_stage_index = 0,
                drawing_rounds_completed = 4,
                drawing_stages_completed = MAX(COALESCE(drawing_stages_completed, 0), 16),
                drawing_scenes_completed = 4,
                drawing_canvas_data = NULL,
                drawing_last_played_at = CURRENT_TIMESTAMP
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
             AND activity_id > ?
            ORDER BY activity_id ASC
            LIMIT 1
        """, (
            activity["activity_id"],
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
             AND activity_id > ?
            ORDER BY activity_id ASC
            LIMIT 1
        """, (
            activity["activity_id"],
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

# =========================

# =========================
# =========================
# Mystery Food Item — Leo restaurant guessing game
# Uses the Mystery Animal / Mystery Classroom Object message flow with a food context.
# Frontend route:
#   /mystery-food-item
# Compatibility alias:
#   /restaurant-worker-game
# API routes:
#   /api/mystery-food-item/thinking-audio
#   /api/mystery-food-item/message
#   /api/mystery-food-item/transcribe
# Progress storage reuses restaurant_* progress columns so the existing restart-activity
# reset path continues to reset this activity.
# =========================

MYSTERY_FOOD_REQUIRED_ROUNDS = 9
MYSTERY_FOOD_MAX_QUESTIONS_PER_ROUND = 8
MYSTERY_FOOD_SOFT_GUESS_LIMIT = 4
MYSTERY_FOOD_MAX_WRONG_GUESSES_PER_ROUND = 2


def ensure_restaurant_game_progress_columns():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(progress)")
    existing_columns = {row["name"] for row in cursor.fetchall()}

    columns_to_add = {
        "restaurant_order_index": "ALTER TABLE progress ADD COLUMN restaurant_order_index INTEGER DEFAULT 0",
        "restaurant_step_index": "ALTER TABLE progress ADD COLUMN restaurant_step_index INTEGER DEFAULT 0",
        "restaurant_orders_completed": "ALTER TABLE progress ADD COLUMN restaurant_orders_completed INTEGER DEFAULT 0",
        "restaurant_steps_completed": "ALTER TABLE progress ADD COLUMN restaurant_steps_completed INTEGER DEFAULT 0",
        "restaurant_spoken_responses": "ALTER TABLE progress ADD COLUMN restaurant_spoken_responses INTEGER DEFAULT 0",
        "restaurant_silent_windows": "ALTER TABLE progress ADD COLUMN restaurant_silent_windows INTEGER DEFAULT 0",
        "restaurant_worker_direct_responses": "ALTER TABLE progress ADD COLUMN restaurant_worker_direct_responses INTEGER DEFAULT 0",
        "restaurant_teacher_redirects": "ALTER TABLE progress ADD COLUMN restaurant_teacher_redirects INTEGER DEFAULT 0",
        "restaurant_total_choices": "ALTER TABLE progress ADD COLUMN restaurant_total_choices INTEGER DEFAULT 0",
        "restaurant_last_pizza_json": "ALTER TABLE progress ADD COLUMN restaurant_last_pizza_json TEXT",
        "restaurant_last_played_at": "ALTER TABLE progress ADD COLUMN restaurant_last_played_at TEXT"
    }

    for column_name, alter_sql in columns_to_add.items():
        if column_name not in existing_columns:
            cursor.execute(alter_sql)

    conn.commit()
    conn.close()


def safe_restaurant_int(value, default=0, max_value=9999):
    try:
        parsed = int(float(value if value is not None else default))
    except (TypeError, ValueError):
        parsed = default

    return max(0, min(max_value, parsed))


def safe_restaurant_float(value, default=0.0):
    try:
        return max(0.0, float(value if value is not None else default))
    except (TypeError, ValueError):
        return default


def sanitize_mystery_food_line(text, fallback="Hmm.", max_len=520):
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


def generate_mystery_food_voice_elevenlabs(text, game_complete=False, thinking=False):
    voice_id = (
        os.getenv("RESTAURANT_WORKER_VOICE_ID")
        or os.getenv("LEO_VOICE_ID")
        or os.getenv("TOY_TRIVIA_VOICE_ID")
        or os.getenv("TOY_WORKER_VOICE_ID")
        or os.getenv("ELEVENLABS_VOICE_ID", "piI8Kku0DcvcL6TTSeQt")
    )

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
            "stability": 0.93,
            "similarity_boost": 0.90,
            "style": 0.08,
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


def mystery_food_profile(display, aliases=(), tags=(), colors=(), hints=()):
    return {
        "display": display,
        "aliases": {display, *aliases},
        "tags": set(tags),
        "colors": set(colors),
        "hints": list(hints)
    }


MYSTERY_FOOD_PROFILES = {
    "pizza": mystery_food_profile(
        "pizza",
        aliases=("cheese pizza", "pepperoni pizza", "slice"),
        tags=("baked", "cheesy", "crust", "dinner", "finger_food", "flat", "hot", "lunch", "meal", "plate", "restaurant", "round", "salty", "savory", "sauce"),
        colors=("orange", "red", "brown", "yellow"),
        hints=("It can have cheese and sauce.", "It is often cut into slices.", "It has a crust.")
    ),
    "burger": mystery_food_profile(
        "burger",
        aliases=("hamburger", "cheeseburger"),
        tags=("bread", "bun", "cheesy", "dinner", "finger_food", "hot", "lunch", "meal", "meat", "plate", "restaurant", "round", "salty", "savory"),
        colors=("red", "brown", "green", "yellow"),
        hints=("It comes in a bun.", "People often eat it with fries.", "It can have cheese or lettuce.")
    ),
    "hot dog": mystery_food_profile(
        "hot dog",
        aliases=("hotdog",),
        tags=("bread", "bun", "dinner", "finger_food", "hot", "long", "lunch", "meal", "meat", "restaurant", "salty", "savory"),
        colors=("red", "brown", "yellow"),
        hints=("It sits in a long bun.", "People might put ketchup or mustard on it.", "It is long, not round.")
    ),
    "sandwich": mystery_food_profile(
        "sandwich",
        aliases=("sub", "hoagie", "turkey sandwich", "ham sandwich"),
        tags=("bread", "cold", "finger_food", "lunch", "meal", "plate", "restaurant", "salty", "savory", "soft"),
        colors=("red", "brown", "green", "yellow", "white"),
        hints=("It has food between pieces of bread.", "People often eat it for lunch.", "It can be cut in half.")
    ),
    "grilled cheese": mystery_food_profile(
        "grilled cheese",
        aliases=("grilled cheese sandwich", "cheese sandwich"),
        tags=("bread", "cheesy", "crispy", "dinner", "finger_food", "hot", "lunch", "meal", "plate", "restaurant", "salty", "savory", "soft"),
        colors=("orange", "brown", "yellow"),
        hints=("It is warm and cheesy.", "The bread can be toasted.", "It goes well with soup.")
    ),
    "pasta": mystery_food_profile(
        "pasta",
        aliases=("spaghetti", "noodles", "macaroni"),
        tags=("bowl", "dinner", "fork", "hot", "lunch", "meal", "plate", "restaurant", "salty", "sauce", "savory", "soft"),
        colors=("orange", "red", "white", "yellow"),
        hints=("People often eat it with a fork.", "It can have sauce.", "It can be noodles.")
    ),
    "mac and cheese": mystery_food_profile(
        "mac and cheese",
        aliases=("macaroni and cheese", "mac n cheese"),
        tags=("bowl", "cheesy", "dinner", "fork", "hot", "lunch", "meal", "plate", "salty", "savory", "soft"),
        colors=("orange", "yellow"),
        hints=("It is cheesy.", "It has small pasta pieces.", "It is usually warm.")
    ),
    "taco": mystery_food_profile(
        "taco",
        aliases=("tacos",),
        tags=("cheesy", "crunchy", "dinner", "finger_food", "hot", "lunch", "meal", "meat", "restaurant", "salty", "savory", "shell"),
        colors=("red", "brown", "green", "yellow"),
        hints=("It can have a shell.", "It may have lettuce, cheese, or meat.", "People hold it in their hands.")
    ),
    "burrito": mystery_food_profile(
        "burrito",
        aliases=("wrap",),
        tags=("beans", "cheesy", "dinner", "finger_food", "hot", "lunch", "meal", "meat", "restaurant", "salty", "savory", "soft", "tortilla"),
        colors=("brown", "white", "green", "yellow"),
        hints=("It is wrapped in a tortilla.", "It can have beans, rice, or meat.", "People hold it in their hands.")
    ),
    "quesadilla": mystery_food_profile(
        "quesadilla",
        aliases=("cheese quesadilla",),
        tags=("cheesy", "dinner", "finger_food", "flat", "hot", "lunch", "meal", "plate", "restaurant", "salty", "savory", "tortilla"),
        colors=("brown", "yellow", "white"),
        hints=("It is flat and cheesy.", "It is made with a tortilla.", "It can be cut into triangles.")
    ),
    "fries": mystery_food_profile(
        "fries",
        aliases=("french fries", "chips"),
        tags=("crispy", "dinner", "finger_food", "hot", "long", "lunch", "potato", "restaurant", "salty", "savory", "side", "snack"),
        colors=("gold", "brown", "yellow"),
        hints=("They are often salty.", "They can be crispy.", "People often eat them with ketchup.")
    ),
    "chicken nuggets": mystery_food_profile(
        "chicken nuggets",
        aliases=("nuggets", "nugget"),
        tags=("crispy", "dinner", "finger_food", "hot", "lunch", "meal", "meat", "plate", "restaurant", "salty", "savory"),
        colors=("gold", "brown", "yellow"),
        hints=("They are small pieces.", "People might dip them in sauce.", "They can be crispy.")
    ),
    "chicken tenders": mystery_food_profile(
        "chicken tenders",
        aliases=("tenders", "chicken fingers"),
        tags=("crispy", "dinner", "finger_food", "hot", "long", "lunch", "meal", "meat", "plate", "restaurant", "salty", "savory"),
        colors=("gold", "brown", "yellow"),
        hints=("They are longer pieces of chicken.", "People might dip them in sauce.", "They can be crispy.")
    ),
    "salad": mystery_food_profile(
        "salad",
        aliases=("garden salad", "caesar salad"),
        tags=("bowl", "cold", "crunchy", "dinner", "fork", "healthy", "lunch", "meal", "plate", "restaurant", "savory", "side", "vegetable"),
        colors=("orange", "red", "white", "green"),
        hints=("It can have lettuce.", "It is usually cold.", "It can be crunchy and green.")
    ),
    "soup": mystery_food_profile(
        "soup",
        aliases=("chicken soup", "tomato soup"),
        tags=("spoon", "soft", "meal", "bowl", "savory", "restaurant", "hot", "liquid", "lunch", "side", "dinner"),
        colors=("orange", "white", "brown", "green", "red"),
        hints=("It comes in a bowl.", "People usually eat it with a spoon.", "It is often warm.")
    ),
    "ramen": mystery_food_profile(
        "ramen",
        aliases=("ramen noodles", "noodle soup"),
        tags=("bowl", "dinner", "hot", "liquid", "lunch", "meal", "noodles", "restaurant", "savory", "spoon", "soft"),
        colors=("brown", "yellow", "green"),
        hints=("It has noodles in broth.", "It comes in a bowl.", "It is usually hot.")
    ),
    "sushi": mystery_food_profile(
        "sushi",
        aliases=("sushi roll",),
        tags=("cold", "dinner", "finger_food", "lunch", "meal", "rice", "restaurant", "savory", "seafood", "small"),
        colors=("white", "green", "orange", "black"),
        hints=("It can be in small rolls.", "It often has rice.", "It can come with soy sauce.")
    ),
    "rice": mystery_food_profile(
        "rice",
        aliases=("white rice", "fried rice"),
        tags=("bowl", "dinner", "fork", "hot", "lunch", "meal", "restaurant", "savory", "side", "soft", "spoon"),
        colors=("white", "brown", "yellow"),
        hints=("It has many small grains.", "It often comes in a bowl.", "It can be a side.")
    ),
    "pancakes": mystery_food_profile(
        "pancakes",
        aliases=("pancake",),
        tags=("breakfast", "sweet", "soft", "round", "plate", "restaurant", "hot", "flat", "fork", "syrup"),
        colors=("brown", "tan", "yellow"),
        hints=("People often eat it for breakfast.", "It can have syrup.", "It is round and flat.")
    ),
    "waffles": mystery_food_profile(
        "waffles",
        aliases=("waffle",),
        tags=("breakfast", "crispy", "fork", "hot", "plate", "restaurant", "sweet", "syrup"),
        colors=("brown", "tan", "yellow"),
        hints=("It has little square spaces.", "People often eat it with syrup.", "It can be crispy outside.")
    ),
    "cereal": mystery_food_profile(
        "cereal",
        aliases=("breakfast cereal",),
        tags=("breakfast", "sweet", "milk", "spoon", "crunchy", "cold", "bowl"),
        colors=("colorful", "brown", "white", "yellow"),
        hints=("It usually goes in a bowl.", "People often add milk.", "It can be crunchy.")
    ),
    "oatmeal": mystery_food_profile(
        "oatmeal",
        aliases=("porridge",),
        tags=("breakfast", "bowl", "hot", "soft", "spoon", "sweet"),
        colors=("brown", "tan", "white"),
        hints=("People often eat it for breakfast.", "It is warm and soft.", "It comes in a bowl.")
    ),
    "eggs": mystery_food_profile(
        "eggs",
        aliases=("egg", "scrambled eggs"),
        tags=("breakfast", "fork", "hot", "meal", "plate", "savory", "soft"),
        colors=("white", "yellow"),
        hints=("People often eat them for breakfast.", "They can be scrambled.", "They are yellow and white.")
    ),
    "bagel": mystery_food_profile(
        "bagel",
        aliases=("bagel with cream cheese",),
        tags=("baked", "bread", "breakfast", "finger_food", "round", "snack"),
        colors=("brown", "tan", "white"),
        hints=("It is round with a hole.", "People often eat it for breakfast.", "It can have cream cheese.")
    ),
    "toast": mystery_food_profile(
        "toast",
        aliases=("bread", "toasted bread"),
        tags=("bread", "breakfast", "crispy", "finger_food", "flat", "hot", "plate"),
        colors=("brown", "tan", "yellow"),
        hints=("It is toasted bread.", "People eat it for breakfast.", "It can have butter or jam.")
    ),
    "apple": mystery_food_profile(
        "apple",
        aliases=("apples",),
        tags=("cold", "crunchy", "finger_food", "fruit", "healthy", "plate", "round", "snack", "sweet"),
        colors=("red", "green", "yellow"),
        hints=("It is a fruit.", "It can be red or green.", "It makes a crunch when you bite it.")
    ),
    "banana": mystery_food_profile(
        "banana",
        aliases=("bananas",),
        tags=("breakfast", "cold", "finger_food", "fruit", "healthy", "long", "snack", "soft", "sweet"),
        colors=("brown", "yellow"),
        hints=("It is a fruit.", "It is usually yellow.", "You peel it before eating.")
    ),
    "strawberries": mystery_food_profile(
        "strawberries",
        aliases=("strawberry",),
        tags=("cold", "finger_food", "fruit", "healthy", "plate", "snack", "soft", "sweet"),
        colors=("red", "green"),
        hints=("They are small red fruits.", "They can go on desserts.", "They have tiny seeds on the outside.")
    ),
    "grapes": mystery_food_profile(
        "grapes",
        aliases=("grape",),
        tags=("cold", "finger_food", "fruit", "healthy", "round", "snack", "sweet"),
        colors=("green", "purple", "red"),
        hints=("They are small round fruits.", "They come in bunches.", "They can be green or purple.")
    ),
    "watermelon": mystery_food_profile(
        "watermelon",
        aliases=("melon",),
        tags=("cold", "finger_food", "fruit", "healthy", "snack", "sweet"),
        colors=("green", "red", "pink"),
        hints=("It is juicy.", "It is green outside and red or pink inside.", "People often eat slices of it.")
    ),
    "orange": mystery_food_profile(
        "orange",
        aliases=("oranges",),
        tags=("cold", "finger_food", "fruit", "healthy", "round", "snack", "sweet"),
        colors=("orange",),
        hints=("It is a fruit.", "It is orange.", "You peel it before eating.")
    ),
    "ice cream": mystery_food_profile(
        "ice cream",
        aliases=("sundae",),
        tags=("bowl", "cold", "creamy", "dessert", "restaurant", "soft", "spoon", "sweet"),
        colors=("brown", "white", "pink", "yellow"),
        hints=("It is cold.", "It can melt.", "People often eat it for dessert.")
    ),
    "cake": mystery_food_profile(
        "cake",
        aliases=("birthday cake",),
        tags=("baked", "dessert", "fork", "frosting", "party", "plate", "soft", "sweet"),
        colors=("colorful", "brown", "white", "pink", "yellow"),
        hints=("People eat it at birthdays.", "It can have frosting.", "It is usually soft.")
    ),
    "cookies": mystery_food_profile(
        "cookies",
        aliases=("cookie", "chocolate chip cookie", "chocolate chip cookies"),
        tags=("baked", "crispy", "dessert", "finger_food", "plate", "round", "snack", "soft", "sweet"),
        colors=("black", "brown", "tan"),
        hints=("They are baked.", "They can have chocolate chips.", "People can hold them in their hands.")
    ),
    "cupcake": mystery_food_profile(
        "cupcake",
        aliases=("cupcakes",),
        tags=("baked", "dessert", "finger_food", "frosting", "party", "plate", "snack", "soft", "sweet"),
        colors=("colorful", "brown", "white", "pink", "yellow"),
        hints=("It is like a tiny cake.", "It can have frosting.", "People often eat it as a treat.")
    ),
    "donut": mystery_food_profile(
        "donut",
        aliases=("doughnut", "donuts", "doughnuts"),
        tags=("breakfast", "dessert", "finger_food", "plate", "restaurant", "round", "snack", "soft", "sweet"),
        colors=("white", "brown", "pink", "yellow"),
        hints=("It is often round.", "It can have a hole in the middle.", "It can have icing.")
    ),
    "brownie": mystery_food_profile(
        "brownie",
        aliases=("brownies",),
        tags=("baked", "chocolate", "dessert", "finger_food", "plate", "soft", "sweet"),
        colors=("brown", "black"),
        hints=("It is chocolatey.", "It is usually a square.", "It is a dessert.")
    ),
    "popcorn": mystery_food_profile(
        "popcorn",
        aliases=(),
        tags=("bowl", "crunchy", "finger_food", "salty", "snack"),
        colors=("white", "yellow"),
        hints=("It comes in little pieces.", "People eat it at movies.", "It can be salty or buttery.")
    ),
    "chips": mystery_food_profile(
        "chips",
        aliases=("potato chips", "chip"),
        tags=("crunchy", "crispy", "finger_food", "potato", "salty", "snack"),
        colors=("yellow", "gold", "brown"),
        hints=("They are crunchy.", "They can be salty.", "They come in a bag.")
    ),
    "pretzels": mystery_food_profile(
        "pretzels",
        aliases=("pretzel",),
        tags=("baked", "crunchy", "finger_food", "salty", "snack"),
        colors=("brown", "tan"),
        hints=("They can be twisted shapes.", "They are often salty.", "People eat them as a snack.")
    ),
    "yogurt": mystery_food_profile(
        "yogurt",
        aliases=("yoghurt",),
        tags=("bowl", "breakfast", "cold", "creamy", "healthy", "snack", "soft", "spoon", "sweet"),
        colors=("white", "pink", "purple"),
        hints=("It is creamy.", "People eat it with a spoon.", "It is usually cold.")
    ),
    "lemonade": mystery_food_profile(
        "lemonade",
        aliases=("lemon aid",),
        tags=("cold", "cup", "drink", "liquid", "restaurant", "sour", "straw", "sweet"),
        colors=("yellow",),
        hints=("It is a drink.", "It tastes lemony.", "It is often yellow.")
    ),
    "milkshake": mystery_food_profile(
        "milkshake",
        aliases=("shake",),
        tags=("cold", "creamy", "cup", "dessert", "drink", "liquid", "restaurant", "straw", "sweet"),
        colors=("brown", "white", "pink"),
        hints=("It is cold and creamy.", "People drink it with a straw.", "It can be chocolate, vanilla, or strawberry.")
    ),
    "smoothie": mystery_food_profile(
        "smoothie",
        aliases=(),
        tags=("cold", "creamy", "cup", "drink", "fruit", "healthy", "liquid", "snack", "straw", "sweet"),
        colors=("orange", "green", "purple", "pink", "yellow"),
        hints=("It is a cold drink.", "It can be made with fruit.", "People drink it with a straw.")
    ),
    "water": mystery_food_profile(
        "water",
        aliases=("ice water",),
        tags=("cold", "cup", "drink", "liquid", "restaurant"),
        colors=("clear", "white"),
        hints=("It is a drink.", "It is clear.", "People drink it when they are thirsty.")
    ),
    "juice": mystery_food_profile(
        "juice",
        aliases=("apple juice", "orange juice"),
        tags=("breakfast", "cold", "cup", "drink", "fruit", "liquid", "straw", "sweet"),
        colors=("orange", "yellow", "red"),
        hints=("It is a drink.", "It can be made from fruit.", "People drink it from a cup.")
    ),
    "soda": mystery_food_profile(
        "soda",
        aliases=("pop", "soft drink", "coke", "sprite"),
        tags=("cold", "cup", "drink", "liquid", "restaurant", "straw", "sweet"),
        colors=("brown", "clear", "orange"),
        hints=("It is a fizzy drink.", "People drink it cold.", "It often comes in a cup or can.")
    ),
    "milk": mystery_food_profile(
        "milk",
        aliases=("chocolate milk",),
        tags=("breakfast", "cold", "cup", "drink", "liquid", "milk", "sweet"),
        colors=("white", "brown"),
        hints=("It is a drink.", "It can go with cereal.", "It is usually white.")
    )
}


MYSTERY_FOOD_QUESTION_BANK = [
    # Rounds 1-3: forced-choice only. These are intentionally answerable with one word.
    {
        "key": "warm_cold_room",
        "question": "Would Leo serve it hot, cold, or room temperature?",
        "stage": "guided_choice",
        "response_mode": "choice",
        "option_tags": {
            "hot": {"hot"},
            "warm": {"hot"},
            "cold": {"cold"},
            "chilled": {"cold"},
            "room temperature": set(),
            "room": set(),
            "both": {"hot", "cold"},
            "sometimes": set()
        }
    },
    {
        "key": "breakfast_lunch_dinner_dessert",
        "question": "Would someone usually have it for breakfast, lunch, dinner, dessert, or a snack?",
        "stage": "guided_choice",
        "response_mode": "choice",
        "option_tags": {
            "breakfast": {"breakfast"},
            "morning": {"breakfast"},
            "lunch": {"lunch", "meal"},
            "dinner": {"dinner", "meal"},
            "dessert": {"dessert", "sweet"},
            "snack": {"snack"},
            "anytime": set(),
            "any": set()
        }
    },
    {
        "key": "plate_bowl_cup",
        "question": "Would Leo bring it on a plate, in a bowl, or in a cup?",
        "stage": "guided_choice",
        "response_mode": "choice",
        "option_tags": {
            "plate": {"plate"},
            "bowl": {"bowl"},
            "cup": {"cup", "drink", "liquid"},
            "glass": {"cup", "drink", "liquid"},
            "bag": {"snack", "finger_food"}
        }
    },
    {
        "key": "hands_fork_spoon_straw",
        "question": "Would someone use their hands, a fork, a spoon, or a straw?",
        "stage": "guided_choice",
        "response_mode": "choice",
        "option_tags": {
            "hands": {"finger_food"},
            "hand": {"finger_food"},
            "fork": {"fork", "plate"},
            "spoon": {"spoon", "bowl"},
            "straw": {"straw", "drink", "cup"},
            "both": set()
        }
    },
    {
        "key": "sweet_salty_savory",
        "question": "Would it taste sweet, salty, savory, sour, or more plain?",
        "stage": "guided_choice",
        "response_mode": "choice",
        "option_tags": {
            "sweet": {"sweet"},
            "salty": {"salty", "savory"},
            "savory": {"savory"},
            "sour": {"sour"},
            "plain": set(),
            "both": set()
        }
    },
    {
        "key": "eat_drink_dip",
        "question": "Would someone eat it, drink it, or dip something into it?",
        "stage": "guided_choice",
        "response_mode": "choice",
        "option_tags": {
            "eat": {"meal", "snack"},
            "chew": {"meal", "snack"},
            "drink": {"drink", "liquid", "cup"},
            "sip": {"drink", "liquid", "cup"},
            "dip": {"sauce", "side"}
        },
        "option_remove_tags": {
            "drink": {"finger_food", "fork", "spoon"},
            "sip": {"finger_food", "fork", "spoon"}
        }
    },
    {
        "key": "texture_choice",
        "question": "Which word fits best: soft, crunchy, crispy, creamy, or juicy?",
        "stage": "guided_choice",
        "response_mode": "choice",
        "option_tags": {
            "soft": {"soft"},
            "crunchy": {"crunchy", "crispy"},
            "crispy": {"crispy", "crunchy"},
            "creamy": {"creamy", "soft"},
            "juicy": {"fruit", "drink", "liquid"},
            "both": set(),
            "sometimes": set()
        }
    },
    {
        "key": "main_clue_choice",
        "question": "Which clue fits better: bread, cheese, fruit, meat, potato, or none of those?",
        "stage": "guided_choice",
        "response_mode": "choice",
        "option_tags": {
            "bread": {"bread"},
            "bun": {"bun", "bread"},
            "cheese": {"cheesy"},
            "fruit": {"fruit", "sweet"},
            "meat": {"meat", "savory"},
            "potato": {"potato"},
            "none": set(),
            "neither": set()
        }
    },

    # Rounds 4-6: easy short-answer clues. Still concrete, but less forced.
    {
        "key": "time_of_day",
        "question": "What time of day would someone usually eat or drink it?",
        "stage": "easy_short_answer",
        "response_mode": "short_phrase",
        "option_tags": {
            "morning": {"breakfast"},
            "breakfast": {"breakfast"},
            "afternoon": {"lunch", "snack"},
            "lunch": {"lunch", "meal"},
            "night": {"dinner"},
            "dinner": {"dinner", "meal"},
            "dessert": {"dessert", "sweet"},
            "anytime": set()
        }
    },
    {
        "key": "meal_part",
        "question": "What part of the meal is it: main food, side, snack, dessert, or drink?",
        "stage": "easy_short_answer",
        "response_mode": "short_phrase",
        "option_tags": {
            "main": {"meal"},
            "meal": {"meal"},
            "side": {"side"},
            "snack": {"snack"},
            "dessert": {"dessert", "sweet"},
            "drink": {"drink", "liquid", "cup"}
        }
    },
    {
        "key": "temperature_detail",
        "question": "How hot or cold is it when someone eats or drinks it?",
        "stage": "easy_short_answer",
        "response_mode": "short_phrase",
        "option_tags": {
            "hot": {"hot"},
            "warm": {"hot"},
            "cold": {"cold"},
            "chilled": {"cold"},
            "frozen": {"cold"},
            "room": set()
        }
    },
    {
        "key": "color_one",
        "question": "What color should Leo picture first?",
        "stage": "easy_short_answer",
        "response_mode": "one_word",
        "option_tags": {
            "red": {"red"},
            "green": {"green"},
            "yellow": {"yellow", "gold"},
            "gold": {"gold", "yellow"},
            "orange": {"orange"},
            "brown": {"brown"},
            "white": {"white"},
            "pink": {"pink"},
            "purple": {"purple"},
            "clear": {"clear"},
            "colorful": {"colorful"},
            "black": {"black"},
            "tan": {"tan", "brown"}
        }
    },
    {
        "key": "shape_one",
        "question": "What shape is it closest to: round, long, flat, square, or something else?",
        "stage": "easy_short_answer",
        "response_mode": "short_phrase",
        "option_tags": {
            "round": {"round"},
            "circle": {"round"},
            "long": {"long"},
            "flat": {"flat"},
            "slice": {"flat", "plate"},
            "square": set(),
            "triangle": set(),
            "something else": set(),
            "else": set()
        }
    },
    {
        "key": "main_part",
        "question": "What is one main part of it, like bread, cheese, fruit, sauce, meat, or something else?",
        "stage": "easy_short_answer",
        "response_mode": "short_phrase",
        "option_tags": {
            "bread": {"bread"},
            "bun": {"bun", "bread"},
            "cheese": {"cheesy"},
            "fruit": {"fruit", "sweet"},
            "sauce": {"sauce"},
            "meat": {"meat"},
            "milk": {"milk"},
            "potato": {"potato"},
            "lettuce": {"vegetable", "green"},
            "ice": {"cold"},
            "chocolate": {"chocolate", "sweet"}
        }
    },
    {
        "key": "top_or_dip",
        "question": "What might someone put on top of it or dip it in?",
        "stage": "easy_short_answer",
        "response_mode": "short_phrase",
        "option_tags": {
            "cheese": {"cheesy"},
            "sauce": {"sauce"},
            "ketchup": {"sauce", "salty"},
            "mustard": {"sauce"},
            "syrup": {"syrup", "sweet"},
            "frosting": {"frosting", "dessert", "sweet"},
            "milk": {"milk", "breakfast"},
            "butter": {"bread", "breakfast"},
            "nothing": set()
        }
    },

    # Rounds 7-9: open clue questions.
    {
        "key": "give_clue",
        "question": "Can you give Leo one clue about it?",
        "stage": "open_hint",
        "response_mode": "open_hint",
        "option_tags": {}
    },
    {
        "key": "restaurant_clue",
        "question": "If Leo saw it in the restaurant, what clue would help him find it?",
        "stage": "open_hint",
        "response_mode": "open_hint",
        "option_tags": {}
    },
    {
        "key": "customer_order",
        "question": "What would a customer say when ordering this food?",
        "stage": "open_hint",
        "response_mode": "open_hint",
        "option_tags": {}
    },
    {
        "key": "describe_without_name",
        "question": "Can you describe it without saying the food’s name?",
        "stage": "open_hint",
        "response_mode": "open_hint",
        "option_tags": {}
    },
    {
        "key": "eating_clue",
        "question": "Give Leo one clue about how someone eats or drinks it.",
        "stage": "open_hint",
        "response_mode": "open_hint",
        "option_tags": {}
    },
    {
        "key": "goes_with_it",
        "question": "What food or drink would go well with it?",
        "stage": "open_hint",
        "response_mode": "open_hint",
        "option_tags": {
            "fries": {"salty", "side"},
            "ketchup": {"sauce", "finger_food"},
            "milk": {"milk"},
            "water": {"drink"},
            "soup": {"bowl", "hot"},
            "salad": {"vegetable", "side"},
            "syrup": {"sweet", "syrup"}
        }
    }
]


MYSTERY_FOOD_FREEFORM_TAGS = {
    "hot": {"hot"},
    "warm": {"hot"},
    "cold": {"cold"},
    "frozen": {"cold"},
    "chilly": {"cold"},
    "breakfast": {"breakfast"},
    "morning": {"breakfast"},
    "lunch": {"lunch", "meal"},
    "dinner": {"dinner", "meal"},
    "dessert": {"dessert", "sweet"},
    "snack": {"snack"},
    "drink": {"drink", "liquid", "cup"},
    "straw": {"straw", "drink", "cup"},
    "cup": {"cup", "drink"},
    "bowl": {"bowl"},
    "plate": {"plate"},
    "fork": {"fork", "plate"},
    "spoon": {"spoon", "bowl"},
    "hands": {"finger_food"},
    "hand": {"finger_food"},
    "sweet": {"sweet"},
    "salty": {"salty"},
    "savory": {"savory"},
    "sour": {"sour"},
    "soft": {"soft"},
    "crunchy": {"crunchy"},
    "crispy": {"crispy"},
    "creamy": {"creamy"},
    "juicy": {"fruit", "liquid"},
    "bread": {"bread"},
    "bun": {"bun", "bread"},
    "cheese": {"cheesy"},
    "cheesy": {"cheesy"},
    "fruit": {"fruit", "sweet"},
    "meat": {"meat", "savory"},
    "chicken": {"meat", "savory"},
    "potato": {"potato"},
    "sauce": {"sauce"},
    "ketchup": {"sauce"},
    "syrup": {"syrup", "sweet"},
    "frosting": {"frosting", "dessert", "sweet"},
    "milk": {"milk"},
    "chocolate": {"chocolate", "sweet"},
    "lettuce": {"vegetable", "green"},
    "vegetable": {"vegetable"},
    "rice": {"rice"},
    "noodles": {"noodles", "soft"},
    "noodle": {"noodles", "soft"},
    "red": {"red"},
    "green": {"green"},
    "yellow": {"yellow"},
    "gold": {"gold", "yellow"},
    "orange": {"orange"},
    "brown": {"brown"},
    "white": {"white"},
    "pink": {"pink"},
    "purple": {"purple"},
    "clear": {"clear"},
    "black": {"black"},
    "tan": {"tan", "brown"},
    "colorful": {"colorful"},
    "round": {"round"},
    "circle": {"round"},
    "long": {"long"},
    "flat": {"flat"},
    "slice": {"flat"}
}


def normalize_mystery_food_text(text):
    text = re.sub(r"\s+", " ", str(text or "")).strip().lower()
    text = text.replace("’", "'")
    text = re.sub(r"[^a-z0-9' -]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def mystery_food_words(text):
    return set(re.findall(r"[a-z']+", normalize_mystery_food_text(text)))


def clean_mystery_food_child_name(child_name):
    name = re.sub(r"[^A-Za-z' -]", "", str(child_name or "")).strip()
    name = re.sub(r"\s+", " ", name)
    if not name or name.lower() in {"none", "child"}:
        return ""
    return name[:28]


def get_mystery_food_default_state(rounds_completed=0):
    try:
        rounds_completed_int = max(0, int(float(rounds_completed or 0)))
    except (TypeError, ValueError):
        rounds_completed_int = 0

    return {
        "stage": "intro",
        "rounds_completed": rounds_completed_int,
        "questions_asked": 0,
        "comfortable_answer_count": 0,
        "unclear_or_silent_count": 0,
        "comfortable_streak": 0,
        "unclear_streak": 0,
        "question_history": [],
        "known_clues": [],
        "clue_tags": [],
        "negative_tags": [],
        "answers_by_key": {},
        "rejected_guesses": [],
        "possible_guess": None,
        "last_question": None,
        "last_question_key": None,
        "last_response_mode": "none",
        "game_complete": False,
        "skip_guess_once": False,
        "guess_cooldown_questions": 0,
        "guesses_made": 0,
        "recent_guesses": [],
        "recent_acknowledgments": [],
        "candidate_keys": list(MYSTERY_FOOD_PROFILES.keys()),
        "candidate_filter_notes": [],
        "void_question_keys": []
    }


def ensure_mystery_food_progress_columns():
    # Reuse the restaurant progress schema from earlier versions.
    ensure_restaurant_game_progress_columns()


def get_mystery_food_activity(cursor):
    cursor.execute("""
        SELECT activity_id, scene_id, activity_order
        FROM activity
        WHERE is_active = 1
          AND activity_name IN (
            'mystery_food_item',
            'mystery_food_item_game',
            'restaurant_worker_game',
            'restaurant_game'
          )
        ORDER BY CASE activity_name
            WHEN 'mystery_food_item' THEN 1
            WHEN 'mystery_food_item_game' THEN 2
            WHEN 'restaurant_worker_game' THEN 3
            ELSE 4
        END
        LIMIT 1
    """)
    return cursor.fetchone()


def get_saved_mystery_food_rounds():
    ensure_mystery_food_progress_columns()

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        activity = get_mystery_food_activity(cursor)

        if not activity:
            conn.close()
            return 0

        cursor.execute("""
            SELECT COALESCE(restaurant_orders_completed, 0) AS rounds_completed
            FROM progress
            WHERE user_id = ? AND activity_id = ?
        """, (session["user_id"], activity["activity_id"]))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return 0

        return max(0, int(row["rounds_completed"] or 0))

    except Exception as e:
        print("Could not load Mystery Food Item progress:", repr(e))
        return 0


def save_mystery_food_round_progress(rounds_completed):
    ensure_mystery_food_progress_columns()

    try:
        rounds_completed = max(0, int(rounds_completed or 0))
        conn = get_db_connection()
        cursor = conn.cursor()
        activity = get_mystery_food_activity(cursor)

        if not activity:
            conn.close()
            return None

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
        """, (session["user_id"], activity["activity_id"]))

        cursor.execute("""
            UPDATE progress
            SET
                restaurant_orders_completed = MAX(COALESCE(restaurant_orders_completed, 0), ?),
                restaurant_steps_completed = MAX(COALESCE(restaurant_steps_completed, 0), ?),
                restaurant_order_index = MIN(?, ?),
                restaurant_step_index = 0,
                restaurant_last_played_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND activity_id = ?
        """, (
            rounds_completed,
            rounds_completed,
            rounds_completed,
            MYSTERY_FOOD_REQUIRED_ROUNDS - 1,
            session["user_id"],
            activity["activity_id"]
        ))

        conn.commit()
        conn.close()
        return activity["activity_id"]

    except Exception as e:
        print("Could not save Mystery Food Item progress:", repr(e))
        return None


def reset_mystery_food_progress_for_user():
    ensure_mystery_food_progress_columns()

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        activity = get_mystery_food_activity(cursor)
        if not activity:
            conn.close()
            return None

        cursor.execute("""
            UPDATE progress
            SET
                restaurant_order_index = 0,
                restaurant_step_index = 0,
                restaurant_orders_completed = 0,
                restaurant_steps_completed = 0,
                restaurant_last_pizza_json = NULL,
                restaurant_last_played_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND activity_id = ?
        """, (session["user_id"], activity["activity_id"]))

        conn.commit()
        conn.close()
        return activity["activity_id"]
    except Exception as e:
        print("Could not reset Mystery Food Item progress:", repr(e))
        return None


def complete_mystery_food_and_unlock_next_for_user(rounds_completed=None):
    ensure_mystery_food_progress_columns()

    try:
        completed_rounds = max(0, int(rounds_completed or MYSTERY_FOOD_REQUIRED_ROUNDS))
        conn = get_db_connection()
        cursor = conn.cursor()
        current_activity = get_mystery_food_activity(cursor)

        if not current_activity:
            conn.close()
            return None

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
        """, (session["user_id"], current_activity["activity_id"]))

        cursor.execute("""
            UPDATE progress
            SET
                is_completed = 1,
                restaurant_orders_completed = MAX(COALESCE(restaurant_orders_completed, 0), ?),
                restaurant_steps_completed = MAX(COALESCE(restaurant_steps_completed, 0), ?),
                restaurant_last_played_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND activity_id = ?
        """, (
            max(completed_rounds, MYSTERY_FOOD_REQUIRED_ROUNDS),
            max(completed_rounds, MYSTERY_FOOD_REQUIRED_ROUNDS),
            session["user_id"],
            current_activity["activity_id"]
        ))

        cursor.execute("""
            SELECT activity_id
            FROM activity
            WHERE is_active = 1
            AND activity_id > ?
            ORDER BY activity_id ASC
            LIMIT 1
        """, (
            current_activity["activity_id"],
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
        print("Could not complete Mystery Food Item and unlock next activity:", repr(e))
        return None


def should_mystery_food_ask_round_choice(rounds_completed):
    completed = int(rounds_completed or 0)
    if completed >= MYSTERY_FOOD_REQUIRED_ROUNDS:
        return True
    return completed > 0 and completed % 2 == 0


def is_mystery_food_final_round_choice(rounds_completed):
    return int(rounds_completed or 0) >= MYSTERY_FOOD_REQUIRED_ROUNDS


def is_mystery_food_unclear_or_silent(text):
    lowered = normalize_mystery_food_text(text)
    if not lowered:
        return True

    unclear_phrases = {
        "i don't know", "i dont know", "i do not know", "don't know", "dont know",
        "idk", "not sure", "i'm not sure", "im not sure", "maybe", "hmm", "hm",
        "mm", "mmm", "uh", "um", "wait", "hold on"
    }

    if lowered in unclear_phrases:
        return True

    words = re.findall(r"[a-z']+", lowered)
    filler_words = {"hmm", "hm", "mm", "mmm", "uh", "um", "like", "wait"}
    return bool(words) and all(word in filler_words for word in words)


def mystery_food_confirms_guess(text, guessed_food):
    lowered = normalize_mystery_food_text(text)
    guessed_clean = normalize_mystery_food_text(guessed_food)
    if guessed_clean and guessed_clean in lowered:
        return True

    profile = None
    for item in MYSTERY_FOOD_PROFILES.values():
        if normalize_mystery_food_text(item.get("display")) == guessed_clean:
            profile = item
            break

    if profile:
        for alias in profile.get("aliases", set()):
            alias_clean = normalize_mystery_food_text(alias)
            if alias_clean and alias_clean in lowered:
                return True

    # The game never asks for this wording, but accepting it keeps accidental replies from breaking the flow.
    words = mystery_food_words(lowered)
    return bool(words & {"correct", "right", "yep", "yeah", "yes", "sure"})


def mystery_food_rejects_guess(text, guessed_food):
    lowered = normalize_mystery_food_text(text)
    guessed_clean = normalize_mystery_food_text(guessed_food)
    words = mystery_food_words(lowered)

    if words & {"wrong", "missed", "close"}:
        return True

    if guessed_clean and any(phrase in lowered for phrase in [f"not {guessed_clean}", f"not a {guessed_clean}", f"not the {guessed_clean}"]):
        return True

    return bool(words & {"no", "nope", "nah"})


def is_clear_mystery_food_response(text, response_mode):
    if is_mystery_food_unclear_or_silent(text):
        return False

    return len(re.findall(r"[A-Za-z']+", str(text or ""))) >= 1


def get_mystery_food_named_food(text):
    lowered = normalize_mystery_food_text(text)
    words = mystery_food_words(lowered)

    for food_key, profile in MYSTERY_FOOD_PROFILES.items():
        for alias in profile.get("aliases", set()):
            alias_clean = normalize_mystery_food_text(alias)
            alias_words = mystery_food_words(alias_clean)

            if not alias_clean:
                continue

            if " " in alias_clean and alias_clean in lowered:
                return profile["display"]

            if alias_clean in words:
                return profile["display"]

            if alias_words and alias_words.issubset(words):
                return profile["display"]

    return None


def parse_child_told_mystery_food(text, allow_short_direct_name=False):
    lowered = normalize_mystery_food_text(text)
    if not lowered:
        return None

    reveal_phrases = [
        "it's", "it is", "my food is", "the food is", "my thing is", "the thing is",
        "i picked", "i chose", "i was thinking of", "i am thinking of", "i'm thinking of",
        "it was", "it's a", "it is a"
    ]

    named = get_mystery_food_named_food(lowered)
    if not named:
        return None

    if any(phrase in lowered for phrase in reveal_phrases):
        return named

    if allow_short_direct_name and len(mystery_food_words(lowered)) <= 4:
        return named

    return None


def classify_mystery_food_round_choice(text):
    lowered = normalize_mystery_food_text(text)
    words = mystery_food_words(lowered)

    if not lowered:
        return "unclear"

    end_phrases = {
        "end here", "end it here", "end for now", "end here for now", "stop here", "stop for now",
        "done here", "done for now", "finish here", "finish for now", "go back", "go to dashboard",
        "back to dashboard", "dashboard", "leave", "quit", "i want to stop", "i want to end", "we can stop"
    }
    same_game_phrases = {
        "another food", "one more", "play again", "keep going", "continue", "another one", "new food", "more food",
        "same game", "again", "yes another", "yes more", "i want another"
    }

    if any(phrase in lowered for phrase in end_phrases):
        return "end"

    if any(phrase in lowered for phrase in same_game_phrases):
        return "same_game"

    stop_words = {"stop", "done", "finish", "finished", "end", "quit", "leave", "dashboard", "break", "pause", "rest"}
    same_game_words = {"again", "same", "replay", "more", "continue", "keep", "another"}

    if words & stop_words:
        return "end"
    if words & same_game_words:
        return "same_game"

    named_food = get_mystery_food_named_food(lowered)
    if named_food:
        return "same_game"

    return "unclear"


def add_mystery_food_clue(state, clue_text, clue_tags=None, negative_tags=None):
    clue_text = sanitize_mystery_food_line(clue_text, fallback="", max_len=180)
    if clue_text:
        known = state.setdefault("known_clues", [])
        if clue_text not in known:
            known.append(clue_text)
        state["known_clues"] = known[-18:]

    if clue_tags:
        existing = set(state.get("clue_tags", []))
        existing.update(str(tag) for tag in clue_tags if tag)
        state["clue_tags"] = sorted(existing)

    if negative_tags:
        existing_negative = set(state.get("negative_tags", []))
        existing_negative.update(str(tag) for tag in negative_tags if tag)
        state["negative_tags"] = sorted(existing_negative)


def apply_mystery_food_candidate_filter(state, keep_tags=None, remove_tags=None, note=""):
    candidates = state.get("candidate_keys") or list(MYSTERY_FOOD_PROFILES.keys())
    keep_tags = set(keep_tags or set())
    remove_tags = set(remove_tags or set())

    filtered = []
    for key in candidates:
        profile = MYSTERY_FOOD_PROFILES.get(key, {})
        profile_tags = set(profile.get("tags", set())) | set(profile.get("colors", set()))
        if keep_tags and not (profile_tags & keep_tags):
            continue
        if remove_tags and (profile_tags & remove_tags):
            continue
        filtered.append(key)

    # Avoid over-filtering if the child gives an answer that could map imperfectly.
    if filtered and len(filtered) >= 2:
        state["candidate_keys"] = filtered
        if note:
            notes = state.setdefault("candidate_filter_notes", [])
            notes.append(note[:80])
            state["candidate_filter_notes"] = notes[-10:]


def extract_mystery_food_option_tags(text, option_tags):
    lowered = normalize_mystery_food_text(text)
    words = mystery_food_words(lowered)

    sorted_options = sorted(
        (option_tags or {}).items(),
        key=lambda item: len(normalize_mystery_food_text(item[0])),
        reverse=True
    )

    for option, tags in sorted_options:
        option_clean = normalize_mystery_food_text(option)
        option_words = mystery_food_words(option_clean)
        if option_clean and (option_clean in lowered or option_clean in words or (option_words and option_words.issubset(words))):
            return option, set(tags or set())

    return None, set()


def extract_mystery_food_freeform_tags(text):
    lowered = normalize_mystery_food_text(text)
    words = mystery_food_words(lowered)
    tags = set()

    for phrase, phrase_tags in MYSTERY_FOOD_FREEFORM_TAGS.items():
        phrase_clean = normalize_mystery_food_text(phrase)
        phrase_words = mystery_food_words(phrase_clean)
        if not phrase_clean:
            continue
        if phrase_clean in lowered or phrase_clean in words or (phrase_words and phrase_words.issubset(words)):
            tags.update(phrase_tags)

    for key, profile in MYSTERY_FOOD_PROFILES.items():
        display = profile.get("display", key)
        if normalize_mystery_food_text(display) in lowered:
            tags.update(profile.get("tags", set()))
            tags.update(profile.get("colors", set()))

    return tags


def process_mystery_food_answer(state, child_response, response_mode):
    last_key = state.get("last_question_key")
    question = next((q for q in MYSTERY_FOOD_QUESTION_BANK if q.get("key") == last_key), None)

    named_food = parse_child_told_mystery_food(child_response, allow_short_direct_name=(response_mode == "guess_reaction"))
    if named_food:
        state["possible_guess"] = named_food
        return {"named_food": named_food, "clear": True}

    if not is_clear_mystery_food_response(child_response, response_mode):
        state["unclear_or_silent_count"] = int(state.get("unclear_or_silent_count", 0)) + 1
        state["unclear_streak"] = int(state.get("unclear_streak", 0)) + 1
        state["comfortable_streak"] = 0
        return {"clear": False}

    state["comfortable_answer_count"] = int(state.get("comfortable_answer_count", 0)) + 1
    state["comfortable_streak"] = int(state.get("comfortable_streak", 0)) + 1
    state["unclear_streak"] = 0

    if last_key:
        answers = state.setdefault("answers_by_key", {})
        answers[last_key] = sanitize_mystery_food_line(child_response, fallback="", max_len=120)
        state["answers_by_key"] = answers

    option = None
    tags = set()
    remove_tags = set()

    if question:
        option, tags = extract_mystery_food_option_tags(child_response, question.get("option_tags", {}))
        if option:
            remove_tags = set((question.get("option_remove_tags", {}) or {}).get(option, set()))

    freeform_tags = extract_mystery_food_freeform_tags(child_response)
    combined_tags = set(tags) | set(freeform_tags)

    if option:
        add_mystery_food_clue(state, option, combined_tags, remove_tags)
        apply_mystery_food_candidate_filter(
            state,
            keep_tags=tags,
            remove_tags=remove_tags,
            note=f"option {question.get('key') if question else 'unknown'}"
        )
    else:
        add_mystery_food_clue(state, child_response, combined_tags, remove_tags)

    return {"clear": True}


def allowed_mystery_food_stages_for_round(rounds_completed, questions_asked):
    round_number = int(rounds_completed or 0) + 1

    if round_number <= 3:
        return {"guided_choice"}

    if round_number <= 6:
        if questions_asked < 1:
            return {"guided_choice", "easy_short_answer"}
        return {"easy_short_answer", "guided_choice"}

    if questions_asked < 1:
        return {"easy_short_answer", "open_hint"}
    return {"open_hint", "easy_short_answer"}


def choose_mystery_food_question(state):
    asked = set(state.get("question_history", [])) | set(state.get("void_question_keys", []))
    stages = allowed_mystery_food_stages_for_round(
        state.get("rounds_completed", 0),
        state.get("questions_asked", 0)
    )

    candidates = [
        q for q in MYSTERY_FOOD_QUESTION_BANK
        if q.get("key") not in asked and q.get("stage") in stages and q.get("response_mode") != "yes_no"
    ]

    if not candidates:
        candidates = [q for q in MYSTERY_FOOD_QUESTION_BANK if q.get("stage") in stages and q.get("response_mode") != "yes_no"]

    if not candidates:
        state["question_history"] = []
        candidates = [q for q in MYSTERY_FOOD_QUESTION_BANK if q.get("response_mode") != "yes_no"]

    import random
    round_number = int(state.get("rounds_completed", 0)) + 1
    questions_asked = int(state.get("questions_asked", 0))

    if round_number <= 3:
        preferred = [
            "warm_cold_room",
            "breakfast_lunch_dinner_dessert",
            "plate_bowl_cup",
            "hands_fork_spoon_straw",
            "sweet_salty_savory",
            "eat_drink_dip",
            "texture_choice",
            "main_clue_choice"
        ]
    elif round_number <= 6:
        preferred = [
            "time_of_day",
            "meal_part",
            "temperature_detail",
            "color_one",
            "shape_one",
            "main_part",
            "top_or_dip",
            "plate_bowl_cup",
            "hands_fork_spoon_straw"
        ]
    else:
        preferred = [
            "give_clue",
            "restaurant_clue",
            "customer_order",
            "describe_without_name",
            "eating_clue",
            "goes_with_it",
            "color_one",
            "main_part"
        ]

    if questions_asked < 4:
        for preferred_key in preferred:
            for q in candidates:
                if q.get("key") == preferred_key:
                    return q

    return random.choice(candidates)


def mystery_food_profile_score(profile, state):
    profile_tags = set(profile.get("tags", set())) | set(profile.get("colors", set()))
    clue_tags = set(state.get("clue_tags", []))
    negative_tags = set(state.get("negative_tags", []))
    known_clues_text = " ".join(state.get("known_clues", []))
    known_words = mystery_food_words(known_clues_text)

    score = 0.0
    score += 3.0 * len(profile_tags & clue_tags)
    score -= 4.0 * len(profile_tags & negative_tags)

    display_words = mystery_food_words(profile.get("display", ""))
    if display_words & known_words:
        score += 4.0

    for alias in profile.get("aliases", set()):
        alias_clean = normalize_mystery_food_text(alias)
        alias_words = mystery_food_words(alias_clean)
        if alias_clean and alias_clean in normalize_mystery_food_text(known_clues_text):
            score += 7.0
        elif alias_words and alias_words & known_words:
            score += 1.2 * len(alias_words & known_words)

    hints_text = " ".join(profile.get("hints", []))
    hint_words = mystery_food_words(hints_text)
    score += 0.25 * len(hint_words & known_words)

    if "restaurant" in profile_tags:
        score += 0.2
    if "meal" in profile_tags:
        score += 0.15

    return score


def choose_mystery_food_guess(state):
    rejected = {normalize_mystery_food_text(item) for item in state.get("rejected_guesses", [])}
    recent = {normalize_mystery_food_text(item) for item in state.get("recent_guesses", [])[-4:]}
    candidate_keys = state.get("candidate_keys") or list(MYSTERY_FOOD_PROFILES.keys())

    scored = []
    for key in candidate_keys:
        profile = MYSTERY_FOOD_PROFILES.get(key, {})
        display = profile.get("display", key)
        display_clean = normalize_mystery_food_text(display)
        if display_clean in rejected or display_clean in recent:
            continue

        score = mystery_food_profile_score(profile, state)
        if key in candidate_keys[:5]:
            score += 0.05
        scored.append((score, display, key))

    if not scored:
        for key, profile in MYSTERY_FOOD_PROFILES.items():
            display = profile.get("display", key)
            if normalize_mystery_food_text(display) not in rejected:
                return display
        return "pizza"

    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def should_mystery_food_guess(state):
    questions = int(state.get("questions_asked", 0))
    if questions < 3:
        return False

    cooldown = int(state.get("guess_cooldown_questions", 0) or 0)
    if cooldown > 0:
        state["guess_cooldown_questions"] = max(0, cooldown - 1)
        return False

    if int(state.get("guesses_made", 0)) >= MYSTERY_FOOD_MAX_WRONG_GUESSES_PER_ROUND:
        return False

    candidate_count = len(state.get("candidate_keys") or [])
    clue_tag_count = len(state.get("clue_tags", []))

    if candidate_count <= 3 and clue_tag_count >= 2:
        return True

    if questions >= MYSTERY_FOOD_SOFT_GUESS_LIMIT and clue_tag_count >= 2:
        return True

    if questions >= 5 and clue_tag_count >= 1:
        return True

    return False


def mystery_food_should_give_up(state):
    questions = int(state.get("questions_asked", 0) or 0)
    guesses = int(state.get("guesses_made", 0) or 0)
    if guesses >= MYSTERY_FOOD_MAX_WRONG_GUESSES_PER_ROUND:
        return True
    if questions >= MYSTERY_FOOD_MAX_QUESTIONS_PER_ROUND:
        return True
    return False


def make_mystery_food_question_message(state, prefix=""):
    question = choose_mystery_food_question(state)
    state["last_question"] = question.get("question")
    state["last_question_key"] = question.get("key")
    state["last_response_mode"] = question.get("response_mode", "choice")
    state["stage"] = question.get("stage", "guided_choice")
    state["questions_asked"] = int(state.get("questions_asked", 0)) + 1

    history = state.setdefault("question_history", [])
    history.append(question.get("key"))
    state["question_history"] = history[-28:]

    lead_ins = [
        "Hmm.",
        "Okay, let me picture it.",
        "That clue helps.",
        "I think I can narrow it down.",
        "Let me ask one more clue."
    ]

    if not prefix:
        import random
        prefix = random.choice(lead_ins) if state["questions_asked"] > 1 else "First clue."

    message = f"{prefix} {question.get('question')}"
    return message, question.get("stage", "guided_choice"), question.get("response_mode", "choice")


def make_mystery_food_payload(
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
    session_done=False,
    audio=True
):
    message = sanitize_mystery_food_line(message, fallback="Hmm.")
    history = list(history or [])
    history.append({
        "event_type": event_type,
        "message": message,
        "child_response": sanitize_mystery_food_line(child_response, fallback="", max_len=180),
        "stage": stage,
        "response_mode": response_mode
    })

    game_state["stage"] = stage
    game_state["last_response_mode"] = response_mode
    game_state["game_complete"] = game_complete

    session["mystery_food_item_history"] = history[-28:]
    session["mystery_food_item_state"] = game_state
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

    if next_event:
        payload["next_event"] = next_event

    if pause_before_next_ms is not None:
        payload["pause_before_next_ms"] = pause_before_next_ms

    if next_url:
        payload["next_url"] = next_url

    if redirect_after_ms is not None:
        payload["redirect_after_ms"] = redirect_after_ms

    if audio:
        try:
            audio_bytes = generate_mystery_food_voice_elevenlabs(
                message,
                game_complete=game_complete,
                thinking=False
            )
            audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
            payload["audio_url"] = f"data:audio/mpeg;base64,{audio_base64}"
        except Exception as e:
            print("Mystery Food Item audio generation error:", repr(e))

    return payload


def start_new_mystery_food_round(rounds_completed, message, event_label="replay", pause_ms=1800):
    game_state = get_mystery_food_default_state(rounds_completed=rounds_completed)
    history = []

    return make_mystery_food_payload(
        message=message,
        stage="intro",
        response_mode="none",
        expects_response=False,
        game_complete=False,
        game_state=game_state,
        history=history,
        event_type=event_label,
        child_response="",
        next_event="first_question",
        pause_before_next_ms=pause_ms
    )


def finish_mystery_food_session(message, game_state, history, unlock_next=False, event_label="session_done", redirect_to_dashboard=False):
    next_url = None

    if unlock_next:
        complete_mystery_food_and_unlock_next_for_user(game_state.get("rounds_completed", MYSTERY_FOOD_REQUIRED_ROUNDS))
        next_url = url_for("dashboard")
    else:
        save_mystery_food_round_progress(game_state.get("rounds_completed", 0))
        if redirect_to_dashboard:
            next_url = url_for("dashboard")

    return make_mystery_food_payload(
        message=message,
        stage="session_done",
        response_mode="none",
        expects_response=False,
        game_complete=unlock_next,
        game_state=game_state,
        history=history,
        event_type=event_label,
        child_response="",
        next_url=next_url,
        redirect_after_ms=1900 if next_url else None,
        session_done=True
    )


def mystery_food_round_choice_payload(game_state, history, base_message=""):
    rounds_completed = int(game_state.get("rounds_completed", 0))
    name = clean_mystery_food_child_name(session.get("child_name", ""))
    name_part = f", {name}" if name else ""

    if is_mystery_food_final_round_choice(rounds_completed):
        message = (
            f"{base_message} " if base_message else ""
        ) + f"That finishes our nine Mystery Food Item rounds for today{name_part}. Say play again to start over, or say end to stop here."
    else:
        message = (
            f"{base_message} " if base_message else ""
        ) + "Say another food to keep playing, or say end to stop here."

    return make_mystery_food_payload(
        message=message,
        stage="round_choice",
        response_mode="round_choice",
        expects_response=True,
        game_complete=False,
        game_state=game_state,
        history=history,
        event_type="round_choice",
        child_response=""
    )


def handle_mystery_food_round_completed(game_state, history, guessed_food):
    rounds_completed = min(
        MYSTERY_FOOD_REQUIRED_ROUNDS,
        int(game_state.get("rounds_completed", 0)) + 1
    )
    game_state["rounds_completed"] = rounds_completed
    save_mystery_food_round_progress(rounds_completed)

    if should_mystery_food_ask_round_choice(rounds_completed):
        base = f"I got it. It was {guessed_food}."
        return mystery_food_round_choice_payload(game_state, history, base_message=base)

    next_message = f"I got it. It was {guessed_food}. Think of a new food, but keep it secret."
    return start_new_mystery_food_round(rounds_completed, next_message, event_label="new_round", pause_ms=1800)


def handle_mystery_food_give_up(game_state, history):
    rounds_completed = min(
        MYSTERY_FOOD_REQUIRED_ROUNDS,
        int(game_state.get("rounds_completed", 0)) + 1
    )
    game_state["rounds_completed"] = rounds_completed
    save_mystery_food_round_progress(rounds_completed)

    base = "I’m going to give up on this one. You picked a tricky food."

    if should_mystery_food_ask_round_choice(rounds_completed):
        return mystery_food_round_choice_payload(game_state, history, base_message=base)

    return start_new_mystery_food_round(
        rounds_completed,
        base + " Think of a new food, but keep it secret.",
        event_label="gave_up_new_round",
        pause_ms=1900
    )


def make_mystery_food_guess_payload(game_state, history, guessed_food, event_label="guess_food", child_response=""):
    recent = game_state.setdefault("recent_guesses", [])
    recent.append(guessed_food)
    game_state["recent_guesses"] = recent[-8:]
    game_state["possible_guess"] = guessed_food
    game_state["last_response_mode"] = "guess_reaction"

    return make_mystery_food_payload(
        message=f"That’s a helpful clue. Leo’s guess is {guessed_food}. Say {guessed_food} if I got it, or give Leo one more clue if I missed it.",
        stage="guess_reaction",
        response_mode="guess_reaction",
        expects_response=True,
        game_complete=False,
        game_state=game_state,
        history=history,
        event_type=event_label,
        child_response=child_response
    )


@app.route("/mystery-food-item")
@login_required
def mystery_food_item_game_preview():
    return render_template(
        "mystery_food_item.html",
        activity=None,
        parent=session.get("parent_name", ""),
        child=session.get("child_name", ""),
        active_page="dashboard",
        profile_icon=session.get("profile_icon", "profileicon.png")
    )


@app.route("/restaurant-worker-game")
@login_required
def restaurant_worker_game_preview():
    return redirect(url_for("mystery_food_item_game_preview"))


@app.route("/api/mystery-food-item/thinking-audio", methods=["GET"])
@csrf.exempt
@login_required
@limiter.limit("50 per minute")
def mystery_food_item_thinking_audio():
    import hashlib
    import random

    thinking_lines = ["Hmm.", "Hmm, okay.", "Let me think."]

    avoid_raw = request.args.get("avoid", "")
    avoid_lines = {
        re.sub(r"\s+", " ", item).strip().lower()
        for item in avoid_raw.split("|")
        if item.strip()
    }

    choices = [line for line in thinking_lines if normalize_mystery_food_text(line) not in avoid_lines]
    line = random.choice(choices or thinking_lines)

    try:
        voice_id = (
            os.getenv("RESTAURANT_WORKER_VOICE_ID")
            or os.getenv("LEO_VOICE_ID")
            or os.getenv("TOY_TRIVIA_VOICE_ID")
            or os.getenv("TOY_WORKER_VOICE_ID")
            or os.getenv("ELEVENLABS_VOICE_ID", "piI8Kku0DcvcL6TTSeQt")
        )

        cache_dir = os.path.join(BASE_DIR, "static", "audio", "mystery_food_item_thinking")
        os.makedirs(cache_dir, exist_ok=True)

        cache_key = f"mystery-food-thinking-v3:{voice_id}:{line}"
        filename = hashlib.sha1(cache_key.encode("utf-8")).hexdigest() + ".mp3"
        file_path = os.path.join(cache_dir, filename)

        if not os.path.exists(file_path):
            audio_bytes = generate_mystery_food_voice_elevenlabs(line, thinking=True)
            with open(file_path, "wb") as f:
                f.write(audio_bytes)

        return jsonify({
            "success": True,
            "line": line,
            "audio_url": url_for("static", filename=f"audio/mystery_food_item_thinking/{filename}")
        })

    except Exception as e:
        print("Mystery Food Item thinking audio error:", repr(e))
        return jsonify({"success": False, "error": "Could not generate thinking audio"}), 500


@app.route("/api/mystery-food-item/message", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("30 per minute")
def mystery_food_item_message():
    data = request.get_json(silent=True) or {}

    event_type = re.sub(r"\s+", " ", str(data.get("event_type", "intro") or "intro")).strip()
    child_response = re.sub(r"\s+", " ", str(data.get("child_response", "") or "")).strip()
    previous_response_mode = re.sub(r"\s+", " ", str(data.get("response_mode", "none") or "none")).strip()

    allowed_events = {"intro", "restart", "first_question", "child_answer", "no_response"}
    if event_type not in allowed_events:
        return jsonify({"success": False, "error": "Invalid event_type"}), 400

    if event_type in {"intro", "restart"}:
        session.pop("mystery_food_item_history", None)
        session.pop("mystery_food_item_state", None)
        session.modified = True

        if event_type == "restart":
            reset_mystery_food_progress_for_user()
            saved_rounds = 0
        else:
            saved_rounds = get_saved_mystery_food_rounds()

        if saved_rounds >= MYSTERY_FOOD_REQUIRED_ROUNDS:
            saved_rounds = 0

        child_name = clean_mystery_food_child_name(session.get("child_name", ""))
        name_part = f", {child_name}" if child_name else ""
        opening = (
            f"Hey{name_part}, it’s Leo. Let’s play Mystery Food Item. "
            "Think of one food, but keep the name secret. "
            "I’ll ask clue questions and try to guess it. "
            "When I guess, say the food name if I got it, or give Leo one more clue if I missed it."
        )

        return jsonify(start_new_mystery_food_round(saved_rounds, opening, event_label=event_type, pause_ms=900))

    game_state = session.get("mystery_food_item_state") or get_mystery_food_default_state(get_saved_mystery_food_rounds())
    history = session.get("mystery_food_item_history") or []

    if event_type == "first_question":
        message, stage, response_mode = make_mystery_food_question_message(game_state, prefix="First clue.")
        return jsonify(make_mystery_food_payload(
            message=message,
            stage=stage,
            response_mode=response_mode,
            expects_response=True,
            game_complete=False,
            game_state=game_state,
            history=history,
            event_type=event_type,
            child_response=""
        ))

    if game_state.get("stage") == "round_choice":
        if event_type == "no_response" or is_mystery_food_unclear_or_silent(child_response):
            return jsonify(make_mystery_food_payload(
                message="You can say another food to keep playing, or say end to stop here.",
                stage="round_choice",
                response_mode="round_choice",
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type="round_choice_retry",
                child_response=child_response
            ))

        choice = classify_mystery_food_round_choice(child_response)
        rounds_completed = int(game_state.get("rounds_completed", 0))

        if choice == "same_game":
            if rounds_completed >= MYSTERY_FOOD_REQUIRED_ROUNDS:
                reset_mystery_food_progress_for_user()
                return jsonify(start_new_mystery_food_round(0, "Okay. New round. Think of a food, but keep it secret.", event_label="play_again"))
            return jsonify(start_new_mystery_food_round(rounds_completed, "Okay. Think of another food, but keep it secret.", event_label="continue_rounds"))

        if choice == "end":
            return jsonify(finish_mystery_food_session(
                "Okay, today was fun. I really liked playing this game with you. See you next time.",
                game_state,
                history,
                unlock_next=(rounds_completed >= MYSTERY_FOOD_REQUIRED_ROUNDS),
                event_label="ended_by_child",
                redirect_to_dashboard=True
            ))

        return jsonify(make_mystery_food_payload(
            message="I didn’t quite get that, but that’s okay. Say another food to keep playing, or say end to stop here.",
            stage="round_choice",
            response_mode="round_choice",
            expects_response=True,
            game_complete=False,
            game_state=game_state,
            history=history,
            event_type="round_choice_unclear",
            child_response=child_response
        ))

    if previous_response_mode in {"guess_reaction", "guess_confirmation"} or game_state.get("last_response_mode") in {"guess_reaction", "guess_confirmation"}:
        guessed_food = game_state.get("possible_guess") or "your food"

        if event_type != "no_response" and mystery_food_confirms_guess(child_response, guessed_food):
            return jsonify(handle_mystery_food_round_completed(game_state, history, guessed_food))

        if event_type != "no_response":
            named_food = parse_child_told_mystery_food(child_response, allow_short_direct_name=True)
            if named_food and normalize_mystery_food_text(named_food) != normalize_mystery_food_text(guessed_food):
                return jsonify(handle_mystery_food_round_completed(game_state, history, named_food))

            rejected = game_state.setdefault("rejected_guesses", [])
            if guessed_food not in rejected:
                rejected.append(guessed_food)
            game_state["rejected_guesses"] = rejected[-14:]
            game_state["possible_guess"] = None
            game_state["guess_cooldown_questions"] = 1
            game_state["guesses_made"] = int(game_state.get("guesses_made", 0) or 0) + 1

            if not mystery_food_rejects_guess(child_response, guessed_food):
                process_mystery_food_answer(game_state, child_response, "open_hint")

            if mystery_food_should_give_up(game_state):
                return jsonify(handle_mystery_food_give_up(game_state, history))

            prefix = f"Okay, I’ll keep thinking. That clue helps narrow it down."
            message, stage, response_mode = make_mystery_food_question_message(game_state, prefix=prefix)
            return jsonify(make_mystery_food_payload(
                message=message,
                stage=stage,
                response_mode=response_mode,
                expects_response=True,
                game_complete=False,
                game_state=game_state,
                history=history,
                event_type="missed_guess_next_question",
                child_response=child_response
            ))

        return jsonify(make_mystery_food_payload(
            message=f"Say {guessed_food} if Leo’s guess was right, or give Leo one more clue if I missed it.",
            stage="guess_reaction",
            response_mode="guess_reaction",
            expects_response=True,
            game_complete=False,
            game_state=game_state,
            history=history,
            event_type="guess_reaction_retry",
            child_response=child_response
        ))

    if event_type == "no_response":
        game_state["unclear_or_silent_count"] = int(game_state.get("unclear_or_silent_count", 0)) + 1
        game_state["unclear_streak"] = int(game_state.get("unclear_streak", 0)) + 1

        if mystery_food_should_give_up(game_state):
            return jsonify(handle_mystery_food_give_up(game_state, history))

        prefix = "I didn’t quite hear that, but that’s okay. Let me ask another clue."
        message, stage, response_mode = make_mystery_food_question_message(game_state, prefix=prefix)
        return jsonify(make_mystery_food_payload(
            message=message,
            stage=stage,
            response_mode=response_mode,
            expects_response=True,
            game_complete=False,
            game_state=game_state,
            history=history,
            event_type="no_response_next_question",
            child_response=""
        ))

    result = process_mystery_food_answer(game_state, child_response, previous_response_mode)

    if result.get("named_food"):
        guessed_food = result["named_food"]
        return jsonify(make_mystery_food_guess_payload(game_state, history, guessed_food, event_label="child_revealed_food", child_response=child_response))

    if not result.get("clear"):
        if mystery_food_should_give_up(game_state):
            return jsonify(handle_mystery_food_give_up(game_state, history))

        prefix = "I didn’t quite get that, but that’s okay. Let me ask another clue."
        message, stage, response_mode = make_mystery_food_question_message(game_state, prefix=prefix)
        return jsonify(make_mystery_food_payload(
            message=message,
            stage=stage,
            response_mode=response_mode,
            expects_response=True,
            game_complete=False,
            game_state=game_state,
            history=history,
            event_type="unclear_next_question",
            child_response=child_response
        ))

    if should_mystery_food_guess(game_state):
        guessed_food = choose_mystery_food_guess(game_state)
        return jsonify(make_mystery_food_guess_payload(game_state, history, guessed_food, event_label="guess_food", child_response=child_response))

    import random
    helpful_prefixes = [
        "That’s a helpful clue.",
        "Okay, that gives me a better picture.",
        "Nice clue.",
        "Got it."
    ]
    prefix = random.choice(helpful_prefixes) if int(game_state.get("comfortable_answer_count", 0)) % 2 == 1 else ""

    message, stage, response_mode = make_mystery_food_question_message(game_state, prefix=prefix)
    return jsonify(make_mystery_food_payload(
        message=message,
        stage=stage,
        response_mode=response_mode,
        expects_response=True,
        game_complete=False,
        game_state=game_state,
        history=history,
        event_type="next_question",
        child_response=child_response
    ))


@app.route("/api/mystery-food-item/transcribe", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("30 per minute")
def mystery_food_item_transcribe():
    if "audio" not in request.files:
        return jsonify({"success": False, "error": "Missing audio"}), 400

    audio_file = request.files["audio"]

    try:
        import io

        audio_bytes = audio_file.read()
        if not audio_bytes:
            return jsonify({"success": False, "error": "Empty audio file"}), 400

        file_obj = io.BytesIO(audio_bytes)
        file_obj.name = "mystery-food-response.webm"

        transcript = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=file_obj
        )

        text = transcript.text.strip()
        print("MYSTERY FOOD ITEM TRANSCRIPT:", text)
        return jsonify({"success": True, "text": text})

    except Exception as e:
        print("Mystery Food Item transcription error:", repr(e))
        return jsonify({"success": False, "error": str(e)}), 500


def generate_librarian_voice_elevenlabs(text):
    voice_id = os.getenv("LIBRARIAN_VOICE_ID")

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

@app.route("/api/restaurant-game/tts", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("30 per minute")
def restaurant_game_tts():
    data = request.get_json(silent=True) or {}

    speaker = str(data.get("speaker", "worker")).strip().lower()
    text = str(data.get("text", "")).strip()
    game_complete = bool(data.get("game_complete", False))

    if not text:
        return jsonify({"success": False, "error": "Missing text"}), 400

    try:
        if speaker == "teacher":
            audio_bytes = generate_librarian_voice_elevenlabs(text)
        else:
            audio_bytes = generate_mystery_food_voice_elevenlabs(
                text,
                game_complete=game_complete,
                thinking=False
            )

        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

        return jsonify({
            "success": True,
            "audio": f"data:audio/mpeg;base64,{audio_base64}"
        })

    except Exception as e:
        print("Restaurant game TTS error:", repr(e))
        return jsonify({"success": False, "error": "Could not generate audio"}), 500

# Add these routes to app.py before: if __name__ == "__main__":
# They are needed because restaurant_worker_game.js calls:
# /api/restaurant-game/state
# /api/restaurant-game/save-progress
# /api/restaurant-game/complete
# /api/restaurant-game/transcribe

@app.route("/api/restaurant-game/state", methods=["GET"])
@csrf.exempt
@login_required
def restaurant_game_state():
    ensure_restaurant_game_progress_columns()

    activity_id = safe_restaurant_int(request.args.get("activity_id"), 10, 9999)

    conn = get_db_connection()
    cursor = conn.cursor()

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
            COALESCE(restaurant_order_index, 0) AS order_index,
            COALESCE(restaurant_step_index, 0) AS step_index,
            COALESCE(restaurant_orders_completed, 0) AS orders_completed,
            COALESCE(restaurant_steps_completed, 0) AS steps_completed,
            COALESCE(restaurant_spoken_responses, 0) AS spoken_responses,
            COALESCE(restaurant_silent_windows, 0) AS silent_windows,
            COALESCE(restaurant_worker_direct_responses, 0) AS worker_direct_responses,
            COALESCE(restaurant_teacher_redirects, 0) AS teacher_redirects,
            COALESCE(restaurant_total_choices, 0) AS total_choices,
            restaurant_last_pizza_json AS last_pizza_json
        FROM progress
        WHERE user_id = ? AND activity_id = ?
    """, (session["user_id"], activity_id))

    row = cursor.fetchone()
    conn.commit()
    conn.close()

    if not row:
        return jsonify({"success": True, "state": {
            "order_index": 0,
            "step_index": 0,
            "orders_completed": 0,
            "steps_completed": 0,
            "spoken_responses": 0,
            "silent_windows": 0,
            "worker_direct_responses": 0,
            "teacher_redirects": 0,
            "total_choices": 0,
            "last_pizza_json": None
        }})

    # Round-level restore: use the furthest completed order, never a half-finished step.
    orders_completed = safe_restaurant_int(row["orders_completed"], 0, 8)
    saved_order_index = safe_restaurant_int(row["order_index"], 0, 7)
    restored_order_index = min(7, max(saved_order_index, orders_completed))

    return jsonify({"success": True, "state": {
        "order_index": restored_order_index,
        "step_index": 0,
        "orders_completed": orders_completed,
        "steps_completed": safe_restaurant_int(row["steps_completed"], 0, 9999),
        "spoken_responses": safe_restaurant_int(row["spoken_responses"], 0, 9999),
        "silent_windows": safe_restaurant_int(row["silent_windows"], 0, 9999),
        "worker_direct_responses": safe_restaurant_int(row["worker_direct_responses"], 0, 9999),
        "teacher_redirects": safe_restaurant_int(row["teacher_redirects"], 0, 9999),
        "total_choices": safe_restaurant_int(row["total_choices"], 0, 9999),
        "last_pizza_json": row["last_pizza_json"]
    }})


@app.route("/api/restaurant-game/save-progress", methods=["POST"])
@csrf.exempt
@login_required
def restaurant_game_save_progress():
    ensure_restaurant_game_progress_columns()

    data = request.get_json(silent=True) or {}
    activity_id = safe_restaurant_int(data.get("activity_id"), 10, 9999)

    orders_completed = safe_restaurant_int(data.get("orders_completed"), 0, 8)
    incoming_order_index = safe_restaurant_int(data.get("order_index"), 0, 7)
    # Round-level save: if order 1 is complete, save order_index as order 2.
    order_index = min(7, max(incoming_order_index, orders_completed))

    steps_completed = safe_restaurant_int(data.get("steps_completed"), 0, 9999)
    spoken_responses = safe_restaurant_int(data.get("spoken_responses"), 0, 9999)
    silent_windows = safe_restaurant_int(data.get("silent_windows"), 0, 9999)
    worker_direct_responses = safe_restaurant_int(data.get("worker_direct_responses"), 0, 9999)
    teacher_redirects = safe_restaurant_int(data.get("teacher_redirects"), 0, 9999)
    total_choices = safe_restaurant_int(data.get("total_choices"), 0, 9999)
    last_pizza_json = str(data.get("last_pizza_json") or "")[:15000] or None

    conn = get_db_connection()
    cursor = conn.cursor()

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
            restaurant_order_index = MAX(COALESCE(restaurant_order_index, 0), ?),
            restaurant_step_index = 0,
            restaurant_orders_completed = MAX(COALESCE(restaurant_orders_completed, 0), ?),
            restaurant_steps_completed = MAX(COALESCE(restaurant_steps_completed, 0), ?),
            restaurant_spoken_responses = MAX(COALESCE(restaurant_spoken_responses, 0), ?),
            restaurant_silent_windows = MAX(COALESCE(restaurant_silent_windows, 0), ?),
            restaurant_worker_direct_responses = MAX(COALESCE(restaurant_worker_direct_responses, 0), ?),
            restaurant_teacher_redirects = MAX(COALESCE(restaurant_teacher_redirects, 0), ?),
            restaurant_total_choices = MAX(COALESCE(restaurant_total_choices, 0), ?),
            restaurant_last_pizza_json = COALESCE(?, restaurant_last_pizza_json),
            restaurant_last_played_at = CURRENT_TIMESTAMP
        WHERE user_id = ? AND activity_id = ?
    """, (
        order_index,
        orders_completed,
        steps_completed,
        spoken_responses,
        silent_windows,
        worker_direct_responses,
        teacher_redirects,
        total_choices,
        last_pizza_json,
        session["user_id"],
        activity_id
    ))

    conn.commit()
    conn.close()
    return jsonify({"success": True, "order_index": order_index, "orders_completed": orders_completed})


@app.route("/api/restaurant-game/complete", methods=["POST"])
@csrf.exempt
@login_required
def restaurant_game_complete():
    ensure_restaurant_game_progress_columns()

    data = request.get_json(silent=True) or {}
    activity_id = safe_restaurant_int(data.get("activity_id"), 10, 9999)

    words_spoken = safe_restaurant_int(data.get("words_spoken"), 0, 999999)
    minutes_spoken = safe_restaurant_float(data.get("minutes_spoken"), 0.0)
    active_minutes = safe_restaurant_float(data.get("active_minutes"), 0.0)
    time_spent = safe_restaurant_float(data.get("time_spent_on_activity"), active_minutes)
    orders_completed = safe_restaurant_int(data.get("orders_completed"), 8, 8)
    steps_completed = safe_restaurant_int(data.get("steps_completed"), 0, 9999)

    conn = get_db_connection()
    cursor = conn.cursor()

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
        SELECT scene_id, activity_order
        FROM activity
        WHERE activity_id = ?
    """, (activity_id,))
    current_activity = cursor.fetchone()

    cursor.execute("""
        UPDATE progress
        SET
            is_completed = 1,
            words_spoken = MAX(COALESCE(words_spoken, 0), ?),
            minutes_spoken = MAX(COALESCE(minutes_spoken, 0), ?),
            active_minutes = MAX(COALESCE(active_minutes, 0), ?),
            time_spent_on_activity = MAX(COALESCE(time_spent_on_activity, 0), ?),
            restaurant_order_index = 0,
            restaurant_step_index = 0,
            restaurant_orders_completed = MAX(COALESCE(restaurant_orders_completed, 0), ?),
            restaurant_steps_completed = MAX(COALESCE(restaurant_steps_completed, 0), ?),
            restaurant_spoken_responses = MAX(COALESCE(restaurant_spoken_responses, 0), ?),
            restaurant_silent_windows = MAX(COALESCE(restaurant_silent_windows, 0), ?),
            restaurant_worker_direct_responses = MAX(COALESCE(restaurant_worker_direct_responses, 0), ?),
            restaurant_teacher_redirects = MAX(COALESCE(restaurant_teacher_redirects, 0), ?),
            restaurant_total_choices = MAX(COALESCE(restaurant_total_choices, 0), ?),
            restaurant_last_played_at = CURRENT_TIMESTAMP
        WHERE user_id = ? AND activity_id = ?
    """, (
        words_spoken,
        minutes_spoken,
        active_minutes,
        time_spent,
        orders_completed,
        steps_completed,
        safe_restaurant_int(data.get("spoken_responses"), 0, 9999),
        safe_restaurant_int(data.get("silent_windows"), 0, 9999),
        safe_restaurant_int(data.get("worker_direct_responses"), 0, 9999),
        safe_restaurant_int(data.get("teacher_redirects"), 0, 9999),
        safe_restaurant_int(data.get("total_choices"), 0, 9999),
        session["user_id"],
        activity_id
    ))

    next_activity_id = None
    if current_activity:
        cursor.execute("""
            SELECT activity_id
            FROM activity
            WHERE is_active = 1
            AND activity_id > ?
            ORDER BY activity_id ASC
            LIMIT 1
        """, (
            current_activity["activity_id"],
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

    return jsonify({"success": True, "next_activity_id": next_activity_id})


@app.route("/api/restaurant-game/transcribe", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("30 per minute")
def restaurant_game_transcribe():
    if "audio" not in request.files:
        return jsonify({"success": False, "error": "Missing audio"}), 400

    audio_file = request.files["audio"]

    try:
        import io

        audio_bytes = audio_file.read()
        if not audio_bytes:
            return jsonify({"success": False, "error": "Empty audio file"}), 400

        file_obj = io.BytesIO(audio_bytes)
        file_obj.name = "restaurant-response.webm"

        transcript = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=file_obj
        )

        text = transcript.text.strip()
        print("RESTAURANT GAME TRANSCRIPT:", text)
        return jsonify({"success": True, "text": text})

    except Exception as e:
        print("Restaurant game transcription error:", repr(e))
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=app.config["DEBUG"])
