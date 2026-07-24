"""Shared conversational-intent classification.

Covers the exact phrase lists in the brief plus the negation cases that the
previous per-game word-set matching got wrong ("I'm not done" was read as
"done" because the word set contained both "not" and "done").
"""
import pytest

from intent import classify_intent, is_continue_intent, is_repeat_request, is_stop_intent


STOP_PHRASES = [
    "I'm done.", "I am done.", "I'm finished.", "I am finished.", "Finished.",
    "I'm done with this.", "I want to stop.", "I want to finish.",
    "Finish for now.", "That's enough.", "I don't want to play anymore.",
    "I'm all done.", "No more.", "I don't want another round.",
    "I don't want to play again.", "That's enough for today.",
]

CONTINUE_PHRASES = [
    "Play again.", "I want to play again.", "Keep playing.",
    "Let's keep playing.", "Another round.", "I want another one.",
    "Continue.", "I'm ready for the next one.", "Let's do the next one.",
    "Move on.", "Next one.", "Go to the next one.", "One more round.",
    "Let's go to the farm.",
]

REPEAT_PHRASES = [
    "Can you repeat that?", "Can you say that again?",
    "Can you repeat the question?", "Ask me again.", "What did you say?",
    "I didn't hear you.", "I couldn't hear that.", "Say it one more time.",
    "Repeat it.", "What was the question?",
]

REDIRECT_PHRASES = [
    "What do you think?", "Do you want to play again?",
    "Do you want to be finished?", "Tell Star what you want.",
    "Mikey, what do you want to do?", "Can you tell her your answer?",
    "Do you want to keep playing or finish?",
]


@pytest.mark.parametrize("phrase", STOP_PHRASES)
def test_stop_phrases(phrase):
    assert classify_intent(phrase)["intent"] == "stop", phrase


@pytest.mark.parametrize("phrase", CONTINUE_PHRASES)
def test_continue_phrases(phrase):
    assert classify_intent(phrase)["intent"] == "continue", phrase


@pytest.mark.parametrize("phrase", REPEAT_PHRASES)
def test_repeat_phrases(phrase):
    assert classify_intent(phrase)["intent"] == "repeat", phrase


@pytest.mark.parametrize("phrase", REDIRECT_PHRASES)
def test_redirect_phrases(phrase):
    assert classify_intent(phrase)["intent"] == "redirect", phrase


# --- Negation: the specific bugs called out in the brief --------------------

@pytest.mark.parametrize(
    "phrase,expected",
    [
        ("I'm not done", "continue"),
        ("I am not done", "continue"),
        ("I'm not finished", "continue"),
        ("I don't want to stop", "continue"),
        ("I don't want to be done", "continue"),
        ("I don't want to play again", "stop"),
        ("I don't want another round", "stop"),
        ("I don't want to play anymore", "stop"),
    ],
)
def test_negation_flips_the_decision(phrase, expected):
    assert classify_intent(phrase)["intent"] == expected, phrase


def test_unsafe_substring_matching_is_not_used():
    """'I'm not done' must never be read as done."""
    assert classify_intent("I'm not done")["intent"] != "stop"
    assert not is_stop_intent("I'm not done")


def test_a_question_offering_both_options_is_not_a_decision():
    """A parent reading Star's own choices back is not an answer."""
    for phrase in [
        "Do you want to keep playing or finish?",
        "Do you want to play again or be done?",
    ]:
        assert classify_intent(phrase)["intent"] == "redirect", phrase


def test_empty_and_filler_are_unclear():
    for phrase in ["", "   ", "umm", "uh"]:
        assert classify_intent(phrase)["intent"] == "unclear", repr(phrase)


def test_ambiguous_ready_is_not_forced_into_a_decision():
    """'I'm ready' is context-dependent; the shared layer must not guess."""
    assert classify_intent("I'm ready")["intent"] == "unclear"


def test_convenience_helpers_agree_with_classify():
    assert is_stop_intent("I'm finished")
    assert is_continue_intent("play again")
    assert is_repeat_request("what did you say")
    assert not is_continue_intent("I'm finished")
