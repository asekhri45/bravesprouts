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

  var lastSession = null;

  function createSession(options) {
    options = options || {};

    var sessionId = shortId();
    var game = options.game || "unknown_game";
    var activityId = options.activityId != null ? options.activityId : null;
    // Optional callback returning a small plain-object snapshot of
    // whatever the game considers its "current state" (stage, flags,
    // selected mime type, etc.) -- attached to every entry so a timeline
    // export shows not just what happened but what state it happened in.
    var getState = typeof options.getState === "function" ? options.getState : null;

    var events = [];
    var roundCounter = 0;
    var operationCounter = 0;
    var currentRoundId = null;

    function safeGetState() {
      if (!getState) return undefined;
      try {
        return getState();
      } catch (e) {
        return { stateError: String(e && e.message || e) };
      }
    }

    function record(eventName, details) {
      var entry = {
        t: nowMs(),
        wallTime: Date.now(),
        sessionId: sessionId,
        game: game,
        activityId: activityId,
        turnId: currentRoundId,
        roundId: currentRoundId,
        event: eventName,
        details: details || {},
        state: safeGetState()
      };

      events.push(entry);
      if (events.length > MAX_EVENTS) {
        events.shift();
      }

      if (window.APP_DEBUG) {
        // eslint-disable-next-line no-console
        console.debug(
          "[" + game + "][" + sessionId + "]" +
          (currentRoundId != null ? "[turn " + currentRoundId + "]" : "") +
          " " + eventName,
          details || ""
        );
      }

      return entry;
    }

    var session = {
      sessionId: sessionId,

      // "Round" and "turn" are the same counter here -- a new turn IS a
      // new round of the game loop. Call this wherever the game already
      // marks the start of a new turn/round so every later event in that
      // turn carries the same id.
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
        return JSON.stringify({
          exportedAt: new Date().toISOString(),
          sessionId: sessionId,
          game: game,
          activityId: activityId,
          events: events
        }, null, 2);
      },

      printTimeline: function () {
        if (window.console && console.table) {
          console.table(events.map(function (e) {
            return {
              t_ms: Math.round(e.t),
              turn: e.turnId,
              event: e.event,
              details: JSON.stringify(e.details),
              state: e.state ? JSON.stringify(e.state) : ""
            };
          }));
        }
      },

      copyToClipboard: function () {
        var text = session.exportTimeline();
        if (navigator.clipboard && navigator.clipboard.writeText) {
          return navigator.clipboard.writeText(text).then(function () { return true; });
        }
        return Promise.resolve(false);
      }
    };

    record("game_initialized", getEnvironmentSnapshot());

    lastSession = session;
    maybeInjectDebugButton();

    return session;
  }

  function maybeInjectDebugButton() {
    if (!window.APP_DEBUG) return;
    if (document.getElementById("__gameDiagnosticsCopyBtn")) return;
    if (!document.body) {
      document.addEventListener("DOMContentLoaded", maybeInjectDebugButton, { once: true });
      return;
    }

    var btn = document.createElement("button");
    btn.id = "__gameDiagnosticsCopyBtn";
    btn.type = "button";
    btn.textContent = "Copy diagnostics";
    btn.setAttribute("style", [
      "position:fixed", "bottom:12px", "left:12px", "z-index:2147483647",
      "font:12px/1.4 monospace", "padding:6px 10px", "border-radius:6px",
      "border:1px solid rgba(255,255,255,0.3)", "background:rgba(0,0,0,0.72)",
      "color:#fff", "cursor:pointer", "opacity:0.75"
    ].join(";"));
    btn.addEventListener("mouseenter", function () { btn.style.opacity = "1"; });
    btn.addEventListener("mouseleave", function () { btn.style.opacity = "0.75"; });

    btn.addEventListener("click", function () {
      if (!lastSession) return;
      lastSession.copyToClipboard().then(function (ok) {
        btn.textContent = ok ? "Copied!" : "Copy failed (clipboard blocked)";
        setTimeout(function () { btn.textContent = "Copy diagnostics"; }, 1500);
      });
    });

    document.body.appendChild(btn);
  }

  // Dev-console entry point: `getGameDiagnostics()` in devtools returns the
  // most recently created session on this page (session.exportTimeline(),
  // .getTimeline(), .copyToClipboard(), .printTimeline() are all
  // available on it). Only meaningful when window.APP_DEBUG is true --
  // debug mode is what the diagnostics system is designed for; nothing
  // stops this from being called otherwise, but production pages won't
  // have set window.APP_DEBUG so there is no PII-exposure change here.
  window.getGameDiagnostics = function () {
    return lastSession;
  };

  window.GameDiagnostics = {
    createSession: createSession,
    getEnvironmentSnapshot: getEnvironmentSnapshot
  };
})(window);
