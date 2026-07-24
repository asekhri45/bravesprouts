/**
 * Structural tests for the Mystery Animal hearing-reliability fixes.
 *
 * The listening state machine in mystery_animal.js is tightly bound to
 * MediaRecorder, SpeechRecognition, and the DOM, so it cannot be unit-tested
 * without a real browser. These tests lock in the specific source-level
 * guarantees of the fix so a future edit cannot silently reintroduce the
 * regressions. Real end-to-end microphone behavior still requires a real-device
 * check (documented in the change summary).
 *
 * Run with:  node --test tests/mystery_animal_hearing.test.mjs
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SRC = readFileSync(join(__dirname, "..", "static", "js", "mystery_animal.js"), "utf8");

test("a soft (RMS-below-threshold) recording is still transcribed, not dropped as no_response", () => {
  // The stop handler must send any non-empty recording to transcription and
  // let the transcript decide silence -- it must NOT gate on speechDetected.
  assert.ok(
    SRC.includes("audioBlob.size >= MIN_TRANSCRIBABLE_BLOB_BYTES"),
    "recorder stop must transcribe based on captured-audio size, not the RMS flag"
  );
  assert.ok(
    !SRC.includes("if (!audioBlob.size || !speechDetected)"),
    "the old speechDetected no_response gate must be gone"
  );
});

test("MIN_TRANSCRIBABLE_BLOB_BYTES is a small floor so soft speech is never discarded", () => {
  const match = SRC.match(/MIN_TRANSCRIBABLE_BLOB_BYTES\s*=\s*(\d+)/);
  assert.ok(match, "MIN_TRANSCRIBABLE_BLOB_BYTES must be defined");
  assert.ok(Number(match[1]) <= 2000, "floor should be small (essentially empty-container detection)");
});

test("thinking-sound resume clears roundResolved so the next window accepts speech", () => {
  const fnStart = SRC.indexOf("function continueListeningAfterThinkingSound");
  assert.notEqual(fnStart, -1);
  const fnBody = SRC.slice(fnStart, fnStart + 1400);

  // When recognition is no longer active it must reset roundResolved and
  // restart listening rather than returning early on browsers that have
  // SpeechRecognition.
  assert.ok(fnBody.includes("recognitionActive"), "must consider whether recognition is still active");
  assert.ok(fnBody.includes("roundResolved = false"), "must clear roundResolved before restarting");
  assert.ok(fnBody.includes("startListeningForChild()"), "must restart the listening window");
});

test("stopping recognition does not clobber isListening while the recorder is still recording", () => {
  const fnStart = SRC.indexOf("function stopLiveSpeechRecognition");
  assert.notEqual(fnStart, -1);
  const fnBody = SRC.slice(fnStart, fnStart + 1400);

  // isListening may only be cleared when the authoritative recorder is not
  // actively capturing.
  assert.ok(
    fnBody.includes('mediaRecorder.state === "inactive"'),
    "isListening must only be cleared when the recorder is inactive"
  );
});
