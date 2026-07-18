"""Candidate ranking and guess cadence for Mystery Animal."""
from __future__ import annotations
import random
from question import infer_candidates


def ranked_candidates(game_state):
    candidates = list(infer_candidates(game_state))
    # Prefer familiar, specific guesses; stable random tie-break prevents identical rounds.
    random.shuffle(candidates)
    return candidates


def choose_database_guess(game_state):
    rejected = {str(x).lower() for x in game_state.get("rejected_guesses", [])}
    for animal in ranked_candidates(game_state):
        if animal not in rejected:
            return animal
    return None


def should_make_guess(game_state):
    questions = int(game_state.get("questions_asked", 0) or 0)
    guesses = int(game_state.get("guesses_made", 0) or 0)
    cooldown = int(game_state.get("guess_cooldown_questions", 0) or 0)
    since = questions - int(game_state.get("last_guess_question_count", 0) or 0)
    candidate_count = len(infer_candidates(game_state))
    if cooldown > 0 or guesses >= 3:
        return False
    if guesses == 0:
        return questions >= 2 and (candidate_count <= 8 or questions >= 3)
    return since >= 1 and candidate_count > 0
