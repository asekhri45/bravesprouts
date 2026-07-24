/**
 * Visual masking for the four-digit parent PIN.
 *
 * The PIN is a lightweight parental gate, not the account password -- the
 * account has its own email/password used for authentication. Chrome offers to
 * save any `type="password"` field as an account password and ignores
 * `autocomplete="off"` on it, so the PIN inputs are plain text inputs with
 * one-time-code semantics and are masked visually instead.
 *
 * INVARIANT: the input's real `.value` is always the four numeric digits, and
 * the masking is purely presentational. Native constraint validation runs
 * against the element's own value, so `pattern="[0-9]{4}"` and `minlength="4"`
 * must always see the real string -- never bullet characters.
 *
 * A previous version had a "bullet-swap" fallback for browsers without
 * `-webkit-text-security`: it wrote `••••` into the native value and moved the
 * real digits to a hidden twin. That is the thing to never do -- when that
 * fallback (or a stale cached copy of it) ran, `pattern="[0-9]{4}"` was tested
 * against "••••" and every four-digit PIN failed with "Please match the
 * requested format." The fallback has been removed. Masking now comes from
 * exactly one place -- the `-webkit-text-security: disc` property -- applied
 * both by the `.pin-masked-input` stylesheet rule (so the field is masked from
 * first paint) and reinforced inline here. That property is visual only; it
 * never changes the value, so validation and submission are always correct.
 *
 * Every current browser (Chrome, Edge, Safari, Firefox 119+) supports
 * `-webkit-text-security`. On an older engine that does not, the field is
 * briefly unmasked but still validates and submits the real four-digit
 * string -- strictly safer than risking a broken submission.
 *
 * Opt in with `data-pin-mask`. Inputs added to the DOM later are picked up too,
 * so a PIN field inside a modal cannot slip through unmasked.
 */
(function (window, document) {
  "use strict";

  var MAX_DIGITS = 4;
  var STATE_KEY = "__pinMaskAttached";

  // Digits only, capped, as a STRING throughout. Never Number() -- that would
  // turn "0123" into 123 and silently drop the leading zero.
  function digitsOnly(value) {
    return String(value == null ? "" : value).replace(/\D/g, "").slice(0, MAX_DIGITS);
  }

  function applyInlineMask(input) {
    input.style.setProperty("-webkit-text-security", "disc");
    input.style.setProperty("text-security", "disc");
  }

  function normalizeAttributes(input) {
    // Never leave password semantics on a masked PIN field -- that is exactly
    // what makes Chrome offer to save it as an account password.
    if (input.type === "password") input.type = "text";

    if (!input.getAttribute("inputmode")) input.setAttribute("inputmode", "numeric");
    if (!input.getAttribute("autocomplete")) input.setAttribute("autocomplete", "one-time-code");
    if (!input.getAttribute("maxlength")) input.setAttribute("maxlength", String(MAX_DIGITS));

    input.setAttribute("autocorrect", "off");
    input.setAttribute("autocapitalize", "off");
    input.setAttribute("spellcheck", "false");
  }

  /**
   * Strips anything that is not a digit as the parent types or pastes, keeping
   * the caret where they expect it. Runs alongside native validation rather
   * than replacing it: the value is always digits, so `pattern="[0-9]{4}"` and
   * `minlength="4"` do the actual accept/reject.
   */
  function attachDigitSanitizer(input) {
    input.addEventListener("input", function () {
      var raw = input.value;
      var cleaned = digitsOnly(raw);

      if (cleaned === raw) return;

      var caret = input.selectionStart;
      var removedBeforeCaret =
        typeof caret === "number"
          ? raw.slice(0, caret).length - digitsOnly(raw.slice(0, caret)).length
          : 0;

      input.value = cleaned;

      if (typeof caret === "number") {
        var next = Math.max(0, Math.min(caret - removedBeforeCaret, cleaned.length));
        try { input.setSelectionRange(next, next); } catch (e) { /* ignore */ }
      }
    });
  }

  function attach(input) {
    if (!input || input[STATE_KEY]) return;
    input[STATE_KEY] = true;

    normalizeAttributes(input);
    applyInlineMask(input);
    attachDigitSanitizer(input);

    // Normalise any prefilled value to digits, without ever going through a
    // proxy or a hidden twin.
    input.value = digitsOnly(input.value);
  }

  function scan() {
    var nodes = document.querySelectorAll("input[data-pin-mask]");
    for (var i = 0; i < nodes.length; i++) attach(nodes[i]);
  }

  function init() {
    scan();

    // PIN fields inside modals can be inserted after load; watch for them so a
    // script-created field is never left showing real digits.
    if (window.MutationObserver) {
      new window.MutationObserver(scan).observe(document.documentElement, {
        childList: true,
        subtree: true
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  window.PinMask = { attach: attach, scan: scan };
})(window, document);
