document.addEventListener("DOMContentLoaded", function () {
  const layout = document.querySelector(".dashboard-layout");

  if (!layout) return;

  const TOUR_CARD_WIDTH = 455;
  const MOBILE_TOUR_BREAKPOINT = 900;
  const MOBILE_TARGET_MIN_VISIBLE_RATIO = 0.75;


  const STEP_2_HIGHLIGHT_EXTRA_LEFT = 60;
  const STEP_2_HIGHLIGHT_EXTRA_RIGHT = 110;
  const STEP_2_HIGHLIGHT_EXTRA_BOTTOM = 18;

  const STEP_2_CARD_LEFT_OFFSET = -245;
  const STEP_2_CARD_TOP_OFFSET = -60;

  const urlParams = new URLSearchParams(window.location.search);
  const urlStep = Number(urlParams.get("tour"));
  const hasUrlStep = Number.isInteger(urlStep) && urlStep >= 1 && urlStep <= 8;

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
      title: "Welcome to MyBraveSprout!",
      text: "Let's take a quick 1 minute tour before getting started. It shows the demo videos, activity path, parent resources, questions, profile setup, and permissions.",
      mobileText: "A quick setup tour for videos, activities, resources, profile, and permissions.",
      badge: "Required setup • About 1 minute",
      instruction: "Select Next to begin the guided tour.",
      mobileInstruction: "Select Next to begin.",
      nextText: "Next",
      intro: true,
      sideImage: true,
      centerOnly: true
    },
    {
      step: 2,
      page: "getting-started",
      path: "/getting-started",
      target: "demo-videos-tab",
      selector: '.sidebar-nav a[href="/getting-started"], .sidebar-nav a[href$="/getting-started"]',
      pillLabel: "Demo Videos",
      title: "Find the Demo Videos",
      text: "This tab has the short parent demo videos. You can come back here anytime to watch the overview or the quick dashboard walkthrough.",
      mobileText: "Watch quick parent demo videos here anytime.",
      instruction: "This keeps the tour card beside the navigation instead of covering the videos.",
      mobileInstruction: "Select Next when ready.",
      nextText: "Next",
      intro: true,
      sideImage: true
    },
    {
      step: 3,
      page: "dashboard",
      path: "/dashboard",
      target: "current-activity",
      pillLabel: "Current Activity",
      title: "Start Activities Here",
      text: "This is the recommended activity to begin with. Activities are designed to build comfort and confidence one small step at a time.",
      mobileText: "Start with the recommended activity here.",
      instruction: "Follow the highlighted area, then select Next to continue.",
      mobileInstruction: "Highlighted area stays visible.",
      nextText: "Next",
      intro: true,
      sideImage: true
    },
    {
      step: 4,
      page: "dashboard",
      path: "/dashboard",
      target: "journey",
      pillLabel: "Progression Path",
      title: "Your Child's Journey",
      text: "Activities unlock in a recommended order. Each one builds on the skills practiced in the previous activity.",
      mobileText: "Activities unlock in order as your child builds comfort.",
      instruction: "Follow the highlighted area, then select Next to continue.",
      mobileInstruction: "Select Next to continue.",
      nextText: "Next",
      sideImage: true
    },
    {
      step: 5,
      page: "parent-academy",
      path: "/parent-academy",
      target: "parent-academy",
      pillLabel: "Parent Resources",
      title: "Parent Resources",
      text: "Browse short articles that explain selective mutism concepts, family situations, and support strategies in parent-friendly language.",
      mobileText: "Browse short parent-friendly articles and support ideas here.",
      instruction: "Follow the highlighted area, then select Next to continue.",
      mobileInstruction: "Select Next to continue.",
      nextText: "Next",
      sideImage: true
    },
    {
      step: 6,
      page: "ask-bravesprouts",
      path: "/ask-bravesprouts",
      target: "ask-input",
      pillLabel: "MyBraveSprout AI",
      title: "MyBraveSprout AI",
      text: "Use this space to ask questions and get general guidance, explanations, and practical ideas. It provides general information, not medical advice.",
      mobileText: "Ask general questions and get practical ideas. Not medical advice.",
      instruction: "Follow the highlighted area, then select Next to continue.",
      mobileInstruction: "Select Next to continue.",
      nextText: "Next",
      sideImage: true
    },
    {
      step: 7,
      page: "settings",
      path: "/settings",
      target: "settings-child-profile",
      pillLabel: "Child Profile",
      title: "Set Up Your Child's Profile",
      text: "You can add your child's name and age now, or come back and fill this in later from the dashboard. MyBraveSprout can use this information to make activities feel more personal.",
      mobileText: "Add your child's name and age now, or skip this and come back later from Settings.",
      instruction: "Fill this in now or later, then select Next to continue.",
      mobileInstruction: "Fill this in now or later, then select Next to continue.",
      nextText: "Next",
      sideImage: true
    },
    {
      step: 8,
      page: "settings",
      path: "/settings",
      target: "settings-permissions",
      pillLabel: "Audio + Microphone",
      title: "Turn On Audio and Microphone",
      text: "Turn on audio and microphone access so your child can hear characters and practice speaking during activities.",
      mobileText: "Turn on audio and microphone so activities can work.",
      instruction: "Turn on both highlighted permissions, then select Finish.",
      mobileInstruction: "Turn both on, then Finish.",
      nextText: "Finish",
      sideImage: true,
      required: "permissions"
    }
  ];

  function currentPage() {
    if (path.startsWith("/getting-started")) return "getting-started";
    if (path.startsWith("/parent-academy")) return "parent-academy";
    if (path.startsWith("/ask-bravesprouts")) return "ask-bravesprouts";
    if (path.startsWith("/settings")) return "settings";
    if (path.startsWith("/dashboard")) return "dashboard";
    return "other";
  }

  function startingStep() {
    if (hasUrlStep) return urlStep;
    if (currentPage() === "dashboard") return 1;
    return null;
  }

  let activeStepNumber = startingStep();

  if (!activeStepNumber) return;

  let overlay = null;
  let spotlight = null;
  let card = null;
  let stepPill = null;
  let imageArrow = null;
  let resizeHandler = null;
  let tourCompleteShowing = false;

  function getStep(stepNumber) {
    return steps.find((item) => item.step === stepNumber);
  }

  function getStepTargetSelector(step) {
    if (step.selector) return step.selector;
    return `[data-tour-target="${step.target}"]`;
  }

  function cleanUrl() {
    if (!window.location.search.includes("tour=")) return;

    const clean = window.location.pathname;
    window.history.replaceState({}, document.title, clean);
  }

  function goToStep(stepNumber) {
    const nextStep = getStep(stepNumber);

    if (!nextStep) return;

    if (currentPage() !== nextStep.page) {
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

    const cardWidth = Math.min(430, window.innerWidth - 36);
    const cardHeight = card.offsetHeight || 320;

    card.style.left = `${Math.max(18, (window.innerWidth - cardWidth) / 2)}px`;
    card.style.top = `${Math.max(88, (window.innerHeight - cardHeight) / 2)}px`;

    card.classList.remove("arrow-left", "arrow-right", "arrow-top", "arrow-bottom");
  }

  function showTourCompleteScreen() {
    tourCompleteShowing = true;

    document.body.classList.remove(
      "bravesprouts-tour-center-active",
      "bravesprouts-tour-step-2-active",
      "bravesprouts-tour-step-5-active",
      "bravesprouts-tour-step-6-active",
      "bravesprouts-tour-step-7-active"
    );

    if (spotlight) {
      spotlight.style.display = "none";
    }

    if (imageArrow) {
      imageArrow.classList.remove("is-visible");
      imageArrow.classList.remove("is-step-2-arrow");
    }

    if (stepPill) {
      stepPill.innerHTML = `
        <span class="bravesprouts-tour-step-number">✓</span>
        <span class="bravesprouts-tour-step-main">
          <span class="bravesprouts-tour-step-type">Guided Tour</span>
          <span class="bravesprouts-tour-step-text">Complete</span>
        </span>
      `;
    }

    card.className = "bravesprouts-tour-card bravesprouts-tour-complete-card is-visible";
    card.style.zIndex = "99997";

    card.innerHTML = `
      <div class="bravesprouts-tour-confetti" aria-hidden="true">
        <span></span><span></span><span></span><span></span>
        <span></span><span></span><span></span><span></span>
        <span></span><span></span><span></span><span></span>
      </div>

      <img src="/static/images/girlstar.png" class="bravesprouts-tour-complete-star" alt="">

      <h3>Tour complete!</h3>

      <p>
        MyBraveSprout is ready. You can start playing games from the dashboard and follow the recommended activity path.
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

    /*
      Keep the actual tour card above highlighted settings cards.
      The settings target needs a high z-index so parents can click toggles,
      but the tour instructions must still stay visible.
    */
    card.style.zIndex = "99997";
    stepPill.style.zIndex = "99998";

    document.documentElement.classList.add("bravesprouts-tour-no-scroll");

    requestAnimationFrame(() => {
      overlay.classList.add("is-visible");
      card.classList.add("is-visible");
    });

    resizeHandler = () => {
      positionTour();
    };

    window.addEventListener("resize", resizeHandler);
    window.addEventListener("scroll", resizeHandler, true);
    document.addEventListener("submit", handleTourFormSubmit, true);
  }

  function destroyTour() {
    if (resizeHandler) {
      window.removeEventListener("resize", resizeHandler);
      window.removeEventListener("scroll", resizeHandler, true);
    }

    document.removeEventListener("submit", handleTourFormSubmit, true);
    tourCompleteShowing = false;

    document.body.classList.remove(
      "bravesprouts-tour-center-active",
      "bravesprouts-tour-step-2-active",
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
  }

  function waitForTarget(selector, attempts = 20) {
    return new Promise((resolve) => {
      let count = 0;

      const check = () => {
        const element = document.querySelector(selector);

        if (element) {
          resolve(element);
          return;
        }

        count += 1;

        if (count >= attempts) {
          resolve(null);
          return;
        }

        setTimeout(check, 100);
      };

      check();
    });
  }

  function renderDots(activeNumber) {
    return steps
      .map((step) => {
        const activeClass = step.step === activeNumber ? "active" : "";
        return `<span class="bravesprouts-tour-dot ${activeClass}"></span>`;
      })
      .join("");
  }

  function showTourRequirement(message) {
    const existing = card.querySelector(".bravesprouts-tour-requirement");

    if (existing) {
      existing.textContent = message;
      return;
    }

    const warning = document.createElement("div");
    warning.className = "bravesprouts-tour-requirement";
    warning.textContent = message;

    const contentArea =
      card.querySelector(".bravesprouts-tour-side-content") || card;

    const dots = card.querySelector(".bravesprouts-tour-dots");

    if (dots) {
      dots.before(warning);
    } else {
      contentArea.prepend(warning);
    }
  }

  function clearTourRequirement() {
    const existing = card.querySelector(".bravesprouts-tour-requirement");
    if (existing) existing.remove();
  }

  function isChildProfileComplete() {
    const childNameInput = document.querySelector('input[name="child_name"]');
    const childAgeInput = document.querySelector('input[name="child_age"]');

    const childName = childNameInput ? childNameInput.value.trim() : "";
    const childAge = childAgeInput ? Number(childAgeInput.value) : 0;

    return (
      childName.length > 0 &&
      childName.toLowerCase() !== "child" &&
      childAge >= 3 &&
      childAge <= 12
    );
  }

  function arePermissionsComplete() {
    const audioToggle = document.getElementById("audioPermissionToggle");
    const micToggle = document.getElementById("microphonePermissionToggle");

    return (
      audioToggle &&
      micToggle &&
      audioToggle.classList.contains("is-on") &&
      micToggle.classList.contains("is-on")
    );
  }

  async function saveChildProfileDuringTour() {
    const form = document.querySelector('[data-tour-target="settings-child-profile"]');

    if (!form || form.tagName.toLowerCase() !== "form") return true;

    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        credentials: "same-origin"
      });

      return response.ok;
    } catch (error) {
      console.error("Could not save child profile during tour:", error);
      return false;
    }
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
    const contentArea =
      card.querySelector(".bravesprouts-tour-side-content") || card;

    if (dots) {
      dots.before(status);
    } else {
      contentArea.appendChild(status);
    }
  }

  async function handleTourFormSubmit(event) {
    const step = getStep(activeStepNumber);

    if (!step || step.required !== "child-profile" || tourCompleteShowing) return;

    const form = event.target.closest
      ? event.target.closest('form[data-tour-target="settings-child-profile"]')
      : null;

    if (!form) return;

    event.preventDefault();
    event.stopPropagation();

    if (event.stopImmediatePropagation) {
      event.stopImmediatePropagation();
    }

    clearTourRequirement();

    if (!isChildProfileComplete()) {
      showTourRequirement("Add your child's real name and age before continuing.");
      return;
    }

    const submitButton = event.submitter;
    const originalButtonText = submitButton ? submitButton.textContent : "";

    if (submitButton) {
      submitButton.disabled = true;
      submitButton.textContent = "Saving...";
    }

    const saved = await saveChildProfileDuringTour();

    if (submitButton) {
      submitButton.disabled = false;
      submitButton.textContent = originalButtonText;
    }

    if (!saved) {
      showTourRequirement("Save failed. Try again, then continue.");
      return;
    }

    showTourStatus("Saved. Select Next to continue.");
  }

  async function validateRequiredStep(step) {
    clearTourRequirement();

    if (step.required === "child-profile") {
      if (!isChildProfileComplete()) {
        showTourRequirement("Add your child's real name and age before continuing.");
        return false;
      }

      const saved = await saveChildProfileDuringTour();

      if (!saved) {
        showTourRequirement("Save failed. Try again, then continue.");
        return false;
      }
    }

    if (step.required === "permissions") {
      if (!arePermissionsComplete()) {
        showTourRequirement("Turn on both audio and microphone before finishing.");
        return false;
      }
    }

    return true;
  }

  function renderCardContent(step) {
    const isLast = step.step === steps.length;
    const displayText = getStepDisplayText(step);
    const displayInstruction = getStepDisplayInstruction(step);

    if (stepPill) {
      stepPill.innerHTML = `
        <span class="bravesprouts-tour-step-number">${step.step}</span>
        <span class="bravesprouts-tour-step-main">
          <span class="bravesprouts-tour-step-type">Guided Tour</span>
          <span class="bravesprouts-tour-step-text">Step ${step.step} of ${steps.length}</span>
        </span>
        <span class="bravesprouts-tour-step-name">${step.pillLabel || step.title}</span>
      `;
    }

    card.classList.toggle("is-intro", !!step.intro);
    card.classList.toggle("has-side-image", !!step.sideImage);
    card.classList.toggle("is-center-only", !!step.centerOnly);
    card.classList.toggle("is-step-2", step.step === 4);
    card.classList.toggle("is-step-7", step.step === 8);
    card.classList.toggle("is-mobile-settings-step", step.step === 7 || step.step === 8);

    if (step.sideImage) {
      card.innerHTML = `
        <div class="bravesprouts-tour-arrow"></div>

        <img src="/static/images/girlstar.png" class="bravesprouts-tour-side-star" alt="">

        <div class="bravesprouts-tour-side-content">
          <h3>${step.title}</h3>

          ${
            step.badge
              ? `<div class="bravesprouts-tour-setup-badge">${step.badge}</div>`
              : ""
          }

          <p>${displayText.replace(/\n\n/g, "<br><br>")}</p>

          <div class="bravesprouts-tour-dots">
            ${renderDots(step.step)}
          </div>

          <p class="bravesprouts-tour-instruction">${displayInstruction}</p>

          <div class="bravesprouts-tour-actions">
            <div class="bravesprouts-tour-left-actions"></div>

            <div class="bravesprouts-tour-right-actions">
              ${
                step.step === 1
                  ? ""
                  : `<button type="button" class="bravesprouts-tour-btn bravesprouts-tour-btn-secondary" data-tour-action="back">
                      Back
                    </button>`
              }

              <button type="button" class="bravesprouts-tour-btn bravesprouts-tour-btn-primary" data-tour-action="${isLast ? "finish" : "next"}">
                ${step.nextText}${isLast ? "" : " →"}
              </button>
            </div>
          </div>
        </div>
      `;
    } else {
      card.innerHTML = `
        <div class="bravesprouts-tour-arrow"></div>

        <h3>${step.title}</h3>

        ${
          step.badge
            ? `<div class="bravesprouts-tour-setup-badge">${step.badge}</div>`
            : ""
        }

        <p>${displayText}</p>

        <div class="bravesprouts-tour-dots">
          ${renderDots(step.step)}
        </div>

        <p class="bravesprouts-tour-instruction">${displayInstruction}</p>

        <div class="bravesprouts-tour-actions">
          <div class="bravesprouts-tour-left-actions"></div>

          <div class="bravesprouts-tour-right-actions">
            <button type="button" class="bravesprouts-tour-btn bravesprouts-tour-btn-secondary" data-tour-action="back">
              Back
            </button>

            <button type="button" class="bravesprouts-tour-btn bravesprouts-tour-btn-primary" data-tour-action="${isLast ? "finish" : "next"}">
              ${step.nextText}${isLast ? "" : " →"}
            </button>
          </div>
        </div>
      `;
    }

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

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }


  function isMobileTourScreen() {
    return window.innerWidth <= MOBILE_TOUR_BREAKPOINT;
  }

  function getStepDisplayText(step) {
    if (isMobileTourScreen() && step.mobileText) return step.mobileText;
    return step.text;
  }

  function getStepDisplayInstruction(step) {
    if (isMobileTourScreen() && step.mobileInstruction) return step.mobileInstruction;
    return step.instruction || "Select Next to continue.";
  }

  function rectToPlain(rect) {
    return {
      left: rect.left,
      top: rect.top,
      right: rect.right,
      bottom: rect.bottom,
      width: rect.width,
      height: rect.height
    };
  }

  function overlapArea(a, b) {
    const left = Math.max(a.left, b.left);
    const right = Math.min(a.right, b.right);
    const top = Math.max(a.top, b.top);
    const bottom = Math.min(a.bottom, b.bottom);

    if (right <= left || bottom <= top) return 0;
    return (right - left) * (bottom - top);
  }

  function cardRectFromPosition(left, top, width, height) {
    return {
      left,
      top,
      right: left + width,
      bottom: top + height,
      width,
      height
    };
  }


  function unionRects(rects) {
    const validRects = rects.filter((rect) => rect && rect.width > 0 && rect.height > 0);
    if (!validRects.length) return null;

    const left = Math.min(...validRects.map((rect) => rect.left));
    const top = Math.min(...validRects.map((rect) => rect.top));
    const right = Math.max(...validRects.map((rect) => rect.right));
    const bottom = Math.max(...validRects.map((rect) => rect.bottom));

    return {
      left,
      top,
      right,
      bottom,
      width: right - left,
      height: bottom - top
    };
  }

  function expandedRect(rect, amount) {
    if (!rect) return null;

    const left = Math.max(10, rect.left - amount);
    const top = Math.max(10, rect.top - amount);
    const right = Math.min(window.innerWidth - 10, rect.right + amount);
    const bottom = Math.min(window.innerHeight - 10, rect.bottom + amount);

    return {
      left,
      top,
      right,
      bottom,
      width: right - left,
      height: bottom - top
    };
  }

  function shiftRectLeftForStep8(rect) {
    if (!rect) return null;

    /*
      Mobile Step 8 looked slightly too far right compared with the
      permission sliders. Move only this highlighted permissions region
      left without changing the rest of the v8 tour.
    */
    const shift = 24;
    const width = rect.width;
    const left = Math.max(10, rect.left - shift);
    const right = Math.min(window.innerWidth - 10, left + width);

    return {
      left,
      top: rect.top,
      right,
      bottom: rect.bottom,
      width: right - left,
      height: rect.height
    };
  }

  function getTourControlRegion(element) {
    if (!element) return null;

    return (
      element.closest(
        '[data-tour-control-region], .settings-field, .settings-form-group, .settings-control-row, .settings-row, .form-group, .field-group, .permission-row, .permission-toggle-row, .settings-toggle-row, .settings-option, .permission-card, .toggle-setting, label'
      ) ||
      (element.parentElement && element.parentElement.parentElement) ||
      element.parentElement ||
      element
    );
  }

  function getMobileSettingsImportantElements(step) {
    if (step.step === 7) {
      const childName = document.querySelector('input[name="child_name"]');
      const childAge = document.querySelector('input[name="child_age"]');

      return [
        getTourControlRegion(childName),
        getTourControlRegion(childAge)
      ].filter(Boolean);
    }

    if (step.step === 8) {
      const audioToggle = document.getElementById("audioPermissionToggle");
      const micToggle = document.getElementById("microphonePermissionToggle");

      return [
        getTourControlRegion(audioToggle),
        getTourControlRegion(micToggle)
      ].filter(Boolean);
    }

    return [];
  }

  function getMobileSettingsImportantRect(step) {
    if (!isMobileTourScreen() || (step.step !== 7 && step.step !== 8)) return null;

    /*
      Step 7 should focus tightly on the two real profile controls.
      Step 8 should use the whole permissions card so there is only one
      clean-looking highlighted region instead of a nested/double highlight.
    */
    if (step.step === 8) {
      const target = document.querySelector(getStepTargetSelector(step));
      if (target) {
        const permissionRect = expandedRect(rectToPlain(target.getBoundingClientRect()), 8);
        return shiftRectLeftForStep8(permissionRect);
      }
    }

    const elements = getMobileSettingsImportantElements(step);
    if (!elements.length) return null;

    const rects = elements.map((element) => element.getBoundingClientRect());
    return expandedRect(unionRects(rects), 14);
  }

  function applyMobileSettingsCardInlineStyles() {
    if (!card) return;

    card.classList.add("is-mobile-settings-step", "is-mobile-extra-compact");

    card.style.setProperty("width", "calc(100vw - 24px)", "important");
    card.style.setProperty("max-width", "calc(100vw - 24px)", "important");
    card.style.setProperty("max-height", "none", "important");
    card.style.setProperty("height", "auto", "important");
    card.style.setProperty("bottom", "auto", "important");
    card.style.setProperty("overflow", "visible", "important");
    card.style.setProperty("padding", "10px 12px", "important");
    card.style.setProperty("border-radius", "18px", "important");

    const sideStar = card.querySelector(".bravesprouts-tour-side-star");
    if (sideStar) sideStar.style.setProperty("display", "none", "important");

    const sideContent = card.querySelector(".bravesprouts-tour-side-content");
    if (sideContent) {
      sideContent.style.setProperty("padding-left", "0", "important");
      sideContent.style.setProperty("width", "100%", "important");
    }

    const dots = card.querySelector(".bravesprouts-tour-dots");
    if (dots) dots.style.setProperty("display", "none", "important");
  }

  function positionMobileSettingsCardAtTop() {
    if (!card) return;

    applyMobileSettingsCardInlineStyles();

    const margin = 12;
    const pillRect = stepPill ? stepPill.getBoundingClientRect() : { bottom: 72 };
    const measured = card.getBoundingClientRect();
    const cardWidth = Math.min(measured.width || window.innerWidth - 24, window.innerWidth - 24);
    const maxLeft = Math.max(margin, window.innerWidth - cardWidth - margin);
    const left = clamp((window.innerWidth - cardWidth) / 2, margin, maxLeft);
    const top = Math.max(76, pillRect.bottom + 8);

    card.style.setProperty("left", `${left}px`, "important");
    card.style.setProperty("top", `${top}px`, "important");
    card.style.setProperty("bottom", "auto", "important");
    card.style.setProperty("height", "auto", "important");
    card.style.zIndex = "99997";

    card.classList.remove("arrow-left", "arrow-right", "arrow-top", "arrow-bottom");
    card.classList.add("arrow-bottom");
  }

  function scrollMobileSettingsControlsIntoView(step, target) {
    if (!isMobileTourScreen() || (step.step !== 7 && step.step !== 8) || !target || !card) return;

    unlockTourScrollForProgrammaticMove();
    positionMobileSettingsCardAtTop();

    const cardRect = card.getBoundingClientRect();
    const currentScrollY = window.pageYOffset || document.documentElement.scrollTop || 0;
    const importantRect = getMobileSettingsImportantRect(step) || target.getBoundingClientRect();

    const safeTop = Math.min(window.innerHeight * 0.46, Math.max(cardRect.bottom + 10, 180));
    const safeBottom = window.innerHeight - 22;
    const availableHeight = Math.max(120, safeBottom - safeTop);

    const importantAbsTop = importantRect.top + currentScrollY;
    const importantHeight = importantRect.height;

    let desiredScrollY;
    if (importantHeight <= availableHeight) {
      desiredScrollY = importantAbsTop - (safeTop + (availableHeight - importantHeight) / 2);
    } else {
      desiredScrollY = importantAbsTop - safeTop;
    }

    window.scrollTo({
      top: Math.max(0, desiredScrollY),
      behavior: "auto"
    });
  }

  function lockTourScroll() {
    document.documentElement.classList.add("bravesprouts-tour-no-scroll");
  }

  function unlockTourScrollForProgrammaticMove() {
    document.documentElement.classList.remove("bravesprouts-tour-no-scroll");
  }

  function scrollTargetForTour(step, target) {
    if (!target || step.centerOnly) return;

    unlockTourScrollForProgrammaticMove();

    const rect = target.getBoundingClientRect();
    const currentScrollY = window.pageYOffset || document.documentElement.scrollTop || 0;
    const absoluteTop = rect.top + currentScrollY;
    const viewportHeight = window.innerHeight;

    /*
      Mobile tour targets should sit in the visual center/lower half so the
      card can be placed above or below without hiding the important area.
    */
    const mobileAnchor = step.step >= 7 ? 0.58 : 0.52;
    const desktopBlock = step.step === 8 ? "center" : "center";

    if (isMobileTourScreen()) {
      if (step.step === 7 || step.step === 8) {
        /*
          Settings tasks need the actual fields/toggles visible. Keep the
          highlighted settings panel lower in the viewport so the compact
          helper card can sit above it instead of covering the controls.
        */
        const desiredTargetTop = Math.min(360, Math.max(300, viewportHeight * 0.30));
        const desiredTop = absoluteTop - desiredTargetTop;

        window.scrollTo({
          top: Math.max(0, desiredTop),
          behavior: "smooth"
        });
        return;
      }

      const desiredTop = absoluteTop - (viewportHeight * mobileAnchor - rect.height / 2);
      window.scrollTo({
        top: Math.max(0, desiredTop),
        behavior: "smooth"
      });
      return;
    }

    if (step.step === 4) {
      scrollStep2Slightly();
      return;
    }

    if (step.step === 8) {
      /*
        Desktop permissions step: push the highlighted permissions card into
        the lower half before positioning the tooltip above it. This prevents
        the tooltip bubble from covering the highlighted permission controls.
      */
      const desiredTargetTop = Math.min(430, Math.max(360, viewportHeight * 0.46));
      const desiredTop = absoluteTop - desiredTargetTop;

      window.scrollTo({
        top: Math.max(0, desiredTop),
        behavior: "smooth"
      });
      return;
    }

    target.scrollIntoView({
      behavior: "smooth",
      block: desktopBlock,
      inline: "nearest"
    });
  }

  function positionStepPill() {
    if (!stepPill) return;

    const dashboardArea =
      document.querySelector(".dashboard-right") ||
      document.querySelector(".dashboard-main") ||
      document.body;

    const rect = dashboardArea.getBoundingClientRect();

    stepPill.style.left = `${rect.left + rect.width / 2}px`;
    stepPill.style.transform = "translateX(-50%)";
  }

  function getTourRect(step, target) {
    const mobileSettingsRect = getMobileSettingsImportantRect(step);
    if (mobileSettingsRect) {
      return mobileSettingsRect;
    }

    if (step.step !== 4) {
      return target.getBoundingClientRect();
    }

    const journeyHeader = document.querySelector(".journey-section .section-header-row");
    const journeyPath = document.querySelector(".journey-path");
    const journeyItems = Array.from(document.querySelectorAll(".journey-path-item")).slice(0, 3);

    if (!journeyHeader || !journeyPath || journeyItems.length === 0) {
      return target.getBoundingClientRect();
    }

    const headerRect = journeyHeader.getBoundingClientRect();
    const pathRect = journeyPath.getBoundingClientRect();
    const itemRects = journeyItems.map((item) => item.getBoundingClientRect());

    const naturalLeft = Math.min(pathRect.left, ...itemRects.map((rect) => rect.left));
    const naturalTop = headerRect.top;
    const naturalRight = Math.max(pathRect.right, ...itemRects.map((rect) => rect.right));
    const naturalBottom = Math.max(...itemRects.map((rect) => rect.bottom));

    const expandedLeft = Math.max(10, naturalLeft - STEP_2_HIGHLIGHT_EXTRA_LEFT);
    const expandedRight = Math.min(window.innerWidth - 10, naturalRight + STEP_2_HIGHLIGHT_EXTRA_RIGHT);
    const expandedBottom = Math.min(window.innerHeight - 10, naturalBottom + STEP_2_HIGHLIGHT_EXTRA_BOTTOM);

    return {
      left: expandedLeft,
      top: naturalTop,
      right: expandedRight,
      bottom: expandedBottom,
      width: expandedRight - expandedLeft,
      height: expandedBottom - naturalTop
    };
  }

  function positionImageArrow(step, rect, cardLeft, cardTop, cardWidth, cardHeight) {
    if (!imageArrow) return;

    if (step.step === 3) {
      imageArrow.classList.add("is-visible");
      imageArrow.classList.remove("is-step-2-arrow");

      imageArrow.style.left = `${cardLeft - 115}px`;
      imageArrow.style.top = `${cardTop + 13}px`;
      imageArrow.style.transform = "rotate(0deg)";
      return;
    }

    if (step.step === 4) {
      imageArrow.classList.add("is-visible");
      imageArrow.classList.add("is-step-2-arrow");

      imageArrow.style.left = `${cardLeft + cardWidth + 8}px`;
      imageArrow.style.top = `${cardTop + cardHeight - 120}px`;
      imageArrow.style.transform = "rotate(180deg)";
      return;
    }

    imageArrow.classList.remove("is-visible");
    imageArrow.classList.remove("is-step-2-arrow");
    imageArrow.style.transform = "rotate(0deg)";
  }

  function positionMobileTourCard(step, rect, spotRect) {
    if (!card) return;

    if (imageArrow) {
      imageArrow.classList.remove("is-visible");
      imageArrow.classList.remove("is-step-2-arrow");
    }

    card.style.removeProperty("width");
    card.style.removeProperty("padding");

    const sideStar = card.querySelector(".bravesprouts-tour-side-star");
    if (sideStar) {
      sideStar.style.removeProperty("left");
      sideStar.style.removeProperty("top");
      sideStar.style.removeProperty("width");
      sideStar.style.removeProperty("height");
    }

    card.classList.remove("is-mobile-extra-compact");

    const margin = 12;
    const gap = 12;
    const pillRect = stepPill ? stepPill.getBoundingClientRect() : { bottom: 72 };
    const minTop = Math.max(72, pillRect.bottom + 10);

    if (step.step === 7 || step.step === 8) {
      /*
        Interactive Settings steps: keep the helper as a tiny top bar and
        highlight only the actual controls so name/age and permission toggles
        remain fully visible underneath it.
      */
      positionMobileSettingsCardAtTop();
      return;
    }

    let measured = card.getBoundingClientRect();
    let cardWidth = Math.min(measured.width || window.innerWidth - 24, window.innerWidth - 24);
    let cardHeight = measured.height || 210;

    if (cardHeight > cardWidth || window.innerHeight < 680) {
      card.classList.add("is-mobile-extra-compact");
      measured = card.getBoundingClientRect();
      cardWidth = Math.min(measured.width || window.innerWidth - 24, window.innerWidth - 24);
      cardHeight = measured.height || 190;
    }

    const maxLeft = Math.max(margin, window.innerWidth - cardWidth - margin);
    const maxTop = Math.max(minTop, window.innerHeight - cardHeight - margin);

    const centerLeft = rect.left + rect.width / 2 - cardWidth / 2;
    const centerTop = rect.top + rect.height / 2 - cardHeight / 2;

    const rawCandidates = [
      { name: "below", left: centerLeft, top: rect.bottom + gap, arrowClass: "arrow-top" },
      { name: "above", left: centerLeft, top: rect.top - cardHeight - gap, arrowClass: "arrow-bottom" },
      { name: "bottom", left: centerLeft, top: window.innerHeight - cardHeight - margin, arrowClass: "arrow-top" },
      { name: "top", left: centerLeft, top: minTop, arrowClass: "arrow-bottom" },
      { name: "right", left: rect.right + gap, top: centerTop, arrowClass: "arrow-left" },
      { name: "left", left: rect.left - cardWidth - gap, top: centerTop, arrowClass: "arrow-right" },
      { name: "below-left", left: margin, top: rect.bottom + gap, arrowClass: "arrow-top" },
      { name: "below-right", left: window.innerWidth - cardWidth - margin, top: rect.bottom + gap, arrowClass: "arrow-top" },
      { name: "above-left", left: margin, top: rect.top - cardHeight - gap, arrowClass: "arrow-bottom" },
      { name: "above-right", left: window.innerWidth - cardWidth - margin, top: rect.top - cardHeight - gap, arrowClass: "arrow-bottom" }
    ];

    const targetArea = Math.max(1, spotRect.width * spotRect.height);

    const scored = rawCandidates.map((candidate) => {
      const left = clamp(candidate.left, margin, maxLeft);
      const top = clamp(candidate.top, minTop, maxTop);
      const candidateRect = cardRectFromPosition(left, top, cardWidth, cardHeight);
      const overlap = overlapArea(candidateRect, spotRect);
      const visibleRatio = 1 - overlap / targetArea;
      const cardCenterX = left + cardWidth / 2;
      const cardCenterY = top + cardHeight / 2;
      const targetCenterX = rect.left + rect.width / 2;
      const targetCenterY = rect.top + rect.height / 2;
      const distance = Math.hypot(cardCenterX - targetCenterX, cardCenterY - targetCenterY);
      const meetsTarget = visibleRatio >= MOBILE_TARGET_MIN_VISIBLE_RATIO;

      return {
        ...candidate,
        left,
        top,
        visibleRatio,
        overlap,
        distance,
        score: (meetsTarget ? 100000 : 0) + visibleRatio * 10000 - distance
      };
    });

    scored.sort((a, b) => b.score - a.score || a.overlap - b.overlap);
    const best = scored[0];

    card.style.left = `${best.left}px`;
    card.style.top = `${best.top}px`;
    card.style.zIndex = "99997";

    card.classList.remove("arrow-left", "arrow-right", "arrow-top", "arrow-bottom");
    card.classList.add(best.arrowClass);
  }

  function positionTour() {
    if (tourCompleteShowing) {
      positionCompleteCard();
      return;
    }

    const step = getStep(activeStepNumber);

    if (!step || !spotlight || !card) return;

    positionStepPill();

    if (step.centerOnly) {
      spotlight.style.display = "none";

      if (imageArrow) {
        imageArrow.classList.remove("is-visible");
        imageArrow.classList.remove("is-step-2-arrow");
      }

      const cardWidth = Math.min(TOUR_CARD_WIDTH, window.innerWidth - 36);
      const finalCardHeight = card.offsetHeight || 250;

      card.style.left = `${Math.max(18, (window.innerWidth - cardWidth) / 2)}px`;
      card.style.top = `${Math.max(88, (window.innerHeight - finalCardHeight) / 2)}px`;

      card.classList.remove("arrow-left", "arrow-right", "arrow-top", "arrow-bottom");
      return;
    }

    spotlight.style.display = "block";

    const target = document.querySelector(getStepTargetSelector(step));

    if (!target) return;

    const rect = getTourRect(step, target);
    const padding = step.step === 4 ? 12 : step.intro ? 8 : 10;

    const spotTop = Math.max(10, rect.top - padding);
    const spotLeft = Math.max(10, rect.left - padding);
    const spotWidth = Math.min(window.innerWidth - 20, rect.width + padding * 2);
    const spotHeight = Math.min(window.innerHeight - 20, rect.height + padding * 2);
    const spotRect = {
      left: spotLeft,
      top: spotTop,
      right: spotLeft + spotWidth,
      bottom: spotTop + spotHeight,
      width: spotWidth,
      height: spotHeight
    };

    spotlight.style.top = `${spotTop}px`;
    spotlight.style.left = `${spotLeft}px`;
    spotlight.style.width = `${spotWidth}px`;
    spotlight.style.height = `${spotHeight}px`;

    if (isMobileTourScreen()) {
      positionMobileTourCard(step, rectToPlain(rect), spotRect);
      return;
    }

    const isDemoSidebarStep = step.step === 2;

    if (isDemoSidebarStep) {
      const sidebar = document.querySelector(".sidebar");
      const sidebarRect = sidebar ? sidebar.getBoundingClientRect() : rect;
      const compactWidth = Math.min(315, Math.max(260, sidebarRect.width - 36), window.innerWidth - 36);

      card.style.setProperty("width", `${compactWidth}px`, "important");
      card.style.setProperty("padding", "22px 18px 20px 76px", "important");

      const sideStar = card.querySelector(".bravesprouts-tour-side-star");
      if (sideStar) {
        sideStar.style.setProperty("left", "18px", "important");
        sideStar.style.setProperty("top", "24px", "important");
        sideStar.style.setProperty("width", "44px", "important");
        sideStar.style.setProperty("height", "44px", "important");
      }
    } else {
      card.style.removeProperty("width");
      card.style.removeProperty("padding");

      const sideStar = card.querySelector(".bravesprouts-tour-side-star");
      if (sideStar) {
        sideStar.style.removeProperty("left");
        sideStar.style.removeProperty("top");
        sideStar.style.removeProperty("width");
        sideStar.style.removeProperty("height");
      }
    }

    const cardWidth = isDemoSidebarStep
      ? Math.min(315, Math.max(260, (document.querySelector(".sidebar")?.getBoundingClientRect().width || 315) - 36), window.innerWidth - 36)
      : Math.min(TOUR_CARD_WIDTH, window.innerWidth - 36);

    const cardHeight = card.offsetHeight || 285;

    let top;
    let left;
    let arrowClass = "arrow-left";

    if (step.step === 2) {
      const sidebar = document.querySelector(".sidebar");
      const sidebarRect = sidebar ? sidebar.getBoundingClientRect() : rect;

      left = Math.max(18, sidebarRect.left + 18);
      top = rect.bottom + 18;
      arrowClass = "arrow-top";
    } else if (step.step === 3) {
      left = rect.left + rect.width / 2 - cardWidth / 2;
      top = rect.bottom - 6;
      arrowClass = "arrow-top";
    } else if (step.step === 8) {
      const pillRect = stepPill ? stepPill.getBoundingClientRect() : { bottom: 74 };
      const gap = 16;
      left = rect.left + rect.width / 2 - cardWidth / 2;
      top = rect.top - cardHeight - gap;

      /*
        Keep the desktop Step 8 bubble fully above the highlighted permissions
        card whenever the page has room. If the browser lands slightly short
        after smooth scrolling, use the safest available top instead of letting
        the bubble sit on top of the highlighted area.
      */
      const safestTop = Math.max(pillRect.bottom + 12, 86);
      if (top < safestTop && rect.top - safestTop >= 190) {
        top = safestTop;
      }

      arrowClass = "arrow-bottom";
    } else if (step.step === 4) {
      const estimatedCardHeight = 210;

      left = rect.left + STEP_2_CARD_LEFT_OFFSET;
      top = rect.top - estimatedCardHeight + STEP_2_CARD_TOP_OFFSET;
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

    left = clamp(left, 18, window.innerWidth - cardWidth - 18);

    if (step.step === 8) {
      top = clamp(top, 76, Math.max(76, window.innerHeight - cardHeight - 18));
    } else if (step.step === 2) {
      top = clamp(top, rect.bottom + 12, Math.max(rect.bottom + 12, window.innerHeight - cardHeight - 18));
    } else {
      top = clamp(top, 86, Math.max(86, window.innerHeight - cardHeight - 18));
    }

    card.style.left = `${left}px`;
    card.style.top = `${top}px`;
    card.style.zIndex = "99997";

    card.classList.remove("arrow-left", "arrow-right", "arrow-top", "arrow-bottom");
    card.classList.add(arrowClass);

    requestAnimationFrame(() => {
      const finalCardHeight = card.offsetHeight || 210;
      positionImageArrow(step, rect, left, top, cardWidth, finalCardHeight);
    });
  }

  function scrollStep2Slightly() {
    const journeySection = document.querySelector(".journey-section");
    if (!journeySection) return;

    const rect = journeySection.getBoundingClientRect();

    const desiredTop = 330;
    const neededScroll = rect.top - desiredTop;

    if (neededScroll <= 0) return;

    const maxStep2Scroll = 95;

    window.scrollBy({
      top: Math.min(neededScroll, maxStep2Scroll),
      behavior: "smooth"
    });
  }

  async function renderStep() {
    const step = getStep(activeStepNumber);

    if (!step) return;

    if (currentPage() !== step.page) {
      window.location.href = `${step.path}?tour=${step.step}`;
      return;
    }

    let target = null;

    if (!step.centerOnly) {
      target = await waitForTarget(getStepTargetSelector(step));

      if (!target) {
        console.warn("Tour target not found:", step.target);
        return;
      }
    }

    document.body.classList.toggle("bravesprouts-tour-center-active", !!step.centerOnly);
    document.body.classList.toggle("bravesprouts-tour-step-2-active", step.step === 4);
    document.body.classList.toggle("bravesprouts-tour-step-6-active", step.step === 7);
    document.body.classList.toggle("bravesprouts-tour-step-7-active", step.step === 8);

    const isMobileSettingsStep =
      target && isMobileTourScreen() && (step.step === 7 || step.step === 8);

    if (target && !isMobileSettingsStep) {
      scrollTargetForTour(step, target);
    } else {
      unlockTourScrollForProgrammaticMove();
    }

    setTimeout(() => {
      if (!overlay || !spotlight || !card) {
        createTourElements();
      }

      renderCardContent(step);

      if (isMobileSettingsStep) {
        scrollMobileSettingsControlsIntoView(step, target);

        requestAnimationFrame(() => {
          lockTourScroll();
          positionTour();
          cleanUrl();
          setTimeout(positionTour, 80);
        });

        return;
      }

      lockTourScroll();
      positionTour();
      cleanUrl();

      if (step.step === 8) {
        setTimeout(positionTour, 250);
      }
    }, step.step === 4 ? 220 : step.centerOnly ? 120 : step.step === 8 ? 380 : 300);
  }

  renderStep();
});