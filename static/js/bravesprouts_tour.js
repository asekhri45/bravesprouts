document.addEventListener("DOMContentLoaded", function () {
  const layout = document.querySelector(".dashboard-layout");

  if (!layout) return;

  const TOUR_CARD_WIDTH = 455;

  const STEP_2_HIGHLIGHT_EXTRA_LEFT = 60;
  const STEP_2_HIGHLIGHT_EXTRA_RIGHT = 110;
  const STEP_2_HIGHLIGHT_EXTRA_BOTTOM = 18;

  const STEP_2_CARD_LEFT_OFFSET = -245;
  const STEP_2_CARD_TOP_OFFSET = -60;

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
      title: "Welcome to BraveSprouts!",
      text: "Let's take a quick 7-step tour before getting started. It takes about one minute and shows the activity path, parent resources, questions, profile setup, and permissions.",
      badge: "Required setup • About 1 minute",
      instruction: "Select Next to begin the guided tour.",
      nextText: "Next",
      intro: true,
      sideImage: true,
      centerOnly: true
    },
    {
      step: 2,
      page: "dashboard",
      path: "/dashboard",
      target: "current-activity",
      pillLabel: "Current Activity",
      title: "Start Activities Here",
      text: "This is the recommended activity to begin with. Activities are designed to build comfort and confidence one small step at a time.",
      instruction: "Follow the highlighted area, then select Next to continue.",
      nextText: "Next",
      intro: true,
      sideImage: true
    },
    {
      step: 3,
      page: "dashboard",
      path: "/dashboard",
      target: "journey",
      pillLabel: "Progression Path",
      title: "Your Child's Journey",
      text: "Activities unlock in a recommended order. Each one builds on the skills practiced in the previous activity.",
      instruction: "Follow the highlighted area, then select Next to continue.",
      nextText: "Next",
      sideImage: true
    },
    {
      step: 4,
      page: "parent-academy",
      path: "/parent-academy",
      target: "parent-academy",
      pillLabel: "Parent Resources",
      title: "Parent Academy",
      text: "Browse short articles that explain selective mutism concepts, family situations, and support strategies in parent-friendly language.",
      instruction: "Follow the highlighted area, then select Next to continue.",
      nextText: "Next",
      sideImage: true
    },
    {
      step: 5,
      page: "ask-bravesprouts",
      path: "/ask-bravesprouts",
      target: "ask-input",
      pillLabel: "Ask BraveSprouts",
      title: "Ask BraveSprouts",
      text: "Use this space to ask questions and get general guidance, explanations, and practical ideas. It provides general information, not medical advice.",
      instruction: "Follow the highlighted area, then select Next to continue.",
      nextText: "Next",
      sideImage: true
    },
    {
      step: 6,
      page: "settings",
      path: "/settings",
      target: "settings-child-profile",
      pillLabel: "Child Profile",
      title: "Set Up Your Child's Profile",
      text: "Add your child's name and age before getting started. BraveSprouts uses this to make activities feel more personal.",
      instruction: "Complete the highlighted section, then select Next to continue.",
      nextText: "Next",
      sideImage: true,
      required: "child-profile"
    },
    {
      step: 7,
      page: "settings",
      path: "/settings",
      target: "settings-permissions",
      pillLabel: "Audio + Microphone",
      title: "Turn On Audio and Microphone",
      text: "Turn on audio and microphone access so your child can hear characters and practice speaking during activities.",
      instruction: "Turn on both highlighted permissions, then select Finish.",
      nextText: "Finish",
      sideImage: true,
      required: "permissions"
    }
  ];

  function currentPage() {
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
        BraveSprouts is ready. You can start playing games from the dashboard and follow the recommended activity path.
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
    card.classList.toggle("is-step-2", step.step === 3);
    card.classList.toggle("is-step-7", step.step === 7);

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

          <p>${step.text.replace(/\n\n/g, "<br><br>")}</p>

          <div class="bravesprouts-tour-dots">
            ${renderDots(step.step)}
          </div>

          <p class="bravesprouts-tour-instruction">${step.instruction || "Select Next to continue."}</p>

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

        <p>${step.text}</p>

        <div class="bravesprouts-tour-dots">
          ${renderDots(step.step)}
        </div>

        <p class="bravesprouts-tour-instruction">${step.instruction || "Select Next to continue."}</p>

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
    if (step.step !== 3) {
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

    if (step.step === 2) {
      imageArrow.classList.add("is-visible");
      imageArrow.classList.remove("is-step-2-arrow");

      imageArrow.style.left = `${cardLeft - 115}px`;
      imageArrow.style.top = `${cardTop + 13}px`;
      imageArrow.style.transform = "rotate(0deg)";
      return;
    }

    if (step.step === 3) {
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

    const target = document.querySelector(`[data-tour-target="${step.target}"]`);

    if (!target) return;

    const rect = getTourRect(step, target);
    const padding = step.step === 3 ? 12 : step.intro ? 8 : 10;

    const spotTop = Math.max(10, rect.top - padding);
    const spotLeft = Math.max(10, rect.left - padding);
    const spotWidth = Math.min(window.innerWidth - 20, rect.width + padding * 2);
    const spotHeight = Math.min(window.innerHeight - 20, rect.height + padding * 2);

    spotlight.style.top = `${spotTop}px`;
    spotlight.style.left = `${spotLeft}px`;
    spotlight.style.width = `${spotWidth}px`;
    spotlight.style.height = `${spotHeight}px`;

    const cardWidth = Math.min(TOUR_CARD_WIDTH, window.innerWidth - 36);
    const cardHeight = card.offsetHeight || 285;

    let top;
    let left;
    let arrowClass = "arrow-left";

    if (step.step === 2) {
      left = rect.left + rect.width / 2 - cardWidth / 2;
      top = rect.bottom - 6;
      arrowClass = "arrow-top";
    } else if (step.step === 7) {
      /*
        Step 7 should sit ABOVE the permissions card.
        arrow-bottom means the pointer appears on the bottom of the tour card,
        pointing down toward the highlighted permissions section.
      */
      left = rect.left + rect.width / 2 - cardWidth / 2;
      top = rect.top - cardHeight - 24;
      arrowClass = "arrow-bottom";
    } else if (step.step === 3) {
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

    if (step.step === 7) {
      top = clamp(top, 76, Math.max(76, window.innerHeight - cardHeight - 18));
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
      target = await waitForTarget(`[data-tour-target="${step.target}"]`);

      if (!target) {
        console.warn("Tour target not found:", step.target);
        return;
      }
    }

    document.body.classList.toggle("bravesprouts-tour-center-active", !!step.centerOnly);
    document.body.classList.toggle("bravesprouts-tour-step-2-active", step.step === 3);
    document.body.classList.toggle("bravesprouts-tour-step-6-active", step.step === 6);
    document.body.classList.toggle("bravesprouts-tour-step-7-active", step.step === 7);

    if (step.step === 3) {
      scrollStep2Slightly();
    } else if (target) {
      if (step.step === 7) {
        /*
          Put permissions lower in the viewport so the tour card has room above it.
        */
        target.scrollIntoView({
          behavior: "smooth",
          block: "end",
          inline: "nearest"
        });
      } else {
        target.scrollIntoView({
          behavior: "smooth",
          block: "center",
          inline: "nearest"
        });
      }
    }

    setTimeout(() => {
      if (!overlay || !spotlight || !card) {
        createTourElements();
      }

      renderCardContent(step);
      positionTour();
      cleanUrl();

      if (step.step === 7) {
        setTimeout(positionTour, 250);
      }
    }, step.step === 3 ? 220 : step.centerOnly ? 120 : step.step === 7 ? 420 : 300);
  }

  renderStep();
});