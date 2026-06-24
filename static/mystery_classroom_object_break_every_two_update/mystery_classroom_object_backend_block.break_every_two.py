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
