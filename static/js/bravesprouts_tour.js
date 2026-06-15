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
  const hasUrlStep = Number.isInteger(urlStep) && urlStep >= 1 && urlStep <= 6;

  const hasSeenTour = layout.dataset.hasSeenTour === "1";

  if (hasSeenTour && !hasUrlStep) return;

  const path = window.location.pathname;

  const steps = [
    {
      step: 1,
      page: "dashboard",
      path: "/dashboard",
      target: "current-activity",
      pillLabel: "Start here",
      title: "Welcome to BraveSprouts!",
      text: "We'll guide your child through activities designed to build confidence one small step at a time.\n\nStart here whenever you're ready.",
      nextText: "Next",
      intro: true,
      sideImage: true
    },
    {
      step: 2,
      page: "dashboard",
      path: "/dashboard",
      target: "journey",
      pillLabel: "Your child's journey",
      title: "Your Child's Journey",
      text: "Activities unlock in a recommended order. Each one builds on the skills practiced in the previous activity.",
      nextText: "Next",
      sideImage: true
    },
    {
      step: 3,
      page: "parent-academy",
      path: "/parent-academy",
      target: "parent-academy",
      pillLabel: "Learn along the way",
      title: "Learn Along the Way",
      text: "Not sure why your child behaves differently in different situations? Browse short, evidence-based articles written specifically for parents.",
      nextText: "Next",
      sideImage: true
    },
    {
      step: 4,
      page: "ask-bravesprouts",
      path: "/ask-bravesprouts",
      target: "ask-input",
      pillLabel: "Get answers anytime",
      title: "Ask BraveSprouts",
      text: "Have a question? Ask BraveSprouts anytime for guidance, explanations, and practical ideas. It provides general information, not medical advice.",
      nextText: "Next",
      sideImage: true
    },
    {
      step: 5,
      page: "settings",
      path: "/settings",
      target: "settings-child-profile",
      pillLabel: "Child profile",
      title: "Set Up Your Child's Profile",
      text: "Add your child's name and age before getting started. BraveSprouts uses this to make activities feel more personal.",
      nextText: "Next",
      sideImage: true,
      required: "child-profile"
    },
    {
      step: 6,
      page: "settings",
      path: "/settings",
      target: "settings-permissions",
      pillLabel: "Site permissions",
      title: "Turn On Audio and Microphone",
      text: "Turn on audio and microphone access so your child can hear characters and practice speaking during activities.",
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

    destroyTour();
    window.location.href = "/dashboard";
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
  }

  function destroyTour() {
    if (resizeHandler) {
      window.removeEventListener("resize", resizeHandler);
      window.removeEventListener("scroll", resizeHandler, true);
    }

    document.body.classList.remove(
      "bravesprouts-tour-step-2-active",
      "bravesprouts-tour-step-5-active",
      "bravesprouts-tour-step-6-active"
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

    return childName.length > 0 && childName.toLowerCase() !== "child" && childAge >= 3 && childAge <= 12;
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

  async function validateRequiredStep(step) {
    clearTourRequirement();

    if (step.required === "child-profile") {
      if (!isChildProfileComplete()) {
        showTourRequirement("Add your child's real name and age before continuing.");
        return false;
      }

      const saved = await saveChildProfileDuringTour();

      if (!saved) {
        showTourRequirement("Save failed. Try clicking the Save button, then continue.");
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
        <span class="bravesprouts-tour-step-text">Step ${step.step} of ${steps.length}</span>
        <span class="bravesprouts-tour-step-name">${step.pillLabel || step.title}</span>
      `;
    }

    card.classList.toggle("is-intro", !!step.intro);
    card.classList.toggle("has-side-image", !!step.sideImage);
    card.classList.toggle("is-step-2", step.step === 2);

    if (step.sideImage) {
      card.innerHTML = `
        <div class="bravesprouts-tour-arrow"></div>

        <img src="/static/images/girlstar.png" class="bravesprouts-tour-side-star" alt="">

        <div class="bravesprouts-tour-side-content">
          <h3>${step.title}</h3>

          <p>${step.text.replace(/\n\n/g, "<br><br>")}</p>

          <div class="bravesprouts-tour-dots">
            ${renderDots(step.step)}
          </div>

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

        <p>${step.text}</p>

        <div class="bravesprouts-tour-dots">
          ${renderDots(step.step)}
        </div>

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
    if (step.step !== 2) {
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

    if (step.step === 1) {
      imageArrow.classList.add("is-visible");
      imageArrow.classList.remove("is-step-2-arrow");

      imageArrow.style.left = `${cardLeft - 115}px`;
      imageArrow.style.top = `${cardTop + 13}px`;
      imageArrow.style.transform = "rotate(0deg)";
      return;
    }

    if (step.step === 2) {
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
    const step = getStep(activeStepNumber);

    if (!step || !spotlight || !card) return;

    positionStepPill();

    const target = document.querySelector(`[data-tour-target="${step.target}"]`);

    if (!target) return;

    const rect = getTourRect(step, target);
    const padding = step.step === 2 ? 12 : step.intro ? 8 : 10;

    const spotTop = Math.max(10, rect.top - padding);
    const spotLeft = Math.max(10, rect.left - padding);
    const spotWidth = Math.min(window.innerWidth - 20, rect.width + padding * 2);
    const spotHeight = Math.min(window.innerHeight - 20, rect.height + padding * 2);

    spotlight.style.top = `${spotTop}px`;
    spotlight.style.left = `${spotLeft}px`;
    spotlight.style.width = `${spotWidth}px`;
    spotlight.style.height = `${spotHeight}px`;

    const cardWidth = Math.min(TOUR_CARD_WIDTH, window.innerWidth - 36);

    let top;
    let left;
    let arrowClass = "arrow-left";

    if (step.step === 1) {
      left = rect.left + rect.width / 2 - cardWidth / 2;
      top = rect.bottom - 6;
      arrowClass = "arrow-top";
    } else if (step.step === 2) {
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
        top = rect.top - 260;
        arrowClass = "arrow-bottom";
      }
    }

    left = clamp(left, 18, window.innerWidth - cardWidth - 18);
    top = clamp(top, 18, window.innerHeight - 280);

    card.style.left = `${left}px`;
    card.style.top = `${top}px`;

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

    const target = await waitForTarget(`[data-tour-target="${step.target}"]`);

    if (!target) {
      console.warn("Tour target not found:", step.target);
      return;
    }

    document.body.classList.toggle("bravesprouts-tour-step-2-active", step.step === 2);
    document.body.classList.toggle("bravesprouts-tour-step-5-active", step.step === 5);
    document.body.classList.toggle("bravesprouts-tour-step-6-active", step.step === 6);

    if (step.step === 2) {
      scrollStep2Slightly();
    } else {
      target.scrollIntoView({
        behavior: "smooth",
        block: "center",
        inline: "nearest"
      });
    }

    setTimeout(() => {
      if (!overlay || !spotlight || !card) {
        createTourElements();
      }

      renderCardContent(step);
      positionTour();
      cleanUrl();
    }, step.step === 2 ? 220 : 300);
  }

  renderStep();
});