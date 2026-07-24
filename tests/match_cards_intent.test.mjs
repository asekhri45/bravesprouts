/**
 * Match Cards: intent handling, listening lifecycle, and the rounds 7-12
 * follow-up questions.
 *
 * Classification now lives in the shared static/js/game-intent.js (mirrored by
 * intent.py on the server), so the behavioural tests below load that module
 * directly and the Match Cards tests check the mapping and the question
 * templates that remain game-specific. Nothing is duplicated: both files are
 * read from the shipped source, so a rename fails loudly rather than silently
 * testing a stale copy.
 *
 * Run with:  node --test tests/match_cards_intent.test.mjs
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");

const MATCH_SRC = readFileSync(join(root, "static", "js", "match_cards.js"), "utf8");
const INTENT_SRC = readFileSync(join(root, "static", "js", "game-intent.js"), "utf8");

const win = {};
new Function("window", INTENT_SRC)(win);
const GameIntent = win.GameIntent;

function sliceBetween(src, startMarker, endMarker) {
  const start = src.indexOf(startMarker);
  const end = src.indexOf(endMarker);
  assert.ok(start !== -1, `could not find start marker: ${startMarker}`);
  assert.ok(end !== -1, `could not find end marker: ${endMarker}`);
  assert.ok(end > start, `markers out of order: ${startMarker} / ${endMarker}`);
  return src.slice(start, end);
}

// The Match Cards mapping + fragment detection, lifted from the shipped file
// and given the real GameIntent to run against.
const mappingBlock = sliceBetween(
  MATCH_SRC,
  "  function classifyPlayAgainResponseLocally(rawTranscript) {",
  "  /*\n    Only consulted when the local patterns above cannot decide."
);

const { classifyPlayAgainResponseLocally, looksLikeIncompleteFragment } = new Function(
  "window",
  `${mappingBlock}\nreturn { classifyPlayAgainResponseLocally, looksLikeIncompleteFragment };`
)(win);

// --- Direct child answers must be recognized -------------------------------

const FINISH_PHRASES = [
  "I'm done.", "I'm finished.", "I want to be done.", "Finish for now.",
  "I am done.", "Finished.", "Let's finish.", "That's enough.",
  "I don't want to play anymore.", "I'm all done.",
];

for (const phrase of FINISH_PHRASES) {
  test(`"${phrase}" -> stop`, () => {
    assert.equal(classifyPlayAgainResponseLocally(phrase), "stop");
  });
}

const CONTINUE_PHRASES = [
  "Play again.", "I want to play again.", "Let's keep playing.",
  "Another round.", "Keep playing.", "Continue.", "I want another one.",
];

for (const phrase of CONTINUE_PHRASES) {
  test(`"${phrase}" -> play_again`, () => {
    assert.equal(classifyPlayAgainResponseLocally(phrase), "play_again");
  });
}

// --- Parent redirection is never a decision --------------------------------

const REDIRECTION_PHRASES = [
  "What do you think?",
  "Do you want to play again?",
  "Do you want to be finished?",
  "Tell Star what you want.",
  "Mikey, what do you want to do?",
  "Can you tell her your answer?",
  "Do you want to keep playing or finish?",
];

for (const phrase of REDIRECTION_PHRASES) {
  test(`"${phrase}" -> redirect (keep listening)`, () => {
    assert.equal(classifyPlayAgainResponseLocally(phrase), "redirect");
  });
}

// --- Negation --------------------------------------------------------------

test("negation is respected", () => {
  assert.equal(classifyPlayAgainResponseLocally("I'm not done"), "play_again");
  assert.equal(classifyPlayAgainResponseLocally("I don't want to stop"), "play_again");
  assert.equal(classifyPlayAgainResponseLocally("I don't want to play again"), "stop");
});

// --- Repeat requests -------------------------------------------------------

test("repeat requests are their own outcome, never an answer", () => {
  for (const phrase of [
    "Can you repeat the question?", "Can you say that again?",
    "What did you say?", "I didn't hear you.", "Say it one more time.",
  ]) {
    assert.equal(classifyPlayAgainResponseLocally(phrase), "repeat", phrase);
  }
});

// --- Fragments must not be dispatched --------------------------------------

test("an unfinished reply is held, not dispatched", () => {
  for (const fragment of ["I want to", "I want to...", "Let us", "I'd like to", "Can we"]) {
    assert.equal(
      looksLikeIncompleteFragment(fragment),
      true,
      `"${fragment}" should be held for the next window`
    );
  }
});

test("a complete short answer is never mistaken for a fragment", () => {
  for (const answer of ["play again", "I'm done", "the cat", "another round"]) {
    assert.equal(looksLikeIncompleteFragment(answer), false, answer);
  }
});

test("a held fragment plus the rest classifies correctly", () => {
  // What runPlayAgainExchange does: stitch, then classify.
  assert.equal(classifyPlayAgainResponseLocally("I want to play again"), "play_again");
  assert.equal(classifyPlayAgainResponseLocally("I want to be done"), "stop");
});

// --- Listening lifecycle ---------------------------------------------------

test("the play-again window closes promptly after the child stops speaking", () => {
  const detector = sliceBetween(MATCH_SRC, "const speechThreshold", "dlog(\"speech detector started\"");
  const silence = detector.match(/endingSilenceMs\s*=\s*isPlayAgainWindow\s*\?\s*(\d+)/);
  assert.ok(silence, "endingSilenceMs must be defined for the play-again window");
  assert.ok(
    Number(silence[1]) <= 1000,
    `trailing silence is ${silence[1]}ms; a direct answer should not wait that long`
  );
});

test("the exchange is a bounded loop with a recovery default", () => {
  assert.ok(MATCH_SRC.includes("async function runPlayAgainExchange(question)"));
  assert.ok(/PLAY_AGAIN_MAX_LISTENS\s*=\s*\d+/.test(MATCH_SRC));
  assert.ok(MATCH_SRC.includes("play_again_exchange_defaulted"));
});

test("mic visual state has a single owner", () => {
  assert.ok(MATCH_SRC.includes("function setMicListeningUI(active)"));
  assert.ok(!MATCH_SRC.includes('micControl.classList.add("quiet-listening")'));
});

test("classification is not duplicated in this file", () => {
  assert.ok(
    !MATCH_SRC.includes("PLAY_AGAIN_CONTINUE_PATTERNS"),
    "the local phrase tables must be gone; GameIntent owns classification"
  );
  assert.ok(MATCH_SRC.includes("window.GameIntent"));
});

// --- Rounds 7-12 question quality ------------------------------------------

const questionBlock = sliceBetween(
  MATCH_SRC,
  "  const CARD_CATEGORIES = {",
  "  function remainingPairsText(count)"
);

const cardQuestions = new Function(
  `${questionBlock}\nreturn { CARD_CATEGORIES, cardCategory, getTwoCardChoiceQuestions,
     ANY_PAIR_QUESTIONS, BOTH_ANIMAL_QUESTIONS, BOTH_PLANT_QUESTIONS,
     MATCHED_CARD_CHOICE_QUESTIONS };`
)();

test("both round bands use the same revealed-card question system", () => {
  assert.ok(MATCH_SRC.includes("function getRevealedCardQuestion(context)"));
  // Rounds 7-9 and rounds 10-12 both delegate to it.
  const help = sliceBetween(MATCH_SRC, "function getHelpPrompt(context = {})", "function getClearQuestion");
  assert.ok(help.includes("getRevealedCardQuestion(context)"));
  const clear = sliceBetween(MATCH_SRC, "function getClearQuestion(context = {})", "function getSimpleChoiceQuestion");
  assert.ok(clear.includes("getRevealedCardQuestion(context)"));
});

function allQuestionText() {
  return [
    ...cardQuestions.ANY_PAIR_QUESTIONS,
    ...cardQuestions.BOTH_ANIMAL_QUESTIONS,
    ...cardQuestions.BOTH_PLANT_QUESTIONS,
    ...Object.values(cardQuestions.MATCHED_CARD_CHOICE_QUESTIONS).flat(),
  ];
}

test("rounds 10-12 no longer ask which card to remember", () => {
  // Checked against the live question pools; the old wording may still appear
  // in a comment explaining why it was replaced.
  for (const q of allQuestionText()) {
    assert.ok(!/should i remember/i.test(q), q);
    assert.ok(!/what card should i watch/i.test(q), q);
  }
});

test("the vague 'take care of' question is gone", () => {
  for (const q of allQuestionText()) {
    assert.ok(
      !/rather take care of/i.test(q),
      `'take care of' is too abstract for a five-year-old: ${q}`
    );
  }
});

test("every generated question is a this-or-that, never yes/no", () => {
  const all = [
    ...cardQuestions.ANY_PAIR_QUESTIONS,
    ...cardQuestions.BOTH_ANIMAL_QUESTIONS,
    ...cardQuestions.BOTH_PLANT_QUESTIONS,
  ];
  assert.ok(all.length >= 15, "expected a decent pool");
  for (const q of all) {
    assert.ok(/^Which /.test(q), `not a this-or-that: ${q}`);
    assert.ok(q.includes("{first}") && q.includes("{second}"), `must name both cards: ${q}`);
  }
});

test("matched-pair questions offer two concrete options", () => {
  for (const [card, options] of Object.entries(cardQuestions.MATCHED_CARD_CHOICE_QUESTIONS)) {
    for (const q of options) {
      assert.ok(/^(Would you rather|Which )/.test(q), `${card}: ${q}`);
      assert.ok(q.includes(" or "), `${card}: must offer two options: ${q}`);
    }
  }
});

// --- Category applicability ------------------------------------------------

test("a pet question is never asked about a flower", () => {
  const mixed = cardQuestions.getTwoCardChoiceQuestions("dog", "flower");
  for (const q of mixed) {
    assert.ok(!q.includes("as a pet"), `pet question offered for a mixed pair: ${q}`);
    assert.ok(!q.includes("at a zoo"), `zoo question offered for a mixed pair: ${q}`);
    assert.ok(!q.includes("move faster"), `speed question offered for a mixed pair: ${q}`);
  }
});

test("a smells-nicer question is never asked about an animal", () => {
  for (const pair of [["dog", "cat"], ["dog", "flower"], ["flower", "bird"]]) {
    const questions = cardQuestions.getTwoCardChoiceQuestions(pair[0], pair[1]);
    for (const q of questions) {
      assert.ok(!q.includes("smell nicer"), `${pair}: ${q}`);
      assert.ok(!q.includes("in a bouquet"), `${pair}: ${q}`);
    }
  }
});

test("animal-only questions are offered for two animals", () => {
  const animals = cardQuestions.getTwoCardChoiceQuestions("dog", "cat");
  assert.ok(animals.some((q) => q.includes("as a pet")));
  assert.ok(animals.some((q) => q.includes("move faster")));
});

test("mixed pairs still get a usable pool of neutral questions", () => {
  const mixed = cardQuestions.getTwoCardChoiceQuestions("bird", "flower");
  assert.ok(mixed.length >= 8, "a mixed pair must still have plenty to ask");
  assert.ok(mixed.some((q) => q.includes("rather draw")));
});

test("every card in the deck has a category", () => {
  for (const card of ["cat", "dog", "bunny", "fish", "bird", "flower"]) {
    assert.ok(cardQuestions.CARD_CATEGORIES[card], `${card} has no category`);
  }
  assert.equal(cardQuestions.cardCategory("flower"), "plant");
  assert.equal(cardQuestions.cardCategory("dog"), "animal");
});

// --- Agreement -------------------------------------------------------------

test("Star can agree using the card the child actually chose", () => {
  assert.ok(MATCH_SRC.includes("CARD_AGREEMENT_LINES"));
  assert.ok(MATCH_SRC.includes("function getCardAgreementLine(cardName)"));
  const block = sliceBetween(MATCH_SRC, "const CARD_AGREEMENT_LINES = {", "function getCardAgreementLine");
  for (const card of ["cat", "dog", "bunny", "fish", "bird", "flower"]) {
    assert.ok(block.includes(`${card}: [`), `no agreement lines for ${card}`);
  }
});

test("agreement is occasional, not every time", () => {
  const ack = sliceBetween(MATCH_SRC, "if (question?.isPreference) {", "preference_ack");
  assert.ok(/Math\.random\(\)\s*<\s*0?\.\d+/.test(ack), "agreement must be probabilistic");
  assert.ok(
    ack.includes("if (namedCard)"),
    "agreement must only fire when the chosen card was actually understood"
  );
});

// --- Shared-module parity --------------------------------------------------

test("the browser classifier agrees with the phrase lists it shares with the server", () => {
  assert.equal(GameIntent.classify("I'm done").intent, "stop");
  assert.equal(GameIntent.classify("play again").intent, "continue");
  assert.equal(GameIntent.classify("can you repeat that").intent, "repeat");
  assert.equal(GameIntent.classify("what do you think").intent, "redirect");
  assert.equal(GameIntent.classify("I'm not done").intent, "continue");
});
