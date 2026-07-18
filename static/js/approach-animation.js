document.addEventListener("DOMContentLoaded", function () {
    var reveals = document.querySelectorAll(".reveal");
    if (!reveals.length) return;

    var reducedMotion = window.matchMedia &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // Elements start visible in CSS by default. Only opt them into the
    // hidden pre-animation state once we know we can actually reveal them
    // again -- if IntersectionObserver isn't supported, or the visitor
    // prefers reduced motion, leave everything in its default visible state.
    if (reducedMotion || !("IntersectionObserver" in window)) {
        return;
    }

    reveals.forEach(function (item) {
        item.classList.add("js-armed");
    });

    var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
            if (entry.isIntersecting) {
                entry.target.classList.add("active");
                observer.unobserve(entry.target);
            }
        });
    }, {
        threshold: 0.15
    });

    reveals.forEach(function (item) {
        observer.observe(item);
    });
});
