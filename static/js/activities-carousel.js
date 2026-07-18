document.addEventListener("DOMContentLoaded", function () {
    var track = document.getElementById("activitiesTrack");
    if (!track) return;
    if (track.dataset.carouselInitialized) return;

    track.dataset.carouselInitialized = "true";

    var region = track.closest(".activities-carousel");
    if (!region) return;

    var prevBtn = region.querySelector(".activities-arrow-prev");
    var nextBtn = region.querySelector(".activities-arrow-next");
    var progressFill = document.getElementById("activitiesProgressFill");
    var progressTrack = document.getElementById("activitiesProgressTrack");
    var counterEl = document.getElementById("activitiesCounter");

    var originalCards = Array.prototype.slice.call(
        track.querySelectorAll(".activity-card")
    );

    if (!originalCards.length) return;

    var originalCardCount = originalCards.length;

    var motionQuery = window.matchMedia
        ? window.matchMedia("(prefers-reduced-motion: reduce)")
        : null;

    var reducedMotion = motionQuery ? motionQuery.matches : false;

    /*
     * Clone the complete set once.
     *
     * The resulting track is:
     *
     * [original cards] [cloned cards]
     *
     * When the scroll position reaches the cloned set, it is moved backward
     * by exactly the width of the original set. Because both sets are visually
     * identical, the reset is invisible.
     */
    originalCards.forEach(function (card) {
        var clone = card.cloneNode(true);

        clone.setAttribute("aria-hidden", "true");
        clone.removeAttribute("id");
        clone.dataset.carouselClone = "true";

        /*
         * Prevent cloned content from appearing as duplicate interactive
         * content to keyboard and assistive-technology users.
         */
        clone.querySelectorAll("a, button, input, select, textarea, [tabindex]")
            .forEach(function (element) {
                element.setAttribute("tabindex", "-1");
            });

        track.appendChild(clone);
    });

    var allCards = Array.prototype.slice.call(
        track.querySelectorAll(".activity-card")
    );

    var autoScrollSpeed = 32; // Pixels per second
    var resumeDelay = 1800;

    var animationFrameId = null;
    var lastFrameTime = null;
    var resumeTimer = null;

    var isPaused = reducedMotion;
    var isDragging = false;
    var dragMoved = false;
    var dragStartX = 0;
    var dragStartScrollLeft = 0;

    function getOriginalSetWidth() {
        if (!allCards[originalCardCount]) {
            return track.scrollWidth / 2;
        }

        return allCards[originalCardCount].offsetLeft - allCards[0].offsetLeft;
    }

    function normalizeScrollPosition() {
        var setWidth = getOriginalSetWidth();

        if (!setWidth) return;

        /*
         * Keep the position inside the first logical set.
         * Use a while loop in case a large resize or gesture moves farther
         * than one complete set.
         */
        while (track.scrollLeft >= setWidth) {
            track.scrollLeft -= setWidth;
        }

        while (track.scrollLeft < 0) {
            track.scrollLeft += setWidth;
        }
    }

    function currentIndex() {
        var setWidth = getOriginalSetWidth();
        var logicalScrollLeft = setWidth
            ? track.scrollLeft % setWidth
            : track.scrollLeft;

        var closestIndex = 0;
        var closestDistance = Infinity;

        originalCards.forEach(function (card, index) {
            var distance = Math.abs(
                card.offsetLeft - originalCards[0].offsetLeft - logicalScrollLeft
            );

            if (distance < closestDistance) {
                closestDistance = distance;
                closestIndex = index;
            }
        });

        return closestIndex;
    }

    function updateCarouselUI() {
        var index = currentIndex();

        if (counterEl) {
            counterEl.textContent =
                (index + 1) + " of " + originalCardCount;
        }

        /*
         * The progress bar represents the logical card number rather than the
         * physical doubled track.
         */
        var ratio = originalCardCount > 1
            ? index / (originalCardCount - 1)
            : 0;

        if (progressFill) {
            progressFill.style.width =
                (ratio * 100).toFixed(2) + "%";
        }

        if (progressTrack) {
            progressTrack.setAttribute(
                "aria-valuenow",
                String(Math.round(ratio * 100))
            );
        }

        /*
         * An infinite carousel never reaches a disabled beginning or end.
         */
        if (prevBtn) prevBtn.disabled = false;
        if (nextBtn) nextBtn.disabled = false;
    }

    function scrollToLogicalCard(index, behavior) {
        var normalizedIndex =
            ((index % originalCardCount) + originalCardCount) %
            originalCardCount;

        var targetCard = originalCards[normalizedIndex];
        if (!targetCard) return;

        track.scrollTo({
            left: targetCard.offsetLeft - originalCards[0].offsetLeft,
            behavior: behavior || (reducedMotion ? "auto" : "smooth")
        });
    }

    function pauseAutoScroll() {
        isPaused = true;
        lastFrameTime = null;

        if (resumeTimer) {
            clearTimeout(resumeTimer);
            resumeTimer = null;
        }
    }

    function resumeAutoScrollAfterDelay() {
        if (reducedMotion) return;

        if (resumeTimer) {
            clearTimeout(resumeTimer);
        }

        resumeTimer = setTimeout(function () {
            isPaused = false;
            lastFrameTime = null;
        }, resumeDelay);
    }

    function autoScrollFrame(timestamp) {
        if (!isPaused && !isDragging && !document.hidden) {
            if (lastFrameTime !== null) {
                var elapsedSeconds = Math.min(
                    (timestamp - lastFrameTime) / 1000,
                    0.05
                );

                track.scrollLeft += autoScrollSpeed * elapsedSeconds;
                normalizeScrollPosition();
                updateCarouselUI();
            }

            lastFrameTime = timestamp;
        } else {
            lastFrameTime = null;
        }

        animationFrameId = window.requestAnimationFrame(autoScrollFrame);
    }

    if (!reducedMotion) {
        animationFrameId = window.requestAnimationFrame(autoScrollFrame);
    }

    function moveByCard(direction) {
        pauseAutoScroll();

        var nextIndex = currentIndex() + direction;
        scrollToLogicalCard(nextIndex);

        resumeAutoScrollAfterDelay();
    }

    if (prevBtn) {
        prevBtn.addEventListener("click", function () {
            moveByCard(-1);
        });
    }

    if (nextBtn) {
        nextBtn.addEventListener("click", function () {
            moveByCard(1);
        });
    }

    region.addEventListener("keydown", function (event) {
        if (event.key === "ArrowRight") {
            event.preventDefault();
            moveByCard(1);
        } else if (event.key === "ArrowLeft") {
            event.preventDefault();
            moveByCard(-1);
        }
    });

    /*
     * Pause while the user is intentionally interacting with the carousel.
     */

    region.addEventListener("focusin", pauseAutoScroll);
    region.addEventListener("focusout", resumeAutoScrollAfterDelay);

    track.addEventListener(
        "touchstart",
        pauseAutoScroll,
        { passive: true }
    );

    track.addEventListener(
        "touchend",
        resumeAutoScrollAfterDelay,
        { passive: true }
    );

    /*
     * Mouse drag-to-scroll.
     */
    track.addEventListener("pointerdown", function (event) {
        if (event.pointerType !== "mouse") return;

        pauseAutoScroll();

        isDragging = true;
        dragMoved = false;
        dragStartX = event.clientX;
        dragStartScrollLeft = track.scrollLeft;

        track.setPointerCapture(event.pointerId);
        track.classList.add("is-dragging");
    });

    track.addEventListener("pointermove", function (event) {
        if (!isDragging) return;

        var dx = event.clientX - dragStartX;

        if (Math.abs(dx) > 3) {
            dragMoved = true;
        }

        track.scrollLeft = dragStartScrollLeft - dx;
        normalizeScrollPosition();
        updateCarouselUI();
    });

    function endDrag() {
        if (!isDragging) return;

        isDragging = false;
        track.classList.remove("is-dragging");

        /*
         * Snap to the nearest logical card after the mouse is released.
         */
        scrollToLogicalCard(currentIndex());
        resumeAutoScrollAfterDelay();
    }

    track.addEventListener("pointerup", endDrag);
    track.addEventListener("pointercancel", endDrag);

    track.addEventListener(
        "click",
        function (event) {
            if (!dragMoved) return;

            event.preventDefault();
            event.stopPropagation();
            dragMoved = false;
        },
        true
    );

    /*
     * Native touch/trackpad scrolling can move the track into the cloned set.
     * Normalize it after every scroll without disturbing the visible content.
     */
    track.addEventListener("scroll", function () {
        normalizeScrollPosition();
        updateCarouselUI();
    });

    function debounce(fn, wait) {
        var timeout;

        return function () {
            clearTimeout(timeout);
            timeout = setTimeout(fn, wait);
        };
    }

    window.addEventListener(
        "resize",
        debounce(function () {
            normalizeScrollPosition();
            updateCarouselUI();
        }, 150)
    );

    document.addEventListener("visibilitychange", function () {
        lastFrameTime = null;
    });

    if (motionQuery) {
        var handleMotionPreference = function (event) {
            reducedMotion = event.matches;

            if (reducedMotion) {
                pauseAutoScroll();

                if (animationFrameId) {
                    window.cancelAnimationFrame(animationFrameId);
                    animationFrameId = null;
                }
            } else if (!animationFrameId) {
                isPaused = false;
                animationFrameId =
                    window.requestAnimationFrame(autoScrollFrame);
            }
        };

        if (motionQuery.addEventListener) {
            motionQuery.addEventListener(
                "change",
                handleMotionPreference
            );
        } else if (motionQuery.addListener) {
            motionQuery.addListener(handleMotionPreference);
        }
    }

    /*
     * First-view analytics.
     */
    if ("IntersectionObserver" in window) {
        var seen = false;

        var viewObserver = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting && !seen) {
                    seen = true;

                    if (window.trackEvent) {
                        window.trackEvent(
                            "activity_carousel_view",
                            {}
                        );
                    }

                    viewObserver.disconnect();
                }
            });
        }, {
            threshold: 0.3
        });

        viewObserver.observe(region);
    }

    /*
     * Only original cards fire preview analytics. Clones are visual copies
     * and should not produce duplicate event listeners.
     */
    originalCards.forEach(function (card) {
        card.addEventListener("click", function () {
            if (window.trackEvent) {
                window.trackEvent(
                    "activity_preview_started",
                    {
                        activity_name:
                            card.getAttribute("data-activity-name")
                    }
                );
            }
        });
    });

    updateCarouselUI();
});