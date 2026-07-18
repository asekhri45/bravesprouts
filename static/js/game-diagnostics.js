/**
 * Shared, privacy-conscious per-session event timeline for the mic/AI games.
 *
 * Never accepts raw audio, full transcripts, or other child speech content —
 * only lengths/booleans/categories. Purely additive: creating a session and
 * logging events has no effect on game behavior.
 */
(function (window) {
  "use strict";

  var MAX_EVENTS = 500;

  function nowMs() {
    return (window.performance && window.performance.now) ? window.performance.now() : Date.now();
  }

  function shortId() {
    if (window.crypto && window.crypto.randomUUID) {
      return window.crypto.randomUUID().replace(/-/g, "").slice(0, 12);
    }
    return Math.random().toString(16).slice(2, 14);
  }

  function getEnvironmentSnapshot() {
    var nav = window.navigator || {};
    var conn = nav.connection || nav.mozConnection || nav.webkitConnection || null;

    return {
      userAgent: nav.userAgent || null,
      language: nav.language || null,
      screenWidth: window.screen ? window.screen.width : null,
      screenHeight: window.screen ? window.screen.height : null,
      devicePixelRatio: window.devicePixelRatio || 1,
      deviceMemoryGb: nav.deviceMemory || null,
      effectiveConnectionType: conn ? conn.effectiveType : null,
      hasMediaRecorder: typeof window.MediaRecorder !== "undefined",
      hasGetUserMedia: !!(nav.mediaDevices && nav.mediaDevices.getUserMedia),
      hasAudioContext: !!(window.AudioContext || window.webkitAudioContext)
    };
  }

  function createSession(options) {
    options = options || {};

    var sessionId = shortId();
    var game = options.game || "unknown_game";
    var activityId = options.activityId != null ? options.activityId : null;

    var events = [];
    var roundCounter = 0;
    var operationCounter = 0;
    var currentRoundId = null;

    function record(eventName, details) {
      var entry = {
        t: nowMs(),
        wallTime: Date.now(),
        sessionId: sessionId,
        game: game,
        activityId: activityId,
        roundId: currentRoundId,
        event: eventName,
        details: details || {}
      };

      events.push(entry);
      if (events.length > MAX_EVENTS) {
        events.shift();
      }

      if (window.APP_DEBUG) {
        // eslint-disable-next-line no-console
        console.debug(
          "[" + game + "][" + sessionId + "]" +
          (currentRoundId != null ? "[round " + currentRoundId + "]" : "") +
          " " + eventName,
          details || ""
        );
      }

      return entry;
    }

    record("game_initialized", getEnvironmentSnapshot());

    return {
      sessionId: sessionId,

      newRound: function () {
        roundCounter += 1;
        currentRoundId = roundCounter;
        record("round_started", { roundId: currentRoundId });
        return currentRoundId;
      },

      currentRoundId: function () {
        return currentRoundId;
      },

      newOperationId: function (kind) {
        operationCounter += 1;
        return (kind || "op") + "_" + operationCounter;
      },

      log: function (eventName, details) {
        return record(eventName, details);
      },

      // Use for anything that touched the network, so a slow/duplicate
      // response can be traced back to exactly which call produced it.
      logTimed: function (eventName, startedAtMs, details) {
        var merged = Object.assign({}, details || {}, {
          durationMs: Math.round(nowMs() - startedAtMs)
        });
        return record(eventName, merged);
      },

      getTimeline: function () {
        return events.slice();
      },

      exportTimeline: function () {
        return JSON.stringify(events, null, 2);
      },

      printTimeline: function () {
        if (window.console && console.table) {
          console.table(events.map(function (e) {
            return {
              t_ms: Math.round(e.t),
              round: e.roundId,
              event: e.event,
              details: JSON.stringify(e.details)
            };
          }));
        }
      }
    };
  }

  window.GameDiagnostics = {
    createSession: createSession,
    getEnvironmentSnapshot: getEnvironmentSnapshot
  };
})(window);
