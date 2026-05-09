document.addEventListener("DOMContentLoaded", function () {
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
});