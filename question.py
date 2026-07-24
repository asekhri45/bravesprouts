"""Decision-tree question selection for Mystery Animal.

There are exactly 60 early-round spoken question variants below. The selector
scores useful concepts against the remaining animal candidates, then chooses a
natural wording variant without repeating a question key in the same session.

Two properties this module is responsible for:

1. An answer is only turned into a fact when the wording actually supports it.
   The previous matcher tested `label in answer`, so "no fur" matched the "fur"
   label, "no wings" matched "wings", and "no tail" matched "tail" -- every
   negative answer was recorded as its own opposite, which both eliminated the
   correct candidates and made later questions assert traits the child had
   denied. Matching now understands negation and per-label phrasing, and
   returns "unknown" rather than guessing when an answer is ambiguous.

2. A question may only assert a trait the evidence has already established.
   Nodes whose wording states something about the animal ("Does the two-legged
   animal fly?") carry a `requires` precondition and are skipped until every
   remaining candidate agrees with it.
"""
from __future__ import annotations

import math
import random
import re
from typing import Dict, List, Optional, Set

from animal_database import ANIMALS


def _q(key, feature, values, *variants, applies=None, requires=None, synonyms=None):
    """One question concept.

    feature  -- the animal_database field the answer narrows.
    values   -- label -> the dataset values that label selects.
    applies  -- only ask when every surviving candidate's value for `feature`
                is already inside this set (the question presupposes it).
    requires -- {feature: allowed_values} that the question's *wording*
                asserts. Only asked once every surviving candidate agrees, so
                Star can never state a trait the child has not established.
    synonyms -- label -> extra phrases a child might say for that label.
    """
    return {
        "key": key,
        "feature": feature,
        "values": values,
        "variants": list(variants),
        "applies": applies,
        "requires": requires or {},
        "synonyms": synonyms or {},
    }


# 30 concepts x 2 natural phrasings = exactly 60 early-round questions.
EARLY_QUESTION_NODES = [
    _q("habitat_land_water", "habitat", {"land": {"land"}, "water": {"water"}, "both": {"both"}},
       "Does it live mostly on land, or mostly in water?",
       "Would I look for it on land, or in the water?",
       synonyms={"land": ["on land", "ground", "dry land"],
                 "water": ["in water", "ocean", "sea", "lake", "river", "pond"],
                 "both": ["both", "either", "sometimes both", "land and water"]}),
    _q("water_only_both", "habitat", {"water": {"water"}, "both": {"both"}},
       "Does it stay in the water, or come onto land too?",
       "Is it always in water, or does it spend time on land too?",
       applies={"water", "both"},
       requires={"habitat": {"water", "both"}},
       synonyms={"water": ["stays in water", "always in water", "only water"],
                 "both": ["comes out", "comes onto land", "both", "sometimes land"]}),
    _q("size_cat", "size", {"small": {"tiny", "small"}, "big": {"medium", "large", "huge"}},
       "Is it smaller than a cat, or bigger than a cat?",
       "Would you say it is cat-sized or smaller, or larger than that?",
       synonyms={"small": ["smaller", "littler", "tiny", "little"],
                 "big": ["bigger", "larger", "huge", "large"]}),
    _q("size_hand", "size", {"hand": {"tiny"}, "larger": {"small", "medium", "large", "huge"}},
       "Could it fit in your hand, or is it bigger?",
       "Is it small enough to hold in one hand, or too big for that?",
       synonyms={"hand": ["fits", "in my hand", "fit in my hand", "yes it fits"],
                 "larger": ["bigger", "too big", "does not fit", "doesn't fit", "larger"]}),
    _q("size_person", "size", {"smaller": {"tiny", "small", "medium"}, "bigger": {"large", "huge"}},
       "Is it smaller than a person, or bigger than a person?",
       "Would it be shorter than you, or taller and bigger?",
       synonyms={"smaller": ["smaller", "shorter", "littler"],
                 "bigger": ["bigger", "taller", "larger", "huge"]}),
    _q("legs_over_four", "legs", {"many": {"six", "eight", "many"}, "few": {"zero", "two", "four"}},
       "Does it have more than four legs, or four or fewer?",
       "Are there lots of legs, or no more than four?",
       synonyms={"many": ["more than four", "lots", "six", "eight", "many legs"],
                 "few": ["four or fewer", "fewer", "four", "two", "none", "no legs"]}),
    _q("legs_many_split", "legs", {"six": {"six"}, "eight": {"eight"}, "many": {"many"}},
       "Does it have six legs, eight legs, or lots more than eight?",
       "Would you count six legs, eight legs, or too many to count quickly?",
       applies={"six", "eight", "many"},
       requires={"legs": {"six", "eight", "many"}},
       synonyms={"six": ["six", "6"], "eight": ["eight", "8"], "many": ["lots", "more than eight", "too many"]}),
    _q("legs_four_less", "legs", {"four": {"four"}, "less": {"zero", "two"}},
       "Does it have four legs, or fewer than four?",
       "Would you count four legs, or less than four?",
       applies={"zero", "two", "four"},
       requires={"legs": {"zero", "two", "four"}},
       synonyms={"four": ["four", "4"], "less": ["fewer", "less", "two", "none", "no legs", "zero"]}),
    _q("legs_two_zero", "legs", {"two": {"two"}, "zero": {"zero"}},
       "Does it have two legs, or no legs?",
       "Would I see two legs, or none at all?",
       applies={"zero", "two"},
       requires={"legs": {"zero", "two"}},
       synonyms={"two": ["two", "2"], "zero": ["no legs", "none", "zero", "not any", "0"]}),
    _q("fur_branch", "covering", {"fur": {"fur", "hair", "wool"}, "other": {"feathers", "scales", "skin", "shell", "spikes"}},
       "Does it have fur, or is its body covered another way?",
       "Would it feel furry, or not really furry?",
       synonyms={"fur": ["fur", "furry", "hairy", "hair", "fluffy", "wool"],
                 "other": ["another way", "different", "not furry", "no fur"]}),
    _q("feather_branch", "covering", {"feathers": {"feathers"}, "other": {"scales", "skin", "shell", "spikes"}},
       "Does it have feathers, or a different covering?",
       "Would you see feathers on it, or something else?",
       applies={"feathers", "scales", "skin", "shell", "spikes"},
       synonyms={"feathers": ["feathers", "feathery"], "other": ["different", "something else", "no feathers"]}),
    _q("scales_branch", "covering", {"scales": {"scales"}, "other": {"skin", "shell", "spikes"}},
       "Does it have scales, or does its body look different?",
       "Would you call it scaly, or not scaly?",
       applies={"scales", "skin", "shell", "spikes"},
       synonyms={"scales": ["scales", "scaly"], "other": ["different", "not scaly", "no scales", "smooth"]}),
    _q("shell_branch", "shell", {"shell": {True}, "none": {False}},
       "Does it have a shell, or no shell?",
       "Can it hide in a shell, or does it not have one?",
       synonyms={"shell": ["shell", "has a shell", "hard shell"],
                 "none": ["no shell", "none", "does not", "doesn't", "not have one"]}),
    _q("wings_branch", "wings", {"wings": {True}, "none": {False}},
       "Does it have wings, or no wings?",
       "Would I see wings on it, or not?",
       synonyms={"wings": ["wings", "has wings", "winged"],
                 "none": ["no wings", "none", "not", "does not", "doesn't"]}),
    _q("flight_branch", "movement", {"fly": {"fly"}, "ground": {"walk", "run", "crawl", "hop", "jump", "slither", "climb", "swing"}},
       "Does it usually fly, or stay closer to the ground?",
       "Would it move through the air, or mostly stay down low?",
       synonyms={"fly": ["fly", "flies", "flying", "air"],
                 "ground": ["ground", "stays down", "walks", "does not fly", "doesn't fly", "no flying"]}),
    _q("swim_branch", "movement", {"swim": {"swim", "float"}, "other": {"walk", "run", "crawl", "hop", "jump", "slither", "climb", "swing", "fly"}},
       "Does it usually swim, or move another way?",
       "Would I see it swimming most, or doing something else?",
       synonyms={"swim": ["swim", "swims", "swimming"],
                 "other": ["another way", "something else", "does not swim", "doesn't swim"]}),
    _q("climb_branch", "movement", {"climb": {"climb", "swing"}, "ground": {"walk", "run", "crawl", "hop", "jump", "slither"}},
       "Does it usually climb, or stay on the ground?",
       "Would it go up trees and walls, or keep closer to the ground?",
       synonyms={"climb": ["climb", "climbs", "climbing", "up trees"],
                 "ground": ["ground", "stays down", "does not climb", "doesn't climb"]}),
    _q("hop_walk", "movement", {"hop": {"hop", "jump"}, "walk": {"walk", "run", "crawl"}},
       "Does it hop and jump, or mostly walk and run?",
       "Would it bounce along, or move with regular steps?",
       synonyms={"hop": ["hop", "hops", "jump", "jumps", "bounce"],
                 "walk": ["walk", "walks", "run", "runs", "steps"]}),
    _q("slither_other", "movement", {"slither": {"slither"}, "other": {"walk", "run", "crawl", "hop", "jump", "climb", "swing"}},
       "Does it slither, or move some other way?",
       "Would it slide along without legs, or not?",
       synonyms={"slither": ["slither", "slithers", "slides", "wriggles"],
                 "other": ["other way", "something else", "does not slither", "doesn't slither"]}),
    _q("pet_wild", "setting", {"pet": {"pet"}, "outside": {"wild", "farm"}},
       "Would people keep it as a pet, or would it usually live outside?",
       "Would it live in someone's home, or mostly somewhere else?",
       synonyms={"pet": ["pet", "at home", "in a house", "people keep it"],
                 "outside": ["outside", "wild", "farm", "not a pet", "somewhere else"]}),
    _q("farm_wild", "setting", {"farm": {"farm"}, "wild": {"wild"}},
       "Would you see it on a farm, or in the wild?",
       "Does it usually live around farms, or away in nature?",
       applies={"farm", "wild"},
       synonyms={"farm": ["farm", "barn"], "wild": ["wild", "nature", "forest", "jungle", "zoo"]}),
    _q("tail_branch", "tail", {"tail": {True}, "none": {False}},
       "Does it have a tail, or no tail?",
       "Would I notice a tail behind it, or not?",
       synonyms={"tail": ["tail", "has a tail"],
                 "none": ["no tail", "none", "not", "does not", "doesn't"]}),
    _q("night_day", "time", {"night": {"night"}, "day": {None, "day"}},
       "Would you usually see it at night, or during the day?",
       "Is it more of a nighttime animal, or a daytime animal?",
       synonyms={"night": ["night", "nighttime", "dark"], "day": ["day", "daytime", "morning"]}),
    _q("water_land_move", "movement", {"swim": {"swim", "float"}, "land": {"walk", "run", "crawl", "hop", "jump"}},
       "Does it spend more time swimming, or moving on land?",
       "Would it be moving in water, or moving on the ground?",
       synonyms={"swim": ["swim", "swimming", "water"], "land": ["land", "ground", "walking"]}),
    # Wording asserts the animal is tiny -- gated on size being established.
    _q("tiny_insect_wings", "wings", {"wings": {True}, "none": {False}},
       "Can the little animal fly, or does it stay on the ground?",
       "Does this tiny animal use wings, or only its legs?",
       requires={"size": {"tiny"}},
       synonyms={"wings": ["fly", "flies", "wings"],
                 "none": ["ground", "legs", "does not fly", "doesn't fly", "no wings"]}),
    _q("large_water_air", "movement", {"surface": {"swim", "float"}, "land": {"walk", "crawl"}},
       "Does it swim most of the time, or rest on land too?",
       "Would it stay in the water, or climb out sometimes?",
       requires={"habitat": {"water", "both"}},
       synonyms={"surface": ["swims", "stays in water", "most of the time"],
                 "land": ["land", "climbs out", "rests", "comes out"]}),
    # Wording asserts four legs.
    _q("four_leg_climb", "movement", {"climb": {"climb", "swing"}, "ground": {"walk", "run"}},
       "Does the four-legged animal climb, or mostly walk on the ground?",
       "Would it go up trees, or stay down on the ground?",
       requires={"legs": {"four"}},
       synonyms={"climb": ["climb", "climbs", "up trees"], "ground": ["ground", "walk", "walks"]}),
    # Wording asserts two legs.
    _q("two_leg_fly", "movement", {"fly": {"fly"}, "ground": {"walk", "run", "swim"}},
       "Does the two-legged animal fly, or mostly stay down?",
       "Would those two legs belong to a flyer, or an animal that stays on the ground?",
       requires={"legs": {"two"}},
       synonyms={"fly": ["fly", "flies", "flying"], "ground": ["ground", "stays down", "walks", "does not fly"]}),
    # Wording asserts no legs.
    _q("zero_leg_water", "habitat", {"water": {"water", "both"}, "land": {"land"}},
       "Does the animal with no legs live in water, or on land?",
       "Would I find this legless animal in water, or on the ground?",
       requires={"legs": {"zero"}},
       synonyms={"water": ["water", "ocean", "sea"], "land": ["land", "ground"]}),
    # Wording asserts lots of legs.
    _q("many_leg_water", "habitat", {"water": {"water", "both"}, "land": {"land"}},
       "Does the animal with lots of legs live in water, or on land?",
       "Would those many legs be underwater, or on dry land?",
       requires={"legs": {"six", "eight", "many"}},
       synonyms={"water": ["water", "ocean", "sea"], "land": ["land", "ground", "dry land"]}),
]

DETAIL_QUESTIONS = [
    ("main_color", "What color is it?"), ("movement_detail", "How does it move?"),
    ("usual_place", "Where does it live?"), ("food", "What does it eat?"),
    ("sound_detail", "What sound does it make?"), ("number_of_legs", "How many legs does it have?"),
    ("body_covering", "What covers its body?"), ("tail_detail", "What does its tail look like?"),
    ("size_detail", "About how big is it?"), ("face_detail", "What does its face look like?"),
]

HINT_QUESTIONS = [
    ("look_sentence", "Tell me what it looks like."), ("action_sentence", "Tell me what it does."),
    ("home_sentence", "Tell me where it lives."), ("body_clue", "Give me one clue about its body."),
    ("movement_clue", "Give me one clue about how it moves."), ("sound_clue", "What sound does it make?"),
    ("face_clue", "What does its face look like?"), ("feet_clue", "What do its feet or legs look like?"),
]


# ---------------------------------------------------------------------------
# Rounds 4-6: open-ended questions
# ---------------------------------------------------------------------------
# Rounds 1-3 use the two-way choice questions above and must stay exactly as
# they are. Rounds 4-6 step up to open-ended questions: Star names the thing it
# wants to know and, only where the question would otherwise be hard for a
# five-year-old, offers at most TWO examples as scaffolding. The examples never
# limit the answer -- the synonym tables below are far wider than the examples,
# so "it runs", "it slithers" and "it walks on four legs" all read correctly
# against a question that only mentioned walking and flying.
#
# Every key is prefixed `open_` so these can never collide with, or be selected
# by, the rounds 1-3 path.
OPEN_ENDED_NODES = [
    _q("open_movement", "movement",
       {"walk": {"walk", "run"}, "hop": {"hop", "jump"}, "swim": {"swim", "float"},
        "fly": {"fly"}, "slither": {"slither"}, "crawl": {"crawl"}, "climb": {"climb", "swing"}},
       "How does it move around? For example, does it walk or fly?",
       "How does your animal get from place to place? For example, walking or swimming?",
       synonyms={
           "walk": ["walk", "walks", "walking", "run", "runs", "running", "gallops",
                    "trots", "waddles", "on four legs", "on two legs", "steps"],
           "hop": ["hop", "hops", "hopping", "jump", "jumps", "jumping", "bounces", "leaps"],
           "swim": ["swim", "swims", "swimming", "paddles", "floats", "in the water"],
           "fly": ["fly", "flies", "flying", "flaps", "in the air", "wings"],
           "slither": ["slither", "slithers", "slithering", "slides", "wriggles", "wiggles"],
           "crawl": ["crawl", "crawls", "crawling", "scuttles"],
           "climb": ["climb", "climbs", "climbing", "swings", "up trees"],
       }),
    _q("open_covering", "covering",
       {"fur": {"fur", "hair", "wool"}, "feathers": {"feathers"}, "scales": {"scales"},
        "shell": {"shell"}, "skin": {"skin"}, "spikes": {"spikes"}},
       "What covers its body? For example, fur or smooth skin?",
       "What does its body feel like? For example, furry or smooth?",
       synonyms={
           "fur": ["fur", "furry", "fluffy", "hair", "hairy", "wool", "woolly", "soft"],
           "feathers": ["feathers", "feathery", "feathered"],
           "scales": ["scales", "scaly", "scaley"],
           "shell": ["shell", "hard shell", "shelly"],
           "skin": ["smooth", "smooth skin", "slimy", "slippery", "bare skin", "just skin", "wet"],
           "spikes": ["spikes", "spiky", "prickly", "quills", "spines", "pointy"],
       }),
    _q("open_habitat", "habitat",
       {"land": {"land"}, "water": {"water"}, "both": {"both"}},
       "Where does it usually live? For example, on land or in water?",
       "Where does your animal spend most of its time?",
       synonyms={
           "land": ["land", "on land", "ground", "dry land", "forest", "jungle", "woods",
                    "desert", "grass", "trees", "house", "home", "farm", "outside"],
           "water": ["water", "in the water", "ocean", "sea", "lake", "river", "pond", "underwater"],
           "both": ["both", "land and water", "either", "sometimes both", "in and out"],
       }),
    _q("open_setting", "setting",
       {"pet": {"pet"}, "farm": {"farm"}, "wild": {"wild"}},
       "Where would you usually find it? For example, at home or in the wild?",
       "Who does it usually live around?",
       synonyms={
           "pet": ["pet", "at home", "in a house", "with people", "people keep it",
                   "lives with people", "someone's home"],
           "farm": ["farm", "on a farm", "barn", "farmer"],
           "wild": ["wild", "in the wild", "forest", "jungle", "zoo", "nature", "outside",
                    "away from people"],
       }),
    _q("open_size", "size",
       {"hold": {"tiny", "small"}, "medium": {"medium"}, "big": {"large", "huge"}},
       "How big is it? For example, could you hold it in your hand?",
       "How big is your animal?",
       synonyms={
           "hold": ["hold it", "in my hand", "fit in my hand", "small", "little", "tiny",
                    "smaller than me", "hold"],
           "medium": ["medium", "middle", "about my size", "like a dog", "dog sized", "medium sized"],
           "big": ["big", "bigger", "huge", "giant", "enormous", "bigger than me",
                   "really big", "tall"],
       }),
    _q("open_legs", "legs",
       {"four": {"four"}, "two": {"two"}, "many": {"six", "eight", "many"}, "none": {"zero"}},
       "How many legs does it have?",
       "How many legs does your animal have?",
       synonyms={
           "four": ["four", "4", "four legs"],
           "two": ["two", "2", "two legs"],
           "many": ["many", "lots", "six", "eight", "6", "8", "a lot", "too many"],
           "none": ["no legs", "none", "zero", "0", "doesn't have legs", "not any"],
       }),
    _q("open_sound", "sound",
       {"bark": {"bark"}, "meow": {"meow"}, "moo": {"moo"}, "quack": {"quack"},
        "roar": {"roar"}, "neigh": {"neigh"}, "oink": {"oink"}, "baa": {"baa"},
        "tweet": {"tweet"}, "squeak": {"squeak"}, "hiss": {"hiss"}, "ribbit": {"ribbit"},
        "quiet": {None}},
       "What sound does it make?",
       "What sound does it make? For example, does it bark or chirp?",
       synonyms={
           "bark": ["bark", "barks", "barking", "woof"],
           "meow": ["meow", "meows", "purr", "purrs"],
           "moo": ["moo", "moos"], "quack": ["quack", "quacks"],
           "roar": ["roar", "roars", "growl", "growls"],
           "neigh": ["neigh", "neighs", "whinny"],
           "oink": ["oink", "oinks"], "baa": ["baa", "bleat", "bleats"],
           "tweet": ["tweet", "tweets", "chirp", "chirps", "sings", "singing"],
           "squeak": ["squeak", "squeaks", "squeaking"],
           "hiss": ["hiss", "hisses", "hissing"],
           "ribbit": ["ribbit", "croak", "croaks"],
           "quiet": ["no sound", "nothing", "quiet", "silent", "does not make a sound", "no noise"],
       }),
    _q("open_wings", "wings", {"wings": {True}, "none": {False}},
       "Does it have any special body parts, like wings?",
       "Does your animal have wings?",
       synonyms={"wings": ["wings", "has wings", "it flies", "winged"],
                 "none": ["no wings", "none", "nothing special", "no", "does not"]}),
    _q("open_shell", "shell", {"shell": {True}, "none": {False}},
       "Does it have a hard shell on its back?",
       "Does it have a shell?",
       synonyms={"shell": ["shell", "has a shell", "hard shell"],
                 "none": ["no shell", "none", "no", "does not", "soft"]}),
]

# Asked when nothing above can narrow the field any further. Open-ended and
# conversational; the dataset has no field for them, so they never filter.
OPEN_ENDED_FALLBACKS = [
    ("open_food", "What does it like to eat? For example, plants or meat?"),
    ("open_color", "What color is it?"),
    ("open_favourite", "What is the easiest thing to notice about it?"),
]

_NODES_BY_KEY = {n["key"]: n for n in EARLY_QUESTION_NODES}
_NODES_BY_KEY.update({n["key"]: n for n in OPEN_ENDED_NODES})

# Words that flip the meaning of a trait word that follows them.
_NEGATORS = {
    "no", "not", "none", "never", "without", "nope", "dont", "doesnt", "didnt",
    "isnt", "arent", "cant", "cannot", "wont", "nothing", "neither", "nor",
}

_NEGATION_WINDOW = 3  # tokens after a negator that it can scope over


def _normalize(text: str) -> str:
    text = str(text or "").lower().replace("'", "")
    return re.sub(r"[^a-z0-9 ]+", " ", text)


def _tokens(text: str) -> List[str]:
    return _normalize(text).split()


def _negated_positions(tokens: List[str]) -> Set[int]:
    """Indices whose meaning is reversed by a preceding negator."""
    negated: Set[int] = set()
    for index, token in enumerate(tokens):
        if token in _NEGATORS:
            for offset in range(1, _NEGATION_WINDOW + 1):
                if index + offset < len(tokens):
                    negated.add(index + offset)
    return negated


def _label_keywords(node, label) -> List[str]:
    """Phrases that indicate `label`, longest first so phrases beat words."""
    keywords = set(node["synonyms"].get(label, []))
    keywords.add(str(label))
    for value in node["values"][label]:
        if isinstance(value, str):
            keywords.add(value)
    return sorted(keywords, key=lambda k: -len(k))


def _label_signal(node, label, text: str, tokens: List[str], negated: Set[int]):
    """Return "affirm", "deny", or None for one label against one answer."""
    for phrase in _label_keywords(node, label):
        phrase_tokens = phrase.split()
        if not phrase_tokens:
            continue

        # A multi-word phrase carries its own polarity ("no legs", "does not
        # fit"), so match it whole and do not re-apply negation to it.
        if len(phrase_tokens) > 1:
            if f" {phrase} " in f" {' '.join(tokens)} ":
                return "affirm"
            continue

        for index, token in enumerate(tokens):
            if token == phrase_tokens[0]:
                return "deny" if index in negated else "affirm"

    return None


def match_answer(node, answer: str) -> Optional[Set]:
    """The dataset values an answer selects, or None when it is unclear.

    Returning None (rather than a best guess) is deliberate: an answer that
    cannot be read confidently must leave the fact unknown instead of
    inventing one.
    """
    tokens = _tokens(answer)
    if not tokens:
        return None

    negated = _negated_positions(tokens)
    text = " ".join(tokens)

    affirmed = []
    denied = []
    for label in node["values"]:
        signal = _label_signal(node, label, text, tokens, negated)
        if signal == "affirm":
            affirmed.append(label)
        elif signal == "deny":
            denied.append(label)

    if len(affirmed) == 1:
        return node["values"][affirmed[0]]

    # "No fur" on a two-way question tells us the other branch is true.
    if not affirmed and len(denied) == 1 and len(node["values"]) == 2:
        other = next(label for label in node["values"] if label != denied[0])
        return node["values"][other]

    return None


def _values_present(candidates: Set[str], feature: str) -> Set:
    present = set()
    for animal in candidates:
        value = ANIMALS[animal].get(feature)
        present.update(value if isinstance(value, set) else {value})
    return present


def infer_state(game_state) -> Dict:
    """Explicit reasoning state: facts, contradictions, and live candidates.

    `facts` holds only what the child's answers actually established, keyed by
    dataset feature. `contradictions` records answers that would have emptied
    the candidate set -- those are reported rather than silently dropped, and
    never become facts.
    """
    candidates: Set[str] = set(ANIMALS)
    facts: Dict[str, Set] = {}
    contradictions: List[Dict] = []
    unreadable: List[str] = []
    asked_keys: List[str] = []

    for item in game_state.get("qa_history", []) or []:
        if not isinstance(item, dict):
            continue

        key = str(item.get("question_key", ""))
        answer = str(item.get("answer", ""))
        # Both tables are consulted so a rounds 4-6 answer narrows candidates
        # too. Keys are disjoint (`open_` prefix), and a rounds 1-3 history only
        # ever contains early keys, so this cannot change rounds 1-3 inference.
        node = _NODES_BY_KEY.get(key)
        if not node:
            continue

        asked_keys.append(key)

        matched = match_answer(node, answer)
        if matched is None:
            unreadable.append(key)
            continue

        feature = node["feature"]
        filtered = set()
        for animal in candidates:
            value = ANIMALS[animal].get(feature)
            if isinstance(value, set):
                if value.intersection(matched):
                    filtered.add(animal)
            elif value in matched:
                filtered.add(animal)

        if not filtered:
            # Keeping the old candidate set is right (the child may have
            # misspoken, or be thinking of an animal outside the dataset), but
            # the conflict must not be recorded as a fact.
            contradictions.append({"question_key": key, "feature": feature, "answer": answer})
            continue

        candidates = filtered
        facts[feature] = matched.intersection(facts[feature]) if feature in facts else set(matched)

    rejected = {str(x).lower() for x in game_state.get("rejected_guesses", []) or []}

    return {
        "candidates": candidates - rejected,
        "facts": facts,
        "contradictions": contradictions,
        "unreadable_answers": unreadable,
        "asked_question_keys": asked_keys,
        "rejected_guesses": rejected,
    }


def infer_candidates(game_state) -> Set[str]:
    return infer_state(game_state)["candidates"]


def _precondition_met(node, candidates: Set[str]) -> bool:
    """True when every surviving candidate agrees with what the wording asserts."""
    for feature, allowed in node.get("requires", {}).items():
        present = _values_present(candidates, feature)
        if not present or not present.issubset(allowed):
            return False
    return True


def _partition_score(node, candidates):
    buckets = []
    for accepted in node["values"].values():
        count = 0
        for animal in candidates:
            value = ANIMALS[animal].get(node["feature"])
            if isinstance(value, set):
                count += bool(value.intersection(accepted))
            else:
                count += value in accepted
        if count:
            buckets.append(count)
    if len(buckets) < 2:
        return -1
    total = sum(buckets)
    entropy = -sum((c / total) * math.log2(c / total) for c in buckets)
    balance = 1 - (max(buckets) - min(buckets)) / total
    return entropy + balance


def select_next_question(game_state, round_number: int):
    asked = set(game_state.get("current_round_question_keys", [])) | set(game_state.get("session_question_keys", []))

    if round_number <= 3:
        state = infer_state(game_state)
        candidates = state["candidates"] or set(ANIMALS)

        usable = []
        for node in EARLY_QUESTION_NODES:
            if node["key"] in asked:
                continue
            # A question whose wording states a trait may only be asked once
            # the evidence has established that trait.
            if not _precondition_met(node, candidates):
                continue
            if node.get("applies") and not _values_present(candidates, node["feature"]).issubset(node["applies"]):
                continue
            score = _partition_score(node, candidates)
            if score >= 0:
                usable.append((score + random.random() * .12, node))

        if usable:
            node = max(usable, key=lambda x: x[0])[1]
        else:
            # Fall back only to questions that assert nothing unestablished.
            safe = [
                n for n in EARLY_QUESTION_NODES
                if n["key"] not in asked and not n["requires"] and not n.get("applies")
            ]
            node = random.choice(safe or [n for n in EARLY_QUESTION_NODES if not n["requires"]])

        question = random.choice(node["variants"])
        return {
            "key": node["key"],
            "question": question,
            "stage": "guided_choice",
            "response_mode": "choice",
            "candidate_count": len(candidates),
        }

    if round_number <= 6:
        return _select_open_ended_question(game_state, asked)

    pool = HINT_QUESTIONS
    fresh = [x for x in pool if x[0] not in asked] or pool
    key, question = random.choice(fresh)
    return {
        "key": key,
        "question": question,
        "stage": "open_hint",
        "response_mode": "open_hint",
    }


def _open_partition_score(node, candidates):
    """Information gain for a rounds 4-6 open-ended question.

    Same idea as `_partition_score`, with one addition: candidates that match
    none of the buckets are counted as their own "no answer" group. The sound
    question has many buckets but only about a third of the database has a
    sound a child would name, and without counting that group it would look
    like the best question every time and waste a turn. Kept separate from
    `_partition_score` so the rounds 1-3 scoring is untouched.
    """
    matched = 0
    buckets = []

    for accepted in node["values"].values():
        count = 0
        for animal in candidates:
            value = ANIMALS[animal].get(node["feature"])
            if isinstance(value, set):
                count += bool(value.intersection(accepted))
            else:
                count += value in accepted
        if count:
            buckets.append(count)
        matched += count

    unmatched = len(candidates) - matched
    if unmatched > 0:
        buckets.append(unmatched)

    if len(buckets) < 2:
        return -1

    total = sum(buckets)
    entropy = -sum((c / total) * math.log2(c / total) for c in buckets)
    balance = 1 - (max(buckets) - min(buckets)) / total
    return entropy + balance


def _select_open_ended_question(game_state, asked):
    """Rounds 4-6: adaptive, but asked in open-ended words.

    The trait is chosen the same way as rounds 1-3 -- whichever unresolved
    distinction best splits the animals still in play -- and only then turned
    into a short question. A trait that is already known scores -1 (every
    surviving candidate lands in one bucket) and is skipped, so Star never asks
    a second size or covering question.
    """
    state = infer_state(game_state)
    candidates = state["candidates"] or set(ANIMALS)

    usable = []
    for node in OPEN_ENDED_NODES:
        if node["key"] in asked:
            continue
        score = _open_partition_score(node, candidates)
        if score >= 0:
            usable.append((score + random.random() * .12, node))

    if usable:
        node = max(usable, key=lambda x: x[0])[1]
        return {
            "key": node["key"],
            "question": random.choice(node["variants"]),
            "stage": "guided_clue",
            "response_mode": "short_phrase",
            "candidate_count": len(candidates),
        }

    # Nothing left to narrow -- keep the conversation going.
    fresh = [x for x in OPEN_ENDED_FALLBACKS if x[0] not in asked] or OPEN_ENDED_FALLBACKS
    key, question = random.choice(fresh)
    return {
        "key": key,
        "question": question,
        "stage": "guided_clue",
        "response_mode": "short_phrase",
        "candidate_count": len(candidates),
    }


def early_question_count():
    return sum(len(node["variants"]) for node in EARLY_QUESTION_NODES)


# Short restatements of what a given feature/value pair means, in the words a
# young child would use. Ordered most specific first within each feature.
_FACT_PHRASES = {
    "habitat": [
        ({"land"}, "it lives mostly on land"),
        ({"water"}, "it lives in the water"),
        ({"both"}, "it spends time on land and in the water"),
        ({"water", "both"}, "it spends time in the water"),
    ],
    "size": [
        ({"tiny"}, "it is small enough to hold"),
        ({"tiny", "small"}, "it is smaller than a cat"),
        ({"large", "huge"}, "it is bigger than a person"),
        ({"medium", "large", "huge"}, "it is bigger than a cat"),
        ({"tiny", "small", "medium"}, "it is smaller than a person"),
    ],
    "covering": [
        ({"fur", "hair", "wool"}, "it has fur"),
        ({"feathers"}, "it has feathers"),
        ({"scales"}, "it has scales"),
        # "Not furry" only rules fur out; it does not tell us which of the
        # other coverings it is, so the phrase must stay negative. Listed last
        # so the specific coverings above win the subset pass.
        ({"feathers", "scales", "skin", "shell", "spikes"}, "it does not have fur"),
    ],
    "legs": [
        ({"zero"}, "it has no legs"),
        ({"two"}, "it has two legs"),
        ({"four"}, "it has four legs"),
        ({"six"}, "it has six legs"),
        ({"eight"}, "it has eight legs"),
        ({"many"}, "it has lots of legs"),
        ({"six", "eight", "many"}, "it has more than four legs"),
    ],
    "wings": [({True}, "it has wings"), ({False}, "it does not have wings")],
    "tail": [({True}, "it has a tail"), ({False}, "it does not have a tail")],
    "shell": [({True}, "it has a shell"), ({False}, "it does not have a shell")],
    "setting": [
        ({"pet"}, "people keep it as a pet"),
        ({"farm"}, "it lives on a farm"),
        ({"wild"}, "it lives out in the wild"),
        ({"wild", "farm"}, "it lives outside"),
    ],
    "movement": [
        ({"fly"}, "it flies"),
        ({"swim", "float"}, "it swims"),
        ({"climb", "swing"}, "it climbs"),
        ({"hop", "jump"}, "it hops and jumps"),
        ({"slither"}, "it slithers"),
        ({"walk", "run", "crawl", "hop", "jump", "slither", "climb", "swing"}, "it stays on the ground"),
    ],
    "time": [({"night"}, "you would see it at night")],
}


def describe_answer(question_key: str, answer: str) -> Optional[str]:
    """A short restatement of what an answer established, or None.

    Runs the answer through the same matcher the candidate filter uses, so
    Star can only ever reflect back a fact the reasoning state actually
    recorded -- never an assumption drawn from the raw transcript.
    """
    node = next((n for n in EARLY_QUESTION_NODES if n["key"] == question_key), None)
    if node is None:
        return None

    matched = match_answer(node, answer)
    if matched is None:
        return None

    for values, phrase in _FACT_PHRASES.get(node["feature"], []):
        if matched == values:
            return phrase

    # Fall back to a subset match so a narrower answer still reads correctly.
    for values, phrase in _FACT_PHRASES.get(node["feature"], []):
        if matched and matched.issubset(values):
            return phrase

    return None
