"""Shared conversational-intent normalization for the mic games.

Every game asks the child some version of "are you done, or shall we keep
going?", and every game needs to survive a parent answering on the child's
behalf or the child asking for the question again. Those three signals were
previously re-implemented per game with ad-hoc word-set matching, which is how
"I'm not done" ended up being read as "done" (the word set contained both
"not" and "done" and simply took the union).

This module produces one normalized signal for a free-text child response. It
deliberately does NOT decide what a game should do with it: "stop" during a
drawing step means "this part is finished", while "stop" at an end-of-round
prompt means "end the session". Each game maps the label to its own state
machine.

Labels:
    "repeat"   - asked for the question again; never an answer
    "redirect" - a question or hand-off aimed at someone else; never an answer
    "stop"     - finish / done / that's enough
    "continue" - play again / keep going / next one
    "unclear"  - nothing confident enough to act on
"""
from __future__ import annotations

import re
from typing import Dict, List

# Contractions are expanded before matching so negation is a real token.
_CONTRACTIONS = [
    (r"\bcan'?t\b", "can not"),
    (r"\bwon'?t\b", "will not"),
    (r"\bdon'?t\b", "do not"),
    (r"\bdoesn'?t\b", "does not"),
    (r"\bdidn'?t\b", "did not"),
    (r"\bcouldn'?t\b", "could not"),
    (r"\bwouldn'?t\b", "would not"),
    (r"\bshouldn'?t\b", "should not"),
    (r"\bhaven'?t\b", "have not"),
    (r"\bhasn'?t\b", "has not"),
    (r"\bisn'?t\b", "is not"),
    (r"\baren'?t\b", "are not"),
    (r"\bwasn'?t\b", "was not"),
    (r"\bain'?t\b", "is not"),
    (r"\bi'?m\b", "i am"),
    (r"\bthat'?s\b", "that is"),
    (r"\bit'?s\b", "it is"),
    (r"\blet'?s\b", "let us"),
    (r"\bwe'?re\b", "we are"),
    (r"\bwe'?ve\b", "we have"),
    (r"\bi'?ve\b", "i have"),
    (r"\bwanna\b", "want to"),
    (r"\bgonna\b", "going to"),
]

_NEGATORS = {"not", "no", "never", "nothing", "neither", "nor", "without"}

# How many tokens after a negator it is taken to govern.
_NEGATION_WINDOW = 4

_REPEAT_PATTERNS = [
    r"\brepeat\b",
    r"\bsay (?:that|it|the question)? ?again\b",
    r"\bsay it one more time\b",
    r"\bone more time\b",
    r"\bagain please\b",
    r"\bwhat did you say\b",
    r"\bwhat was the question\b",
    r"\bwhat is the question\b",
    r"\bwhat were you saying\b",
    r"\bi did not hear\b",
    r"\bi could not hear\b",
    r"\bi cannot hear\b",
    r"\bi did not catch\b",
    r"\bask me again\b",
    r"\bask again\b",
    r"\bsay again\b",
    r"\bcome again\b",
    r"\bpardon\b",
    r"\bhuh\b",
]

# A question or hand-off aimed at someone else. Speech-to-text often drops the
# question mark, so this keys on structure and second-person phrasing instead.
_REDIRECT_PATTERNS = [
    r"\bwhat do you (?:think|want|say)\b",
    r"\bwhat about you\b",
    r"\bhow about you\b",
    r"\bdo you want\b",
    r"\bdo you think\b",
    r"\bwould you like\b",
    r"\bwould you rather\b",
    r"\bare you (?:done|finished|ready)\b",
    r"\bdo you wish\b",
    r"\bshould we\b",
    r"\bshould you\b",
    r"\bwhich (?:one )?do you\b",
    r"\btell (?:star|him|her|them|me what you)\b",
    r"\bcan you tell (?:star|him|her|them)\b",
    r"\bsay (?:it )?to star\b",
    r"\btalk to star\b",
    r"\banswer (?:star|the star|him|her)\b",
    r"\byou can (?:say|tell|answer|choose|pick|decide)\b",
    r"\byou decide\b",
    r"\bit is your (?:turn|choice|call)\b",
    r"\byour choice\b",
    r"\bup to you\b",
    r"\bwhat do you want to do\b",
]

# Multi-word cues are checked before single words so "no more" is not read as
# a bare negator, and "another round" beats a lone "another".
_STOP_CUES = [
    "all done", "be done", "am done", "are done", "is done", "no more",
    "that is enough", "enough for now", "enough for today", "had enough",
    "done for now", "done for today", "finish for now", "finish for today",
    "stop here", "end here", "be finished", "am finished",
    "go back", "take a break",
    "done", "finished", "finish", "stop", "quit", "enough",
]

_CONTINUE_CUES = [
    "play again", "play some more", "play more", "another round",
    "another one", "one more round", "one more time", "one more",
    "keep playing", "keep going", "go again", "carry on", "keep on",
    # "let's go to the farm" -- moving on to a named next thing. Distinct from
    # the "go back" stop cue, which is matched separately.
    "go to",
    "next one", "next round", "next drawing", "next part", "next thing",
    "do another", "do it again", "try again", "move on", "same game",
    "continue", "again", "another", "more", "next",
    # Almost always appears negated ("I don't want to play anymore"), where the
    # negation flips it to a stop. Listed here so that flip happens naturally.
    "anymore",
]


def normalize(text: str) -> str:
    lowered = str(text or "").lower().replace("’", "'")
    for pattern, replacement in _CONTRACTIONS:
        lowered = re.sub(pattern, replacement, lowered)
    lowered = re.sub(r"[^a-z0-9 ]+", " ", lowered)
    lowered = re.sub(r"\bany more\b", "anymore", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _negated_indices(tokens: List[str]) -> set:
    negated = set()
    for index, token in enumerate(tokens):
        if token not in _NEGATORS:
            continue

        # A sentence-initial "no" before a clause with its own subject is a
        # discourse marker contradicting the question, not a negation of what
        # follows: "No, I want to keep playing" means keep playing. Without
        # this it negated "keep playing" and read as a decision to stop.
        if (
            index == 0
            and token in {"no", "nope", "nah"}
            and index + 1 < len(tokens)
            and tokens[index + 1] in {"i", "we", "let", "lets", "im", "id"}
        ):
            continue

        for offset in range(1, _NEGATION_WINDOW + 1):
            if index + offset < len(tokens):
                negated.add(index + offset)
    return negated


def _find_cue(tokens: List[str], negated: set, cues: List[str]):
    """Return ("positive"|"negative", cue) for the first cue present."""
    joined = " ".join(tokens)

    for cue in cues:
        cue_tokens = cue.split()
        span = len(cue_tokens)

        for start in range(0, len(tokens) - span + 1):
            if tokens[start:start + span] != cue_tokens:
                continue
            # A cue is negated when the negator governs its first token.
            polarity = "negative" if start in negated else "positive"
            return polarity, cue

        if span > 1 and cue in joined:
            return "positive", cue

    return None, None


def classify_intent(text: str) -> Dict:
    """Normalized conversational intent for one child/parent utterance."""
    normalized = normalize(text)

    if not normalized:
        return {"intent": "unclear", "normalized": "", "cue": None}

    # A request to hear the question again is never an answer to it.
    for pattern in _REPEAT_PATTERNS:
        if re.search(pattern, normalized):
            return {"intent": "repeat", "normalized": normalized, "cue": pattern}

    # Neither is a question handed to someone else.
    for pattern in _REDIRECT_PATTERNS:
        if re.search(pattern, normalized):
            return {"intent": "redirect", "normalized": normalized, "cue": pattern}

    tokens = normalized.split()
    negated = _negated_indices(tokens)

    stop_polarity, stop_cue = _find_cue(tokens, negated, _STOP_CUES)
    continue_polarity, continue_cue = _find_cue(tokens, negated, _CONTINUE_CUES)

    stop_yes = stop_polarity == "positive"
    stop_no = stop_polarity == "negative"
    continue_yes = continue_polarity == "positive"
    continue_no = continue_polarity == "negative"

    # Straight readings first.
    if stop_yes and not continue_yes:
        return {"intent": "stop", "normalized": normalized, "cue": stop_cue}
    if continue_yes and not stop_yes:
        return {"intent": "continue", "normalized": normalized, "cue": continue_cue}

    # "I'm not done" / "I don't want to stop" -> keep going.
    if stop_no and not continue_yes:
        return {"intent": "continue", "normalized": normalized, "cue": "not " + str(stop_cue)}
    # "I don't want to play again" -> finish.
    if continue_no and not stop_yes:
        return {"intent": "stop", "normalized": normalized, "cue": "not " + str(continue_cue)}

    # Both sides present ("keep playing or finish?") -- not a decision.
    return {"intent": "unclear", "normalized": normalized, "cue": None}


def is_repeat_request(text: str) -> bool:
    return classify_intent(text)["intent"] == "repeat"


def is_stop_intent(text: str) -> bool:
    return classify_intent(text)["intent"] == "stop"


def is_continue_intent(text: str) -> bool:
    return classify_intent(text)["intent"] == "continue"
