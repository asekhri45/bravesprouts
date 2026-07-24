"""Coverage for the original Animal Guessing Game's question-vs-guess intent.

The core bug: a question that merely mentioned an animal ("Does it eat fish?")
was scored as a direct guess ("No, it is not a fish.") instead of being
answered as the food question it is. These tests pin:
  * is_guessing_direct_guess requires real guess syntax,
  * answer_guessing_question answers the actual semantic question,
  * the OpenAI semantic fallback handles valid-but-unusual questions, and
  * the secret animal is never leaked in a non-guess answer.

These are pure functions -- no Flask context needed. OpenAI is mocked where the
semantic fallback is exercised.
"""
import json
from unittest.mock import MagicMock, patch

import app as app_module


class _FakeResponse:
    def __init__(self, text):
        self.output_text = text


def _mock_openai(payload):
    return MagicMock(return_value=_FakeResponse(json.dumps(payload)))


# --- is_guessing_direct_guess: descriptive questions are NOT guesses ---------

def test_descriptive_questions_are_not_direct_guesses():
    not_guesses = [
        "does it eat fish",
        "is it bigger than a dog",
        "does it sound like a bird",
        "can it run as fast as a horse",
        "does it live near sharks",
    ]
    for phrase in not_guesses:
        assert app_module.is_guessing_direct_guess(phrase) is False, phrase


def test_real_guess_syntax_is_a_direct_guess():
    guesses = [
        "is it a dog",
        "i think it is a fish",
        "could it be a penguin",
        "maybe it's a cat",
        "penguin",
    ]
    for phrase in guesses:
        assert app_module.is_guessing_direct_guess(phrase) is True, phrase


def test_broad_category_question_is_not_a_direct_guess():
    # "Is it a bird?" must not be scored as a final guess (a penguin IS a bird).
    assert app_module.is_guessing_direct_guess("is it a bird") is False
    assert app_module.is_guessing_direct_guess("is it a fish") is False


# --- answer_guessing_question: answers the real question --------------------

def test_does_it_eat_fish_is_answered_as_food_not_a_wrong_guess():
    state = {"secret_animal": "cat"}
    result = app_module.answer_guessing_question("does it eat fish", state)

    assert result["type"] == "answer"
    assert result["question_answered"] is True
    # It must NOT be treated as "the animal is a fish".
    assert "not a fish" not in result["message"].lower()
    assert result.get("type") != "wrong_guess"


def test_is_it_a_fish_when_secret_is_fish_answers_the_category():
    state = {"secret_animal": "fish"}
    result = app_module.answer_guessing_question("is it a fish", state)

    assert result["type"] == "answer"
    assert "fish" in result["message"].lower()


def test_what_does_it_eat_is_a_food_answer():
    state = {"secret_animal": "giraffe"}
    result = app_module.answer_guessing_question("what does it eat", state)

    assert result["type"] == "answer"
    assert result["question_answered"] is True


# --- semantic fallback ------------------------------------------------------

def test_unusual_question_reaches_openai_semantic_fallback():
    state = {"secret_animal": "dolphin"}
    payload = {"question_understood": True, "is_direct_guess": False, "answer": "Yes, it is very playful."}

    with patch.object(app_module.client.responses, "create", _mock_openai(payload)):
        result = app_module.answer_guessing_question("is it a playful animal that likes games", state)

    assert result["type"] == "answer"
    assert result["question_answered"] is True
    assert "playful" in result["message"].lower()


def test_semantic_fallback_never_leaks_secret_animal_name():
    state = {"secret_animal": "dolphin"}
    # The model slips the secret name into a non-guess answer -- it must be
    # scrubbed before Star speaks it.
    payload = {"question_understood": True, "is_direct_guess": False, "answer": "Yes, a dolphin is very smart."}

    with patch.object(app_module.client.responses, "create", _mock_openai(payload)):
        result = app_module.answer_guessing_question("is it a smart animal", state)

    assert "dolphin" not in result["message"].lower()


def test_unintelligible_input_falls_back_to_gentle_support():
    state = {"secret_animal": "cat"}
    payload = {"question_understood": False, "is_direct_guess": False, "answer": None}

    with patch.object(app_module.client.responses, "create", _mock_openai(payload)):
        result = app_module.answer_guessing_question("blorptown wumbo", state)

    assert result["type"] == "support"
    assert result["question_answered"] is False


# --- live-route smoke test (full request path) ------------------------------

def _fake_tts_bytes(_text):
    return b"fake-mp3-bytes"


def test_does_it_eat_fish_through_live_endpoint_is_not_a_wrong_guess(app_client, make_user):
    """End-to-end through /api/guessing-game/message: 'Does it eat fish?' must
    be answered as a food question, never scored as a wrong guess of 'fish'.

    Uses the temp-DB fixtures so the real app.db is never touched.
    """
    from conftest import login_as_user

    user_id = make_user()
    login_as_user(app_client, user_id)

    with app_client.session_transaction() as sess:
        sess["guessing_game_history"] = []
        sess["guessing_game_state"] = {
            "secret_animal": "dog",  # deliberately NOT a fish
            "rounds_completed": 0,
            "wrong_guess_count": 0,
            "wrong_guesses": [],
        }

    with patch.object(app_module, "generate_star_voice_elevenlabs", side_effect=_fake_tts_bytes):
        resp = app_client.post(
            "/api/guessing-game/message",
            json={
                "event_type": "child_answer",
                "child_response": "does it eat fish",
                "response_mode": "open_hint",
            },
        )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    # It must not have been treated as guessing the animal "fish".
    assert body["stage"] != "wrong_guess"
    assert "not a fish" not in body["message"].lower()
    assert body["game_state"]["wrong_guess_count"] == 0
