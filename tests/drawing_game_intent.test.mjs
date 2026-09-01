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

const passiveBlock = sliceBetween(
  "  function transcriptHasPassiveDoneIntent(text)",
  "  function isLikelyChildQuestion"
);

const { transcriptHasPassiveDoneIntent } = new Function(
  "window",
  `${doneBlock}
   ${passiveBlock}
   function nextStageNameForSpeech() { return "sun"; }
   function nextSceneNameForSpeech() { return "farm picture"; }
   return { transcriptHasPassiveDoneIntent };`
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

test("passive listening accepts the same natural completion phrases", () => {
  for (const phrase of DONE_PHRASES) {
    assert.equal(transcriptHasPassiveDoneIntent(phrase), true, phrase);
  }
});

// --- Negation --------------------------------------------------------------

const KEEP_PHRASES = [
  "I'm not done.", "I am not done.", "I'm not ready.", "I need more time.",
  "Keep drawing.", "Wait.", "Not yet.", "A little more.", "I'm still drawing.",
  "I don't want to move on.", "I don't want to stop.",
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
  assert.ok(retry.includes("take a moment first"));
  assert.ok(!retry.includes("keep working on this part"));
});

test("a completed part is not described as unfinished in the follow-up choice", () => {
  const block = sliceBetween("async function askStarConfirmStageDone()", "async function saveNextSceneForReentryAfterCompletedScene");
  const options = block.slice(block.indexOf("} else {\n      const nextPartName"));
  assert.ok(options.includes("is finished"));
  assert.ok(!options.includes("keep working on the ${partName}"));
  assert.ok(!options.includes("continue adding details to the ${partName}"));
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

test("the final-stage choice accepts the short destination name", () => {
  const classifier = sliceBetween(
    "function classifyStageDoneResponse(text) {",
    "function transcriptSoundsLikeDone"
  );

  const classifyStageDoneResponse = new Function(
    `${classifier}
     function normalizedWords(text) {
       return String(text || "").toLowerCase().replace(/[^a-z0-9' ]/g, " ").split(/\\s+/).filter(Boolean);
     }
     function transcriptWantsToKeepDrawing() { return false; }
     function transcriptHasExplicitDoneIntent() { return false; }
     function nextStageNameForSpeech() { return "the next part"; }
     function nextSceneNameForSpeech() { return "farm picture"; }
     function nextSceneDrawingTargetForSpeech() { return "a farm"; }
     return classifyStageDoneResponse;`
  )();

  for (const answer of [
    "farm",
    "the farm",
    "I want to get started on the farm",
    "let's start the farm",
    "I want to draw the farm"
  ]) {
    assert.equal(classifyStageDoneResponse(answer), "done", answer);
  }
});

test("accepting the next drawing celebrates before advancing it", () => {
  const handler = sliceBetween("async function handleStageDoneResponse(transcript)", "function classifySceneChoice");
  const nextSceneBranch = handler.slice(handler.indexOf("} else if (shouldMoveStraightToNextScene)"));

  assert.ok(nextSceneBranch.includes("Yay! Let's get started"));
  assert.ok(nextSceneBranch.indexOf("Yay! Let's get started") < nextSceneBranch.indexOf("advanceStage({"));
  assert.ok(nextSceneBranch.includes("skipSceneChoice: shouldMoveStraightToNextScene"));
});

test("round 3 loads without waiting for progress saving", () => {
  const advance = sliceBetween("async function advanceStage(options = {})", "async function offerContinueAfterScene");
  const transition = sliceBetween("async function continueToNextScene()", "async function finishFullActivity");
  const skipBranch = advance.slice(advance.indexOf("if (!isLastScene)"));

  assert.ok(
    skipBranch.indexOf("if (options.skipSceneChoice)") < skipBranch.indexOf("await saveDrawingProgress()"),
    "a confirmed scene choice must bypass the blocking pre-transition save"
  );
  assert.ok(transition.includes("state.sceneIndex += 1"));
  assert.ok(transition.includes('saveDrawingProgress({ canvas_data: "" });'));
  assert.ok(!transition.includes('await saveDrawingProgress({ canvas_data: "" })'));
  assert.ok(transition.includes("beginStage({ clearCanvas: true })"));
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

test("speech can be interrupted by a natural completion phrase", () => {
  const listener = sliceBetween(
    "function startEarlyResponseSpeechRecognition(question, promptText)",
    "async function startResponseWindow"
  );

  assert.ok(listener.includes("transcriptHasPassiveDoneIntent(transcript)"));
  assert.ok(listener.includes("interruptCurrentCharacterAudio()"));
  assert.ok(listener.includes("interruptedDone = true"));
});

test("an early continue answer stops the prompt and is handled immediately", () => {
  const choiceReader = sliceBetween(
    "function isLikelyEarlyChoiceResponse(text, promptText = \"\")",
    "function stopEarlyResponseSpeechRecognition"
  );
  const listener = sliceBetween(
    "function startEarlyResponseSpeechRecognition(question, promptText)",
    "async function startResponseWindow"
  );

  assert.ok(choiceReader.includes("window.GameIntent.classify(lower)"));
  assert.ok(listener.includes('audioManager.cancelActive("child_answered_early")'));
});

test("an interrupted character reacts before the normal done acknowledgement", () => {
  const handler = sliceBetween(
    "async function handleDoneIntentFromSpeech(options = {})",
    "function countWords"
  );

  assert.ok(handler.includes("playInterruptionReaction"));
  assert.ok(handler.includes('"Oh!"'));
  assert.ok(handler.indexOf('"Oh!"') < handler.indexOf("askStarConfirmStageDone()"));
});

test("interrupting invalidates dialogue that was queued behind the speaker", () => {
  const queue = sliceBetween("function queueSpeak(actor, text, options = {})", "async function speakNow");
  const interrupt = sliceBetween("function interruptCurrentCharacterAudio()", "async function handleDoneIntentFromSpeech");

  assert.ok(queue.includes("generation !== speechQueueGeneration"));
  assert.ok(interrupt.includes("speechQueueGeneration += 1"));
});
