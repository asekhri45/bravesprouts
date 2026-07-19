/**
 * Shared microphone/MediaRecorder lifecycle for the mic/AI games.
 *
 * Extracted from the Mystery Animal reference implementation. Handles only
 * the mechanical parts that were independently duplicated (and buggy) in
 * every game: requesting/verifying the mic stream, picking a MIME type the
 * browser actually supports, gating "recording started" on the real
 * MediaRecorder `start` event, enforcing a single active recorder, and
 * cleanup. Silence detection, response-mode timing tables, and other
 * game-specific tuning stay in each game's own file -- those are
 * intentional pacing decisions, not mechanical bugs, and this module does
 * not try to own them.
 */
(function (window) {
  "use strict";

  var MIME_CANDIDATES = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/mp4;codecs=mp4a.40.2",
    "audio/mp4",
    "audio/ogg;codecs=opus"
  ];

  function pickSupportedMimeType() {
    if (typeof MediaRecorder === "undefined" || !MediaRecorder.isTypeSupported) return null;

    for (var i = 0; i < MIME_CANDIDATES.length; i++) {
      if (MediaRecorder.isTypeSupported(MIME_CANDIDATES[i])) return MIME_CANDIDATES[i];
    }

    return null;
  }

  function extensionForMimeType(mimeType) {
    if (!mimeType) return "webm";
    if (mimeType.indexOf("mp4") !== -1) return "mp4";
    if (mimeType.indexOf("ogg") !== -1) return "ogg";
    return "webm";
  }

  function verifyStreamReady(stream) {
    var track = stream && stream.getAudioTracks ? stream.getAudioTracks()[0] : null;

    if (!track) return { ok: false, reason: "no_audio_track" };
    if (track.readyState !== "live") return { ok: false, reason: "track_not_live" };
    if (!track.enabled) return { ok: false, reason: "track_disabled" };
    if (track.muted) return { ok: false, reason: "track_muted" };

    return { ok: true, track: track };
  }

  function stopStreamTracks(stream) {
    if (!stream || !stream.getTracks) return;
    stream.getTracks().forEach(function (track) {
      try { track.stop(); } catch (e) { /* ignore */ }
    });
  }

  function createGameMicManager(options) {
    options = options || {};
    var diagnostics = options.diagnostics || null;

    var activeRecorder = null;

    function log(eventName, details) {
      if (diagnostics) diagnostics.log(eventName, details);
    }

    /**
     * Requests a mic stream and verifies it's actually usable. Does not
     * start recording. Returns { ok, stream, reason }.
     */
    async function requestStream() {
      log("microphone_permission_requested", {});

      var stream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      } catch (error) {
        log("microphone_permission_denied", { message: String(error && error.message || error) });
        return { ok: false, stream: null, reason: "permission_denied", error: error };
      }

      log("microphone_permission_granted", {});

      var readiness = verifyStreamReady(stream);
      if (!readiness.ok) {
        log("microphone_track_not_ready", { reason: readiness.reason });
        stopStreamTracks(stream);
        return { ok: false, stream: null, reason: readiness.reason };
      }

      return { ok: true, stream: stream };
    }

    /**
     * Stops whatever recorder is currently active, if any. Safe to call
     * even when nothing is active. Call this before starting a new
     * recording (startRecording does this itself) and on restart/exit.
     *
     * Deliberately does NOT touch the underlying stream -- some games
     * (Mystery Animal) request a fresh stream per turn and expect it
     * released with the recorder; others (Match Cards) intentionally
     * reuse one persistent stream across many recordings to avoid
     * repeated permission prompts. Stream lifecycle is the caller's call;
     * use stopStreamTracks(stream) explicitly when a game actually wants
     * to release its stream (e.g. on page exit).
     */
    function stopActive(reason) {
      if (activeRecorder && activeRecorder.state !== "inactive") {
        try {
          activeRecorder.stop();
        } catch (e) { /* ignore */ }
      }
      activeRecorder = null;

      log("recording_cleanup", { reason: reason || "stop_active" });
    }

    /**
     * Starts recording on `stream`. Enforces a single active recorder --
     * any previously active recorder/stream is stopped and cleaned up
     * first. `onStart` fires only once MediaRecorder's real `start` event
     * lands (never before) -- that's the only correct signal to show a
     * "listening" UI on. `onStop(blob, mimeType)` fires once the recorder
     * has actually stopped and produced its data.
     *
     * Returns the created MediaRecorder, or null if construction failed
     * (logged as an error either way).
     */
    function startRecording(stream, config) {
      config = config || {};
      var mimeType = pickSupportedMimeType();
      var extension = extensionForMimeType(mimeType);

      stopActive("superseded_by_new_recording");

      var chunks = [];
      var recorder;

      log("recording_requested", { mimeType: mimeType || "browser_default" });

      try {
        recorder = mimeType
          ? new MediaRecorder(stream, { mimeType: mimeType })
          : new MediaRecorder(stream);
      } catch (error) {
        log("error", { where: "MediaRecorder_construct", message: String(error && error.message || error) });
        if (config.onError) config.onError(error);
        return null;
      }

      activeRecorder = recorder;

      recorder.addEventListener("dataavailable", function (event) {
        if (event.data && event.data.size > 0) chunks.push(event.data);
      });

      recorder.addEventListener("start", function () {
        if (activeRecorder !== recorder) return; // superseded before it actually started
        log("recording_started", { mimeType: recorder.mimeType, extension: extension });
        if (config.onStart) config.onStart({ mimeType: recorder.mimeType, extension: extension });
      });

      recorder.addEventListener("stop", function () {
        var wasActive = activeRecorder === recorder;
        if (activeRecorder === recorder) activeRecorder = null;

        var blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
        log("recording_stopped", { chunkCount: chunks.length, size: blob.size, superseded: !wasActive });

        if (config.onStop) config.onStop(blob, recorder.mimeType || "audio/webm", extension, wasActive);
      });

      recorder.addEventListener("error", function (event) {
        log("error", { where: "MediaRecorder_runtime", message: String(event && event.error && event.error.message || event) });
        if (config.onError) config.onError(event && event.error);
      });

      try {
        recorder.start();
      } catch (error) {
        log("error", { where: "MediaRecorder_start", message: String(error && error.message || error) });
        activeRecorder = null;
        if (config.onError) config.onError(error);
        return null;
      }

      return recorder;
    }

    function isRecording() {
      return !!activeRecorder && activeRecorder.state !== "inactive";
    }

    return {
      requestStream: requestStream,
      startRecording: startRecording,
      stopActive: stopActive,
      isRecording: isRecording,
      pickSupportedMimeType: pickSupportedMimeType,
      extensionForMimeType: extensionForMimeType,
      verifyStreamReady: verifyStreamReady,
      stopStreamTracks: stopStreamTracks
    };
  }

  window.GameMicManager = {
    create: createGameMicManager,
    pickSupportedMimeType: pickSupportedMimeType,
    extensionForMimeType: extensionForMimeType,
    verifyStreamReady: verifyStreamReady,
    stopStreamTracks: stopStreamTracks
  };
})(window);
