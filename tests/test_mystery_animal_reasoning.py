"""Reasoning tests for Mystery Animal's question selection and guessing.

These cover the three defects that made the game feel unintelligent:

1. Negative answers were read as their opposite. `label in answer` meant
   "no fur" matched the "fur" label, "no wings" matched "wings", and "no tail"
   matched "tail", so a denial eliminated exactly the animals it should have
   kept.

2. Questions asserted traits the child never gave ("Does the two-legged animal
   fly?" before legs were known). Those nodes now carry `requires`
   preconditions.

3. Guesses were drawn from a shuffled candidate list, so Star guessed obscure
   animals while common ones were still live.

The simulation tests play full rounds against the dataset -- an oracle answers
each question truthfully for a chosen animal -- and assert the game converges.
"""
import random

import pytest

from animal_database import ANIMALS
from question import (
    EARLY_QUESTION_NODES,
    infer_state,
    match_answer,
    select_next_question,
)
from guessing import choose_database_guess, familiarity, should_make_guess


def node_by_key(key):
    return next(n for n in EARLY_QUESTION_NODES if n["key"] == key)


# --------------------------------------------------------------------------
# 1. Answer interpretation must respect negation
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "key,answer,expected_excludes",
    [
        ("fur_branch", "no fur", "fur"),
        ("fur_branch", "it doesn't have fur", "fur"),
        ("wings_branch", "no wings", True),
        ("wings_branch", "it does not have wings", True),
        ("tail_branch", "no tail", True),
        ("shell_branch", "no shell", True),
    ],
)
def test_negative_answers_are_not_read_as_positive(key, answer, expected_excludes):
    node = node_by_key(key)
    matched = match_answer(node, answer)
    assert matched is not None, "a clear negative answer must still be readable"
    assert expected_excludes not in matched, (
        f'"{answer}" must not be recorded as having that trait'
    )


@pytest.mark.parametrize(
    "key,answer,expected_includes",
    [
        ("fur_branch", "it has fur", "fur"),
        ("fur_branch", "furry", "fur"),
        ("wings_branch", "it has wings", True),
        ("tail_branch", "yes it has a tail", True),
        ("legs_two_zero", "no legs", "zero"),
        ("legs_two_zero", "two legs", "two"),
        ("habitat_land_water", "on land", "land"),
        ("habitat_land_water", "in the water", "water"),
        ("size_cat", "bigger than a cat", "large"),
        ("size_cat", "smaller", "small"),
    ],
)
def test_positive_answers_are_read_correctly(key, answer, expected_includes):
    matched = match_answer(node_by_key(key), answer)
    assert matched is not None, f'"{answer}" should be readable'
    assert expected_includes in matched


def test_ambiguous_answers_leave_the_fact_unknown():
    # Neither branch is indicated -- the game must not invent a fact.
    assert match_answer(node_by_key("fur_branch"), "um I don't know") is None
    assert match_answer(node_by_key("habitat_land_water"), "maybe") is None
    assert match_answer(node_by_key("size_cat"), "") is None


# --------------------------------------------------------------------------
# 2. Questions must never assert an unconfirmed trait
# --------------------------------------------------------------------------

ASSERTING_NODES = {
    "two_leg_fly": ("legs", {"two"}),
    "four_leg_climb": ("legs", {"four"}),
    "zero_leg_water": ("legs", {"zero"}),
    "many_leg_water": ("legs", {"six", "eight", "many"}),
    "tiny_insect_wings": ("size", {"tiny"}),
    "water_only_both": ("habitat", {"water", "both"}),
    "large_water_air": ("habitat", {"water", "both"}),
}


def test_every_trait_asserting_question_declares_a_precondition():
    for key, (feature, allowed) in ASSERTING_NODES.items():
        node = node_by_key(key)
        assert node["requires"], f"{key} states a trait and must declare `requires`"
        assert feature in node["requires"], f"{key} must gate on {feature}"
        assert node["requires"][feature] == allowed


def test_leg_and_habitat_assertions_never_appear_on_a_fresh_game():
    """With no answers yet, nothing about legs/size/habitat is established."""
    random.seed(0)
    for _ in range(300):
        chosen = select_next_question({"qa_history": []}, round_number=1)
        assert chosen["key"] not in ASSERTING_NODES, (
            f'{chosen["key"]} asserts a trait but nothing has been established: '
            f'"{chosen["question"]}"'
        )


def test_aquatic_followup_only_after_aquatic_is_established():
    """The 'does it come onto land' follow-up needs water/both confirmed."""
    random.seed(1)
    land_game = {
        "qa_history": [{"question_key": "habitat_land_water", "answer": "on land"}],
        "current_round_question_keys": ["habitat_land_water"],
    }
    for _ in range(200):
        chosen = select_next_question(land_game, round_number=1)
        assert chosen["key"] not in {"water_only_both", "large_water_air", "zero_leg_water"}


def test_two_leg_question_can_appear_once_two_legs_is_established():
    """The precondition gates the question; it must not ban it forever.

    Selection may still legitimately prefer a different question -- the
    multi-way movement question outscores this one and asserts nothing -- so
    what is checked here is that the gate itself opens, not that this exact
    question wins.
    """
    game = {
        "qa_history": [
            {"question_key": "legs_two_zero", "answer": "two legs"},
        ],
        "current_round_question_keys": [],
    }
    state = infer_state(game)
    legs = {ANIMALS[a]["legs"] for a in state["candidates"]}
    assert legs == {"two"}, "the answer should have established two legs"

    from question import _precondition_met

    assert _precondition_met(node_by_key("two_leg_fly"), state["candidates"]), (
        "a gated question must become available once its trait is established"
    )


# --------------------------------------------------------------------------
# 3. Structured state
# --------------------------------------------------------------------------

def test_state_records_facts_and_keeps_contradictions_out_of_them():
    game = {
        "qa_history": [
            {"question_key": "habitat_land_water", "answer": "on land"},
            {"question_key": "fur_branch", "answer": "it has fur"},
            # A land, furry animal with a shell contradicts the dataset.
            {"question_key": "shell_branch", "answer": "it has a shell"},
        ]
    }
    state = infer_state(game)

    assert state["facts"]["habitat"] == {"land"}
    assert state["facts"]["covering"] == {"fur", "hair", "wool"}
    assert "shell" not in state["facts"], "a contradicting answer must not become a fact"
    assert state["contradictions"], "the contradiction must be recorded"
    assert state["candidates"], "candidates must survive a contradicting answer"


def test_rejected_guesses_are_removed_from_candidates():
    game = {
        "qa_history": [{"question_key": "habitat_land_water", "answer": "on land"}],
        "rejected_guesses": ["dog", "cat"],
    }
    candidates = infer_state(game)["candidates"]
    assert "dog" not in candidates
    assert "cat" not in candidates


def test_a_rejected_guess_is_never_offered_again():
    game = {
        "qa_history": [
            {"question_key": "habitat_land_water", "answer": "on land"},
            {"question_key": "fur_branch", "answer": "it has fur"},
            {"question_key": "pet_wild", "answer": "a pet"},
        ],
        "rejected_guesses": ["dog"],
    }
    for _ in range(50):
        assert choose_database_guess(game) != "dog"


# --------------------------------------------------------------------------
# 4. Guess quality
# --------------------------------------------------------------------------

def test_guesses_are_always_real_animals():
    random.seed(3)
    game = {"qa_history": [{"question_key": "habitat_land_water", "answer": "on land"}]}
    for _ in range(100):
        guess = choose_database_guess(game)
        assert guess in ANIMALS, f"{guess!r} is not an animal in the dataset"


def test_common_animals_are_preferred_over_obscure_ones():
    assert familiarity("dog") < familiarity("centipede")
    assert familiarity("cat") < familiarity("lobster")
    assert familiarity("horse") < familiarity("sloth")

    # A furry land pet should guess dog/cat/rabbit long before hamster/hedgehog.
    game = {
        "qa_history": [
            {"question_key": "habitat_land_water", "answer": "on land"},
            {"question_key": "fur_branch", "answer": "it has fur"},
            {"question_key": "pet_wild", "answer": "a pet"},
        ]
    }
    random.seed(4)
    guesses = {choose_database_guess(game) for _ in range(60)}
    assert guesses <= {"dog", "cat", "rabbit"}, f"expected familiar pets, got {guesses}"


def test_no_guess_while_the_field_is_still_wide():
    wide = {"questions_asked": 2, "guesses_made": 0, "qa_history": []}
    assert should_make_guess(wide) is False, "must not guess with 64 candidates live"


# --------------------------------------------------------------------------
# 5. Full-round simulation against the animals the brief lists
# --------------------------------------------------------------------------

def oracle_answer(node, animal):
    """Answer `node` truthfully for `animal`, in child-like wording."""
    value = ANIMALS[animal].get(node["feature"])
    values = value if isinstance(value, set) else {value}

    for label, accepted in node["values"].items():
        if values.intersection(accepted):
            synonyms = node["synonyms"].get(label)
            return synonyms[0] if synonyms else str(label)
    return None


def play_round(animal, max_questions=10, seed=0):
    """Play a round; return (questions_asked, guesses_made, solved)."""
    random.seed(seed)
    game = {
        "qa_history": [],
        "current_round_question_keys": [],
        "session_question_keys": [],
        "rejected_guesses": [],
        "questions_asked": 0,
        "guesses_made": 0,
        "last_guess_question_count": 0,
        "guess_cooldown_questions": 0,
    }

    for _ in range(max_questions):
        if should_make_guess(game):
            guess = choose_database_guess(game)
            game["guesses_made"] += 1
            game["last_guess_question_count"] = game["questions_asked"]
            if guess == animal:
                return game["questions_asked"], game["guesses_made"], True
            game["rejected_guesses"].append(guess)
            if game["guesses_made"] >= 3:
                return game["questions_asked"], game["guesses_made"], False
            continue

        chosen = select_next_question(game, round_number=1)
        node = next((n for n in EARLY_QUESTION_NODES if n["key"] == chosen["key"]), None)
        if node is None:
            break

        answer = oracle_answer(node, animal)
        game["current_round_question_keys"].append(chosen["key"])
        game["questions_asked"] += 1
        if answer is not None:
            game["qa_history"].append({"question_key": chosen["key"], "answer": answer})

    return game["questions_asked"], game["guesses_made"], False


BRIEF_ANIMALS = ["dog", "cat", "snake", "bird", "dolphin", "elephant", "frog", "horse", "penguin", "turtle"]


@pytest.mark.parametrize("animal", BRIEF_ANIMALS)
def test_common_animals_converge_in_a_reasonable_number_of_questions(animal):
    """Star should land these without ten weak questions."""
    solved_runs = []
    for seed in range(8):
        questions, guesses, solved = play_round(animal, seed=seed)
        if solved:
            solved_runs.append(questions)

    assert len(solved_runs) >= 5, (
        f"{animal}: solved only {len(solved_runs)}/8 rounds"
    )
    average = sum(solved_runs) / len(solved_runs)
    assert average <= 7, f"{animal}: averaged {average:.1f} questions before guessing"


@pytest.mark.parametrize("animal", BRIEF_ANIMALS)
def test_no_question_asserts_an_unestablished_trait_during_a_real_round(animal):
    """Replay each round and check every asked question's preconditions held."""
    for seed in range(6):
        random.seed(seed)
        game = {
            "qa_history": [], "current_round_question_keys": [], "session_question_keys": [],
            "rejected_guesses": [], "questions_asked": 0, "guesses_made": 0,
            "last_guess_question_count": 0, "guess_cooldown_questions": 0,
        }

        for _ in range(10):
            candidates_before = infer_state(game)["candidates"] or set(ANIMALS)
            chosen = select_next_question(game, round_number=1)
            node = next((n for n in EARLY_QUESTION_NODES if n["key"] == chosen["key"]), None)
            if node is None:
                break

            for feature, allowed in node["requires"].items():
                present = {
                    v for a in candidates_before
                    for v in (ANIMALS[a].get(feature) if isinstance(ANIMALS[a].get(feature), set)
                              else {ANIMALS[a].get(feature)})
                }
                assert present.issubset(allowed), (
                    f'{animal}: "{chosen["question"]}" asserts {feature}={allowed} '
                    f"but candidates still allow {present}"
                )

            answer = oracle_answer(node, animal)
            game["current_round_question_keys"].append(chosen["key"])
            game["questions_asked"] += 1
            if answer is not None:
                game["qa_history"].append({"question_key": chosen["key"], "answer": answer})
