"""Candidate ranking and guess cadence for Mystery Animal.

Two behaviors this module is responsible for:

1. Guessing the *likeliest* candidate rather than an arbitrary one. The
   previous ranking shuffled the surviving candidates and returned the first,
   so with (say) eight candidates left Star had a one-in-eight chance of being
   right and would burn its guesses on obscure animals while a dog or a cat was
   still on the list. Candidates are now ordered by how recognizable they are
   to a young child, with the random element reduced to a tie-break between
   animals of equal familiarity.

2. Not guessing before the evidence supports it. The first guess now needs the
   field genuinely narrowed, not just a question count.
"""
from __future__ import annotations

import random

from animal_database import ANIMALS
from question import infer_candidates, infer_state

# How readily a five- to seven-year-old recognizes and names each animal.
# Tier 1 is what a child is most likely to be thinking of; anything absent
# falls to the default tier, so an unusual animal is only guessed once the
# evidence has actually ruled the familiar ones out.
FAMILIARITY_TIERS = {
    1: {"dog", "cat", "bird", "fish", "horse", "cow", "rabbit", "duck", "chicken",
        "pig", "sheep", "elephant", "lion", "monkey", "bear", "frog", "snake",
        "turtle", "penguin", "dolphin", "giraffe", "tiger", "bee",
        "butterfly", "spider"},
    2: {"goat", "goose", "owl", "eagle", "zebra", "panda", "gorilla", "kangaroo",
        "deer", "fox", "wolf", "squirrel", "mouse", "hamster", "shark", "whale",
        "crab", "seal", "octopus", "bat", "snail", "ant", "ladybug", "lizard",
        "crocodile", "flamingo", "raccoon"},
}

_DEFAULT_TIER = 3


def familiarity(animal: str) -> int:
    for tier, members in FAMILIARITY_TIERS.items():
        if animal in members:
            return tier
    return _DEFAULT_TIER


def ranked_candidates(game_state):
    """Surviving candidates, most likely first."""
    candidates = list(infer_candidates(game_state))
    # Shuffle first so equally familiar animals do not always appear in the
    # same order, then sort by familiarity -- Python's sort is stable, so the
    # shuffle only breaks ties within a tier.
    random.shuffle(candidates)
    candidates.sort(key=familiarity)
    return candidates


def choose_database_guess(game_state):
    rejected = {str(x).lower() for x in game_state.get("rejected_guesses", []) or []}
    for animal in ranked_candidates(game_state):
        # The candidate set already excludes rejected guesses; this is a second
        # guard so a rejected animal can never be offered twice.
        if animal.lower() not in rejected and animal in ANIMALS:
            return animal
    return None


def should_make_guess(game_state):
    questions = int(game_state.get("questions_asked", 0) or 0)
    guesses = int(game_state.get("guesses_made", 0) or 0)
    cooldown = int(game_state.get("guess_cooldown_questions", 0) or 0)
    since = questions - int(game_state.get("last_guess_question_count", 0) or 0)

    state = infer_state(game_state)
    candidate_count = len(state["candidates"])

    if cooldown > 0 or guesses >= 3:
        return False

    if candidate_count == 0:
        return False

    if guesses == 0:
        # Guess as soon as the field is genuinely narrow, and hold off on a
        # blind guess while many candidates remain. The question-count escape
        # hatch is kept so a vague round still reaches a guess, but it now
        # requires the field to be at least moderately narrowed rather than
        # firing on question count alone.
        if candidate_count <= 3 and questions >= 2:
            return True
        if candidate_count <= 8 and questions >= 3:
            return True
        return questions >= 5 and candidate_count <= 15

    # After a wrong guess, wait for at least one new clue and only re-guess
    # while the field is small enough for the next guess to be meaningful.
    return since >= 1 and candidate_count <= 8
