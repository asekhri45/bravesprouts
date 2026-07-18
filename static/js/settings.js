document.addEventListener("DOMContentLoaded", () => {
  setupSettingsTourMode();
  setupProfileDropdown();
  setupAgeSlider();
  setupPermissionToggles();
  setupPasswordModal();
  setupPinModal();
  setupDeleteModal();
});

function setupSettingsTourMode() {
  const tourStep = new URLSearchParams(window.location.search).get("tour");

  const isChildProfileTourStep = tourStep === "6";
  const isPermissionsTourStep = tourStep === "7";

  document.body.classList.toggle("settings-tour-child-profile-active", isChildProfileTourStep);
  document.body.classList.toggle("settings-tour-permissions-active", isPermissionsTourStep);

  if (!isChildProfileTourStep) return;

  const childProfileForm = document.querySelector('[data-tour-target="settings-child-profile"]');

  if (!childProfileForm) return;

  childProfileForm.addEventListener("submit", (event) => {
    event.preventDefault();
    event.stopPropagation();

    if (event.stopImmediatePropagation) {
      event.stopImmediatePropagation();
    }
  }, true);
}

function setupProfileDropdown() {
  const profileDropdown = document.querySelector(".profile-dropdown");
  const profileTrigger = document.getElementById("profileTrigger");
  const dropdownMenu = document.getElementById("dropdownMenu");
  const currentProfileIcon = document.getElementById("currentProfileIcon");
  const iconButtons = document.querySelectorAll(".icon-option");

  if (!profileDropdown || !profileTrigger || !dropdownMenu) return;

  profileTrigger.addEventListener("click", (event) => {
    event.stopPropagation();
    dropdownMenu.classList.toggle("active");
  });

  dropdownMenu.addEventListener("click", (event) => {
    event.stopPropagation();
  });

  document.addEventListener("click", () => {
    dropdownMenu.classList.remove("active");
  });

  iconButtons.forEach((button) => {
    button.addEventListener("click", async () => {
      const icon = button.dataset.icon;

      if (!icon) return;

      try {
        const formData = new FormData();
        formData.append("icon", icon);

        const response = await fetch("/update-profile-icon", {
          method: "POST",
          body: formData
        });

        const data = await response.json();

        if (!data.success) return;

        if (currentProfileIcon) {
          currentProfileIcon.src = `/static/images/${icon}`;
        }

        dropdownMenu.classList.remove("active");
      } catch (error) {
        console.error("Profile icon update failed:", error);
      }
    });
  });
}

function setupAgeSlider() {
  const slider = document.getElementById("childAgeSlider");
  const ageValue = document.getElementById("ageValue");

  if (!slider || !ageValue) return;

  const updateSlider = () => {
    const min = Number(slider.min);
    const max = Number(slider.max);
    const value = Number(slider.value);
    const percent = ((value - min) / (max - min)) * 100;

    ageValue.textContent = value;
    slider.style.setProperty("--slider-fill", `${percent}%`);
  };

  slider.addEventListener("input", updateSlider);

const isTourChildProfileStep =
  new URLSearchParams(window.location.search).get("tour") === "6";

if (isTourChildProfileStep) {
  const min = Number(slider.min);
  const max = Number(slider.max);
  const value = Number(slider.value);
  const percent = ((value - min) / (max - min)) * 100;

  ageValue.textContent = "—";
  slider.style.setProperty("--slider-fill", `${percent}%`);
} else {
  updateSlider();
}
}

function setupPermissionToggles() {
  const audioToggle = document.getElementById("audioPermissionToggle");
  const micToggle = document.getElementById("microphonePermissionToggle");
  const message = document.getElementById("permissionMessage");

  if (
    !audioToggle ||
    !micToggle ||
    !window.BraveSproutPermissions
  ) {
    return;
  }

  const permissions = window.BraveSproutPermissions;

  const isTourPermissionStep =
    new URLSearchParams(window.location.search).get("tour") === "7";

  async function refreshStates() {
    if (isTourPermissionStep) {
      permissions.setAudioPreference(false);
      permissions.setMicrophonePreference(false);

      setToggleState(audioToggle, false);
      setToggleState(micToggle, false);
      return;
    }

    const audioEnabled = permissions.getAudioPreference();
    const microphoneState =
      await permissions.getMicrophoneReadiness();

    setToggleState(audioToggle, audioEnabled);

    setToggleState(
      micToggle,
      microphoneState.ready,
      microphoneState.state === "denied"
    );
  }

  audioToggle.addEventListener("click", async () => {
    const currentlyOn =
      audioToggle.classList.contains("is-on");

    if (currentlyOn) {
      permissions.setAudioPreference(false);
      setToggleState(audioToggle, false);

      setPermissionMessage(
        message,
        "Audio is turned off for this browser.",
        "neutral"
      );

      return;
    }

    try {
      await permissions.unlockAudio();
      setToggleState(audioToggle, true);

      setPermissionMessage(
        message,
        "Audio is enabled for this browser.",
        "success"
      );
    } catch (error) {
      permissions.setAudioPreference(false);
      setToggleState(audioToggle, false, true);

      setPermissionMessage(
        message,
        "Audio could not be enabled. Click the page and try again.",
        "error"
      );
    }
  });

  micToggle.addEventListener("click", async () => {
    const currentlyOn =
      micToggle.classList.contains("is-on");

    if (currentlyOn) {
      permissions.setMicrophonePreference(false);
      setToggleState(micToggle, false);

      setPermissionMessage(
        message,
        "Microphone is turned off inside MyBraveSprout. Browser permission may still remain allowed.",
        "neutral"
      );

      return;
    }

    const result = await permissions.requestMicrophone();

    if (result.enabled) {
      permissions.stopStream(result.stream);
      setToggleState(micToggle, true);

      setPermissionMessage(
        message,
        "Microphone access is enabled for this browser.",
        "success"
      );

      return;
    }

    setToggleState(
      micToggle,
      false,
      result.state === "denied"
    );

    let errorMessage =
      "Microphone access could not be enabled.";

    if (result.state === "denied") {
      errorMessage =
        "Microphone permission was blocked. Open your browser’s site settings to allow it.";
    } else if (result.state === "no-device") {
      errorMessage =
        "No microphone was found on this device.";
    } else if (result.state === "unavailable") {
      errorMessage =
        "The microphone is currently unavailable or is being used by another app.";
    } else if (result.state === "unsupported") {
      errorMessage =
        "This browser does not support microphone access here.";
    }

    setPermissionMessage(
      message,
      errorMessage,
      "error"
    );
  });

  refreshStates();
}

async function unlockAudioPlayback() {
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;

  if (!AudioContextClass) return;

  const audioContext = new AudioContextClass();

  if (audioContext.state === "suspended") {
    await audioContext.resume();
  }

  const oscillator = audioContext.createOscillator();
  const gain = audioContext.createGain();

  gain.gain.value = 0.0001;

  oscillator.connect(gain);
  gain.connect(audioContext.destination);

  oscillator.start();
  oscillator.stop(audioContext.currentTime + 0.03);

  setTimeout(() => {
    audioContext.close();
  }, 120);
}

function setToggleState(toggle, enabled, denied = false) {
  const label = toggle.querySelector(".toggle-label");

  toggle.classList.toggle("is-on", enabled);
  toggle.classList.toggle("is-denied", denied);
  toggle.setAttribute("aria-pressed", enabled ? "true" : "false");

  if (label) {
    if (denied) {
      label.textContent = "Blocked";
    } else {
      label.textContent = enabled ? "On" : "Off";
    }
  }
}

function setPermissionMessage(element, text, type) {
  if (!element) return;

  element.textContent = text;
  element.classList.remove("success", "error");

  if (type === "success") {
    element.classList.add("success");
  }

  if (type === "error") {
    element.classList.add("error");
  }
}

function setupPasswordModal() {
  setupBasicModal({
    openButtonId: "openPasswordModal",
    closeButtonId: "closePasswordModal",
    modalId: "passwordModal"
  });
}

function setupPinModal() {
  setupBasicModal({
    openButtonId: "openPinModal",
    closeButtonId: "closePinModal",
    modalId: "pinModal"
  });
}

function setupDeleteModal() {
  const deleteForm = document.getElementById("deleteAccountForm");
  const confirmDelete = document.getElementById("confirmDelete");
  const cancelDeleteModal = document.getElementById("cancelDeleteModal");

  const modalControls = setupBasicModal({
    openButtonId: "openDeleteModal",
    closeButtonId: "closeDeleteModal",
    modalId: "deleteModal"
  });

  if (cancelDeleteModal && modalControls) {
    cancelDeleteModal.addEventListener("click", modalControls.close);
  }

  if (confirmDelete && deleteForm) {
    confirmDelete.addEventListener("click", () => {
      deleteForm.submit();
    });
  }
}

function setupBasicModal({ openButtonId, closeButtonId, modalId }) {
  const openButton = document.getElementById(openButtonId);
  const closeButton = document.getElementById(closeButtonId);
  const modal = document.getElementById(modalId);

  if (!openButton || !closeButton || !modal) return null;

  const open = () => {
    modal.classList.add("show");
    modal.setAttribute("aria-hidden", "false");
    document.body.classList.add("settings-modal-open");
  };

  const close = () => {
    modal.classList.remove("show");
    modal.setAttribute("aria-hidden", "true");

    if (!document.querySelector(".settings-modal-overlay.show")) {
      document.body.classList.remove("settings-modal-open");
    }
  };

  openButton.addEventListener("click", open);
  closeButton.addEventListener("click", close);

  modal.addEventListener("click", (event) => {
    if (event.target === modal) {
      close();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && modal.classList.contains("show")) {
      close();
    }
  });

  return { open, close };
}