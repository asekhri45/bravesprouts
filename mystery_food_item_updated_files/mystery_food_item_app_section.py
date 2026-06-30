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

