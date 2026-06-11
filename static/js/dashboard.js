document.addEventListener("DOMContentLoaded", function () {
  // ---------------------
  // PROFILE DROPDOWN
  // ---------------------
  const profileDropdown = document.querySelector(".profile-dropdown");
  const profileTrigger = document.getElementById("profileTrigger");
  const dropdownMenu = document.getElementById("dropdownMenu");

  if (profileDropdown && profileTrigger && dropdownMenu) {
    profileTrigger.addEventListener("click", function (event) {
      event.stopPropagation();

      dropdownMenu.classList.toggle("active");
      profileDropdown.classList.toggle("open");
    });

    dropdownMenu.addEventListener("click", function (event) {
      event.stopPropagation();
    });

    document.addEventListener("click", function () {
      dropdownMenu.classList.remove("active");
      profileDropdown.classList.remove("open");
    });
  }

  // ---------------------
  // PROFILE ICON
  // ---------------------
  const currentProfileIcon = document.getElementById("currentProfileIcon");
  const iconOptions = document.querySelectorAll(".icon-option");

  iconOptions.forEach((button) => {
    button.addEventListener("click", async function () {
      const selectedIcon = this.dataset.icon;

      if (!selectedIcon || !currentProfileIcon) return;

      currentProfileIcon.src = `/static/images/${selectedIcon}`;

      try {
        const response = await fetch("/update-profile-icon", {
          method: "POST",
          headers: {
            "Content-Type": "application/x-www-form-urlencoded"
          },
          credentials: "same-origin",
          body: new URLSearchParams({
            icon: selectedIcon
          })
        });

        const data = await response.json();

        if (!data.success) {
          console.error(data.error || "Failed to save icon");
        }
      } catch (error) {
        console.error("Error saving profile icon:", error);
      }
    });
  });

  // ---------------------
  // ACTIVITY BUTTONS
  // ---------------------
  const activityButtons = document.querySelectorAll(".activity-action-btn");

  const unlockModal = document.getElementById("unlockModal");
  const confirmUnlockBtn = document.getElementById("confirmUnlockBtn");
  const cancelUnlockBtn = document.getElementById("cancelUnlockBtn");
  const unlockChecks = document.querySelectorAll(".unlock-check");

  const unlockModalTitle = document.getElementById("unlockModalTitle");
  const characterCheckText = document.getElementById("characterCheckText");
  const activityCheckText = document.getElementById("activityCheckText");
  const timeCheckText = document.getElementById("timeCheckText");

  let pendingUnlockActivityId = null;
  let pendingUnlockButton = null;

  function resetUnlockModal() {
    unlockChecks.forEach((check) => {
      check.checked = false;
    });

    confirmUnlockBtn.disabled = true;
  }

  function allUnlockChecksComplete() {
    return [...unlockChecks].every((check) => check.checked);
  }

  async function sendActivityAction(endpoint, activityId, button) {
    try {
      if (button) {
        button.disabled = true;
      }

      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        credentials: "same-origin",
        body: JSON.stringify({
          activity_id: activityId
        })
      });

      const data = await response.json();

      if (data.success) {
        location.reload();
      } else {
        console.error(data.error || "Action failed");
        alert(data.error || "Something went wrong.");

        if (button) {
          button.disabled = false;
        }
      }
    } catch (error) {
      console.error("Fetch error:", error);
      alert("Something went wrong. Check the console.");

      if (button) {
        button.disabled = false;
      }
    }
  }

  activityButtons.forEach((button) => {
    button.addEventListener("click", async function () {
      const action = this.dataset.action;
      const activityId = this.dataset.activityId;

      if (!action || !activityId) {
        console.error("Missing action or activity ID");
        return;
      }

      if (action === "set-current") {
        await sendActivityAction("/set-current", activityId, this);
        return;
      }

      if (action === "unlock") {
        pendingUnlockActivityId = activityId;
        pendingUnlockButton = this;

        const activityName = this.dataset.activityName || "this activity";
        const character = this.dataset.character || "the character";
        const time = this.dataset.time || "30";

        unlockModalTitle.textContent = `Unlock ${activityName}?`;

        characterCheckText.textContent =
          `Is the child comfortable speaking to ${character}?`;

        activityCheckText.textContent =
          `Can the child comfortably complete ${activityName}?`;

        timeCheckText.textContent =
          `Has the child been on this activity for at least ${time} minutes?`;

        resetUnlockModal();
        unlockModal.classList.add("active");
        return;
      }

      console.error("Unknown action:", action);
    });
  });

  unlockChecks.forEach((check) => {
    check.addEventListener("change", function () {
      confirmUnlockBtn.disabled = !allUnlockChecksComplete();
    });
  });

  cancelUnlockBtn.addEventListener("click", function () {
    unlockModal.classList.remove("active");
    pendingUnlockActivityId = null;
    pendingUnlockButton = null;
  });

  confirmUnlockBtn.addEventListener("click", async function () {
    if (!pendingUnlockActivityId) return;

    unlockModal.classList.remove("active");

    await sendActivityAction(
      "/unlock-activity",
      pendingUnlockActivityId,
      pendingUnlockButton
    );
  });

  function getJourneyColor(index, isLocked) {
  if (isLocked) return "#d8d8e0";

  if (index >= 1 && index <= 3) return "#8b5cf6";
  if (index >= 4 && index <= 6) return "#3b99fc";
  if (index >= 7 && index <= 9) return "#73c4a1";
  if (index >= 10 && index <= 12) return "#f4b46a";

  return "#8b5cf6";
}

function drawJourneyConnector() {
  const pathContainer = document.querySelector(".journey-path");
  const svg = document.querySelector(".journey-connector-svg");
  const items = [...document.querySelectorAll(".journey-path-item")];
  const nodes = [...document.querySelectorAll(".journey-node")];

  if (!pathContainer || !svg || nodes.length < 2) return;

  const containerRect = pathContainer.getBoundingClientRect();

  svg.setAttribute(
    "viewBox",
    `0 0 ${pathContainer.offsetWidth} ${pathContainer.offsetHeight}`
  );

  svg.innerHTML = `
    <defs id="journeyGradientDefs"></defs>
  `;

  const defs = svg.querySelector("#journeyGradientDefs");

  for (let i = 0; i < nodes.length - 1; i++) {
    const currentRect = nodes[i].getBoundingClientRect();
    const nextRect = nodes[i + 1].getBoundingClientRect();

    const startX = currentRect.left + currentRect.width / 2 - containerRect.left;
    const startY = currentRect.bottom - containerRect.top;

    const endX = nextRect.left + nextRect.width / 2 - containerRect.left;
    const endY = nextRect.top - containerRect.top +7;

    const midY = (startY + endY) / 2;

    const nextItem = items[i + 1];
    const nextIsLocked = nextItem.classList.contains("journey-locked");

    const fromColor = getJourneyColor(i + 1, false);
    const toColor = getJourneyColor(i + 2, nextIsLocked);

    const gradientId = `journey-gradient-${i}`;

    const gradient = document.createElementNS("http://www.w3.org/2000/svg", "linearGradient");
    gradient.setAttribute("id", gradientId);
    gradient.setAttribute("x1", startX);
    gradient.setAttribute("y1", startY);
    gradient.setAttribute("x2", endX);
    gradient.setAttribute("y2", endY);
    gradient.setAttribute("gradientUnits", "userSpaceOnUse");

    gradient.innerHTML = `
      <stop offset="0%" stop-color="${nextIsLocked ? "#d8d8e0" : fromColor}" />
      <stop offset="100%" stop-color="${nextIsLocked ? "#d8d8e0" : toColor}" />
    `;

    defs.appendChild(gradient);

    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");

    path.setAttribute(
      "d",
      `
      M ${startX} ${startY}
      C ${startX} ${midY}, ${endX} ${midY}, ${endX} ${endY}
      `
    );

    path.setAttribute("fill", "none");
    path.setAttribute("stroke", `url(#${gradientId})`);
    path.setAttribute("stroke-width", "5");
    path.setAttribute("stroke-linecap", "round");
    path.setAttribute("stroke-linejoin", "round");

    svg.appendChild(path);
  }
}

drawJourneyConnector();
window.addEventListener("resize", drawJourneyConnector);
});