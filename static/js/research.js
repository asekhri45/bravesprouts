// /research page behaviour: BibTeX copy button, desktop-only embedded PDF
// viewer, and current-section highlighting in the sidebar contents.
(function () {
    "use strict";

    // --- Copy BibTeX ---
    document.querySelectorAll("[data-copy-target]").forEach(function (button) {
        var status = button.parentElement.querySelector("[data-copy-status]");

        button.addEventListener("click", function () {
            var source = document.getElementById(button.getAttribute("data-copy-target"));
            if (!source) return;
            var text = source.textContent;

            var done = function (ok) {
                button.textContent = ok ? "Copied" : "Copy failed";
                if (status) status.textContent = ok ? "BibTeX copied to clipboard" : "Copy failed";
                window.setTimeout(function () {
                    button.textContent = "Copy";
                    if (status) status.textContent = "";
                }, 2000);
            };

            // Selection-based copy, for browsers without the async clipboard
            // API or that deny its permission.
            var fallbackCopy = function () {
                var range = document.createRange();
                range.selectNodeContents(source);
                var selection = window.getSelection();
                selection.removeAllRanges();
                selection.addRange(range);
                var ok = false;
                try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
                selection.removeAllRanges();
                done(ok);
            };

            if (navigator.clipboard && window.isSecureContext) {
                navigator.clipboard.writeText(text).then(function () { done(true); }, fallbackCopy);
                return;
            }
            fallbackCopy();
        });
    });

    // --- Embedded PDF viewer ---
    // Only on wide, fine-pointer screens: mobile browsers render embedded PDFs
    // poorly, and deferring until the section nears the viewport keeps the PDF
    // off the initial page load.
    var viewer = document.querySelector(".rp-viewer[data-pdf-src]");
    var wantsViewer = window.matchMedia("(min-width: 900px) and (pointer: fine)").matches;

    if (viewer && wantsViewer) {
        var insertFrame = function () {
            if (viewer.classList.contains("has-frame")) return;
            var frame = document.createElement("iframe");
            frame.src = viewer.getAttribute("data-pdf-src");
            frame.title = viewer.getAttribute("data-pdf-title") || "Manuscript PDF";
            viewer.appendChild(frame);
            viewer.classList.add("has-frame");
        };

        if ("IntersectionObserver" in window) {
            var frameObserver = new IntersectionObserver(function (entries) {
                if (entries.some(function (entry) { return entry.isIntersecting; })) {
                    insertFrame();
                    frameObserver.disconnect();
                }
            }, { rootMargin: "600px 0px" });
            frameObserver.observe(viewer);
        } else {
            insertFrame();
        }
    }

    // --- Current section in sidebar contents ---
    // The current section is the last one whose top has scrolled above 30% of
    // the viewport height (sections are long, so edge-crossing observers miss it).
    var tocLinks = Array.prototype.slice.call(document.querySelectorAll(".rp-toc a[href^='#']"));
    var tracked = tocLinks.map(function (link) {
        return { link: link, section: document.getElementById(link.getAttribute("href").slice(1)) };
    }).filter(function (item) { return item.section; });

    if (tracked.length) {
        var ticking = false;
        var updateCurrent = function () {
            ticking = false;
            var line = window.innerHeight * 0.3;
            var current = tracked[0];
            tracked.forEach(function (item) {
                if (item.section.getBoundingClientRect().top <= line) current = item;
            });
            tracked.forEach(function (item) {
                item.link.classList.toggle("is-current", item === current);
            });
        };
        window.addEventListener("scroll", function () {
            if (!ticking) {
                ticking = true;
                window.requestAnimationFrame(updateCurrent);
            }
        }, { passive: true });
        updateCurrent();
    }
})();
