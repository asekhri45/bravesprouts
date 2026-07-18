/*
 * Debug-only diagnostic harness for the concurrent MediaRecorder +
 * SpeechRecognition coordination pattern shared by guessing_game.js,
 * guessing_game_2.js, mystery_animal.js, book_guessing_game.js,
 * library_guessing_game.js, mystery_food_item.js, and toy_trivia_game.js.
 *
 * This is NOT a general-purpose test framework and does not load or invoke
 * the real game files -- none of them expose their internal state for
 * outside testing, and adding that hook to seven working games was judged
 * too risky for what this task needs. Instead, SpeechRoundCoordinator below
 * is a small, faithful re-implementation of the exact guard logic those
 * files now share (the "roundResolved" flag and the cross-cancellation
 * rules around it), so its behavior can be asserted deterministically with
 * mocked recognition/recorder events. If this coordinator's tests pass, the
 * pattern itself is sound; it does not prove any single game file wires the
 * pattern correctly -- that still needs a real browser + real game session.
 *
 * Only ever loaded by /debug/speech-harness, which 404s unless
 * app.config["DEBUG"] is true (see app.py). Never linked from any
 * production page or activity template.
 */

class SpeechRoundCoordinator {
  constructor() {
    this.reset();
    this.log = [];
  }

  reset() {
    this.roundResolved = false;
    this.recognitionActive = false;
    this.recorderActive = false;
    this.recorderIgnored = false;
    this.serverRequestCount = 0;
    this.roundAdvanceCount = 0;
    this.noResponseCount = 0;
  }

  _emit(action, detail) {
    this.log.push({ action, detail: detail || null });
  }

  // Mirrors startListeningForChild(): always starts the recorder first,
  // then layers recognition on top if available.
  startRound({ withRecognition = true } = {}) {
    this.roundResolved = false;
    this.recorderIgnored = false;
    this._emit("round_started");

    this.recorderActive = true;
    this._emit("recorder_started");

    if (this.roundResolved) return;

    if (withRecognition) {
      this.recognitionActive = true;
      this._emit("recognition_started");
    }
  }

  // Mirrors submitLiveTranscript(): recognition produced a usable
  // transcript and wins the race.
  recognitionResult(transcript) {
    if (this.roundResolved) {
      this._emit("recognition_result_ignored_already_resolved", transcript);
      return;
    }
    this.roundResolved = true;
    this.recognitionActive = false;
    this._emit("recognition_won", transcript);

    // cancelConcurrentRecorder()
    if (this.recorderActive) {
      this.recorderIgnored = true;
      this.recorderActive = false;
      this._emit("recorder_cancelled");
    }

    this.roundAdvanceCount += 1;
    this._emit("round_advanced", { via: "recognition", transcript });
  }

  // Mirrors recognition.onerror: any error just stops the recognizer and
  // defers to the still-running recorder. Never independently resolves.
  recognitionError(errorType) {
    if (this.roundResolved) {
      this._emit("recognition_error_ignored_already_resolved", errorType);
      return;
    }
    this.recognitionActive = false;
    this._emit("recognition_error_deferred_to_recorder", errorType);
  }

  // Mirrors recognitionHardCapTimer with no usable transcript: stop
  // recognizing, defer to the recorder, do not resolve the round.
  recognitionHardCapNoTranscript() {
    if (this.roundResolved) {
      this._emit("recognition_hardcap_ignored_already_resolved");
      return;
    }
    this.recognitionActive = false;
    this._emit("recognition_hardcap_deferred_to_recorder");
  }

  // Mirrors recognition.onend firing more than once for the same
  // recognizer instance (a duplicate/late browser event).
  recognitionEndDuplicate() {
    this._emit("recognition_end_duplicate_received");
    // No-op by design: onend never resolves the round on its own in the
    // real implementation, so a duplicate firing has nothing to do.
  }

  // Mirrors the MediaRecorder "stop" handler: the recorder is the
  // authoritative end of the response window.
  recorderStop({ size, speechDetected }) {
    if (this.recorderIgnored) {
      this._emit("recorder_stop_ignored_cancelled");
      this.recorderIgnored = false;
      return;
    }
    if (this.roundResolved) {
      this._emit("recorder_stop_ignored_already_resolved");
      return;
    }

    this.roundResolved = true;
    this.recorderActive = false;
    if (this.recognitionActive) {
      this.recognitionActive = false;
      this._emit("recognition_cross_cancelled");
    }

    if (!size || !speechDetected) {
      this.noResponseCount += 1;
      this._emit("round_advanced", { via: "recorder_no_speech" });
      this.roundAdvanceCount += 1;
      return;
    }

    this.serverRequestCount += 1;
    this._emit("server_request_sent", { size });
  }

  // Mirrors sendAudioToTranscribe()'s catch block on a non-200/500 response.
  serverError(status) {
    this._emit("server_error_handled", status);
    this.roundAdvanceCount += 1;
    this._emit("round_advanced", { via: "server_error_no_response" });
  }

  serverSuccess(transcript) {
    this._emit("server_success", transcript);
    this.roundAdvanceCount += 1;
    this._emit("round_advanced", { via: "server_transcript" });
  }
}

function assert(condition, message, results) {
  results.push({ pass: !!condition, message });
}

const SPEECH_HARNESS_SCENARIOS = [
  {
    name: "successful browser transcript",
    run() {
      const c = new SpeechRoundCoordinator();
      const results = [];
      c.startRound();
      c.recognitionResult("the red one");
      assert(c.roundAdvanceCount === 1, "round advances exactly once", results);
      assert(c.serverRequestCount === 0, "no server request needed when recognition succeeds", results);
      assert(!c.recorderActive && !c.recognitionActive, "both capture mechanisms stopped after resolution", results);
      // The cancelled recorder's real MediaRecorder.stop() fires its "stop"
      // event asynchronously; simulate that late event arriving and confirm
      // it's absorbed as a no-op (ignoreNextRecording/roundResolved guard).
      c.recorderStop({ size: 4096, speechDetected: true });
      assert(c.serverRequestCount === 0, "the cancelled recorder's late stop event does not send a second request", results);
      assert(c.roundAdvanceCount === 1, "the cancelled recorder's late stop event does not advance the round again", results);
      return results;
    }
  },
  {
    name: "no-speech error",
    run() {
      const c = new SpeechRoundCoordinator();
      const results = [];
      c.startRound();
      c.recognitionError("no-speech");
      assert(c.recorderActive === true, "recorder keeps running after a no-speech error (audio not lost)", results);
      assert(c.roundResolved === false, "round is not resolved by the error alone", results);
      c.recorderStop({ size: 4096, speechDetected: true });
      assert(c.serverRequestCount === 1, "recorder eventually sends the captured audio to the server", results);
      c.serverSuccess("the child's actual answer");
      assert(c.roundAdvanceCount === 1, "round advances exactly once overall", results);
      return results;
    }
  },
  {
    name: "network error",
    run() {
      const c = new SpeechRoundCoordinator();
      const results = [];
      c.startRound();
      c.recognitionError("network");
      assert(c.recorderActive === true, "recorder unaffected by a recognition network error", results);
      c.recorderStop({ size: 8192, speechDetected: true });
      assert(c.serverRequestCount === 1, "captured audio still reaches the server despite the network error", results);
      return results;
    }
  },
  {
    name: "recorder-only fallback (no SpeechRecognition support)",
    run() {
      const c = new SpeechRoundCoordinator();
      const results = [];
      c.startRound({ withRecognition: false });
      assert(c.recorderActive === true, "recorder starts even with no SpeechRecognition constructor available", results);
      assert(c.recognitionActive === false, "recognition never starts when unsupported", results);
      c.recorderStop({ size: 5000, speechDetected: true });
      assert(c.serverRequestCount === 1, "recorder-only path still reaches the server", results);
      return results;
    }
  },
  {
    name: "empty recording",
    run() {
      const c = new SpeechRoundCoordinator();
      const results = [];
      c.startRound();
      c.recognitionError("no-speech");
      c.recorderStop({ size: 0, speechDetected: false });
      assert(c.serverRequestCount === 0, "no server request for a genuinely empty recording", results);
      assert(c.noResponseCount === 1, "empty recording is treated as no_response, not a crash", results);
      assert(c.roundAdvanceCount === 1, "round still advances (does not hang) on empty recording", results);
      return results;
    }
  },
  {
    name: "server 500",
    run() {
      const c = new SpeechRoundCoordinator();
      const results = [];
      c.startRound();
      c.recorderStop({ size: 6000, speechDetected: true });
      assert(c.serverRequestCount === 1, "request was sent", results);
      c.serverError(500);
      assert(c.roundAdvanceCount === 1, "a 500 still resolves the round instead of leaving it stuck", results);
      return results;
    }
  },
  {
    name: "duplicate onend",
    run() {
      const c = new SpeechRoundCoordinator();
      const results = [];
      c.startRound();
      c.recognitionResult("yes please");
      const advancesAfterFirst = c.roundAdvanceCount;
      c.recognitionEndDuplicate();
      c.recognitionEndDuplicate();
      assert(c.roundAdvanceCount === advancesAfterFirst, "duplicate onend events do not advance the round again", results);
      return results;
    }
  },
  {
    name: "timeout firing after a successful result",
    run() {
      const c = new SpeechRoundCoordinator();
      const results = [];
      c.startRound();
      c.recognitionResult("the blue truck");
      assert(c.roundAdvanceCount === 1, "recognition already resolved the round", results);
      // The recorder's own stop event fires late, after resolution.
      c.recorderStop({ size: 4096, speechDetected: true });
      assert(c.roundAdvanceCount === 1, "a late recorder stop after resolution does not send a duplicate server request", results);
      assert(c.serverRequestCount === 0, "no duplicate transcription request from the late stop", results);
      return results;
    }
  },
  {
    name: "rapid transition between consecutive rounds",
    run() {
      const c = new SpeechRoundCoordinator();
      const results = [];

      c.startRound();
      c.recognitionResult("first answer");
      assert(c.roundAdvanceCount === 1, "round 1 resolves", results);

      // Next round starts immediately -- roundResolved must reset cleanly.
      c.startRound();
      assert(c.roundResolved === false, "roundResolved resets at the start of round 2", results);
      assert(c.recorderActive === true, "recorder restarts cleanly for round 2", results);

      c.recognitionError("no-speech");
      c.recorderStop({ size: 3000, speechDetected: true });
      c.serverSuccess("second answer");
      assert(c.roundAdvanceCount === 2, "round 2 resolves independently of round 1", results);
      assert(c.serverRequestCount === 1, "exactly one server request across round 2 (round 1 needed none)", results);
      return results;
    }
  }
];

function runSpeechHarnessTests() {
  return SPEECH_HARNESS_SCENARIOS.map(scenario => {
    let results;
    let threw = null;
    try {
      results = scenario.run();
    } catch (error) {
      threw = error;
      results = [];
    }
    const pass = !threw && results.every(r => r.pass);
    return { name: scenario.name, pass, results, threw };
  });
}

if (typeof window !== "undefined") {
  window.SpeechRoundCoordinator = SpeechRoundCoordinator;
  window.runSpeechHarnessTests = runSpeechHarnessTests;
}
