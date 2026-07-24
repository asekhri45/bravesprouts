/**
 * Drawing Game: completion phrases, transition choice recognition, and the
 * navigation decision.
 *
 * Covers the defects reported from real play:
 *   - completing a part effectively required the exact phrase "I'm done";
 *   - "I'm not done" was read as done, because the phrase list matched "done"
 *     as a bare substring with no negation handling;
 *   - naming the destination ("the farm") was classified unclear, so choosing
 *     the next drawing left the game sitting on the finished one;
 *   - an unclear answer silently kept the child on the current part instead of
 *     asking the choice again.
 *
 * Run with:  node --test tests/drawing_game_intent.test.mjs
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");

const SRC = readFileSync(join(root, "static", "js", "drawing_game.js"), "utf8");
const INTENT_SRC = readFileSync(join(root, "static", "js", "game-intent.js"), "utf8");

const win = {};
new Function("window", INTENT_SRC)(win);

function sliceBetween(startMarker, endMarker) {
  const start = SRC.indexOf(startMarker);
  const end = SRC.indexOf(endMarker);
  assert.ok(start !== -1, `missing start marker: ${startMarker}`);
  assert.ok(end !== -1, `missing end marker: ${endMarker}`);
  assert.ok(end > start, `markers out of order: ${startMarker} / ${endMarker}`);
  return SRC.slice(start, end);
}

// The completion-intent readers, lifted from the shipped file.
const doneBlock = sliceBetween(
  "  const KEEP_DRAWING_PHRASES = [",
  "  function transcriptHasPassiveDoneIntent(text)"
);

const { transcriptHasExplicitDoneIntent, transcriptWantsToKeepDrawing } = new Function(
  "window",
  `${doneBlock}
   return { transcriptHasExplicitDoneIntent, transcriptWantsToKeepDrawing };`
)(win);

// --- A. Natural completion phrases -----------------------------------------

const DONE_PHRASES = [
  "I'm done.", "I'm finished.", "Finished.", "I'm ready.",
  "I'm ready for the next part.", "Next.", "Let's move on.",
  "I finished it.", "I'm done with the flower.", "Go to the next one.",
  "I completed it.", "All done.", "That's it.",
];

for (const phrase of DONE_PHRASES) {
  test(`"${phrase}" completes the drawing part`, () => {
    assert.equal(transcriptHasExplicitDoneIntent(phrase), true);
  });
}

test("the exact phrase 'I'm done' is not required", () => {
  // The point of the activity is to encourage speech, not drill one sentence.
  const alternatives = DONE_PHRASES.filter((p) => !/i'm done/i.test(p));
  for (const phrase of alternatives) {
    assert.equal(transcriptHasExplicitDoneIntent(phrase), true, phrase);
  }
});

// --- Negation --------------------------------------------------------------

const KEEP_PHRASES = [
  "I'm not done.", "I am not done.", "I'm not ready.", "I need more time.",
  "Keep drawing.", "Wait.", "Not yet.", "A little more.", "I'm still drawing.",
];

for (const phrase of KEEP_PHRASES) {
  test(`"${phrase}" keeps drawing`, () => {
    assert.equal(
      transcriptHasExplicitDoneIntent(phrase),
      false,
      `"${phrase}" must not be read as completion`
    );
    assert.equal(transcriptWantsToKeepDrawing(phrase), true);
  });
}

test("'I'm not done' is never read as done", () => {
  assert.equal(transcriptHasExplicitDoneIntent("I'm not done"), false);
  assert.equal(transcriptHasExplicitDoneIntent("I am not done yet"), false);
});

// --- Repeat requests are not completion ------------------------------------

test("a repeat request does not complete the part", () => {
  for (const phrase of ["Can you repeat that?", "What did you say?", "Say it again."]) {
    assert.equal(transcriptHasExplicitDoneIntent(phrase), false, phrase);
  }
});

// --- C. Final transition wording -------------------------------------------

test("the final transition offers the next drawing or finishing, not more of a finished picture", () => {
  const block = sliceBetween(
    "This drawing is complete, so the real choice is",
    "} else if (isLastStageInCurrentScene() && isLastSceneInGame()) {"
  );

  // Only the spoken options matter; the surrounding comment legitimately
  // quotes the old wording to explain why it was replaced.
  const spoken = block.slice(block.indexOf("options = ["));

  assert.ok(
    /be done with drawing for today|finish drawing for today/.test(spoken),
    "the completed-drawing choice must offer finishing for today"
  );
  assert.ok(
    !/continue drawing this|keep working on this|keep adding details/.test(spoken),
    "must not offer to keep working on a picture that is already finished"
  );
  assert.ok(
    spoken.includes("nextSceneTarget"),
    "the next drawing must be named dynamically"
  );
});

test("the retry prompt matches the new wording", () => {
  const retry = sliceBetween("function buildStageDoneRetryPrompt()", "async function handleNoSpeech");
  assert.ok(retry.includes("be done with drawing for today"));
});

// --- D. The navigation decision --------------------------------------------

test("naming the destination is recognized as choosing the next drawing", () => {
  const block = sliceBetween("function classifySceneChoice(text) {", "async function handleSceneChoiceResponse");
  assert.ok(
    block.includes("namesDestination"),
    "answering with the drawing's name must be recognized"
  );
  assert.ok(
    block.includes("nextSceneDrawingTargetForSpeech()"),
    "the destination check must use the real next-drawing name"
  );
  // Recognized before the generic cue matching, and returns continue.
  assert.ok(/if \(namesDestination && !lower\.includes\("not "\)\) return "continue";/.test(block));
});

test("choosing the next drawing actually navigates to it", () => {
  const handler = sliceBetween("async function handleSceneChoiceResponse(transcript)", "function buildStageDoneRetryPrompt");
  const continueBranch = handler.slice(handler.indexOf('if (choice === "continue")'));
  assert.ok(
    continueBranch.includes("continueToNextScene()"),
    "the continue branch must actually advance the scene"
  );
});

test("an unclear stage answer re-asks instead of silently staying put", () => {
  const handler = sliceBetween("async function handleStageDoneResponse(transcript)", "function classifySceneChoice");
  assert.ok(
    handler.includes("stageDoneClarifications"),
    "unclear answers must be counted and re-asked"
  );
  assert.ok(
    handler.includes("buildStageDoneRetryPrompt()"),
    "the same choice must be asked again"
  );
  // Bounded, so an unreadable microphone cannot loop forever.
  assert.ok(/stageDoneClarifications <= \d/.test(handler));
});

test("a scene-choice repeat request replays the choice and changes nothing", () => {
  const handler = sliceBetween("async function handleSceneChoiceResponse(transcript)", "function buildStageDoneRetryPrompt");
  const repeatBranch = handler.slice(handler.indexOf('if (choice === "repeat")'));
  assert.ok(repeatBranch.includes("offerContinueAfterScene()"));
  assert.ok(
    !repeatBranch.slice(0, repeatBranch.indexOf("return;")).includes("continueToNextScene"),
    "repeating must not advance the game"
  );
});

// --- Shared module ---------------------------------------------------------

test("classification is delegated to the shared intent module", () => {
  assert.ok(SRC.includes("window.GameIntent"), "drawing game must use the shared classifier");
});

test("the keep-drawing gate is shared by both completion readers", () => {
  const passive = sliceBetween("function transcriptHasPassiveDoneIntent(text)", "function isLikelyChildQuestion");
  assert.ok(
    passive.includes("transcriptWantsToKeepDrawing(lower)"),
    "both readers must use the same keep-drawing gate so they cannot disagree"
  );
});
