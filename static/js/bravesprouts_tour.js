document.addEventListener("DOMContentLoaded", function () {
  const layout = document.querySelector(".dashboard-layout");
  if (!layout) return;

  const MOBILE_TOUR_BREAKPOINT = 900;
  const DESKTOP_CARD_WIDTH = 520;

  const urlParams = new URLSearchParams(window.location.search);
  const urlStep = Number(urlParams.get("tour"));
  const hasUrlStep = Number.isInteger(urlStep) && urlStep >= 1 && urlStep <= 7;

  const hasSeenTour = layout.dataset.hasSeenTour === "1";
  if (hasSeenTour && !hasUrlStep) return;

  const path = window.location.pathname;

  const steps = [
    {
      step: 1,
      page: "dashboard",
      path: "/dashboard",
      target: null,
      pillLabel: "Start guided tour",
      icon: "👋",
      title: "Welcome to MyBraveSprout!",
      text: "Let's take a quick 1 minute tour before getting started. It shows the demo videos, activity path, questions, profile setup, and permissions.",
      mobileText: "This quick tour will show you the main features you'll use most.",
      badge: "Required setup • About 1 minute",
      instruction: "Select Next to begin the guided tour.",
      mobileInstruction: "Select Next to begin.",
      nextText: "Next",
      sideImage: true,
      centerOnly: true
    },
    {
      step: 2,
      page: "getting-started",
      path: "/getting-started",
      target: "demo-videos",
      selector: '[data-tour-target="demo-videos"]',
      mobileScrollSelector: '[data-tour-target="demo-videos"]',
      highlightSelectors: [
        '[data-tour-target="demo-videos"] .video-guide-card',
        '.sidebar-nav a[href="/getting-started"], .sidebar-nav a[href$="/getting-started"]'
      ],
      pillLabel: "Demo Videos",
      icon: "🎬",
      title: "Find demo videos here",
      text: "This tab has the short parent demo videos. You can come back here anytime to watch the overview or the quick dashboard walkthrough.",
      mobileText: "Watch short videos anytime to learn how to support your child.",
      instruction: "Select Next when ready.",
      mobileInstruction: "Select Next when ready.",
      nextText: "Next",
      sideImage: true
    },
    {
      step: 3,
      page: "dashboard",
      path: "/dashboard",
      target: "current-activity",
      highlightSelectors: [
        '[data-tour-target="current-activity"]',
        '.sidebar-nav a[href="/dashboard"], .sidebar-nav a[href$="/dashboard"]'
      ],
      pillLabel: "Current Activity",
      icon: "⭐",
      title: "Start activities here",
      text: "This is the recommended activity to begin with. Activities are designed to build comfort and confidence one small step at a time.",
      mobileText: "Jump right into the recommended activity for your child.",
      instruction: "Follow the highlighted area, then select Next to continue.",
      mobileInstruction: "Select Next to continue.",
      nextText: "Next",
      sideImage: true
    },
    {
      step: 4,
      page: "dashboard",
      path: "/dashboard",
      target: "journey",
      selector: '[data-tour-target="journey"]',
      mobileScrollSelector: '[data-tour-target="journey"]',
      highlightSelectors: [
        '[data-tour-target="journey"]',
        '.sidebar-nav a[href="/dashboard"], .sidebar-nav a[href$="/dashboard"]'
      ],
      pillLabel: "Progression Path",
      icon: "🗺️",
      title: "Your child's journey",
      text: "Activities unlock in a recommended order. Each one builds on the skills practiced in the previous activity.",
      mobileText: "Activities unlock step by step as your child builds comfort and confidence.",
      instruction: "Select Next to continue.",
      mobileInstruction: "Select Next to continue.",
      nextText: "Next",
      sideImage: true
    },
    {
      step: 5,
      page: "ask-bravesprouts",
      path: "/ask-bravesprouts",
      target: "ask-input",
      highlightSelectors: [
        '[data-tour-target="ask-input"]',
        '.sidebar-nav a[href="/ask-bravesprouts"], .sidebar-nav a[href$="/ask-bravesprouts"]'
      ],
      pillLabel: "MyBraveSprout AI",
      icon: "🤖",
      title: "Ask MyBraveSprout AI",
      text: "Use this space to ask questions and get general guidance, explanations, and practical ideas. It provides general information, not medical advice.",
      mobileText: "Get quick answers and ideas anytime. Not medical advice.",
      instruction: "Select Next to continue.",
      mobileInstruction: "Select Next to continue.",
      nextText: "Next",
      sideImage: true
    },
    {
      step: 6,
      page: "settings",
      path: "/settings",
      target: "settings-child-profile",
      highlightSelectors: [
        '[data-tour-target="settings-child-profile"]',
        '.sidebar-nav a[href="/settings"], .sidebar-nav a[href$="/settings"]'
      ],
      pillLabel: "Child Profile",
      icon: "👤",
      title: "Set up your child's profile",
      text: "You can add your child's name and age now, or come back and fill this in later from Settings. MyBraveSprout can use this information to make activities feel more personal.",
      mobileText: "Add your child's name and age so activities can be personalized.",
      instruction: "Fill this in now or later, then select Next to continue.",
      mobileInstruction: "Fill this in now or later, then select Next.",
      nextText: "Next",
      sideImage: true
    },
    {
      step: 7,
      page: "settings",
      path: "/settings",
      target: "settings-permissions",
      mobileScrollSelector: '[data-tour-target="settings-permissions"]',
      highlightSelectors: [
        ".permissions-section .settings-section-heading",
        '[data-tour-target="settings-permissions"]',
        "#audioPermissionToggle",
        "#microphonePermissionToggle",
        '.sidebar-nav a[href="/settings"], .sidebar-nav a[href$="/settings"]'
      ],
      pillLabel: "Audio + Microphone",
      icon: "🎧",
      title: "Turn on audio & mic",
      text: "Turn on audio and microphone access so your child can hear characters and practice speaking during activities.",
      mobileText: "You can turn these on now or come back later from Settings.",
      instruction: "Turn these on now, or select Finish to continue.",
      mobileInstruction: "Turn these on now, or Finish.",
      nextText: "Finish",
      sideImage: true
    }
  ];

  let activeStepNumber = getStartingStep();
  if (!activeStepNumber) return;

  let overlay = null;
  let spotlight = null;
  let card = null;
  let stepPill = null;
  let imageArrow = null;
  let resizeHandler = null;
  let scrollHandler = null;
  let activeTargets = [];
  let tourCompleteShowing = false;
  let renderRequestId = 0;

  function isMobileTourScreen() {
    return window.innerWidth <= MOBILE_TOUR_BREAKPOINT;
  }

  function currentPage() {
    if (path.startsWith("/getting-started")) return "getting-started";
    if (path.startsWith("/ask-bravesprouts")) return "ask-bravesprouts";
    if (path.startsWith("/settings")) return "settings";
    if (path.startsWith("/dashboard")) return "dashboard";
    return "other";
  }

  function getStartingStep() {
    if (hasUrlStep) return urlStep;
    if (currentPage() === "dashboard") return 1;
    return null;
  }

  function getStep(stepNumber) {
    return steps.find((item) => item.step === stepNumber);
  }

  function getStepTargetSelector(step) {
    if (step.selector) return step.selector;
    return `[data-tour-target="${step.target}"]`;
  }

  function cleanUrl() {
    if (!window.location.search.includes("tour=")) return;
    window.history.replaceState({}, document.title, window.location.pathname);
  }

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  /*
    Resolves the instant the target exists.

    This used to poll every 80ms for up to 25 attempts, so a target that
    mounted a moment after the check began still cost a full 80ms tick, and a
    slower one cost multiples of that -- on top of the fixed positioning
    delays below. A MutationObserver fires as soon as the node is inserted and
    is disconnected immediately, so nothing is left observing between steps.
    The timeout is only a safety net for a target that never appears.
  */
  function waitForTarget(selector, timeoutMs = 2000) {
    const existing = document.querySelector(selector);
    if (existing) return Promise.resolve(existing);

    return new Promise((resolve) => {
      let settled = false;
      let observer = null;
      let timer = null;

      const finish = (element) => {
        if (settled) return;
        settled = true;
        if (observer) observer.disconnect();
        if (timer) window.clearTimeout(timer);
        resolve(element);
      };

      observer = new MutationObserver(() => {
        const element = document.querySelector(selector);
        if (element) finish(element);
      });

      observer.observe(document.documentElement, { childList: true, subtree: true });

      timer = window.setTimeout(() => finish(document.querySelector(selector)), timeoutMs);
    });
  }

  /*
    The next step usually lives on another page, and that navigation is a full
    document load. Warming it while the current tooltip is on screen means the
    HTML/CSS is already in the HTTP cache by the time Next is pressed.
    Hint-only: if the browser ignores it, behaviour is unchanged.
  */
  function prefetchStepRoute(stepNumber) {
    const step = getStep(stepNumber);
    if (!step || !step.path || currentPage() === step.page) return;

    const href = `${step.path}?tour=${step.step}`;
    if (document.querySelector(`link[data-tour-prefetch="${href}"]`)) return;

    const link = document.createElement("link");
    link.rel = "prefetch";
    link.as = "document";
    link.href = href;
    link.dataset.tourPrefetch = href;
    document.head.appendChild(link);
  }

  function createTourElements() {
    overlay = document.createElement("div");
    overlay.className = "bravesprouts-tour-overlay";

    spotlight = document.createElement("div");
    spotlight.className = "bravesprouts-tour-spotlight";

    stepPill = document.createElement("div");
    stepPill.className = "bravesprouts-tour-step-pill";

    imageArrow = document.createElement("img");
    imageArrow.src = "/static/images/white_arrpw.png";
    imageArrow.alt = "";
    imageArrow.setAttribute("aria-hidden", "true");
    imageArrow.className = "bravesprouts-tour-image-arrow";

    card = document.createElement("div");
    card.className = "bravesprouts-tour-card";

    document.body.appendChild(overlay);
    document.body.appendChild(spotlight);
    document.body.appendChild(stepPill);
    document.body.appendChild(imageArrow);
    document.body.appendChild(card);

    resizeHandler = () => {
      positionTour();
    };

    scrollHandler = () => {
      if (isMobileTourScreen()) {
        positionTour();
      }
    };

    window.addEventListener("resize", resizeHandler);
    window.addEventListener("orientationchange", resizeHandler);
    window.addEventListener("scroll", scrollHandler, true);
    document.addEventListener("submit", handleTourFormSubmit, true);

    document.body.classList.toggle("bravesprouts-tour-mobile-active", isMobileTourScreen());

    if (!isMobileTourScreen()) {
      document.documentElement.classList.add("bravesprouts-tour-no-scroll");
    }

    requestAnimationFrame(() => {
      overlay.classList.add("is-visible");
      card.classList.add("is-visible");
    });
  }

  function destroyTour() {
    if (resizeHandler) {
      window.removeEventListener("resize", resizeHandler);
      window.removeEventListener("orientationchange", resizeHandler);
    }

    if (scrollHandler) {
      window.removeEventListener("scroll", scrollHandler, true);
    }

    document.removeEventListener("submit", handleTourFormSubmit, true);

    clearActiveTarget();

    document.body.classList.remove(
      "bravesprouts-tour-center-active",
      "bravesprouts-tour-mobile-active",
      "bravesprouts-tour-step-1-active",
      "bravesprouts-tour-step-2-active",
      "bravesprouts-tour-step-3-active",
      "bravesprouts-tour-step-4-active",
      "bravesprouts-tour-step-5-active",
      "bravesprouts-tour-step-6-active",
      "bravesprouts-tour-step-7-active"
    );

    document.documentElement.classList.remove("bravesprouts-tour-no-scroll");

    if (overlay) overlay.remove();
    if (spotlight) spotlight.remove();
    if (stepPill) stepPill.remove();
    if (imageArrow) imageArrow.remove();
    if (card) card.remove();

    overlay = null;
    spotlight = null;
    stepPill = null;
    imageArrow = null;
    card = null;
    resizeHandler = null;
    scrollHandler = null;
    activeTargets = [];
    tourCompleteShowing = false;
  }

  function clearActiveTarget() {
    activeTargets.forEach((element) => {
      element.classList.remove("bravesprouts-tour-target-active");
    });

    document
      .querySelectorAll(".bravesprouts-tour-target-active")
      .forEach((element) => element.classList.remove("bravesprouts-tour-target-active"));

    activeTargets = [];
  }

  function getHighlightElementsForStep(step, target) {
    const elements = [];

    if (isMobileTourScreen() && Array.isArray(step.highlightSelectors)) {
      step.highlightSelectors.forEach((selector) => {
        document.querySelectorAll(selector).forEach((element) => {
          elements.push(element);
        });
      });
    }

    if (!elements.length && target) {
      elements.push(target);
    }

    return [...new Set(elements)].filter(Boolean);
  }

  function setActiveTarget(step, target) {
    clearActiveTarget();

    const elements = getHighlightElementsForStep(step, target);

    elements.forEach((element) => {
      element.classList.add("bravesprouts-tour-target-active");
    });

    activeTargets = elements;
  }

  function renderDots(activeNumber) {
    return steps
      .map((step) => {
        const activeClass = step.step === activeNumber ? "active" : "";
        return `<span class="bravesprouts-tour-dot ${activeClass}" aria-hidden="true"></span>`;
      })
      .join("");
  }

  function getStepDisplayText(step) {
    if (isMobileTourScreen() && step.mobileText) return step.mobileText;
    return step.text;
  }

  function getStepDisplayInstruction(step) {
    if (isMobileTourScreen() && step.mobileInstruction) return step.mobileInstruction;
    return step.instruction || "Select Next to continue.";
  }

  function renderStepPill(step) {
    if (!stepPill) return;

    stepPill.innerHTML = `
      <span class="bravesprouts-tour-step-number">${step.step}</span>
      <span class="bravesprouts-tour-step-main">
        <span class="bravesprouts-tour-step-type">Guided Tour</span>
        <span class="bravesprouts-tour-step-text">Step ${step.step} of ${steps.length}</span>
      </span>
      <span class="bravesprouts-tour-step-name">${step.pillLabel || step.title}</span>
    `;
  }

  function renderCardContent(step) {
    const isLast = step.step === steps.length;
    const displayText = getStepDisplayText(step);
    const displayInstruction = getStepDisplayInstruction(step);
    const title = `${step.icon ? `<span aria-hidden="true">${step.icon}</span> ` : ""}${step.title}`;

    card.className = "bravesprouts-tour-card is-visible";
    card.classList.toggle("has-side-image", !!step.sideImage);
    card.classList.toggle("is-center-only", !!step.centerOnly);
    card.classList.toggle("is-intro", step.step === 1);
    card.classList.toggle("is-last-step", isLast);

    card.innerHTML = `
      <div class="bravesprouts-tour-arrow"></div>

      ${
        step.sideImage
          ? `<img src="/static/images/girlstar.png" class="bravesprouts-tour-side-star" alt="">`
          : ""
      }

      <div class="bravesprouts-tour-side-content">
        <h3>${title}</h3>

        ${
          step.badge
            ? `<div class="bravesprouts-tour-setup-badge">${step.badge}</div>`
            : ""
        }

        <p>${displayText.replace(/\n\n/g, "<br><br>")}</p>

        <div class="bravesprouts-tour-dots" aria-hidden="true">
          ${renderDots(step.step)}
        </div>

        <p class="bravesprouts-tour-instruction">${displayInstruction}</p>

        <div class="bravesprouts-tour-actions">
          <div class="bravesprouts-tour-right-actions">
            ${
              step.step === 1
                ? ""
                : `<button type="button" class="bravesprouts-tour-btn bravesprouts-tour-btn-secondary" data-tour-action="back">
                    Back
                  </button>`
            }

            <button type="button" class="bravesprouts-tour-btn bravesprouts-tour-btn-primary" data-tour-action="${isLast ? "finish" : "next"}">
              ${step.nextText}${isLast ? " ✓" : " →"}
            </button>
          </div>
        </div>
      </div>
    `;

    card.querySelectorAll("[data-tour-action]").forEach((button) => {
      button.addEventListener("click", async function () {
        const action = button.dataset.tourAction;

        if (action === "back") {
          goToStep(step.step - 1);
          return;
        }

        if (action === "next") {
          const allowed = await validateRequiredStep(step);

          if (allowed) {
            goToStep(step.step + 1);
          }

          return;
        }

        if (action === "finish") {
          const allowed = await validateRequiredStep(step);

          if (allowed) {
            completeTour();
          }
        }
      });
    });
  }

  function showTourRequirement(message) {
    if (!card) return;

    const existing = card.querySelector(".bravesprouts-tour-requirement");

    if (existing) {
      existing.textContent = message;
      return;
    }

    const warning = document.createElement("div");
    warning.className = "bravesprouts-tour-requirement";
    warning.textContent = message;

    const dots = card.querySelector(".bravesprouts-tour-dots");

    if (dots) {
      dots.before(warning);
    } else {
      card.appendChild(warning);
    }
  }

  function clearTourRequirement() {
    if (!card) return;

    const existing = card.querySelector(".bravesprouts-tour-requirement");
    if (existing) existing.remove();
  }

  function showTourStatus(message) {
    if (!card) return;

    const existing = card.querySelector(".bravesprouts-tour-status");

    if (existing) {
      existing.textContent = message;
      return;
    }

    const status = document.createElement("div");
    status.className = "bravesprouts-tour-status";
    status.textContent = message;

    const dots = card.querySelector(".bravesprouts-tour-dots");

    if (dots) {
      dots.before(status);
    } else {
      card.appendChild(status);
    }
  }

  function isToggleOn(toggle) {
    if (!toggle) return false;

    const label = toggle.querySelector(".toggle-label");
    const labelText = label ? label.textContent.trim().toLowerCase() : "";

    return (
      toggle.classList.contains("is-on") ||
      toggle.getAttribute("aria-pressed") === "true" ||
      labelText === "on" ||
      labelText === "allowed" ||
      labelText === "enabled"
    );
  }

  function arePermissionsComplete() {
    const audioToggle = document.getElementById("audioPermissionToggle");
    const micToggle = document.getElementById("microphonePermissionToggle");

    return isToggleOn(audioToggle) && isToggleOn(micToggle);
  }

  async function validateRequiredStep(step) {
    clearTourRequirement();

    if (step.required === "permissions") {
      if (!arePermissionsComplete()) {
        showTourRequirement("Please turn on both Audio and Microphone before finishing.");
        return false;
      }
    }

    return true;
  }

  async function saveChildProfileDuringTour(form, submitButton) {
    if (!form || form.tagName.toLowerCase() !== "form") return false;

    const originalText = submitButton ? submitButton.textContent : "";

    if (submitButton) {
      submitButton.disabled = true;
      submitButton.textContent = "Saving...";
    }

    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        credentials: "same-origin"
      });

      if (!response.ok) {
        showTourRequirement("Save failed. Try again, or select Next to skip for now.");
        return false;
      }

      clearTourRequirement();
      showTourStatus("Saved. Select Next to continue.");
      return true;
    } catch (error) {
      console.error("Could not save child profile during tour:", error);
      showTourRequirement("Save failed. Try again, or select Next to skip for now.");
      return false;
    } finally {
      if (submitButton) {
        submitButton.disabled = false;
        submitButton.textContent = originalText;
      }
    }
  }

  function handleTourFormSubmit(event) {
    const step = getStep(activeStepNumber);
    if (!step || step.step !== 6 || tourCompleteShowing) return;

    const form = event.target.closest
      ? event.target.closest('form[data-tour-target="settings-child-profile"]')
      : null;

    if (!form) return;

    event.preventDefault();
    event.stopPropagation();

    if (event.stopImmediatePropagation) {
      event.stopImmediatePropagation();
    }

    saveChildProfileDuringTour(form, event.submitter);
  }

  function addPermissionListenersForStep7() {
    const audioToggle = document.getElementById("audioPermissionToggle");
    const micToggle = document.getElementById("microphonePermissionToggle");

    [audioToggle, micToggle].forEach((toggle) => {
      if (!toggle || toggle.dataset.tourPermissionListener === "1") return;

      toggle.dataset.tourPermissionListener = "1";

      toggle.addEventListener("click", function () {
        window.setTimeout(() => {
          if (activeStepNumber === 7 && arePermissionsComplete()) {
            clearTourRequirement();
            showTourStatus("Audio and microphone are both on.");
          }
        }, 350);
      });
    });
  }

  // Set once a cross-page navigation has been committed. A second rapid click
  // must not fire window.location.href again, which would restart the load and
  // make the next step appear to take twice as long.
  let tourNavigationStarted = false;

  function goToStep(stepNumber) {
    if (tourNavigationStarted) return;

    const nextStep = getStep(stepNumber);
    if (!nextStep) return;

    if (currentPage() !== nextStep.page) {
      tourNavigationStarted = true;
      window.location.href = `${nextStep.path}?tour=${nextStep.step}`;
      return;
    }

    activeStepNumber = stepNumber;
    renderStep();
  }

  async function completeTour() {
    try {
      await fetch("/complete-tour", {
        method: "POST",
        credentials: "same-origin"
      });
    } catch (error) {
      console.error("Could not save tour completion:", error);
    }

    showTourCompleteScreen();
  }

  function positionCompleteCard() {
    if (!card) return;

    if (isMobileTourScreen()) {
      card.style.left = "12px";
      card.style.right = "12px";
      card.style.bottom = "calc(12px + env(safe-area-inset-bottom))";
      card.style.top = "auto";
      return;
    }

    const cardWidth = Math.min(430, window.innerWidth - 36);
    const cardHeight = card.offsetHeight || 320;

    card.style.left = `${Math.max(18, (window.innerWidth - cardWidth) / 2)}px`;
    card.style.top = `${Math.max(88, (window.innerHeight - cardHeight) / 2)}px`;
    card.style.right = "auto";
    card.style.bottom = "auto";
  }

  function showTourCompleteScreen() {
    tourCompleteShowing = true;

    clearActiveTarget();

    document.body.classList.remove(
      "bravesprouts-tour-center-active",
      "bravesprouts-tour-step-1-active",
      "bravesprouts-tour-step-2-active",
      "bravesprouts-tour-step-3-active",
      "bravesprouts-tour-step-4-active",
      "bravesprouts-tour-step-5-active",
      "bravesprouts-tour-step-6-active",
      "bravesprouts-tour-step-7-active"
    );

    if (spotlight) {
      spotlight.style.display = "none";
    }

    if (imageArrow) {
      imageArrow.classList.remove("is-visible");
    }

    if (stepPill) {
      stepPill.innerHTML = `
        <span class="bravesprouts-tour-step-number">✓</span>
        <span class="bravesprouts-tour-step-main">
          <span class="bravesprouts-tour-step-type">Guided Tour</span>
          <span class="bravesprouts-tour-step-text">Complete</span>
        </span>
        <span class="bravesprouts-tour-step-name">Ready</span>
      `;
    }

    card.className = "bravesprouts-tour-card bravesprouts-tour-complete-card is-visible";

    card.innerHTML = `
      <div class="bravesprouts-tour-confetti" aria-hidden="true">
        <span></span><span></span><span></span><span></span>
        <span></span><span></span><span></span><span></span>
        <span></span><span></span><span></span><span></span>
      </div>

      <img src="/static/images/girlstar.png" class="bravesprouts-tour-complete-star" alt="">

      <h3>Tour complete!</h3>

      <p>
        MyBraveSprout is ready. You can start activities from the dashboard and follow the recommended path.
      </p>

      <div class="bravesprouts-tour-actions bravesprouts-tour-complete-actions">
        <button type="button" class="bravesprouts-tour-btn bravesprouts-tour-btn-primary" data-tour-action="go-dashboard">
          Go to Dashboard →
        </button>
      </div>
    `;

    const dashboardButton = card.querySelector('[data-tour-action="go-dashboard"]');

    dashboardButton.addEventListener("click", function () {
      destroyTour();
      window.location.href = "/dashboard";
    });

    positionCompleteCard();
  }

  function getRectForDesktopSpotlight(step, target) {
    if (!target) return null;

    return target.getBoundingClientRect();
  }

  function getMobileScrollTarget(step, fallbackTarget) {
    if (step.mobileScrollSelector) {
      const scrollTarget = document.querySelector(step.mobileScrollSelector);
      if (scrollTarget) return scrollTarget;
    }

    return fallbackTarget;
  }

  function scrollTargetIntoViewForMobile(step, target) {
    if (!target || step.centerOnly) return;

    const scrollTarget = getMobileScrollTarget(step, target);
    if (!scrollTarget) return;

    const targetRect = scrollTarget.getBoundingClientRect();
    const currentScrollY = window.pageYOffset || document.documentElement.scrollTop || 0;
    const targetTop = targetRect.top + currentScrollY;

    const pillRect = stepPill ? stepPill.getBoundingClientRect() : { bottom: 72 };
    const cardHeight = card ? card.offsetHeight || 165 : 165;

    const safeTop = Math.max(76, pillRect.bottom + 18);
    const safeBottom = window.innerHeight - cardHeight - 24;
    const availableHeight = Math.max(140, safeBottom - safeTop);

    let desiredScrollY;

    if (targetRect.height <= availableHeight) {
      desiredScrollY = targetTop - (safeTop + (availableHeight - targetRect.height) / 2);
    } else {
      desiredScrollY = targetTop - safeTop;
    }

    window.scrollTo({
      top: Math.max(0, desiredScrollY),
      behavior: "smooth"
    });
  }

  function scrollTargetIntoViewForDesktop(step, target) {
    if (!target || step.centerOnly) return;

    if (step.step === 7) {
      const rect = target.getBoundingClientRect();
      const currentScrollY = window.pageYOffset || document.documentElement.scrollTop || 0;
      const absoluteTop = rect.top + currentScrollY;

      window.scrollTo({
        top: Math.max(0, absoluteTop - Math.min(430, Math.max(360, window.innerHeight * 0.46))),
        behavior: "smooth"
      });

      return;
    }

    target.scrollIntoView({
      behavior: "smooth",
      block: "center",
      inline: "nearest"
    });
  }

  function scrollTargetIntoView(step, target) {
    if (isMobileTourScreen()) {
      document.documentElement.classList.remove("bravesprouts-tour-no-scroll");
      scrollTargetIntoViewForMobile(step, target);
      return;
    }

    scrollTargetIntoViewForDesktop(step, target);
  }

  function positionStepPill() {
    if (!stepPill) return;

    if (isMobileTourScreen()) {
      stepPill.style.left = "50%";
      stepPill.style.transform = "translateX(-50%)";
      return;
    }

    const dashboardArea =
      document.querySelector(".dashboard-right") ||
      document.querySelector(".dashboard-main") ||
      document.body;

    const rect = dashboardArea.getBoundingClientRect();

    stepPill.style.left = `${rect.left + rect.width / 2}px`;
    stepPill.style.transform = "translateX(-50%)";
  }

  function positionImageArrow(step, rect, cardLeft, cardTop, cardWidth, cardHeight) {
    if (!imageArrow || isMobileTourScreen()) return;

    if (step.step === 3) {
      imageArrow.classList.add("is-visible");
      imageArrow.style.left = `${cardLeft - 115}px`;
      imageArrow.style.top = `${cardTop + 13}px`;
      imageArrow.style.transform = "rotate(0deg)";
      return;
    }

    if (step.step === 4) {
      imageArrow.classList.add("is-visible");
      imageArrow.style.left = `${cardLeft + cardWidth + 8}px`;
      imageArrow.style.top = `${cardTop + cardHeight - 120}px`;
      imageArrow.style.transform = "rotate(180deg)";
      return;
    }

    imageArrow.classList.remove("is-visible");
    imageArrow.style.transform = "rotate(0deg)";
  }

  function positionMobileTourCard() {
    if (!card) return;

    card.style.left = "12px";
    card.style.right = "12px";
    card.style.top = "auto";
    card.style.bottom = "calc(12px + env(safe-area-inset-bottom))";

    card.classList.remove("arrow-left", "arrow-right", "arrow-top", "arrow-bottom");

    if (imageArrow) {
      imageArrow.classList.remove("is-visible");
    }
  }

  function positionDesktopTourCard(step, rect) {
    if (!card || !rect) return;

    const cardWidth = Math.min(DESKTOP_CARD_WIDTH, window.innerWidth - 36);
    const cardHeight = card.offsetHeight || 285;

    let top;
    let left;
    let arrowClass = "arrow-left";

    if (step.centerOnly) {
      left = Math.max(18, (window.innerWidth - cardWidth) / 2);
      top = Math.max(88, (window.innerHeight - cardHeight) / 2);
      arrowClass = "";
    } else if (step.step === 2) {
      left = rect.left + rect.width / 2 - cardWidth / 2;
      top = rect.bottom + 18;
      arrowClass = "arrow-top";
    } else if (step.step === 3) {
      left = rect.left + rect.width / 2 - cardWidth / 2;
      top = rect.bottom + 18;
      arrowClass = "arrow-top";
    } else if (step.step === 4) {
      left = rect.left;
      top = rect.top - cardHeight - 22;
      arrowClass = "arrow-bottom";
    } else if (step.step === 7) {
      left = rect.left + rect.width / 2 - cardWidth / 2;
      top = rect.top - cardHeight - 18;
      arrowClass = "arrow-bottom";
    } else {
      const gap = 24;
      const spaceRight = window.innerWidth - rect.right;
      const spaceLeft = rect.left;
      const spaceBelow = window.innerHeight - rect.bottom;

      if (spaceRight >= cardWidth + gap + 20) {
        left = rect.right + gap;
        top = rect.top;
        arrowClass = "arrow-left";
      } else if (spaceLeft >= cardWidth + gap + 20) {
        left = rect.left - cardWidth - gap;
        top = rect.top;
        arrowClass = "arrow-right";
      } else if (spaceBelow >= 220) {
        left = rect.left;
        top = rect.bottom + gap;
        arrowClass = "arrow-top";
      } else {
        left = rect.left;
        top = rect.top - cardHeight - 24;
        arrowClass = "arrow-bottom";
      }
    }

    left = clamp(left, 18, Math.max(18, window.innerWidth - cardWidth - 18));
    top = clamp(top, 86, Math.max(86, window.innerHeight - cardHeight - 18));

    card.style.left = `${left}px`;
    card.style.top = `${top}px`;
    card.style.right = "auto";
    card.style.bottom = "auto";

    card.classList.remove("arrow-left", "arrow-right", "arrow-top", "arrow-bottom");

    if (arrowClass) {
      card.classList.add(arrowClass);
    }

    requestAnimationFrame(() => {
      positionImageArrow(step, rect, left, top, cardWidth, card.offsetHeight || cardHeight);
    });
  }

  function positionTour() {
    if (tourCompleteShowing) {
      positionCompleteCard();
      return;
    }

    const step = getStep(activeStepNumber);
    if (!step || !card || !stepPill) return;

    document.body.classList.toggle("bravesprouts-tour-mobile-active", isMobileTourScreen());

    positionStepPill();

    if (isMobileTourScreen()) {
      if (spotlight) spotlight.style.display = "none";
      document.documentElement.classList.remove("bravesprouts-tour-no-scroll");
      positionMobileTourCard();
      return;
    }

    document.documentElement.classList.add("bravesprouts-tour-no-scroll");

    if (step.centerOnly) {
      if (spotlight) spotlight.style.display = "none";

      if (imageArrow) {
        imageArrow.classList.remove("is-visible");
      }

      positionDesktopTourCard(step, {
        left: 0,
        top: 0,
        right: window.innerWidth,
        bottom: window.innerHeight,
        width: window.innerWidth,
        height: window.innerHeight
      });

      return;
    }

    const target = document.querySelector(getStepTargetSelector(step));
    if (!target || !spotlight) return;

    const rect = getRectForDesktopSpotlight(step, target);
    if (!rect) return;

    const padding = step.step === 4 ? 10 : 8;
    const spotTop = Math.max(10, rect.top - padding);
    const spotLeft = Math.max(10, rect.left - padding);
    const spotWidth = Math.min(window.innerWidth - 20, rect.width + padding * 2);
    const spotHeight = Math.min(window.innerHeight - 20, rect.height + padding * 2);

    spotlight.style.display = "block";
    spotlight.style.top = `${spotTop}px`;
    spotlight.style.left = `${spotLeft}px`;
    spotlight.style.width = `${spotWidth}px`;
    spotlight.style.height = `${spotHeight}px`;

    positionDesktopTourCard(step, {
      left: spotLeft,
      top: spotTop,
      right: spotLeft + spotWidth,
      bottom: spotTop + spotHeight,
      width: spotWidth,
      height: spotHeight
    });
  }

  async function renderStep() {
    const requestId = ++renderRequestId;
    const step = getStep(activeStepNumber);

    if (!step) return;

    if (currentPage() !== step.page) {
      window.location.href = `${step.path}?tour=${step.step}`;
      return;
    }

    if (!overlay || !spotlight || !card || !stepPill) {
      createTourElements();
    }

    clearTourRequirement();

    let target = null;

    if (!step.centerOnly) {
      target = await waitForTarget(getStepTargetSelector(step));

      if (requestId !== renderRequestId) return;

      if (!target) {
        console.warn("Tour target not found:", step.target);
        return;
      }
    }

    document.body.classList.toggle("bravesprouts-tour-center-active", !!step.centerOnly);

    steps.forEach((item) => {
      document.body.classList.toggle(
        `bravesprouts-tour-step-${item.step}-active`,
        item.step === step.step
      );
    });

    renderStepPill(step);
    renderCardContent(step);

    if (step.step === 7) {
      addPermissionListenersForStep7();
    }

    setActiveTarget(step, target);

    if (isMobileTourScreen()) {
      document.documentElement.classList.remove("bravesprouts-tour-no-scroll");
    } else {
      document.documentElement.classList.add("bravesprouts-tour-no-scroll");
    }

    /*
      Position as soon as layout is ready, then re-position when the smooth
      scroll actually finishes.

      This previously waited a fixed 330ms (260ms on mobile) before the first
      positioning and another 220ms before the second -- 550ms of dead time on
      every step, including same-page steps where nothing needed to settle.
      That was the bulk of the "laggy" feeling. The tooltip now appears on the
      next frame, and the follow-up positioning is driven by the scroll
      genuinely coming to rest rather than by a guessed duration.
    */
    requestAnimationFrame(() => {
      if (requestId !== renderRequestId) return;

      scrollTargetIntoView(step, target);

      positionTour();
      cleanUrl();

      whenScrollSettles(() => {
        if (requestId !== renderRequestId) return;
        positionTour();
      });
    });

    // Warm the next step's page while this one is being read.
    prefetchStepRoute(step.step + 1);
  }

  /*
    Calls `done` once the window has stopped scrolling. Uses the native
    `scrollend` event where available and otherwise watches scrollY settle
    across animation frames. Either way it is bounded, so a scroll that never
    settles cannot strand the tour.
  */
  function whenScrollSettles(done) {
    let finished = false;

    const finish = () => {
      if (finished) return;
      finished = true;
      window.removeEventListener("scrollend", finish);
      done();
    };

    if ("onscrollend" in window) {
      window.addEventListener("scrollend", finish, { once: true });
      window.setTimeout(finish, 600);
      return;
    }

    let lastY = window.scrollY;
    let stableFrames = 0;
    let frames = 0;

    const tick = () => {
      if (finished) return;

      frames += 1;
      const y = window.scrollY;
      stableFrames = y === lastY ? stableFrames + 1 : 0;
      lastY = y;

      // Two consecutive still frames means the scroll has come to rest.
      if (stableFrames >= 2 || frames > 40) {
        finish();
        return;
      }

      requestAnimationFrame(tick);
    };

    requestAnimationFrame(tick);
  }

  renderStep();
});