// /research page behaviour: embed the paper PDF on screens that can show it.
(function () {
    "use strict";

    // Only on wide, fine-pointer screens: phone and tablet browsers render
    // embedded PDFs poorly (often only page one, or not at all), so those
    // keep the fallback card with Open/Download links instead.
    var viewer = document.querySelector(".rp-viewer[data-pdf-src]");
    var wantsViewer = window.matchMedia("(min-width: 900px) and (pointer: fine)").matches;

    if (viewer && wantsViewer) {
        var frame = document.createElement("iframe");
        frame.src = viewer.getAttribute("data-pdf-src");
        frame.title = viewer.getAttribute("data-pdf-title") || "Research paper PDF";
        viewer.appendChild(frame);
        viewer.classList.add("has-frame");
    }
})();
