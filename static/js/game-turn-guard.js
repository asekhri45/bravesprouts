/**
 * Shared turn-token lifecycle for the mic/AI games.
 *
 * A "turn" is one full request/response cycle of a game's conversation
 * loop (a fresh prompt, its playback, listening, and processing the
 * child's answer). Call beginNewTurn() at the start of each new turn and
 * whenever the game restarts/exits; capture the returned token in any
 * async operation that starts during that turn, and check isStale(token)
 * before letting that operation's result touch UI, audio, recording, or
 * game state. This is intentionally just a counter + comparison -- each
 * game's actual state machine (what a turn *means*, when one begins)
 * stays in that game's own file.
 */
(function (window) {
  "use strict";

  function createTurnGuard(options) {
    options = options || {};
    var diagnostics = options.diagnostics || null;

    var currentToken = 0;

    function beginNewTurn() {
      currentToken += 1;
      if (diagnostics) diagnostics.newRound();
      return currentToken;
    }

    function isStale(token) {
      return token !== currentToken;
    }

    function getCurrentToken() {
      return currentToken;
    }

    // Convenience for the common "log + bail out" pattern at every stale
    // check site. Always logs both the stale token and the current one,
    // per the diagnostics requirement that a superseded-turn rejection be
    // traceable from the exported timeline alone.
    function rejectIfStale(token, where, extraDetails) {
      if (!isStale(token)) return false;

      if (diagnostics) {
        diagnostics.log("stale_callback_rejected", Object.assign(
          { where: where, staleTurnToken: token, currentTurnToken: currentToken },
          extraDetails || {}
        ));
      }

      return true;
    }

    return {
      beginNewTurn: beginNewTurn,
      isStale: isStale,
      currentToken: getCurrentToken,
      rejectIfStale: rejectIfStale
    };
  }

  window.GameTurnGuard = {
    create: createTurnGuard
  };
})(window);
