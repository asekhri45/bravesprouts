"""Mystery Animal round bands.

Rounds 1-3 were restored to the implementation that existed immediately before
the large multi-game pass (checkpoint 2026-07-23T13:20:59, reconstructed from
the session transcripts). Rounds 4-6 are a new open-ended adaptive band. These
tests lock in both, and in particular that the two bands stay separate.

This file replaces tests/test_mystery_animal_paths.py, which encoded the
now-reverted all-rounds selector (multi-way question nodes, sound scoring,
commonness ranking) and therefore asserted the opposite of what is wanted.
"""
import random
import re

import pytest

from animal_database import ANIMALS
import question
from question import (
    EARLY_QUESTION_NODES,
    OPEN_ENDED_FALLBACKS,
    OPEN_ENDED_NODES,
    infer_state,
    match_answer,
    select_next_question,
)
from guessing import choose_database_guess, should_make_guess


# ---------------------------------------------------------------------------
# A. Rounds 1-3 are the restored historical implementation
# ---------------------------------------------------------------------------

def test_early_band_is_the_checkpoint_node_set():
    """30 concepts x 2 phrasings = the 60 variants app.py advertises."""
    assert len(EARLY_QUESTION_NODES) == 30
    assert question.early_question_count() == 60


def test_size_cat_is_restored():
    """The named pass deleted this node; rounds 1-3 depend on it."""
    node = next((n for n in EARLY_QUESTION_NODES if n["key"] == "size_cat"), None)
    assert node is not None, "size_cat must be present again"
    assert "Is it smaller than a cat, or bigger than a cat?" in node["variants"]


@pytest.mark.parametrize(
    "removed",
    ["covering_multi", "movement_multi", "legs_multi", "setting_multi", "sound_known", "size_band"],
)
def test_named_pass_multi_way_nodes_are_gone(removed):
    assert all(n["key"] != removed for n in EARLY_QUESTION_NODES)


def test_rounds_1_to_3_use_only_the_early_band():
    """No rounds 4-6 question may ever surface in rounds 1-3."""
    random.seed(0)
    for round_number in (1, 2, 3):
        for _ in range(300):
            chosen = select_next_question({"qa_history": []}, round_number)
            assert not chosen["key"].startswith("open_"), (
                f'round {round_number} leaked a rounds 4-6 question: {chosen["question"]}'
            )


def test_rounds_1_to_3_first_questions_are_two_way_choices():
    random.seed(1)
    for _ in range(100):
        chosen = select_next_question({"qa_history": []}, 1)
        assert chosen["response_mode"] == "choice"
        assert chosen["stage"] == "guided_choice"
        node = next(n for n in EARLY_QUESTION_NODES if n["key"] == chosen["key"])
        assert 2 <= len(node["values"]) <= 3


def test_early_scorer_has_no_unmatched_bucket():
    """The unmatched-group scoring was a named-pass change; rounds 1-3 must
    use the checkpoint scorer."""
    import inspect
    src = inspect.getsource(question._partition_score)
    assert "unmatched" not in src


# ---------------------------------------------------------------------------
# B. Rounds 4-6 are short, open-ended and adaptive
# ---------------------------------------------------------------------------

def _example_count(text):
    match = re.search(r"(for example,|, like)(.*)$", text, re.I)
    if not match:
        return 0
    tail = match.group(2)
    return len([p for p in re.split(r",| or ", tail) if p.strip(" ?.")])


def all_open_question_text():
    texts = []
    for node in OPEN_ENDED_NODES:
        texts.extend(node["variants"])
    texts.extend(q for _, q in OPEN_ENDED_FALLBACKS)
    return texts


@pytest.mark.parametrize("text", all_open_question_text())
def test_open_questions_give_at_most_two_examples(text):
    assert _example_count(text) <= 2, f"too many examples: {text}"


@pytest.mark.parametrize("text", all_open_question_text())
def test_open_questions_are_not_long_multiple_choice_lists(text):
    """The complaint was 'does it walk, fly, crawl, hop, swim, or slither?'."""
    body = text.split("For example")[0]
    assert body.count(",") <= 1, f"reads like an answer list: {text}"
    assert len(text.split()) <= 16, f"too long for a five-year-old: {text}"


def test_open_questions_are_open_ended_not_yes_no_lists():
    # "Does it have any special body parts, like wings?" is one of the shapes
    # the brief explicitly asks for, so `does` is a valid opener here.
    openers = ("how", "what", "where", "who", "does")
    for node in OPEN_ENDED_NODES:
        for variant in node["variants"]:
            assert variant.lower().startswith(openers), variant


def test_rounds_4_to_6_are_adaptive_not_a_fixed_sequence():
    """Different evidence must lead to a different next question."""
    fresh = {"qa_history": [], "current_round_question_keys": [], "session_question_keys": []}
    known_movement = {
        "qa_history": [{"question_key": "open_movement", "answer": "it swims"}],
        "current_round_question_keys": ["open_movement"],
        "session_question_keys": [],
    }
    random.seed(2)
    a = select_next_question(fresh, 4)["key"]
    b = select_next_question(known_movement, 4)["key"]
    assert a != b


def test_rounds_4_to_6_never_reask_a_known_trait():
    """Once a trait is resolved its question can no longer split anything."""
    for key, answer, feature in [
        ("open_size", "it can fit in my hand", "size"),
        ("open_covering", "it has fur", "covering"),
        ("open_habitat", "it lives in the ocean", "habitat"),
    ]:
        game = {
            "qa_history": [{"question_key": key, "answer": answer}],
            "current_round_question_keys": [key],
            "session_question_keys": [],
        }
        same_feature = {n["key"] for n in OPEN_ENDED_NODES if n["feature"] == feature}
        random.seed(3)
        for _ in range(120):
            chosen = select_next_question(game, 5)
            assert chosen["key"] not in same_feature, (
                f'asked about {feature} again: {chosen["question"]}'
            )


# ---------------------------------------------------------------------------
# C. Open-ended answers normalize without repeating the example
# ---------------------------------------------------------------------------

NATURAL_ANSWERS = [
    ("open_movement", "It walks.", "walk"),
    ("open_movement", "It walks on four legs.", "walk"),
    ("open_movement", "It runs.", "run"),
    ("open_movement", "It hops.", "hop"),
    ("open_movement", "It slithers.", "slither"),
    ("open_movement", "It mostly swims.", "swim"),
    ("open_movement", "It flies.", "fly"),
    ("open_covering", "It has fur.", "fur"),
    ("open_covering", "It is really furry.", "fur"),
    ("open_covering", "It has feathers.", "feathers"),
    ("open_covering", "Its skin is smooth.", "skin"),
    ("open_covering", "It has a shell.", "shell"),
    ("open_habitat", "It lives in the ocean.", "water"),
    ("open_habitat", "It lives in a forest.", "land"),
    ("open_setting", "It lives with people.", "pet"),
    ("open_setting", "You find it on a farm.", "farm"),
    ("open_sound", "It barks.", "bark"),
    ("open_sound", "It makes a squeaking sound.", "squeak"),
    ("open_size", "It can fit in my hand.", "small"),
    ("open_size", "It is bigger than me.", "large"),
    ("open_legs", "It has four legs.", "four"),
]


@pytest.mark.parametrize("key,answer,expected", NATURAL_ANSWERS)
def test_natural_answers_normalize(key, answer, expected):
    node = next(n for n in OPEN_ENDED_NODES if n["key"] == key)
    matched = match_answer(node, answer)
    assert matched is not None, f"could not read: {answer}"
    assert expected in matched, f"{answer} -> {matched}, expected {expected}"


def test_answers_do_not_have_to_repeat_the_examples():
    """The movement question only mentions walking and flying."""
    node = next(n for n in OPEN_ENDED_NODES if n["key"] == "open_movement")
    for answer in ["It slithers.", "It hops.", "It crawls.", "It climbs trees."]:
        assert match_answer(node, answer) is not None, answer


# ---------------------------------------------------------------------------
# D. Convergence for the animals named in the brief
# ---------------------------------------------------------------------------

BRIEF_ANIMALS = ["dog", "cat", "fish", "bird", "snake", "turtle", "frog",
                 "elephant", "penguin", "rabbit"]


def _nodes():
    return EARLY_QUESTION_NODES + OPEN_ENDED_NODES


def _oracle(node, animal):
    value = ANIMALS[animal].get(node["feature"])
    values = value if isinstance(value, set) else {value}
    for label, accepted in node["values"].items():
        if values & accepted:
            synonyms = node["synonyms"].get(label)
            return synonyms[0] if synonyms else str(label)
    return None


def play_round(animal, seed, round_number, max_questions=12):
    random.seed(seed)
    game = {
        "qa_history": [], "current_round_question_keys": [], "session_question_keys": [],
        "rejected_guesses": [], "questions_asked": 0, "guesses_made": 0,
        "last_guess_question_count": 0, "guess_cooldown_questions": 0,
    }
    for _ in range(max_questions):
        if should_make_guess(game):
            guess = choose_database_guess(game)
            game["guesses_made"] += 1
            game["last_guess_question_count"] = game["questions_asked"]
            if guess == animal:
                return True
            game["rejected_guesses"].append(guess)
            if game["guesses_made"] >= 3:
                return False
            continue

        chosen = select_next_question(game, round_number)
        node = next((n for n in _nodes() if n["key"] == chosen["key"]), None)
        game["current_round_question_keys"].append(chosen["key"])
        game["questions_asked"] += 1
        if node is None:
            continue
        answer = _oracle(node, animal)
        if answer:
            game["qa_history"].append({"question_key": chosen["key"], "answer": answer})
    return False


@pytest.mark.parametrize("animal", BRIEF_ANIMALS)
def test_rounds_4_to_6_accuracy_does_not_regress(animal):
    solved = sum(play_round(animal, seed, 4) for seed in range(20))
    assert solved >= 18, f"{animal}: solved only {solved}/20 in rounds 4-6"


@pytest.mark.parametrize("animal", BRIEF_ANIMALS)
def test_restored_rounds_1_to_3_still_converge(animal):
    """The checkpoint's own accuracy -- restored, not improved on."""
    solved = sum(play_round(animal, seed, 1) for seed in range(20))
    assert solved >= 14, f"{animal}: solved only {solved}/20 in rounds 1-3"
