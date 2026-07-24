/**
 * Shared conversational-intent normalization for the mic games (browser side).
 *
 * Mirror of intent.py. Kept deliberately small and behaviour-compatible: the
 * same phrase lists, the same negation handling, the same five labels. Games
 * that classify on the client (Match Cards, Drawing Game) use this; games that
 * classify on the server use intent.py. Both must agree, so the phrase tables
 * below and in intent.py are maintained together.
 *
 * This module decides only what was *said*, never what a game should do with
 * it -- "stop" during a drawing step means "this part is finished", while
 * "stop" at an end-of-round prompt means "end the session". Each game maps the
 * label onto its own state machine.
 *
 * Labels: "repeat" | "redirect" | "stop" | "continue" | "unclear".
 */
(function (window) {
  "use strict";

  var CONTRACTIONS = [
    [/\bcan'?t\b/g, "can not"],
    [/\bwon'?t\b/g, "will not"],
    [/\bdon'?t\b/g, "do not"],
    [/\bdoesn'?t\b/g, "does not"],
    [/\bdidn'?t\b/g, "did not"],
    [/\bcouldn'?t\b/g, "could not"],
    [/\bwouldn'?t\b/g, "would not"],
    [/\bshouldn'?t\b/g, "should not"],
    [/\bhaven'?t\b/g, "have not"],
    [/\bhasn'?t\b/g, "has not"],
    [/\bisn'?t\b/g, "is not"],
    [/\baren'?t\b/g, "are not"],
    [/\bwasn'?t\b/g, "was not"],
    [/\bain'?t\b/g, "is not"],
    [/\bi'?m\b/g, "i am"],
    [/\bthat'?s\b/g, "that is"],
    [/\bit'?s\b/g, "it is"],
    [/\blet'?s\b/g, "let us"],
    [/\bwe'?re\b/g, "we are"],
    [/\bwe'?ve\b/g, "we have"],
    [/\bi'?ve\b/g, "i have"],
    [/\bwanna\b/g, "want to"],
    [/\bgonna\b/g, "going to"]
  ];

  var NEGATORS = {
    not: 1, no: 1, never: 1, nothing: 1, neither: 1, nor: 1, without: 1
  };

  var NEGATION_WINDOW = 4;

  var REPEAT_PATTERNS = [
    /\brepeat\b/,
    /\bsay (?:that|it|the question)? ?again\b/,
    /\bsay it one more time\b/,
    /\bone more time\b/,
    /\bagain please\b/,
    /\bwhat did you say\b/,
    /\bwhat was the question\b/,
    /\bwhat is the question\b/,
    /\bwhat were you saying\b/,
    /\bi did not hear\b/,
    /\bi could not hear\b/,
    /\bi cannot hear\b/,
    /\bi did not catch\b/,
    /\bask me again\b/,
    /\bask again\b/,
    /\bsay again\b/,
    /\bcome again\b/,
    /\bpardon\b/,
    /\bhuh\b/
  ];

  // Speech-to-text often drops the question mark, so redirection is detected
  // from question words, second-person phrasing and hand-off structure.
  var REDIRECT_PATTERNS = [
    /\bwhat do you (?:think|want|say)\b/,
    /\bwhat about you\b/,
    /\bhow about you\b/,
    /\bdo you want\b/,
    /\bdo you think\b/,
    /\bwould you like\b/,
    /\bwould you rather\b/,
    /\bare you (?:done|finished|ready)\b/,
    /\bdo you wish\b/,
    /\bshould we\b/,
    /\bshould you\b/,
    /\bwhich (?:one )?do you\b/,
    /\btell (?:star|him|her|them|me what you)\b/,
    /\bcan you tell (?:star|him|her|them)\b/,
    /\bsay (?:it )?to star\b/,
    /\btalk to star\b/,
    /\banswer (?:star|the star|him|her)\b/,
    /\byou can (?:say|tell|answer|choose|pick|decide)\b/,
    /\byou decide\b/,
    /\bit is your (?:turn|choice|call)\b/,
    /\byour choice\b/,
    /\bup to you\b/,
    /\bwhat do you want to do\b/
  ];

  // Multi-word cues come first so "no more" is not read as a bare negator and
  // "another round" beats a lone "another".
  var STOP_CUES = [
    "all done", "be done", "am done", "are done", "is done", "no more",
    "that is enough", "enough for now", "enough for today", "had enough",
    "done for now", "done for today", "finish for now", "finish for today",
    "stop here", "end here", "be finished", "am finished",
    "go back", "take a break",
    "done", "finished", "finish", "stop", "quit", "enough"
  ];

  var CONTINUE_CUES = [
    "play again", "play some more", "play more", "another round",
    "another one", "one more round", "one more time", "one more",
    "keep playing", "keep going", "go again", "carry on", "keep on", "go to",
    "next one", "next round", "next drawing", "next part", "next thing",
    "do another", "do it again", "try again", "move on", "same game",
    "continue", "again", "another", "more", "next",
    "anymore"
  ];

  function normalize(text) {
    var lowered = String(text == null ? "" : text).toLowerCase().replace(/’/g, "'");

    for (var i = 0; i < CONTRACTIONS.length; i++) {
      lowered = lowered.replace(CONTRACTIONS[i][0], CONTRACTIONS[i][1]);
    }

    lowered = lowered.replace(/[^a-z0-9 ]+/g, " ");
    lowered = lowered.replace(/\bany more\b/g, "anymore");
    return lowered.replace(/\s+/g, " ").trim();
  }

  function negatedIndices(tokens) {
    var SUBJECTS = { i: 1, we: 1, let: 1, lets: 1, im: 1, id: 1 };
    var negated = {};
    for (var i = 0; i < tokens.length; i++) {
      if (!NEGATORS[tokens[i]]) continue;

      // A sentence-initial "no" before a clause with its own subject is a
      // discourse marker contradicting the question, not a negation of what
      // follows: "No, I want to keep playing" means keep playing.
      if (i === 0 &&
          (tokens[i] === "no" || tokens[i] === "nope" || tokens[i] === "nah") &&
          SUBJECTS[tokens[i + 1]]) {
        continue;
      }

      for (var offset = 1; offset <= NEGATION_WINDOW; offset++) {
        if (i + offset < tokens.length) negated[i + offset] = true;
      }
    }
    return negated;
  }

  function findCue(tokens, negated, cues) {
    var joined = tokens.join(" ");

    for (var c = 0; c < cues.length; c++) {
      var cueTokens = cues[c].split(" ");
      var span = cueTokens.length;

      for (var start = 0; start + span <= tokens.length; start++) {
        var match = true;
        for (var k = 0; k < span; k++) {
          if (tokens[start + k] !== cueTokens[k]) { match = false; break; }
        }
        if (!match) continue;
        return { polarity: negated[start] ? "negative" : "positive", cue: cues[c] };
      }

      if (span > 1 && joined.indexOf(cues[c]) !== -1) {
        return { polarity: "positive", cue: cues[c] };
      }
    }

    return { polarity: null, cue: null };
  }

  function classifyIntent(text) {
    var normalized = normalize(text);

    if (!normalized) return { intent: "unclear", normalized: "", cue: null };

    var i;

    // A request to hear the question again is never an answer to it.
    for (i = 0; i < REPEAT_PATTERNS.length; i++) {
      if (REPEAT_PATTERNS[i].test(normalized)) {
        return { intent: "repeat", normalized: normalized, cue: "repeat" };
      }
    }

    // Neither is a question handed to someone else.
    for (i = 0; i < REDIRECT_PATTERNS.length; i++) {
      if (REDIRECT_PATTERNS[i].test(normalized)) {
        return { intent: "redirect", normalized: normalized, cue: "redirect" };
      }
    }

    var tokens = normalized.split(" ");
    var negated = negatedIndices(tokens);

    var stop = findCue(tokens, negated, STOP_CUES);
    var cont = findCue(tokens, negated, CONTINUE_CUES);

    var stopYes = stop.polarity === "positive";
    var stopNo = stop.polarity === "negative";
    var contYes = cont.polarity === "positive";
    var contNo = cont.polarity === "negative";

    if (stopYes && !contYes) return { intent: "stop", normalized: normalized, cue: stop.cue };
    if (contYes && !stopYes) return { intent: "continue", normalized: normalized, cue: cont.cue };

    // "I'm not done" / "I don't want to stop" -> keep going.
    if (stopNo && !contYes) return { intent: "continue", normalized: normalized, cue: "not " + stop.cue };
    // "I don't want to play again" -> finish.
    if (contNo && !stopYes) return { intent: "stop", normalized: normalized, cue: "not " + cont.cue };

    // Both sides present ("keep playing or finish?") -- not a decision.
    return { intent: "unclear", normalized: normalized, cue: null };
  }

  /**
   * True when the utterance expresses a complete conversational intent that a
   * game can act on right away. "Play again" and "the cat" are complete;
   * "umm", a trailing fragment, or a parent's question are not.
   */
  function isActionableIntent(intent) {
    return intent === "stop" || intent === "continue" || intent === "repeat";
  }

  window.GameIntent = {
    normalize: normalize,
    classify: classifyIntent,
    isActionableIntent: isActionableIntent,
    STOP_CUES: STOP_CUES,
    CONTINUE_CUES: CONTINUE_CUES
  };
})(window);
