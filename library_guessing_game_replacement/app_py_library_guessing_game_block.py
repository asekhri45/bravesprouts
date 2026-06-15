# =========================
# Library Guessing Game — Librarian thinks of an elementary-school object
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
            "You can carry school things in this.",
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
        "rounds_completed": int(rounds_completed or 0),
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
        return "I'm thinking of a school object."

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
        ("general", "You can ask me a yes or no school-object question.")
    ]

    fresh_topic_lines = [
        line for topic, line in topic_options
        if topic not in asked_topics and line not in recent_support_lines
    ]

    general_fallbacks = [
        "I can answer school-object questions best.",
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

The librarian is thinking of one secret object that can be found in an elementary school.
The child is asking questions to guess it.

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
- Keep the focus on the school object game.
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

Answer the child's question about the secret school object without revealing the object's name.
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
    game_state["rounds_completed"] = rounds_completed
    game_state["game_complete"] = True

    if rounds_completed >= LIBRARY_GUESSING_GAME_MAX_ROUNDS:
        unlock_library_guessing_game_next_activity_for_user()

        message = (
            f"{base_message} "
            "That was our last school object for today. "
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
            "Hi, I'm the librarian. I'm thinking of something you can find in an elementary school. You can ask me questions, ask for a hint, or guess whenever you know it.",
            "Hi, I'm the librarian. I picked a school object. You can ask questions to figure it out.",
            "Hi, I'm the librarian. I have an elementary school object in my head. Ask me anything about it.",
            "Hi, I'm the librarian. Let's play Library Guessing Game. I picked one school object, and you can ask me questions."
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
                "I have my last school object for today. What do you want to ask first?",
                "Okay, I picked our last school object for today. It's time to guess.",
                "I am thinking of the last school object now. You can ask me a question.",
                "Last object for today. What is your first question?"
            ]
        else:
            prompts = [
                "I have my school object. What do you want to ask first?",
                "I am thinking of it now. You can ask me a question.",
                "My school object is ready. What do you want to know?",
                "I picked one. You can ask your first question."
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
                    "Okay. Let's play one more game before we end our call today. I picked a new school object.",
                    "Okay. One more school object for today. I have a new one in my head.",
                    "Sure. This will be our last school object today. I picked one."
                ]
            else:
                replay_prompts = [
                    "Okay. I picked a new school object.",
                    "Sure. I have a different school object now.",
                    "Okay. New school object.",
                    "Let's do another one. I picked a different school object."
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
        "You can ask me a yes or no school-object question.",
        "You can ask me about the school object.",
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
