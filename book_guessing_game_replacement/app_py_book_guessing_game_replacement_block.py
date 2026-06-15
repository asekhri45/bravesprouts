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
        "rounds_completed": int(rounds_completed or 0),
        "skip_guess_once": False,
        "guess_cooldown_questions": 0,
        "last_acknowledgment_index": -1,
        "clear_answer_word_counts": [],
        "recent_question_families": [],
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
        "don't know",
        "dont know",
        "idk",
        "not sure",
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


def get_question_family(question):
    lowered = normalize_child_text(question).lower()

    if any(word in lowered for word in ["animal", "dog", "cat", "bear", "pig", "spider", "caterpillar"]):
        return "animal"

    if any(word in lowered for word in ["person", "kid", "character", "who", "main character"]):
        return "character"

    if any(word in lowered for word in ["color", "cover", "blue", "red", "green", "bright", "dark"]):
        return "cover"

    if any(word in lowered for word in ["funny", "silly", "serious", "sleepy", "magical", "adventure"]):
        return "tone"

    if any(word in lowered for word in ["picture", "chapter", "short", "long", "pages"]):
        return "format"

    if any(word in lowered for word in ["home", "school", "library", "far away", "place", "where"]):
        return "place"

    if any(word in lowered for word in ["hint", "clue", "know", "guess", "favorite"]):
        return "hint"

    return "general"


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
            "That's okay, we can keep going.",
            "No worries."
        ]

        prefix_index = int(game_state.get("unclear_or_silent_count", 0)) % len(calm_prefixes)
        message = f"{calm_prefixes[prefix_index]} {question_text}"
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
- Do not repeat previous questions.
- Use the clues already given.
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
    