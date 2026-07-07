(() => {
  const PHONE_MEDIA_QUERY =
    "(max-width: 760px), (hover: none) and (pointer: coarse) and (max-width: 940px)";

  const modal = document.getElementById("mobileActivityModal");
  const closeButton = document.getElementById("closeMobileActivityModalBtn");
  const backButton = document.getElementById("mobileActivityModalBackBtn");

  if (!modal) return;

  function isPhoneSizedScreen() {
    const matchesPhoneQuery = window.matchMedia(PHONE_MEDIA_QUERY).matches;
    const shortestScreenSide = Math.min(
      window.screen?.width || window.innerWidth,
      window.screen?.height || window.innerHeight
    );

    return matchesPhoneQuery && shortestScreenSide <= 520;
  }

  function openModal() {
    modal.classList.add("is-open");
    modal.setAttribute("aria-hidden", "false");
    document.body.classList.add("mobile-activity-modal-open");

    if (closeButton) {
      closeButton.focus({ preventScroll: true });
    }
  }

  function closeModal() {
    modal.classList.remove("is-open");
    modal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("mobile-activity-modal-open");
  }

  function isActivityLink(element) {
    if (!element || !element.closest) return null;

    return element.closest(
      'a[href*="/activity/"], a.start-activity-btn, a.journey-current-pill'
    );
  }

  document.addEventListener(
    "click",
    function (event) {
      const activityLink = isActivityLink(event.target);

      if (!activityLink) return;
      if (!isPhoneSizedScreen()) return;

      event.preventDefault();
      event.stopPropagation();

      if (event.stopImmediatePropagation) {
        event.stopImmediatePropagation();
      }

      openModal();
    },
    true
  );

  if (closeButton) {
    closeButton.addEventListener("click", closeModal);
  }

  if (backButton) {
    backButton.addEventListener("click", closeModal);
  }

  modal.addEventListener("click", function (event) {
    if (event.target === modal) {
      closeModal();
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && modal.classList.contains("is-open")) {
      closeModal();
    }
  });
})();
