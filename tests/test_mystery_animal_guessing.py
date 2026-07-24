"""Coverage for the Mystery Animal guessing brain.

get_open_ended_mystery_animal_guess is the single source of truth for whether
Star guesses and what she guesses. These tests pin the contract that:
  * OpenAI is the decision-maker (its should_guess drives the guess),
  * the full ordered question-answer history and the exact latest pair are sent,
  * rejected guesses are never repeated,
  * animals outside the local database are allowed through,
  * a deliberate "not yet" from OpenAI is respected (no silent rule-guess), and
  * the rule/database guess is used only as a fallback when OpenAI errors out.

No Flask app context is needed -- the function operates on a plain game_state
dict and only reaches out through app_module.client.responses.create, which is
mocked here so no real network call happens.
"""
import json
from unittest.mock import MagicMock, patch

import app as app_module


class _FakeResponse:
    def __init__(self, text):
        self.output_text = text


def _mock_openai(payload):
    """Return a MagicMock suitable for patching client.responses.create."""
    return MagicMock(return_value=_FakeResponse(json.dumps(payload)))


def _penguin_state(rejected=None):
    return {
        "qa_history": [
            {"question_key": "feathers", "question": "Does it have feathers?", "answer": "yes"},
            {"question_key": "fly", "question": "Can it fly?", "answer": "no"},
            {"question_key": "swim", "question": "Can it swim?", "answer": "yes"},
            {"question_key": "cold", "question": "Does it live somewhere cold?", "answer": "yes"},
        ],
        "rejected_guesses": list(rejected or []),
    }


def test_guesses_when_openai_says_should_guess():
    state = _penguin_state()
    payload = {"should_guess": True, "guess": "penguin", "confidence": 0.72, "reason": "cold swimming bird"}

    with patch.object(app_module.client.responses, "create", _mock_openai(payload)):
        guess = app_module.get_open_ended_mystery_animal_guess(state)

    assert guess == "penguin"


def test_does_not_guess_when_openai_says_not_yet():
    state = _penguin_state()
    payload = {"should_guess": False, "guess": None, "confidence": 0.3, "reason": "still broad"}

    with patch.object(app_module.client.responses, "create", _mock_openai(payload)):
        guess = app_module.get_open_ended_mystery_animal_guess(state)

    assert guess is None


def test_never_repeats_a_rejected_guess():
    state = _penguin_state(rejected=["penguin"])
    payload = {"should_guess": True, "guess": "penguin", "confidence": 0.9, "reason": "same as before"}

    with patch.object(app_module.client.responses, "create", _mock_openai(payload)):
        guess = app_module.get_open_ended_mystery_animal_guess(state)

    assert guess is None


def test_allows_animal_outside_local_database():
    # "axolotl" is not in animal_database.py / the guess profiles, but OpenAI
    # must still be allowed to propose it when the clues support it.
    state = {
        "qa_history": [
            {"question_key": "water", "question": "Does it live in water?", "answer": "yes"},
            {"question_key": "legs", "question": "Does it have legs?", "answer": "yes it has little legs"},
            {"question_key": "pink", "question": "What color is it?", "answer": "pink"},
        ],
        "rejected_guesses": [],
    }
    payload = {"should_guess": True, "guess": "axolotl", "confidence": 0.66, "reason": "pink water creature with legs"}

    with patch.object(app_module.client.responses, "create", _mock_openai(payload)):
        guess = app_module.get_open_ended_mystery_animal_guess(state)

    assert guess == "axolotl"


def test_prompt_contains_full_qa_history_and_latest_pair():
    state = _penguin_state()
    mock = _mock_openai({"should_guess": False, "guess": None, "confidence": 0.2, "reason": "x"})

    with patch.object(app_module.client.responses, "create", mock):
        app_module.get_open_ended_mystery_animal_guess(state)

    sent_prompt = mock.call_args.kwargs["input"][0]["content"]

    # Every question/answer in the round, plus the exact latest pair, must be
    # visible to the model.
    assert "Does it have feathers?" in sent_prompt
    assert "Does it live somewhere cold?" in sent_prompt
    assert "The exact latest question" in sent_prompt
    assert "The exact latest answer" in sent_prompt


def test_falls_back_to_rule_guess_only_when_openai_errors():
    state = _penguin_state()

    with patch.object(app_module.client.responses, "create", side_effect=RuntimeError("openai down")):
        with patch.object(app_module, "get_rule_based_mystery_animal_guess", return_value="bird"):
            guess = app_module.get_open_ended_mystery_animal_guess(state)

    assert guess == "bird"


def test_openai_not_yet_is_respected_even_if_rule_guess_exists():
    # A deliberate OpenAI "not yet" must win over any available local rule
    # guess -- the rule guess is a fallback for OpenAI being unavailable, not
    # an override of a real decision.
    state = _penguin_state()
    payload = {"should_guess": False, "guess": None, "confidence": 0.25, "reason": "still ambiguous"}

    with patch.object(app_module.client.responses, "create", _mock_openai(payload)):
        with patch.object(app_module, "get_rule_based_mystery_animal_guess", return_value="bird"):
            guess = app_module.get_open_ended_mystery_animal_guess(state)

    assert guess is None
