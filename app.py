from flask import Flask, render_template, request, redirect, session, url_for, abort
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

import json

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
    
def generate_star_voice_elevenlabs(text):
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "piI8Kku0DcvcL6TTSeQt")

    response = eleven_client.text_to_speech.convert(
        voice_id=voice_id,
        text=text,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
        voice_settings={
            "stability": 0.9,
            "similarity_boost": 0.95,
            "style": 0.0,
            "use_speaker_boost": False
        }
    )

    return b"".join(response)

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

@app.route("/api/matching-game/message", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("30 per minute")
def matching_game_message():
    data = request.get_json(silent=True) or {}

    event_type = data.get("event_type", "general")
    card_name = data.get("card_name", "")
    player = data.get("player", "child")
    stage = int(data.get("stage", 0))
    ask_type = data.get("ask_type", "none")
    recent_messages = data.get("recent_star_messages", [])

    allowed_events = {
        "game_start",
        "card_flip",
        "match_found",
        "no_match",
        "turn_change",
        "game_complete",
        "gentle_prompt",
        "child_turn",
        "parent_turn"
    }

    if event_type not in allowed_events:
        return jsonify({"success": False, "error": "Invalid event_type"}), 400

    child_name = session.get("child_name", "there")

    stage_rules = {
        0: """
Stage 0: Presence and safety.
Star should only make light game comments.
No questions. No pressure. No requests to speak.
The sentence should be under 8 words.
""",
        1: """
Stage 1: Nonverbal invitation.
Star may invite pointing, choosing, or noticing.
No required speech.
The sentence should be under 10 words.
""",
        2: """
Stage 2: Yes/no or forced choice.
Star may ask one very concrete question.
Examples: "Cat or dog?" "Was that a match?"
Avoid abstract feelings questions.
""",
        3: """
Stage 3: One-word responses.
Star may ask for one simple word.
Examples: "What animal is that?" "Which card next?"
Keep it playful and low-pressure.
"""
    }

    ask_rules = {
        "none": "Do not ask a question.",
        "nonverbal": "Ask for a pointing/clicking/choosing response, not speech.",
        "yes_no": "Ask a tiny yes/no question.",
        "choice": "Ask a forced-choice question with two options.",
        "one_word": "Ask for one simple word."
    }

    prompt = f"""
You are Star, a warm animated star mascot in a parent-child matching card game.

Your job is to make the game feel safe, light, and fun for a child who may be hesitant to speak.

Rules:
- Never mention selective mutism, anxiety, therapy, progress, stages, confidence, or bravery.
- Never pressure the child to talk.
- Never say "use your words."
- Never sound disappointed.
- Never overpraise.
- Keep attention on the game, not on the child.
- Use exactly one short sentence.
- No quotation marks.
- Do not repeat these recent messages: {recent_messages}

Current stage:
{stage_rules.get(stage, stage_rules[0])}

Question rule:
{ask_rules.get(ask_type, ask_rules["none"])}

Context:
Event type: {event_type}
Card: {card_name}
Current player: {player}
Child name: {child_name}

Good examples:
Nice flip.
That was close.
The turtle is sneaky.
Good memory.
Ooo, almost.
Should we try this one?
Cat or dog?
Was that a match?

Generate one Star line only.
"""

    try:
        text_response = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt
        )

        message = text_response.output_text.strip().replace('"', "")

        audio_bytes = generate_star_voice_elevenlabs(message)

        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
        # audio_base64 = base64.b64encode(speech_response.content).decode("utf-8")

        # audio_base64 = base64.b64encode(speech_response.content).decode("utf-8")

        return jsonify({
            "success": True,
            "message": message,
            "audio": f"data:audio/mpeg;base64,{audio_base64}",
            "ask_type": ask_type
        })

    except Exception as e:
        print("Matching game AI error:", e)
        return jsonify({
            "success": False,
            "error": "Could not generate message"
        }), 500

@app.route("/api/mystery-animal/message", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("30 per minute")
def mystery_animal_message():
    data = request.get_json(silent=True) or {}

    event_type = data.get("event_type", "intro")
    child_response = data.get("child_response", "").strip()
    response_mode = data.get("response_mode", "none")

    child_name = session.get("child_name", "there")

    if event_type == "restart":
        session.pop("mystery_animal_history", None)
        session.pop("mystery_animal_state", None)

    history = session.get("mystery_animal_history", [])

    game_state = session.get("mystery_animal_state", {
        "stage": "intro",
        "questions_asked": 0,
        "comfortable_answer_count": 0,
        "unclear_or_silent_count": 0,
        "question_history": [],
        "known_clues": [],
        "rejected_guesses": [],
        "possible_guess": None
    })

    system_prompt = """
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
- Never ask abstract emotion questions like "Are you having fun?"
- Keep attention on the animal game, not on the child.
- Ask only one question at a time.
- Do not repeat previous questions.
- Use the clues already given.
- If the child gives no answer, an unclear answer, or seems stuck, make the next question easier.
- If the child answers comfortably several times, you may gently increase verbal demand.

Voice style:
Star should sound warm, gentle, playful, calm, and mascot-like.
Not babyish. Not hyper. Not teacher-like.

Natural thinking:
Star may sometimes begin with a tiny thinking phrase, but not every time.
Examples:
- "Hmm..."
- "Ooo, let me think..."
- "Okay, I have an idea..."
- "Hmm, I'm not sure yet..."
- "Let me think for a second..."

Keep thinking phrases short and natural.

Progression logic:
1. intro:
   Explain the game simply. Ask the child to think of any animal. Say Star will ask tiny clues to guess it.
2. yes_no:
   Ask concrete yes/no questions.
   Examples: "Does it live in water?" "Can it fly?" "Is it bigger than a dog?"
3. forced_choice:
   Ask two-option questions.
   Examples: "Is it furry or scaly?" "Does it live on land or in water?"
4. one_word:
   Ask for one simple word.
   Examples: "What color is it?" "Where does it live?" "What sound does it make?"
5. short_phrase:
   Ask for a tiny clue.
   Examples: "What does it like to eat?" "Tell me one tiny clue."
6. open_hint:
   Only use after the child has shown comfort with shorter answers.
   Example: "Hmm, can you give me any hint you want?"
7. guess:
   Guess the animal when there are enough clues.

Stage movement:
- Stay in yes_no early.
- Move up only after repeated clear responses.
- Move down if the child is silent, unclear, or gives very limited responses after harder prompts.
- Do not jump to open-ended hints too early.

Output JSON only:
{
  "message": "Star's spoken line",
  "stage": "intro | yes_no | forced_choice | one_word | short_phrase | open_hint | guess",
  "expects_response": true,
  "response_mode": "none | yes_no | choice | one_word | short_phrase | open_hint",
  "is_question": true,
  "question_text": "the question Star asked, or null",
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
- If event_type is "intro" or "restart", start the game gently.
- If child_response is empty, unclear, "I don't know", or silence, count it as unclear_or_silent.
- If child_response is a clear answer to Star's last question, count it as comfortable.
- If the last Star question was yes/no, interpret yes/no as a clue.
- If Star guessed and the child says no, add the guess to rejected_guesses.
- If Star guessed and the child says yes, respond warmly and finish the round.

Important:
Update the state based on the child response before choosing the next line.
Ask a useful next question that narrows down the animal.
Do not repeat any question in question_history.
If there are not enough clues, do not guess yet.
If there are enough clues, make one playful guess.
Generate the next Star line now.
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
            message = "Hmm... does it live on land?"

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

        history.append({
            "event_type": event_type,
            "child_response": child_response,
            "star": message,
            "stage": parsed.get("stage"),
            "response_mode": parsed.get("response_mode")
        })

        session["mystery_animal_history"] = history[-20:]
        session["mystery_animal_state"] = game_state
        session.modified = True

        audio_bytes = generate_star_voice_elevenlabs(message)
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

        return jsonify({
            "success": True,
            "message": message,
            "audio": f"data:audio/mpeg;base64,{audio_base64}",
            "stage": parsed.get("stage"),
            "expects_response": parsed.get("expects_response", True),
            "response_mode": parsed.get("response_mode", "yes_no"),
            "game_state": game_state
        })

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
    
@app.route("/api/guessing-game/message", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("30 per minute")
def guessing_game_message():
    data = request.get_json(silent=True) or {}

    event_type = data.get("event_type", "intro")
    child_response = data.get("child_response", "").strip()
    response_mode = data.get("response_mode", "none")

    child_name = session.get("child_name", "there")

    if event_type == "restart":
        session.pop("guessing_game_history", None)
        session.pop("guessing_game_state", None)

    history = session.get("guessing_game_history", [])

    easy_animals = [
        "dog", "cat", "fish", "bird", "horse", "cow", "pig", "duck",
        "chicken", "rabbit", "lion", "tiger", "bear", "monkey",
        "elephant", "giraffe", "zebra", "kangaroo", "penguin",
        "dolphin", "whale", "shark", "turtle", "frog", "owl",
        "panda", "koala", "seal", "otter"
    ]

    game_state = session.get("guessing_game_state")

    if not game_state:
        import random
        secret_animal = random.choice(easy_animals)

        game_state = {
            "stage": "intro",
            "secret_animal": secret_animal,
            "questions_asked": 0,
            "comfortable_question_count": 0,
            "unclear_or_silent_count": 0,
            "hint_count": 0,
            "wrong_guesses": [],
            "asked_questions": [],
            "game_complete": False
        }

    system_prompt = """
You are Star, a warm animated star mascot playing an animal guessing game.

Star is thinking of one secret animal. The child is trying to guess it.

The child can:
- Ask Star yes/no questions.
- Ask for a hint.
- Make a guess whenever they think they know the animal.

Core goal:
Help the child have a real back-and-forth conversation while keeping the game light and safe.

Hard rules:
- Never mention selective mutism, anxiety, therapy, treatment, exposure, stages, progress, confidence, or bravery.
- Never pressure the child to speak.
- Never say "use your words."
- Never sound disappointed.
- Never overpraise.
- Never make the child feel evaluated.
- Keep attention on the animal game, not on the child.
- Do not reveal the animal unless the child guesses correctly or the game is clearly ending.
- If the child is silent, unclear, or stuck, gently help the game continue.
- If the child asks a question, answer it clearly and briefly.
- If the child asks for a hint, give one helpful hint.
- If the child guesses wrong, say it is not that animal and offer a tiny clue.
- If the child guesses correctly, celebrate warmly and end the round.
- Do not choose hard or obscure animals.
- Keep Star's response to 1-3 short sentences.

Voice style:
Warm, playful, calm, mascot-like.
Not babyish. Not hyper. Not teacher-like.

Intro:
For intro or restart, say something like:
"I'm thinking of an animal. You can ask me questions, ask for a hint, or guess whenever you think you know it. Are you ready?"

Silence/stuck handling:
If the child says nothing or gives an unclear response:
- Do not say "I couldn't hear you."
- Do not call attention to silence.
- Offer an easy way back into the game.
Examples:
"Want a tiny hint?"
"You can ask me, 'Does it live in water?'"
"I'll give you a clue. This animal is one many kids know."

Conversation behavior:
If the child asks a good question, answer it and lightly invite another turn.
Examples:
"Yes, it lives on land. What else should we check?"
"Nope, it does not fly. Want another clue?"
"Yes, it can be very big."

If the child seems comfortable, Star can gently bounce off their thinking:
Examples:
"Ooo, interesting question."
"That's a smart thing to check."
"You're looking in the right direction."

Output JSON only:
{
  "message": "Star's spoken line",
  "stage": "intro | answering | hint | wrong_guess | correct_guess | support",
  "expects_response": true,
  "response_mode": "open_hint",
  "game_complete": false,
  "state_update": {
    "comfortable_question_delta": 0,
    "unclear_or_silent_delta": 0,
    "questions_asked_increment": 0,
    "hint_increment": 0,
    "asked_question": null,
    "wrong_guess": null
  }
}
"""

    user_prompt = f"""
Child name:
{child_name}

Secret animal:
{game_state["secret_animal"]}

Current game state:
{game_state}

Recent history:
{history[-12:]}

New event:
event_type: {event_type}
child_response: {child_response}
previous_response_mode: {response_mode}

Interpretation help:
- If event_type is intro or restart, introduce the game.
- If event_type is no_response, treat it as silence or uncertainty.
- If child_response is empty, unclear, "I don't know", or unrelated, count it as unclear_or_silent.
- If the child asks for a hint, give a clue about the secret animal.
- If the child asks a yes/no question, answer truthfully based on the secret animal.
- If the child makes a guess, check whether it matches the secret animal.
- If the guess is correct, say they got it and set game_complete to true.
- If the guess is wrong, add it to wrong_guesses and give a small helpful clue.
- Do not reveal the secret animal unless the child guesses correctly.
- Keep the animal appropriate for young kids.

Generate the next Star response now.
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
                "stage": "answering",
                "expects_response": True,
                "response_mode": "open_hint",
                "game_complete": False,
                "state_update": {
                    "comfortable_question_delta": 0,
                    "unclear_or_silent_delta": 0,
                    "questions_asked_increment": 0,
                    "hint_increment": 0,
                    "asked_question": None,
                    "wrong_guess": None
                }
            }

        message = parsed.get("message", "").strip().replace('"', "")

        if not message:
            message = "I'm thinking of an animal. You can ask me a question, ask for a hint, or make a guess."

        state_update = parsed.get("state_update", {}) or {}

        game_state["stage"] = parsed.get("stage", game_state.get("stage", "answering"))

        game_state["comfortable_question_count"] = max(
            0,
            int(game_state.get("comfortable_question_count", 0))
            + int(state_update.get("comfortable_question_delta", 0))
        )

        game_state["unclear_or_silent_count"] = max(
            0,
            int(game_state.get("unclear_or_silent_count", 0))
            + int(state_update.get("unclear_or_silent_delta", 0))
        )

        game_state["questions_asked"] = int(game_state.get("questions_asked", 0)) + int(
            state_update.get("questions_asked_increment", 0)
        )

        game_state["hint_count"] = int(game_state.get("hint_count", 0)) + int(
            state_update.get("hint_increment", 0)
        )

        if state_update.get("asked_question"):
            game_state.setdefault("asked_questions", []).append(state_update["asked_question"])

        if state_update.get("wrong_guess"):
            game_state.setdefault("wrong_guesses", []).append(state_update["wrong_guess"])

        game_complete = bool(parsed.get("game_complete", False))
        game_state["game_complete"] = game_complete

        history.append({
            "event_type": event_type,
            "child_response": child_response,
            "star": message,
            "stage": parsed.get("stage"),
            "response_mode": parsed.get("response_mode"),
            "game_complete": game_complete
        })

        session["guessing_game_history"] = history[-20:]
        session["guessing_game_state"] = game_state
        session.modified = True

        audio_bytes = generate_star_voice_elevenlabs(message)
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

        return jsonify({
            "success": True,
            "message": message,
            "audio": f"data:audio/mpeg;base64,{audio_base64}",
            "stage": parsed.get("stage"),
            "expects_response": parsed.get("expects_response", True),
            "response_mode": parsed.get("response_mode", "open_hint"),
            "game_complete": game_complete,
            "game_state": game_state
        })

    except Exception as e:
        print("Guessing Game AI error:", e)
        return jsonify({
            "success": False,
            "error": "Could not generate Star response"
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
    
def generate_toy_trivia_voice_elevenlabs(text):
    voice_id = os.getenv("TOY_TRIVIA_VOICE_ID")

    if not voice_id:
        voice_id = os.getenv("ELEVENLABS_VOICE_ID", "piI8Kku0DcvcL6TTSeQt")

    response = eleven_client.text_to_speech.convert(
        voice_id=voice_id,
        text=text,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
        voice_settings={
            "stability": 0.86,
            "similarity_boost": 0.92,
            "style": 0.12,
            "use_speaker_boost": False
        }
    )

    return b"".join(response)


@app.route("/api/toy-trivia-game/message", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("30 per minute")
def toy_trivia_game_message():
    data = request.get_json(silent=True) or {}

    event_type = data.get("event_type", "intro")
    child_response = data.get("child_response", "").strip()
    response_mode = data.get("response_mode", "none")

    child_name = session.get("child_name", "there")

    if event_type == "restart":
        session.pop("toy_trivia_game_history", None)
        session.pop("toy_trivia_game_state", None)

    history = session.get("toy_trivia_game_history", [])

    game_state = session.get("toy_trivia_game_state", {
        "stage": "intro",
        "questions_answered": 0,
        "comfortable_answer_count": 0,
        "unclear_or_silent_count": 0,
        "current_toy": None,
        "current_question": None,
        "question_history": [],
        "game_complete": False
    })

    system_prompt = """
You are a warm, friendly toy store worker on a video call with a young child.

You are playing a simple Toy Trivia game.

Core game:
The toy store worker asks the child easy questions about familiar toys.
The child answers.
The worker responds warmly, gives tiny hints when needed, and continues the game.

The purpose is to create natural back-and-forth conversation.
Do not make it feel like a test.

Hard rules:
- Never mention selective mutism, anxiety, therapy, treatment, exposure, stages, progress, confidence, or bravery.
- Never pressure the child to speak.
- Never say "use your words."
- Never sound disappointed.
- Never overpraise.
- Never make the child feel evaluated.
- Keep attention on the toy store and the toys.
- Ask only one question at a time.
- Use simple, familiar toys.
- Avoid hard trivia.
- Avoid obscure toys.
- Keep each spoken line to 1-3 short sentences.

Toy examples:
teddy bear, blocks, toy car, doll, puzzle, ball, train, stuffed animal, kite, robot, crayons, jump rope, rubber duck, dinosaur toy, toy truck.

Question examples:
- I found a teddy bear. What color should it be?
- This toy has wheels and goes vroom. What is it?
- Should we look at blocks or toy cars?
- What toy would you take to the park?
- I found a puzzle. Should it have animals or shapes?
- This toy bounces. What do you think it is?
- Do you like the red truck or the blue truck?
- What animal should this stuffed animal be?

Conversation style:
Warm, playful, calm, and natural.
Not babyish. Not too energetic. Not teacher-like.
Sound like a friendly toy store worker helping the child explore the store.

Intro:
For intro or restart, introduce the premise.
Say something like:
"Hi! I'm calling from the toy store. I found so many toys, and I need your help with a toy trivia game. Are you ready?"

Silence or unclear response:
If the child says nothing, gives an unclear answer, or seems stuck:
- Do not say "I could not hear you."
- Do not call attention to silence.
- Make the next step easier.
Examples:
"Let's make it easy. Should we pick the red toy or the blue toy?"
"I'll give you a tiny hint. This toy has wheels."
"You can say car or truck."
"Want to try teddy bear or blocks?"

Difficulty movement:
- Start with yes/no or forced-choice questions.
- If the child answers clearly several times, ask one-word or tiny phrase questions.
- If the child is silent or unclear, return to easier choices.
- Keep the child supported without drawing attention to why.

Output JSON only:
{
  "message": "the toy store worker's spoken line",
  "stage": "intro | choice | yes_no | one_word | short_phrase | support | complete",
  "expects_response": true,
  "response_mode": "none | yes_no | choice | one_word | short_phrase",
  "game_complete": false,
  "question_text": "the question asked, or null",
  "state_update": {
    "comfortable_answer_delta": 0,
    "unclear_or_silent_delta": 0,
    "questions_answered_increment": 0,
    "current_toy": null
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
- If event_type is intro or restart, introduce the toy trivia game.
- If event_type is no_response, treat it as silence or uncertainty.
- If child_response is empty, unclear, "I don't know", or unrelated, count it as unclear_or_silent.
- If the child gives a clear answer, count it as comfortable.
- If the child has answered about 6 clear questions, end the round warmly and set game_complete to true.
- Do not make questions hard.
- Ask one simple toy-related question at a time.
- Keep the game flowing naturally.

Generate the next toy store worker line now.
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
                "stage": game_state.get("stage", "choice"),
                "expects_response": True,
                "response_mode": "choice",
                "game_complete": False,
                "question_text": raw.replace('"', ""),
                "state_update": {
                    "comfortable_answer_delta": 0,
                    "unclear_or_silent_delta": 0,
                    "questions_answered_increment": 0,
                    "current_toy": None
                }
            }

        message = parsed.get("message", "").strip().replace('"', "")

        if not message:
            message = "I found a toy car and some blocks. Which one should we look at first?"

        state_update = parsed.get("state_update", {}) or {}

        game_state["stage"] = parsed.get("stage", game_state.get("stage", "choice"))

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

        game_state["questions_answered"] = int(game_state.get("questions_answered", 0)) + int(
            state_update.get("questions_answered_increment", 0)
        )

        if state_update.get("current_toy"):
            game_state["current_toy"] = state_update["current_toy"]

        question_text = parsed.get("question_text")
        if question_text:
            game_state["current_question"] = question_text
            game_state.setdefault("question_history", []).append({
                "question": question_text,
                "stage": parsed.get("stage"),
                "response_mode": parsed.get("response_mode")
            })

        game_complete = bool(parsed.get("game_complete", False))

        if game_state.get("questions_answered", 0) >= 6:
            game_complete = True
            game_state["stage"] = "complete"

        game_state["game_complete"] = game_complete

        history.append({
            "event_type": event_type,
            "child_response": child_response,
            "character": message,
            "stage": parsed.get("stage"),
            "response_mode": parsed.get("response_mode"),
            "game_complete": game_complete
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
            "stage": parsed.get("stage"),
            "expects_response": parsed.get("expects_response", True) and not game_complete,
            "response_mode": parsed.get("response_mode", "choice"),
            "game_complete": game_complete,
            "game_state": game_state
        })

    except Exception as e:
        print("Toy Trivia AI error:", e)
        return jsonify({
            "success": False,
            "error": "Could not generate toy trivia response"
        }), 500


@app.route("/api/toy-trivia-game/transcribe", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("20 per minute")
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
        file_obj.name = "child-response.webm"

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

def generate_guessing_game_2_voice_elevenlabs(text):
    voice_id = os.getenv("TOY_TRIVIA_VOICE_ID")

    if not voice_id:
        voice_id = os.getenv("ELEVENLABS_VOICE_ID", "piI8Kku0DcvcL6TTSeQt")

    response = eleven_client.text_to_speech.convert(
        voice_id=voice_id,
        text=text,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
        voice_settings={
            "stability": 0.86,
            "similarity_boost": 0.92,
            "style": 0.12,
            "use_speaker_boost": False
        }
    )

    return b"".join(response)


@app.route("/api/guessing-game-2/message", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("30 per minute")
def guessing_game_2_message():
    data = request.get_json(silent=True) or {}

    event_type = data.get("event_type", "intro")
    child_response = data.get("child_response", "").strip()
    response_mode = data.get("response_mode", "none")

    child_name = session.get("child_name", "there")

    if event_type == "restart":
        session.pop("guessing_game_2_history", None)
        session.pop("guessing_game_2_state", None)

    history = session.get("guessing_game_2_history", [])

    easy_animals = [
        "dog", "cat", "fish", "bird", "horse", "cow", "pig", "duck",
        "chicken", "rabbit", "lion", "tiger", "bear", "monkey",
        "elephant", "giraffe", "zebra", "kangaroo", "penguin",
        "dolphin", "whale", "shark", "turtle", "frog", "owl",
        "panda", "koala", "seal", "otter"
    ]

    game_state = session.get("guessing_game_2_state")

    if not game_state:
        import random

        game_state = {
            "stage": "intro",
            "secret_animal": random.choice(easy_animals),
            "questions_asked": 0,
            "comfortable_question_count": 0,
            "unclear_or_silent_count": 0,
            "hint_count": 0,
            "wrong_guesses": [],
            "asked_questions": [],
            "game_complete": False
        }

    system_prompt = """
You are a warm, friendly toy store worker on a video call with a young child.

You are playing an animal guessing game from inside a toy store.

The toy store worker is thinking of one secret animal.
The child is trying to figure out the animal.

The child can:
- Ask yes/no questions.
- Ask for a hint.
- Make a guess whenever they think they know the animal.

Core goal:
Create a natural back-and-forth conversation.
The child should feel like they are leading the game by asking questions, asking for hints, or guessing.

Hard rules:
- Never mention selective mutism, anxiety, therapy, treatment, exposure, stages, progress, confidence, or bravery.
- Never pressure the child to speak.
- Never say "use your words."
- Never sound disappointed.
- Never overpraise.
- Never make the child feel evaluated.
- Keep attention on the animal game and the toy store.
- Do not reveal the secret animal unless the child guesses correctly.
- If the child is silent, unclear, or stuck, gently help the game continue.
- If the child asks a question, answer it clearly and briefly.
- If the child asks for a hint, give one helpful hint.
- If the child guesses wrong, say it is not that animal and offer a tiny clue.
- If the child guesses correctly, celebrate warmly and end the round.
- Do not choose hard or obscure animals.
- Keep each spoken line to 1-3 short sentences.

Voice style:
Warm, playful, calm, and natural.
Not babyish. Not hyper. Not teacher-like.
Sound like a friendly toy store worker helping the child play a guessing game.

Intro:
For intro or restart, say something like:
"Hi! I'm calling from the toy store, and I'm thinking of an animal. You can ask me questions, ask for a hint, or guess whenever you think you know it. Are you ready?"

Silence or stuck handling:
If the child says nothing, gives an unclear answer, or seems stuck:
- Do not say "I could not hear you."
- Do not call attention to silence.
- Offer an easy way back into the game.

Examples:
"Want a tiny hint?"
"You can ask me, does it live in water?"
"I'll give you a clue. This animal is one many kids know."
"You can ask about where it lives, what it eats, or how big it is."

Conversation behavior:
If the child asks a good question, answer it and lightly invite another turn.

Examples:
"Yes, it lives on land. What else should we check?"
"Nope, it does not fly. Want another clue?"
"Yes, it can be very big."
"Not quite. It is smaller than that."

If the child seems comfortable, the worker can gently bounce off their thinking:
Examples:
"Ooo, interesting question."
"That's a good thing to check."
"You're looking in the right direction."

Output JSON only:
{
  "message": "the toy store worker's spoken line",
  "stage": "intro | answering | hint | wrong_guess | correct_guess | support",
  "expects_response": true,
  "response_mode": "open_hint",
  "game_complete": false,
  "state_update": {
    "comfortable_question_delta": 0,
    "unclear_or_silent_delta": 0,
    "questions_asked_increment": 0,
    "hint_increment": 0,
    "asked_question": null,
    "wrong_guess": null
  }
}
"""

    user_prompt = f"""
Child name:
{child_name}

Secret animal:
{game_state["secret_animal"]}

Current game state:
{game_state}

Recent history:
{history[-12:]}

New event:
event_type: {event_type}
child_response: {child_response}
previous_response_mode: {response_mode}

Interpretation help:
- If event_type is intro or restart, introduce the game.
- If event_type is no_response, treat it as silence or uncertainty.
- If child_response is empty, unclear, "I don't know", or unrelated, count it as unclear_or_silent.
- If the child asks for a hint, give a clue about the secret animal.
- If the child asks a yes/no question, answer truthfully based on the secret animal.
- If the child makes a guess, check whether it matches the secret animal.
- If the guess is correct, say they got it and set game_complete to true.
- If the guess is wrong, add it to wrong_guesses and give a small helpful clue.
- Do not reveal the secret animal unless the child guesses correctly.
- Keep the animal appropriate for young kids.
- Keep the toy store worker's line short, warm, and natural.

Generate the next toy store worker response now.
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
                "stage": "answering",
                "expects_response": True,
                "response_mode": "open_hint",
                "game_complete": False,
                "state_update": {
                    "comfortable_question_delta": 0,
                    "unclear_or_silent_delta": 0,
                    "questions_asked_increment": 0,
                    "hint_increment": 0,
                    "asked_question": None,
                    "wrong_guess": None
                }
            }

        message = parsed.get("message", "").strip().replace('"', "")

        if not message:
            message = "I'm thinking of an animal. You can ask me a question, ask for a hint, or make a guess."

        state_update = parsed.get("state_update", {}) or {}

        game_state["stage"] = parsed.get("stage", game_state.get("stage", "answering"))

        game_state["comfortable_question_count"] = max(
            0,
            int(game_state.get("comfortable_question_count", 0))
            + int(state_update.get("comfortable_question_delta", 0))
        )

        game_state["unclear_or_silent_count"] = max(
            0,
            int(game_state.get("unclear_or_silent_count", 0))
            + int(state_update.get("unclear_or_silent_delta", 0))
        )

        game_state["questions_asked"] = int(game_state.get("questions_asked", 0)) + int(
            state_update.get("questions_asked_increment", 0)
        )

        game_state["hint_count"] = int(game_state.get("hint_count", 0)) + int(
            state_update.get("hint_increment", 0)
        )

        if state_update.get("asked_question"):
            game_state.setdefault("asked_questions", []).append(state_update["asked_question"])

        if state_update.get("wrong_guess"):
            game_state.setdefault("wrong_guesses", []).append(state_update["wrong_guess"])

        game_complete = bool(parsed.get("game_complete", False))
        game_state["game_complete"] = game_complete

        history.append({
            "event_type": event_type,
            "child_response": child_response,
            "character": message,
            "stage": parsed.get("stage"),
            "response_mode": parsed.get("response_mode"),
            "game_complete": game_complete
        })

        session["guessing_game_2_history"] = history[-20:]
        session["guessing_game_2_state"] = game_state
        session.modified = True

        audio_bytes = generate_guessing_game_2_voice_elevenlabs(message)
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

        return jsonify({
            "success": True,
            "message": message,
            "audio": f"data:audio/mpeg;base64,{audio_base64}",
            "stage": parsed.get("stage"),
            "expects_response": parsed.get("expects_response", True) and not game_complete,
            "response_mode": parsed.get("response_mode", "open_hint"),
            "game_complete": game_complete,
            "game_state": game_state
        })

    except Exception as e:
        print("Guessing Game 2 AI error:", e)
        return jsonify({
            "success": False,
            "error": "Could not generate guessing game 2 response"
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
        file_obj.name = "child-response.webm"

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
    
@app.route("/parent-academy")
@login_required
def parent_academy():
    return render_template(
        "parent_academy.html",
        active_page="parent_academy",
        parent=session["parent_name"],
        child=session["child_name"],
        profile_icon=session.get("profile_icon", "profileicon.png")
    )

def generate_librarian_voice_elevenlabs(text):
    voice_id = os.getenv("LIBRARIAN_VOICE_ID")

    if not voice_id:
        voice_id = os.getenv("ELEVENLABS_VOICE_ID", "piI8Kku0DcvcL6TTSeQt")

    response = eleven_client.text_to_speech.convert(
        voice_id=voice_id,
        text=text,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
        voice_settings={
            "stability": 0.88,
            "similarity_boost": 0.92,
            "style": 0.08,
            "use_speaker_boost": False
        }
    )

    return b"".join(response)


@app.route("/api/book-guessing-game/message", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("30 per minute")
def book_guessing_game_message():
    data = request.get_json(silent=True) or {}

    event_type = data.get("event_type", "intro")
    child_response = data.get("child_response", "").strip()
    response_mode = data.get("response_mode", "none")

    child_name = session.get("child_name", "there")

    if event_type == "restart":
        session.pop("book_guessing_game_history", None)
        session.pop("book_guessing_game_state", None)

    history = session.get("book_guessing_game_history", [])

    game_state = session.get("book_guessing_game_state", {
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
You are a warm, friendly librarian on a video call with a young child.

You are playing a Book Guessing Game.

The child is thinking of one specific book.
The librarian asks gentle questions to figure out which book it is.

Core goal:
Create a natural back-and-forth conversation.
The child should feel like they are helping the librarian solve a fun mystery.

Hard rules:
- Never mention selective mutism, anxiety, therapy, treatment, exposure, stages, progress, confidence, or bravery.
- Never pressure the child to speak.
- Never say "use your words."
- Never sound disappointed.
- Never overpraise.
- Never make the child feel evaluated.
- Keep attention on the book mystery and the library.
- Ask only one question at a time.
- Do not repeat previous questions.
- Use the clues already given.
- If the child gives no answer, an unclear answer, or seems stuck, make the next question easier.
- If the child answers comfortably several times, you may gently increase verbal demand.
- Do not make the child prove they know the book.
- Do not shame wrong or unclear answers.
- Keep each spoken line to 1-3 short sentences.

Voice style:
Warm, calm, curious, friendly, librarian-like.
Not babyish. Not hyper. Not teacher-like.

Good question areas:
- cover color
- animal or person on the cover
- main character
- setting
- whether it is funny, silly, sleepy, adventurous, or magical
- whether there are animals
- whether it has rhymes
- whether the child has read it at home or school
- tiny story clues

Avoid:
- asking for the author
- asking for exact publication details
- asking hard literary questions
- asking multiple questions at once

Progression logic:
1. intro:
   Explain the game simply.
   Ask the child to think of a book.
   Say the librarian will ask tiny clues to guess it.
2. yes_no:
   Ask concrete yes/no questions.
   Examples:
   "Is there an animal in the book?"
   "Is the cover mostly blue?"
   "Is the story funny?"
3. forced_choice:
   Ask two-option questions.
   Examples:
   "Is it about an animal or a person?"
   "Is it silly or sleepy?"
4. one_word:
   Ask for one simple word.
   Examples:
   "What color is the cover?"
   "Who is in the book?"
5. short_phrase:
   Ask for a tiny clue.
   Examples:
   "What happens in the story?"
   "Tell me one tiny clue."
6. guess:
   Guess the book when there are enough clues.

Silence or stuck handling:
If the child says nothing or gives an unclear response:
- Do not say "I could not hear you."
- Do not call attention to silence.
- Offer an easier path.

Examples:
"Let's make it easy. Is there an animal in the book?"
"Hmm, I can ask a tiny question. Is the cover bright?"
"You can say yes or no."
"Is it a silly book or a sleepy book?"

Output JSON only:
{
  "message": "the librarian's spoken line",
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
- If child_response is a clear answer to the librarian's last question, count it as comfortable.
- If the librarian guessed and the child says no, add the guess to rejected_guesses.
- If the librarian guessed and the child says yes, respond warmly and finish the round.
- Update the state based on the child response before choosing the next line.
- Ask a useful next question that narrows down the book.
- Do not repeat any question in question_history.
- If there are not enough clues, do not guess yet.
- If there are enough clues, make one gentle guess.
- Avoid guessing too early unless the book is very clear.
- Keep it easy and friendly for young children.

Generate the next librarian line now.
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
            message = "I'm ready for the book mystery. Is there an animal in your book?"

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
            "librarian": message,
            "stage": parsed.get("stage"),
            "response_mode": parsed.get("response_mode"),
            "game_complete": game_complete
        })

        session["book_guessing_game_history"] = history[-20:]
        session["book_guessing_game_state"] = game_state
        session.modified = True

        audio_bytes = generate_librarian_voice_elevenlabs(message)
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
        print("Book Guessing Game AI error:", e)
        return jsonify({
            "success": False,
            "error": "Could not generate librarian response"
        }), 500


@app.route("/api/book-guessing-game/transcribe", methods=["POST"])
@csrf.exempt
@login_required
@limiter.limit("20 per minute")
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
        file_obj.name = "child-response.webm"

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
- Do not repeat previous questions.
- Use the clues already given.
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
        profile_icon=session.get("profile_icon", "profileicon.png")
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

if __name__ == "__main__":
    app.run(debug=app.config["DEBUG"])
