/**
 * Shared, event-driven playback for the mic/AI games.
 *
 * Root cause this replaces: each game created a fresh AudioContext per
 * spoken line (never resumed inside a user gesture) and treated a rejected
 * `play()` the same as a finished line, so a required prompt could be
 * silently skipped. This manager makes both mistakes structurally hard to
 * repeat: there is exactly one AudioContext, created lazily and resumed
 * only inside `unlock()` (call that from the initiating click handler),
 * and `playAndWait()` never resolves "ended" for anything other than a
 * real `ended` event — a rejected play(), a stall, or a timeout each
 * resolve with their own distinct status the caller must handle.
 */
(function (window) {
  "use strict";

  function createGameAudioManager(options) {
    options = options || {};
    var diagnostics = options.diagnostics || null;
    var defaultTimeoutMs = options.defaultTimeoutMs || 20000;

    var audioContext = null;
    var activeAudio = null;
    var activeOperationToken = 0;
    var activeMouthSync = null;
    var activeCancel = null;

    function log(eventName, details) {
      if (diagnostics) diagnostics.log(eventName, details);
    }

    // Most games serve dialogue audio as a short cached-file URL, safe to
    // log in full. At least one (Guessing Game) embeds the audio directly
    // as a `data:audio/...;base64,...` URI in the response, which can run
    // to hundreds of kilobytes of encoded speech per line -- logging that
    // in full would both bloat the diagnostics timeline uselessly and log
    // actual audio content, which the diagnostics design explicitly rules
    // out. Anything that isn't a short, safe-to-display URL is reduced to
    // its scheme + length instead.
    function safeUrlForLog(url) {
      if (typeof url !== "string") return String(url);
      if (url.length <= 200 && url.indexOf("base64,") === -1) return url;

      var scheme = url.split(",")[0].split(":")[1] || "data";
      return "[" + scheme + ", " + url.length + " chars, omitted from log]";
    }

    /**
     * Must be called synchronously from inside a user-gesture event handler
     * (click/pointerdown/keydown). Safe to call more than once.
     */
    function unlock() {
      var Ctor = window.AudioContext || window.webkitAudioContext;
      if (!Ctor) {
        log("audio_context_unavailable", {});
        return Promise.resolve(false);
      }

      if (!audioContext) {
        audioContext = new Ctor();
      }

      if (audioContext.state === "suspended") {
        return audioContext.resume().then(function () {
          log("audio_context_resumed", { state: audioContext.state });
          return audioContext.state === "running";
        }).catch(function (err) {
          log("audio_context_resume_failed", { message: String(err && err.message || err) });
          return false;
        });
      }

      log("audio_context_resumed", { state: audioContext.state });
      return Promise.resolve(audioContext.state === "running");
    }

    function getContext() {
      return audioContext;
    }

    function stopMouthSync() {
      if (activeMouthSync) {
        activeMouthSync.stop();
        activeMouthSync = null;
      }
    }

    /**
     * Attaches an analyser (on the single shared AudioContext) to `audioEl`
     * and calls onLevel(0..1) on every animation frame while audio is
     * actually playing. Starts/stops strictly on real playback events, so
     * mouth animation can never keep running after audio has stopped.
     */
    function attachMouthSync(audioEl, onLevel) {
      stopMouthSync();

      if (!audioContext || typeof onLevel !== "function") {
        return { stop: function () {} };
      }

      var source, analyser, rafId, dataArray;

      try {
        source = audioContext.createMediaElementSource(audioEl);
        analyser = audioContext.createAnalyser();
        analyser.fftSize = 256;
        dataArray = new Uint8Array(analyser.frequencyBinCount);
        source.connect(analyser);
        analyser.connect(audioContext.destination);
      } catch (err) {
        // createMediaElementSource throws if called twice on the same
        // element; treat as non-fatal, mouth animation just won't run.
        log("mouth_sync_attach_failed", { message: String(err && err.message || err) });
        return { stop: function () {} };
      }

      function tick() {
        analyser.getByteFrequencyData(dataArray);
        var sum = 0;
        for (var i = 0; i < dataArray.length; i++) sum += dataArray[i];
        var level = dataArray.length ? sum / dataArray.length / 255 : 0;
        onLevel(level);
        rafId = window.requestAnimationFrame(tick);
      }

      var handle = {
        start: function () {
          if (!rafId) rafId = window.requestAnimationFrame(tick);
        },
        stop: function () {
          if (rafId) {
            window.cancelAnimationFrame(rafId);
            rafId = null;
          }
          onLevel(0);
        }
      };

      activeMouthSync = handle;
      return handle;
    }

    /**
     * Stops whatever is currently the authoritative dialogue audio. Any
     * pending playAndWait() promise for it resolves as {status:"cancelled"}
     * rather than being left dangling.
     */
    function cancelActive(reason) {
      // Stop the element before settling its promise; settlement clears the
      // active reference, so doing this afterward would let the voice keep
      // playing even though the queue believed it had been cancelled.
      if (activeAudio) {
        try {
          activeAudio.pause();
        } catch (e) { /* ignore */ }
        activeAudio = null;
      }

      // Resolve the current caller before invalidating its token. Previously
      // cancelActive() paused the element and changed the token, while the
      // pending playAndWait() promise could no longer settle. Any dialogue
      // queue awaiting that promise then remained frozen forever.
      var cancel = activeCancel;
      activeCancel = null;
      if (cancel) cancel(reason || "superseded");

      activeOperationToken += 1;
      stopMouthSync();

      log("audio_cancelled", { reason: reason || "superseded" });
    }

    /**
     * Plays `url` as THE authoritative dialogue audio (cancelling whatever
     * was playing before) and resolves once its fate is known. Result is
     * always one of:
     *   { status: "ended" }                  - real `ended` event fired
     *   { status: "cancelled" }               - superseded by a newer call/cancelActive()
     *   { status: "play_rejected", error }    - browser blocked play() (e.g. autoplay policy)
     *   { status: "stalled" }                 - playback stalled past the timeout
     *   { status: "timed_out" }               - neither ended/error fired in time
     *   { status: "error", error }            - media `error` event fired
     *
     * Only "ended" means the line was actually heard. Every other status
     * is a distinct, must-handle failure — callers must not advance the
     * game on anything but "ended".
     */
    function playAndWait(url, config) {
      config = config || {};
      var timeoutMs = config.timeoutMs || defaultTimeoutMs;
      var onMouthLevel = config.onMouthLevel || null;

      cancelActive("new_prompt");
      var myToken = activeOperationToken;

      var audioEl = new Audio(url);
      // Lets a game apply its own volume/playbackRate/etc. -- kept generic
      // here rather than adding per-game options, since different games
      // use different values for legitimate pacing/mixing reasons that
      // aren't this module's concern.
      if (typeof config.configureAudio === "function") {
        try { config.configureAudio(audioEl); } catch (e) { /* ignore */ }
      }
      activeAudio = audioEl;

      log("prompt_play_requested", { url: safeUrlForLog(url) });

      return new Promise(function (resolve) {
        var settled = false;
        var timeoutHandle = null;
        var mouthSync = null;
        // Whether the browser ever actually started producing sound. Callers
        // need this to tell "the child never heard the line" (safe to replay)
        // from "we lost track of the end of a line they did hear" (replaying
        // would say the whole thing twice).
        var startedPlaying = false;

        function cleanup() {
          audioEl.removeEventListener("playing", onPlaying);
          audioEl.removeEventListener("ended", onEnded);
          audioEl.removeEventListener("error", onError);
          audioEl.removeEventListener("stalled", onStalled);
          audioEl.removeEventListener("loadedmetadata", onLoadedMetadata);
          if (timeoutHandle) window.clearTimeout(timeoutHandle);
          if (mouthSync) mouthSync.stop();
        }

        function settle(result) {
          if (settled) return;
          if (myToken !== activeOperationToken) {
            // A newer call already superseded this one; do not double-resolve
            // and do not let this stale result look like a fresh outcome.
            return;
          }
          settled = true;
          cleanup();
          if (activeCancel === cancelThisOperation) activeCancel = null;
          if (activeAudio === audioEl) activeAudio = null;
          result.startedPlaying = startedPlaying;
          log("prompt_play_" + result.status, result.error ? { message: String(result.error && result.error.message || result.error) } : {});
          resolve(result);
        }

        function cancelThisOperation(reason) {
          settle({ status: "cancelled", reason: reason || "superseded" });
        }

        activeCancel = cancelThisOperation;

        function armTimeout(ms) {
          if (timeoutHandle) window.clearTimeout(timeoutHandle);
          timeoutHandle = window.setTimeout(function () {
            settle({ status: "timed_out" });
          }, ms);
        }

        /*
          The flat timeout was a guess made before the clip's length was
          known, so a long line could out-run it and be reported as
          "timed_out" even while it was still playing perfectly well. Once the
          real duration is available, extend the deadline to cover it (plus
          headroom for buffering). Never shortens the caller's timeout.
        */
        function onLoadedMetadata() {
          var duration = Number(audioEl.duration);
          if (!isFinite(duration) || duration <= 0) return;

          var rate = Number(audioEl.playbackRate) || 1;
          var needed = (duration / rate) * 1000 + 5000;

          if (needed > timeoutMs) armTimeout(needed);
        }

        function onPlaying() {
          startedPlaying = true;
          log("prompt_playing", { url: safeUrlForLog(url) });
          if (onMouthLevel && audioContext) {
            mouthSync = attachMouthSync(audioEl, onMouthLevel);
            mouthSync.start();
          }
        }

        function onEnded() {
          settle({ status: "ended" });
        }

        function onError() {
          settle({ status: "error", error: audioEl.error });
        }

        function onStalled() {
          log("prompt_play_stalled_event", { url: safeUrlForLog(url) });
        }

        audioEl.addEventListener("playing", onPlaying);
        audioEl.addEventListener("ended", onEnded);
        audioEl.addEventListener("error", onError);
        audioEl.addEventListener("stalled", onStalled);
        audioEl.addEventListener("loadedmetadata", onLoadedMetadata);

        armTimeout(timeoutMs);

        var playPromise = audioEl.play();
        if (playPromise && typeof playPromise.catch === "function") {
          playPromise.catch(function (err) {
            settle({ status: "play_rejected", error: err });
          });
        }
      });
    }

    return {
      unlock: unlock,
      getContext: getContext,
      playAndWait: playAndWait,
      cancelActive: cancelActive,
      attachMouthSync: attachMouthSync
    };
  }

  window.GameAudioManager = {
    create: createGameAudioManager
  };
})(window);
