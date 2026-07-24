/**
 * Focused tests for the Drawing Game done-intent priority fix.
 *
 * drawing_game.js is a browser IIFE with heavy DOM/audio dependencies, so the
 * two self-contained done-detection functions are extracted from the real
 * source text (via brace matching) and evaluated in isolation -- this exercises
 * the shipped code, not a copy. Structural assertions then verify the
 * handleSpeech reorder and the passive-recorder format fix directly against the
 * source.
 *
 * Run with:  node --test tests/drawing_game_done.test.mjs
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SRC = readFileSync(join(__dirname, "..", "static", "js", "drawing_game.js"), "utf8");

/** Extract a full `function NAME(...) { ... }` block by brace matching. */
function extractFunction(source, name) {
  const start = source.indexOf(`function ${name}(`);
  assert.notEqual(start, -1, `could not find function ${name} in source`);

  const braceStart = source.indexOf("{", start);
  let depth = 0;
  for (let i = braceStart; i < source.length; i++) {
    if (source[i] === "{") depth++;
    else if (source[i] === "}") {
      depth--;
      if (depth === 0) return source.slice(start, i + 1);
    }
  }
  throw new Error(`unbalanced braces extracting ${name}`);
}

// transcriptSoundsLikeDone calls transcriptHasExplicitDoneIntent, which in
// turn uses the shared keep-drawing gate and the shared GameIntent classifier
// -- eval them all together so every reference resolves.
const INTENT_SRC = readFileSync(join(__dirname, "..", "static", "js", "game-intent.js"), "utf8");
const intentWindow = {};
new Function("window", INTENT_SRC)(intentWindow);

const KEEP_PHRASES_SRC = SRC.slice(
  SRC.indexOf("const KEEP_DRAWING_PHRASES = ["),
  SRC.indexOf("function transcriptHasExplicitDoneIntent")
);

const doneFns = new Function(
  "window",
  KEEP_PHRASES_SRC +
    "\n" +
    extractFunction(SRC, "transcriptHasExplicitDoneIntent") +
    "\n" +
    extractFunction(SRC, "transcriptSoundsLikeDone") +
    "\nreturn { transcriptSoundsLikeDone, transcriptHasExplicitDoneIntent };"
)(intentWindow);

test("explicit completion phrases are detected as done", () => {
  const donePhrases = [
    "I'm done",
    "I am done",
    "All done",
    "I'm finished",
    "Finished",
    "That's it",
    "Ready for the next one",
    "Move on",
    "done",
  ];
  for (const phrase of donePhrases) {
    assert.equal(doneFns.transcriptSoundsLikeDone(phrase), true, phrase);
  }
});

test("keep-going phrases must NOT be treated as done", () => {
  const keepPhrases = [
    "Not done yet",
    "I'm not done",
    "I need more time",
    "keep drawing",
    "wait, not yet",
    "a little more",
  ];
  for (const phrase of keepPhrases) {
    assert.equal(doneFns.transcriptSoundsLikeDone(phrase), false, phrase);
  }
});

test("handleSpeech checks explicit done-intent BEFORE the side_question branch", () => {
  const doneCheck = SRC.indexOf("hasDrawnThisStage && transcriptSoundsLikeDone(transcript)");
  const sideQuestion = SRC.indexOf('question?.intent === "side_question"');

  assert.notEqual(doneCheck, -1, "done-intent check not found");
  assert.notEqual(sideQuestion, -1, "side_question branch not found");
  assert.ok(
    doneCheck < sideQuestion,
    "explicit done-intent must be evaluated before the generic side_question handler"
  );
});

test("passive recorder uploads the actual browser format, not a hardcoded .webm", () => {
  assert.ok(
    !SRC.includes('"drawing-passive-done.webm"'),
    "passive recorder must not hardcode a .webm filename"
  );
  assert.ok(
    SRC.includes("drawing-passive-done.${passiveExtension}"),
    "passive recorder must derive the upload extension from the recorded mime type"
  );
});
