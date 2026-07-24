/* =========================================
   SHARED BROWSER PERMISSIONS
   Used by Settings and the activity setup gate.
========================================= */
window.BraveSproutPermissions = (() => {
  const AUDIO_KEY = "bravesprouts_audio_enabled";
  const MICROPHONE_KEY = "bravesprouts_microphone_enabled";

  let sharedAudioContext = null;

  function preferenceEnabled(key) {
    return localStorage.getItem(key) === "true";
  }

  function setPreference(key, enabled) {
    localStorage.setItem(key, enabled ? "true" : "false");
  }

  function microphoneSupported() {
    return Boolean(
      navigator.mediaDevices &&
      typeof navigator.mediaDevices.getUserMedia === "function"
    );
  }

  function microphoneErrorMessage(error) {
    switch (error?.name) {
      case "NotAllowedError":
      case "PermissionDeniedError":
        return "Microphone access was blocked. Allow it in your browser's site settings, then try again.";
      case "NotFoundError":
      case "DevicesNotFoundError":
        return "No microphone was found on this device.";
      case "NotReadableError":
      case "TrackStartError":
        return "Your microphone is being used by another app or browser tab.";
      case "SecurityError":
        return "Your browser blocked microphone access for security reasons.";
      case "AbortError":
        return "The microphone request was interrupted. Please try again.";
      default:
        return "The microphone could not be enabled. Check your browser permissions and try again.";
    }
  }

  async function isAudioUnlocked() {
    if (!preferenceEnabled(AUDIO_KEY)) {
      return false;
    }

    const AudioContextClass =
      window.AudioContext || window.webkitAudioContext;

    if (!AudioContextClass) {
      return true;
    }

    /*
      AudioContext state is page-specific. The saved preference records that
      the user has intentionally enabled sound for BraveSprout. A later user
      gesture in an activity can resume its own context when needed.
    */
    return true;
  }

  async function unlockAudio() {
    const AudioContextClass =
      window.AudioContext || window.webkitAudioContext;

    if (!AudioContextClass) {
      setPreference(AUDIO_KEY, true);
      return { success: true, ready: true };
    }

    try {
      sharedAudioContext =
        sharedAudioContext || new AudioContextClass();

      if (sharedAudioContext.state === "suspended") {
        await sharedAudioContext.resume();
      }

      const source = sharedAudioContext.createBufferSource();
      const gain = sharedAudioContext.createGain();

      gain.gain.value = 0;
      source.buffer = sharedAudioContext.createBuffer(
        1,
        1,
        sharedAudioContext.sampleRate
      );

      source.connect(gain);
      gain.connect(sharedAudioContext.destination);
      source.start(0);

      const success = sharedAudioContext.state === "running";

      if (success) {
        setPreference(AUDIO_KEY, true);
      }

      return {
        success,
        ready: success,
        message: success
          ? ""
          : "Your browser did not allow audio to start."
      };
    } catch (error) {
      console.error("Could not unlock browser audio:", error);
      setPreference(AUDIO_KEY, false);

      return {
        success: false,
        ready: false,
        message: "Audio could not be enabled. Check that this tab is not muted."
      };
    }
  }

  function disableAudio() {
    setPreference(AUDIO_KEY, false);
    return { success: true, ready: false };
  }

  async function getMicrophoneReadiness() {
    if (!preferenceEnabled(MICROPHONE_KEY)) {
      return { ready: false, state: "app-disabled" };
    }

    if (!window.isSecureContext) {
      return { ready: false, state: "insecure-context" };
    }

    if (!microphoneSupported()) {
      return { ready: false, state: "unsupported" };
    }

    try {
      if (
        navigator.permissions &&
        typeof navigator.permissions.query === "function"
      ) {
        const permission = await navigator.permissions.query({
          name: "microphone"
        });

        if (permission.state !== "granted") {
          setPreference(MICROPHONE_KEY, false);
        }

        return {
          ready: permission.state === "granted",
          state: permission.state
        };
      }
    } catch (error) {
      /* Safari does not consistently support microphone permission queries. */
      console.debug("Microphone permission query unavailable:", error);
    }

    return {
      ready: preferenceEnabled(MICROPHONE_KEY),
      state: "saved-preference"
    };
  }

  async function requestMicrophone() {
    if (!window.isSecureContext) {
      return {
        success: false,
        ready: false,
        message: "Microphone access requires HTTPS or localhost."
      };
    }

    if (!microphoneSupported()) {
      return {
        success: false,
        ready: false,
        message: "This browser does not support microphone access."
      };
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        },
        video: false
      });

      /* The activity requests its own stream, so release this test stream. */
      stream.getTracks().forEach((track) => track.stop());
      setPreference(MICROPHONE_KEY, true);

      return { success: true, ready: true };
    } catch (error) {
      console.error("Could not request microphone permission:", error);
      setPreference(MICROPHONE_KEY, false);

      return {
        success: false,
        ready: false,
        errorName: error?.name || "UnknownError",
        message: microphoneErrorMessage(error)
      };
    }
  }

  function disableMicrophone() {
    /* Browsers do not let websites revoke permission programmatically. */
    setPreference(MICROPHONE_KEY, false);
    return { success: true, ready: false };
  }

  return {
    isAudioUnlocked,
    unlockAudio,
    disableAudio,
    getMicrophoneReadiness,
    requestMicrophone,
    disableMicrophone
  };
})();

document.addEventListener("DOMContentLoaded", () => {
  setupSettingsTourMode();
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

  if (!audioToggle || !micToggle) return;

  const permissions = window.BraveSproutPermissions;
  const isTourPermissionStep =
    new URLSearchParams(window.location.search).get("tour") === "7";

  async function refreshPermissionToggles() {
    if (isTourPermissionStep) {
      /* Tour mode is visual only and must not overwrite real preferences. */
      setToggleState(audioToggle, false);
      setToggleState(micToggle, false);
      return;
    }

    const [audioResult, microphoneResult] = await Promise.allSettled([
      permissions.isAudioUnlocked(),
      permissions.getMicrophoneReadiness()
    ]);

    const audioEnabled =
      audioResult.status === "fulfilled" && Boolean(audioResult.value);

    const microphoneEnabled =
      microphoneResult.status === "fulfilled" &&
      Boolean(microphoneResult.value?.ready ?? microphoneResult.value);

    setToggleState(audioToggle, audioEnabled);
    setToggleState(micToggle, microphoneEnabled);
  }

  refreshPermissionToggles();

  audioToggle.addEventListener("click", async () => {
    const currentlyOn = audioToggle.classList.contains("is-on");
    audioToggle.disabled = true;

    try {
      const result = currentlyOn
        ? permissions.disableAudio()
        : await permissions.unlockAudio();

      const enabled = Boolean(result?.ready);
      setToggleState(audioToggle, enabled);
      setPermissionMessage(
        message,
        enabled
          ? "Audio is enabled for this browser."
          : "Audio is turned off for BraveSprout on this browser.",
        enabled ? "success" : "neutral"
      );
    } catch (error) {
      console.error("Audio setting failed:", error);
      setToggleState(audioToggle, false, true);
      setPermissionMessage(
        message,
        "Audio could not be enabled. Click the page and try again.",
        "error"
      );
    } finally {
      audioToggle.disabled = false;
    }
  });

  micToggle.addEventListener("click", async () => {
    const currentlyOn = micToggle.classList.contains("is-on");
    micToggle.disabled = true;

    try {
      if (currentlyOn) {
        permissions.disableMicrophone();
        setToggleState(micToggle, false);
        setPermissionMessage(
          message,
          "Microphone is turned off inside BraveSprout. Browser permission may still remain allowed.",
          "neutral"
        );
        return;
      }

      const result = await permissions.requestMicrophone();

      if (!result?.success || !result?.ready) {
        throw new Error(
          result?.message || "Microphone permission was not granted."
        );
      }

      setToggleState(micToggle, true);
      setPermissionMessage(
        message,
        "Microphone access is enabled for this browser.",
        "success"
      );
    } catch (error) {
      console.error("Microphone setting failed:", error);
      setToggleState(micToggle, false, true);
      setPermissionMessage(
        message,
        error.message || "Microphone access could not be enabled.",
        "error"
      );
    } finally {
      micToggle.disabled = false;
    }
  });
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