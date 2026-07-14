/*
  Shared, privacy-conscious analytics helpers -- Phase 2.

  Loaded sitewide via base.html (so it never touches activity pages, which
  use activity_layout.html and don't extend base.html), but only does
  anything beyond the global JS-error listener on pages that actually mark
  up elements with the data-track-* attributes below. This phase only wires
  those attributes into home.html.

  Hard rule enforced throughout: every event below carries only fixed
  labels (which button, which section, which video, an error message/source)
  -- never form field values, never user-entered text, never anything that
  could contain a name, email, or other personal data.
*/

(function () {
  "use strict";

  function hasGtag() {
    return typeof window.gtag === "function";
  }

  function hasClarity() {
    return typeof window.clarity === "function";
  }

  function trackEvent(name, params) {
    if (hasGtag()) {
      window.gtag("event", name, params || {});
    }
  }

  // Custom Clarity event/tag calls (not the base pageview script, which
  // always loads per existing sitewide behavior) respect Do Not Track.
  function clarityConsented() {
    return navigator.doNotTrack !== "1" && window.doNotTrack !== "1";
  }

  function trackClarityEvent(name) {
    if (hasClarity() && clarityConsented()) {
      window.clarity("event", name);
    }
  }

  function setClarityPageTag(pageName) {
    if (hasClarity() && clarityConsented()) {
      window.clarity("set", "page", pageName);
    }
  }

  function wireClickTracking(root) {
    var elements = (root || document).querySelectorAll("[data-track-click]");
    elements.forEach(function (el) {
      el.addEventListener("click", function () {
        var eventName = el.getAttribute("data-track-click");
        var label = el.getAttribute("data-track-label") || "";
        trackEvent(eventName, { label: label });
        trackClarityEvent(eventName);
      });
    });
  }

  function observeSections(root) {
    var elements = (root || document).querySelectorAll("[data-track-section]");
    if (!elements.length || typeof IntersectionObserver === "undefined") {
      return;
    }

    var seen = new Set();
    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          var label = entry.target.getAttribute("data-track-section");
          if (entry.isIntersecting && !seen.has(label)) {
            seen.add(label);
            trackEvent("section_view", { label: label });
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.4 }
    );

    elements.forEach(function (el) {
      observer.observe(el);
    });
  }

  // Uncaught JS errors -- message + source file only, never PII.
  window.addEventListener("error", function (event) {
    trackEvent("js_error", {
      message: (event.message || "").slice(0, 150),
      source: (event.filename || "").split("/").pop()
    });
  });

  window.MBS = window.MBS || {};
  window.MBS.trackEvent = trackEvent;
  window.MBS.trackClarityEvent = trackClarityEvent;
  window.MBS.setClarityPageTag = setClarityPageTag;

  document.addEventListener("DOMContentLoaded", function () {
    wireClickTracking(document);
    observeSections(document);
  });
})();
