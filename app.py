from flask import Flask, render_template, request, redirect, session, url_for, abort
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

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

import os

app = Flask(__name__)

load_dotenv()

client = OpenAI(api_key=os.getenv("API_KEY"))

debug_mode = os.environ.get("FLASK_DEBUG") == "1"
app.config["DEBUG"] = debug_mode

app.secret_key = secrets.token_hex(32)
csrf = CSRFProtect(app)

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

Talisman(app, content_security_policy=csp)

# RATE Limiting
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"]
)

def get_db_connection():
    conn = sqlite3.connect("app.db")
    conn.row_factory = sqlite3.Row
    return conn


def initialize_user_progress(cursor, user_id):
    cursor.execute("""
        SELECT activity_id, scene_id, activity_order
        FROM activity
        WHERE is_active = 1
        ORDER BY scene_id, activity_order
    """)
    activities = cursor.fetchall()

    first_activity_id = None

    for activity in activities:
        activity_id = activity["activity_id"]
        activity_order = activity["activity_order"]

        is_unlocked = 1 if activity_order == 1 else 0

        if first_activity_id is None and is_unlocked == 1:
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

        conn = sqlite3.connect("app.db")
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
        email = request.form["email"]
        parent_name = request.form["parent_name"]
        child_name = request.form["child_name"]
        child_dob = request.form["child_dob"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]
        terms_check = 1 if request.form.get("terms_check") else 0

        if password != confirm_password:
            return render_template("signup.html", error="* Passwords do not match")

        error = validate_password(password)
        if error:
            return render_template("signup.html", error=error)

        hashed_password = generate_password_hash(password)

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
                terms_check
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (email, hashed_password, parent_name, child_name, child_dob, terms_check))

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
    return None


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


@app.route("/dashboard")
@login_required
def dashboard():
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
        SELECT current_activity_id
        FROM users
        WHERE user_id = ?
    """, (session["user_id"],))
    user_row = cursor.fetchone()
    current_activity_id = user_row["current_activity_id"] if user_row else None

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
    ORDER BY a.scene_id, a.activity_order
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
        current_activity_id=current_activity_id,
        default_slide_index=default_slide_index,
        session_chart_data=session_chart_data,
        recent_sessions=recent_sessions
    )


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
    return render_template(
        "settings.html",
        active_page="settings",
        parent=session["parent_name"],
        child=session["child_name"],
        profile_icon=session.get("profile_icon", "profileicon.png")
    )


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

    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE users SET profile_icon = ? WHERE user_id = ?",
        (icon, session["user_id"])
    )

    conn.commit()
    conn.close()

    session["profile_icon"] = icon

    return {"success": True}


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

@app.route("/api/matching-game/message", methods=["POST"])
@csrf.exempt
@login_required
# @limiter.limit("20 per minute")
# @limiter.limit("120 per hour")
def matching_game_message():
    data = request.get_json(silent=True) or {}

    event_type = data.get("event_type", "general")
    card_name = data.get("card_name", "")
    player = data.get("player", "child")

    minutes_played = float(data.get("minutes_played", 0))
    stage = int(data.get("stage", 0))
    should_ask_question = bool(data.get("should_ask_question", False))
    unanswered_questions = int(data.get("unanswered_questions", 0))
    star_messages_played = int(data.get("star_messages_played", 0))
    star_questions_asked = int(data.get("star_questions_asked", 0))

    allowed_events = {
        "game_start",
        "child_turn",
        "parent_turn",
        "match_found",
        "card_flip",
        "no_match",
        "game_complete"
    }

    if event_type not in allowed_events:
        return jsonify({"success": False, "error": "Invalid event_type"}), 400

    child_name = session.get("child_name", "there")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT child_dob
        FROM users
        WHERE user_id = ?
    """, (session["user_id"],))

    user_row = cursor.fetchone()
    conn.close()

    child_dob = user_row["child_dob"] if user_row else None
    child_age = calculate_child_age(child_dob)

    if stage <= 0:
        stage_instructions = """
Stage 0:
Only give short encouragement, motivation, or reactions to the move.
Do NOT describe the card in a silly way.
Do NOT say things like "funny card", "shiny fish", or "sneaky bunny."
Do NOT ask questions.
Do NOT invite the child to talk.
Do NOT mention turns too much.

Good Stage 0 examples:
"Nice move!"
"Good try!"
"Great flip!"
"That was close!"
"Good memory!"
"Nice match!"
"Keep going!"
"Almost got it!"
"Great focus!"
"Good one!"
"""
    elif stage == 1:
        stage_instructions = """
Stage 1:
Mostly make playful comments.
If should_ask_question is true, ask a very tiny card-based question.
Good question examples:
"Cat or dog?"
"Fish or bunny?"
"Which one is silly?"
Otherwise, do not ask a question.
"""
    else:
        stage_instructions = """
Stage 2:
Use playful game comments and occasional slightly longer card-based questions.
Good question examples:
"Where do you think the cat is hiding?"
"Which card should we find next?"
"Do you think the bunny is nearby?"
Only ask a question if should_ask_question is true.
"""

    question_rule = "You SHOULD ask one tiny game-based question." if should_ask_question else "You should NOT ask a question."

    prompt = f"""
You are Star, a cheerful cartoon mascot in a children's matching card game.

Talk like a playful game buddy for young kids.

IMPORTANT RULES:
- Never sound like a therapist.
- Never mention anxiety, bravery, comfort level, silence, mutism, progress, stages, or emotions.
- Never pressure the child to answer.
- Never say "you don't have to answer."
- Never say "I'll watch you play."
- Do not make the child feel observed.
- Keep things light, playful, and game-focused.
- Use only ONE short sentence.
- Stage 1 must be 4 words or fewer.
- Stage 0 and Stage 2 should usually be 8 words or fewer.
- Sound like a fun cartoon game character.

The parent and child are playing together.
Treat both players naturally.
Do not overfocus on the child.

{stage_instructions}

Question instruction:
{question_rule}

Context:
Event type: {event_type}
Card name: {card_name}
Current player: {player}
Effective minutes played: {minutes_played:.1f}
Stage: {stage}
Unanswered questions: {unanswered_questions}
Star messages already played: {star_messages_played}
Star questions already asked: {star_questions_asked}
Child name: {child_name}
Child age: {child_age if child_age is not None else "unknown"}

Good comment examples:
"Nice move!"
"Good try!"
"Great flip!"
"That was close!"
"Good memory!"
"Nice match!"
"Keep going!"
"Almost got it!"
"Great focus!"
"Good one!"
"That was close"

Bad examples:
"How are you feeling?"
"Are you comfortable talking?"
"I'll watch you play."
"You're doing great communicating."
"It's okay if you don't answer."

Generate exactly ONE line.
"""

    try:
        text_response = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt
        )

        message = text_response.output_text.strip().replace('"', "")

        speech_response = client.audio.speech.create(
            model="gpt-4o-mini-tts",
            voice="coral",
            input=message,
            response_format="mp3"
        )

        audio_bytes = speech_response.content
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

        return jsonify({
            "success": True,
            "message": message,
            "audio": f"data:audio/mpeg;base64,{audio_base64}",
            "asked_question": should_ask_question
        })

    except Exception as e:
        print("Matching game AI error:", e)

        return jsonify({
            "success": False,
            "error": "Could not generate message"
        }), 500

if __name__ == "__main__":
    app.run(debug=True)