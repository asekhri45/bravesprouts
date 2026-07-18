(function () {
    // Thin wrapper around the GA4 gtag() already loaded by base.html /
    // activity_layout.html. Every call site in this codebase is
    // responsible for keeping `properties` free of PII (no email, name,
    // password, PIN, child info, DOB, transcripts, or audio) -- this
    // helper does not collect anything on its own, it only forwards
    // whatever a caller explicitly passes.
    window.trackEvent = function (eventName, properties) {
        if (!eventName) return;
        properties = properties || {};
        if (typeof window.gtag === "function") {
            window.gtag("event", eventName, properties);
        }
    };

    document.addEventListener("DOMContentLoaded", function () {
        var elements = document.querySelectorAll("[data-analytics-event]");

        elements.forEach(function (el) {
            var eventName = el.getAttribute("data-analytics-event");
            var propsRaw = el.getAttribute("data-analytics-props");
            var props = {};

            if (propsRaw) {
                try {
                    props = JSON.parse(propsRaw);
                } catch (e) {
                    props = {};
                }
            }

            var isInteractive = el.tagName === "A" || el.tagName === "BUTTON";

            if (isInteractive) {
                el.addEventListener("click", function () {
                    window.trackEvent(eventName, props);
                });
            } else {
                // A non-interactive container (e.g. the page wrapper) means
                // "fire once when this page loads" -- homepage_view,
                // signup_page_view, parent_setup_started.
                window.trackEvent(eventName, props);
            }
        });
    });
})();
