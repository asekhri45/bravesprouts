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

    function log(eventName, details) {
      if (diagnostics) diagnostics.log(eventName, details);
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
      activeOperationToken += 1;
      stopMouthSync();

      if (activeAudio) {
        try {
          activeAudio.pause();
        } catch (e) { /* ignore */ }
        activeAudio = null;
      }

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
      activeAudio = audioEl;

      log("prompt_play_requested", { url: url });

      return new Promise(function (resolve) {
        var settled = false;
        var timeoutHandle = null;
        var mouthSync = null;

        function cleanup() {
          audioEl.removeEventListener("playing", onPlaying);
          audioEl.removeEventListener("ended", onEnded);
          audioEl.removeEventListener("error", onError);
          audioEl.removeEventListener("stalled", onStalled);
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
          log("prompt_play_" + result.status, result.error ? { message: String(result.error && result.error.message || result.error) } : {});
          resolve(result);
        }

        function onPlaying() {
          log("prompt_playing", { url: url });
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
          log("prompt_play_stalled_event", { url: url });
        }

        audioEl.addEventListener("playing", onPlaying);
        audioEl.addEventListener("ended", onEnded);
        audioEl.addEventListener("error", onError);
        audioEl.addEventListener("stalled", onStalled);

        timeoutHandle = window.setTimeout(function () {
          settle({ status: "timed_out" });
        }, timeoutMs);

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
