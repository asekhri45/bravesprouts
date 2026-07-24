"""Round-1 coaching for the child-led animal guessing game.

Star should help a first-round child know what to ask next and what their
options are, without repeating the same template, without suggesting a topic
they already asked about, and without changing how later rounds behave.
"""
import random

import app as app_module


def make_state(rounds_completed=0, questions_asked=0, wrong_guess_count=0, asked_topics=None,
               recent_follow_ups=None):
    return {
        "rounds_completed": rounds_completed,
        "questions_asked": questions_asked,
        "wrong_guess_count": wrong_guess_count,
        "asked_topics": list(asked_topics or []),
        "recent_follow_ups": list(recent_follow_ups or []),
    }


# --- Suggestions ----------------------------------------------------------

def test_suggestion_never_repeats_an_already_asked_topic():
    random.seed(0)
    state = make_state(asked_topics=["habitat", "size", "appearance"])

    for _ in range(200):
        suggestion = app_module.get_guessing_game_topic_suggestion(state)
        if not suggestion:
            continue
        lowered = suggestion.lower()
        assert "where it lives" not in lowered
        assert "habitat" not in lowered
        assert "how big it is" not in lowered
        assert "covers its body" not in lowered


def test_suggestion_is_empty_once_every_topic_has_been_asked():
    state = make_state(asked_topics=list(app_module.GUESSING_GAME_SUGGESTION_ORDER))
    assert app_module.get_guessing_game_topic_suggestion(state) == ""


def test_suggestions_vary_rather_than_repeating_one_template():
    random.seed(1)
    state = make_state()
    seen = {app_module.get_guessing_game_topic_suggestion(state) for _ in range(120)}
    seen.discard("")
    assert len(seen) >= 6, f"suggestions should vary, only saw {len(seen)}"


def test_suggestion_never_names_an_animal_or_reveals_the_answer():
    random.seed(2)
    state = make_state()
    for _ in range(150):
        suggestion = app_module.get_guessing_game_topic_suggestion(state).lower()
        for animal in ["dog", "cat", "horse", "elephant", "bird", "fish", "rabbit"]:
            assert animal not in suggestion, f"suggestion leaked an animal: {suggestion}"


# --- Reminders ------------------------------------------------------------

def test_reminder_appears_on_reminder_turns_and_mentions_the_options():
    random.seed(3)
    for turn in (2, 6, 10):
        state = make_state()
        line = app_module.get_guessing_game_first_round_follow_up(state, turn).lower()
        assert line, f"turn {turn} should produce a reminder"
        assert any(word in line for word in ["ask", "guess", "clue"])


def test_reminders_are_not_repeated_back_to_back():
    random.seed(4)
    state = make_state()
    first = app_module.get_guessing_game_first_round_follow_up(state, 2)
    second = app_module.get_guessing_game_first_round_follow_up(state, 6)
    assert first != second, "consecutive reminders must not use identical wording"


def test_coaching_does_not_fire_after_every_single_answer():
    """Some turns must stay quiet so Star does not crowd the child."""
    random.seed(5)
    state = make_state()
    quiet_turns = 0
    for turn in range(1, 13):
        if not app_module.get_guessing_game_first_round_follow_up(state, turn):
            quiet_turns += 1
    assert quiet_turns >= 4, f"expected several quiet turns, got {quiet_turns}"


# --- Round scoping --------------------------------------------------------

def test_later_rounds_keep_their_original_follow_up_behaviour():
    """Rounds 2+ must be untouched: silent except on turns 4 and 8."""
    random.seed(6)
    for turn in range(1, 13):
        state = make_state(rounds_completed=1, questions_asked=turn)
        follow_up = app_module.get_guessing_game_follow_up_after_answer(state)
        if turn in {4, 8}:
            assert follow_up, f"round 2 turn {turn} should still give the original follow-up"
            assert "example questions" in follow_up
        else:
            assert follow_up == "", f"round 2 turn {turn} should stay silent, got: {follow_up}"


def test_first_round_uses_the_new_coaching_path():
    random.seed(7)
    state = make_state(rounds_completed=0, questions_asked=1)
    follow_up = app_module.get_guessing_game_follow_up_after_answer(state)
    assert follow_up, "round 1 should offer a suggestion on turn 1"
    assert "example questions" not in follow_up, "round 1 uses the coaching wording"


def test_suggestions_only_reference_known_topics():
    valid_phrases = {
        phrase
        for phrases in app_module.GUESSING_GAME_TOPIC_SUGGESTIONS.values()
        for phrase in phrases
    }
    random.seed(8)
    state = make_state()
    for _ in range(100):
        suggestion = app_module.get_guessing_game_topic_suggestion(state)
        if suggestion:
            assert any(phrase in suggestion for phrase in valid_phrases)


def test_every_suggestion_topic_is_a_real_question_topic():
    """Topic keys must match what get_guessing_question_topic() records."""
    for topic in app_module.GUESSING_GAME_SUGGESTION_ORDER:
        assert topic in app_module.GUESSING_GAME_TOPIC_SUGGESTIONS
