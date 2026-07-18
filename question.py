"""Decision-tree question selection for Mystery Animal.

There are exactly 60 early-round spoken question variants below. The selector
scores useful concepts against the remaining animal candidates, then chooses a
natural wording variant without repeating a question key in the same session.
"""
from __future__ import annotations

import math
import random
import re
from typing import Dict, Iterable, List, Optional, Set

from animal_database import ANIMALS


def _q(key, feature, values, *variants, applies=None):
    return {"key": key, "feature": feature, "values": values, "variants": list(variants), "applies": applies}

# 30 concepts x 2 natural phrasings = exactly 60 early-round questions.
EARLY_QUESTION_NODES = [
    _q("habitat_land_water", "habitat", {"land": {"land"}, "water": {"water"}, "both": {"both"}}, "Does it live mostly on land, or mostly in water?", "Would I look for it on land, or in the water?"),
    _q("water_only_both", "habitat", {"water": {"water"}, "both": {"both"}}, "Does it stay in the water, or come onto land too?", "Is it always in water, or does it spend time on land too?", applies={"water", "both"}),
    _q("size_cat", "size", {"small": {"tiny", "small"}, "big": {"medium", "large", "huge"}}, "Is it smaller than a cat, or bigger than a cat?", "Would you say it is cat-sized or smaller, or larger than that?"),
    _q("size_hand", "size", {"hand": {"tiny"}, "larger": {"small", "medium", "large", "huge"}}, "Could it fit in your hand, or is it bigger?", "Is it small enough to hold in one hand, or too big for that?"),
    _q("size_person", "size", {"smaller": {"tiny", "small", "medium"}, "bigger": {"large", "huge"}}, "Is it smaller than a person, or bigger than a person?", "Would it be shorter than you, or taller and bigger?"),
    _q("legs_over_four", "legs", {"many": {"six", "eight", "many"}, "few": {"zero", "two", "four"}}, "Does it have more than four legs, or four or fewer?", "Are there lots of legs, or no more than four?"),
    _q("legs_many_split", "legs", {"six": {"six"}, "eight": {"eight"}, "many": {"many"}}, "Does it have six legs, eight legs, or lots more than eight?", "Would you count six legs, eight legs, or too many to count quickly?", applies={"six", "eight", "many"}),
    _q("legs_four_less", "legs", {"four": {"four"}, "less": {"zero", "two"}}, "Does it have four legs, or fewer than four?", "Would you count four legs, or less than four?", applies={"zero", "two", "four"}),
    _q("legs_two_zero", "legs", {"two": {"two"}, "zero": {"zero"}}, "Does it have two legs, or no legs?", "Would I see two legs, or none at all?", applies={"zero", "two"}),
    _q("fur_branch", "covering", {"fur": {"fur", "hair", "wool"}, "other": {"feathers", "scales", "skin", "shell", "spikes"}}, "Does it have fur, or is its body covered another way?", "Would it feel furry, or not really furry?"),
    _q("feather_branch", "covering", {"feathers": {"feathers"}, "other": {"scales", "skin", "shell", "spikes"}}, "Does it have feathers, or a different covering?", "Would you see feathers on it, or something else?", applies={"feathers", "scales", "skin", "shell", "spikes"}),
    _q("scales_branch", "covering", {"scales": {"scales"}, "other": {"skin", "shell", "spikes"}}, "Does it have scales, or does its body look different?", "Would you call it scaly, or not scaly?", applies={"scales", "skin", "shell", "spikes"}),
    _q("shell_branch", "shell", {"shell": {True}, "none": {False}}, "Does it have a shell, or no shell?", "Can it hide in a shell, or does it not have one?"),
    _q("wings_branch", "wings", {"wings": {True}, "none": {False}}, "Does it have wings, or no wings?", "Would I see wings on it, or not?"),
    _q("flight_branch", "movement", {"fly": {"fly"}, "ground": {"walk", "run", "crawl", "hop", "jump", "slither", "climb", "swing"}}, "Does it usually fly, or stay closer to the ground?", "Would it move through the air, or mostly stay down low?"),
    _q("swim_branch", "movement", {"swim": {"swim", "float"}, "other": {"walk", "run", "crawl", "hop", "jump", "slither", "climb", "swing", "fly"}}, "Does it usually swim, or move another way?", "Would I see it swimming most, or doing something else?"),
    _q("climb_branch", "movement", {"climb": {"climb", "swing"}, "ground": {"walk", "run", "crawl", "hop", "jump", "slither"}}, "Does it usually climb, or stay on the ground?", "Would it go up trees and walls, or keep closer to the ground?"),
    _q("hop_walk", "movement", {"hop": {"hop", "jump"}, "walk": {"walk", "run", "crawl"}}, "Does it hop and jump, or mostly walk and run?", "Would it bounce along, or move with regular steps?"),
    _q("slither_other", "movement", {"slither": {"slither"}, "other": {"walk", "run", "crawl", "hop", "jump", "climb", "swing"}}, "Does it slither, or move some other way?", "Would it slide along without legs, or not?"),
    _q("pet_wild", "setting", {"pet": {"pet"}, "outside": {"wild", "farm"}}, "Would people keep it as a pet, or would it usually live outside?", "Would it live in someone's home, or mostly somewhere else?"),
    _q("farm_wild", "setting", {"farm": {"farm"}, "wild": {"wild"}}, "Would you see it on a farm, or in the wild?", "Does it usually live around farms, or away in nature?"),
    _q("tail_branch", "tail", {"tail": {True}, "none": {False}}, "Does it have a tail, or no tail?", "Would I notice a tail behind it, or not?"),
    _q("night_day", "time", {"night": {"night"}, "day": {None, "day"}}, "Would you usually see it at night, or during the day?", "Is it more of a nighttime animal, or a daytime animal?"),
    _q("water_land_move", "movement", {"swim": {"swim", "float"}, "land": {"walk", "run", "crawl", "hop", "jump"}}, "Does it spend more time swimming, or moving on land?", "Would it be moving in water, or moving on the ground?"),
    _q("tiny_insect_wings", "wings", {"wings": {True}, "none": {False}}, "Can the little animal fly, or does it stay on the ground?", "Does this tiny animal use wings, or only its legs?"),
    _q("large_water_air", "movement", {"surface": {"swim", "float"}, "land": {"walk", "crawl"}}, "Does it swim most of the time, or rest on land too?", "Would it stay in the water, or climb out sometimes?"),
    _q("four_leg_climb", "movement", {"climb": {"climb", "swing"}, "ground": {"walk", "run"}}, "Does the four-legged animal climb, or mostly walk on the ground?", "Would it go up trees, or stay down on the ground?"),
    _q("two_leg_fly", "movement", {"fly": {"fly"}, "ground": {"walk", "run", "swim"}}, "Does the two-legged animal fly, or mostly stay down?", "Would those two legs belong to a flyer, or an animal that stays on the ground?"),
    _q("zero_leg_water", "habitat", {"water": {"water", "both"}, "land": {"land"}}, "Does the animal with no legs live in water, or on land?", "Would I find this legless animal in water, or on the ground?"),
    _q("many_leg_water", "habitat", {"water": {"water", "both"}, "land": {"land"}}, "Does the animal with lots of legs live in water, or on land?", "Would those many legs be underwater, or on dry land?"),
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


def _text(game_state):
    return " ".join(str(x.get("answer", "")).lower() for x in game_state.get("qa_history", []) if isinstance(x, dict))


def infer_candidates(game_state) -> Set[str]:
    candidates = set(ANIMALS)
    text = _text(game_state)
    for item in game_state.get("qa_history", []):
        if not isinstance(item, dict):
            continue
        key, answer = str(item.get("question_key", "")), str(item.get("answer", "")).lower()
        node = next((n for n in EARLY_QUESTION_NODES if n["key"] == key), None)
        if not node:
            continue
        matched = None
        for label, accepted in node["values"].items():
            if label in answer or any(str(v).lower() in answer for v in accepted if v is not None):
                matched = accepted
                break
        if matched is None:
            continue
        feature = node["feature"]
        filtered = set()
        for animal in candidates:
            value = ANIMALS[animal].get(feature)
            if isinstance(value, set):
                if value.intersection(matched): filtered.add(animal)
            elif value in matched:
                filtered.add(animal)
        if filtered:
            candidates = filtered
    rejected = {str(x).lower() for x in game_state.get("rejected_guesses", [])}
    return candidates - rejected


def _partition_score(node, candidates):
    buckets = []
    for accepted in node["values"].values():
        count = 0
        for animal in candidates:
            value = ANIMALS[animal].get(node["feature"])
            if isinstance(value, set): count += bool(value.intersection(accepted))
            else: count += value in accepted
        if count: buckets.append(count)
    if len(buckets) < 2: return -1
    total = sum(buckets)
    entropy = -sum((c/total) * math.log2(c/total) for c in buckets)
    balance = 1 - (max(buckets) - min(buckets)) / total
    return entropy + balance


def select_next_question(game_state, round_number: int):
    asked = set(game_state.get("current_round_question_keys", [])) | set(game_state.get("session_question_keys", []))
    if round_number <= 3:
        candidates = infer_candidates(game_state)
        usable = []
        values_present = {}
        for feature in {n["feature"] for n in EARLY_QUESTION_NODES}:
            values_present[feature] = set()
            for animal in candidates:
                value = ANIMALS[animal].get(feature)
                values_present[feature].update(value if isinstance(value, set) else {value})
        for node in EARLY_QUESTION_NODES:
            if node["key"] in asked: continue
            if node.get("applies") and not values_present.get(node["feature"], set()).issubset(node["applies"]): continue
            score = _partition_score(node, candidates)
            if score >= 0: usable.append((score + random.random() * .12, node))
        node = max(usable, key=lambda x: x[0])[1] if usable else random.choice([n for n in EARLY_QUESTION_NODES if n["key"] not in asked] or EARLY_QUESTION_NODES)
        question = random.choice(node["variants"])
        return {"key": node["key"], "question": question, "stage": "guided_choice", "response_mode": "choice", "candidate_count": len(candidates)}
    pool = DETAIL_QUESTIONS if round_number <= 6 else HINT_QUESTIONS
    fresh = [x for x in pool if x[0] not in asked] or pool
    key, question = random.choice(fresh)
    return {"key": key, "question": question, "stage": "guided_clue" if round_number <= 6 else "open_hint", "response_mode": "short_phrase" if round_number <= 6 else "open_hint"}


def early_question_count():
    return sum(len(node["variants"]) for node in EARLY_QUESTION_NODES)
