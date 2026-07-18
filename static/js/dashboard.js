document.addEventListener("DOMContentLoaded", function () {

  function trackEvent(eventName, parameters = {}) {
    if (typeof window.gtag !== "function") {
      return;
    }

    window.gtag("event", eventName, parameters);
  }

function getActivityIdFromHref(activityHref) {
  try {
    const url = new URL(activityHref, window.location.origin);
    const match = url.pathname.match(/\/activity\/(\d+)/);

    return match ? match[1] : "unknown";
  } catch {
    return "unknown";
  }
}

function getMicrophoneErrorType(error) {
  switch (error?.name) {
    case "NotAllowedError":
    case "PermissionDeniedError":
      return "permission_denied";

    case "NotFoundError":
    case "DevicesNotFoundError":
      return "no_microphone";

    case "NotReadableError":
    case "TrackStartError":
      return "microphone_unavailable";

    case "SecurityError":
      return "security_error";

    case "AbortError":
      return "request_aborted";

    default:
      return "unknown";
  }
}

    // ---------------------
  // ACTIVITY SETUP GATE
  // ---------------------
  const startActivityBtn = document.getElementById("startActivityBtn");
  const activityLaunchLinks =
    document.querySelectorAll(".js-activity-launch");

  const activitySetupModal = document.getElementById("activitySetupModal");
  const activitySetupData = document.getElementById("activitySetupData");

  const childNameSetupItem = document.getElementById("childNameSetupItem");
  const parentPinSetupItem = document.getElementById("parentPinSetupItem");
  const audioSetupItem = document.getElementById("audioSetupItem");
  const microphoneSetupItem = document.getElementById("microphoneSetupItem");

  const activitySetupChildName =
    document.getElementById("activitySetupChildName");

  const activitySetupParentPin =
    document.getElementById("activitySetupParentPin");

  const activitySetupParentPinConfirm =
    document.getElementById("activitySetupParentPinConfirm");

  const enableSetupAudioBtn =
    document.getElementById("enableSetupAudioBtn");

  const enableSetupMicrophoneBtn =
    document.getElementById("enableSetupMicrophoneBtn");

  const saveSetupAndStartBtn =
    document.getElementById("saveSetupAndStartBtn");

  const closeActivitySetupBtn =
    document.getElementById("closeActivitySetupBtn");

  const cancelActivitySetupBtn =
    document.getElementById("cancelActivitySetupBtn");

  const activitySetupMessage =
    document.getElementById("activitySetupMessage");

  const activitySetupSubtitle =
    document.getElementById("activitySetupSubtitle");

  const microphoneSetupError =
    document.getElementById("microphoneSetupError");

  let pendingActivityHref = null;

  let setupState = {
    hasChildName:
      activitySetupData?.dataset.hasChildName === "true",

    hasParentPin:
      activitySetupData?.dataset.hasParentPin === "true",

    audioReady: false,
    microphoneReady: false
  };

  function hasRealChildName(value) {
    const cleaned = String(value || "").trim().toLowerCase();

    return (
      cleaned.length > 0 &&
      cleaned !== "child" &&
      cleaned !== "none" &&
      cleaned !== "null"
    );
  }

  function isValidPin(value) {
    return /^\d{4}$/.test(String(value || ""));
  }

  function setSetupMessage(message, type = "") {
    if (!activitySetupMessage) return;

    activitySetupMessage.textContent = message || "";
    activitySetupMessage.dataset.type = type;
  }

  function setMicrophoneError(message = "") {
    if (!microphoneSetupError) return;

    microphoneSetupError.textContent = message;
    microphoneSetupError.hidden = !message;
  }

  function showSetupItem(element, shouldShow) {
    if (!element) return;
    element.hidden = !shouldShow;
  }

  function setSetupPermissionToggle(
    button,
    { enabled = false, busy = false, denied = false } = {}
  ) {
    if (!button) return;

    const label = button.querySelector(".activity-setup-toggle-label");

    button.disabled = busy;
    button.classList.toggle("is-on", enabled);
    button.classList.toggle("is-denied", denied);
    button.classList.toggle("is-busy", busy);
    button.setAttribute("aria-pressed", enabled ? "true" : "false");

    if (label) {
      label.textContent = busy
        ? "Working…"
        : denied
          ? "Blocked"
          : enabled
            ? "On"
            : "Off";
    }
  }

  function getPermissionsHelper() {
    const permissions = window.BraveSproutPermissions;

    if (!permissions) {
      console.error(
        "browser_permissions.js must load before dashboard.js."
      );
    }

    return permissions || null;
  }

  async function checkAudioReadiness() {
    const permissions = getPermissionsHelper();

    if (!permissions) {
      setupState.audioReady = false;
      return false;
    }

    /*
      Audio cannot always be proven ready before a user gesture.
      If your shared helper has isAudioUnlocked(), use it.
      Otherwise, treat the saved app preference as the initial state.
    */
    if (typeof permissions.isAudioUnlocked === "function") {
      setupState.audioReady =
        Boolean(await permissions.isAudioUnlocked());
    } else {
      setupState.audioReady =
        localStorage.getItem("bravesprouts_audio_enabled") === "true";
    }

    return setupState.audioReady;
  }

  async function checkMicrophoneReadiness() {
    const permissions = getPermissionsHelper();

    if (
      !permissions ||
      typeof permissions.getMicrophoneReadiness !== "function"
    ) {
      setupState.microphoneReady = false;
      return false;
    }

    try {
      const result =
        await permissions.getMicrophoneReadiness();

      /*
        Supports either:
        { ready: true }
        or a direct true/false result.
      */
      setupState.microphoneReady =
        typeof result === "boolean"
          ? result
          : Boolean(result?.ready);

      return setupState.microphoneReady;
    } catch (error) {
      console.error(
        "Could not check microphone readiness:",
        error
      );

      setupState.microphoneReady = false;
      return false;
    }
  }

  function refreshVisibleRequirements() {
    showSetupItem(
      childNameSetupItem,
      !setupState.hasChildName
    );

    showSetupItem(
      parentPinSetupItem,
      !setupState.hasParentPin
    );

    showSetupItem(
      audioSetupItem,
      !setupState.audioReady
    );

    showSetupItem(
      microphoneSetupItem,
      !setupState.microphoneReady
    );

    setSetupPermissionToggle(enableSetupAudioBtn, {
      enabled: setupState.audioReady
    });

    setSetupPermissionToggle(enableSetupMicrophoneBtn, {
      enabled: setupState.microphoneReady
    });

    updateStartButtonState();
  }

  function validateVisibleFields({ showErrors = false } = {}) {
    if (!setupState.hasChildName) {
      const childName =
        activitySetupChildName?.value.trim() || "";

      if (!hasRealChildName(childName)) {
        if (showErrors) {
          setSetupMessage(
            "Please enter your child’s name.",
            "error"
          );

          activitySetupChildName?.focus();
        }

        return false;
      }
    }

    if (!setupState.hasParentPin) {
      const pin =
        activitySetupParentPin?.value || "";

      const confirmation =
        activitySetupParentPinConfirm?.value || "";

      if (!isValidPin(pin)) {
        if (showErrors) {
          setSetupMessage(
            "Please create a four-digit parent PIN.",
            "error"
          );

          activitySetupParentPin?.focus();
        }

        return false;
      }

      if (pin !== confirmation) {
        if (showErrors) {
          setSetupMessage(
            "The two parent PIN entries do not match.",
            "error"
          );

          activitySetupParentPinConfirm?.focus();
        }

        return false;
      }
    }

    return true;
  }

  function updateStartButtonState() {
    if (!saveSetupAndStartBtn) return;

    const fieldsReady =
      validateVisibleFields({ showErrors: false });

    saveSetupAndStartBtn.disabled = !(
      fieldsReady &&
      setupState.audioReady &&
      setupState.microphoneReady
    );
  }

  function allSetupReady() {
    return (
      setupState.hasChildName &&
      setupState.hasParentPin &&
      setupState.audioReady &&
      setupState.microphoneReady
    );
  }

  async function refreshSetupState() {
    const readinessCheck = Promise.allSettled([
      checkAudioReadiness(),
      checkMicrophoneReadiness()
    ]);

    /*
      Browser permission APIs can occasionally remain pending. Do not let a
      pending permission check make the activity button appear unresponsive.
    */
    await Promise.race([
      readinessCheck,
      new Promise((resolve) => setTimeout(resolve, 1200))
    ]);

    refreshVisibleRequirements();
  }

  function openActivitySetup(activityHref, activityName) {
    if (!activitySetupModal) {
      console.error(
        "Activity Setup modal is missing from dashboard.html."
      );
      return;
    }

  pendingActivityHref = activityHref;

  trackEvent("activity_setup_opened", {
    activity_id: getActivityIdFromHref(activityHref),
    activity_name: activityName || "unknown",
    missing_child_name: !setupState.hasChildName,
    missing_parent_pin: !setupState.hasParentPin,
    missing_audio: !setupState.audioReady,
    missing_microphone: !setupState.microphoneReady
  });

  if (activitySetupSubtitle) {
    activitySetupSubtitle.textContent =
      `Complete the steps below before starting ${
        activityName || "this activity"
      }.`;
  }

    setSetupMessage("");
    setMicrophoneError("");

    activitySetupModal.classList.add("active");
    activitySetupModal.setAttribute("aria-hidden", "false");

    /*
      Fail-safe visibility. This keeps the gate usable even if the new modal
      CSS has not yet been deployed or an older stylesheet is cached.
    */
    activitySetupModal.hidden = false;
    activitySetupModal.style.display = "flex";
    activitySetupModal.style.visibility = "visible";
    activitySetupModal.style.opacity = "1";
    activitySetupModal.style.pointerEvents = "auto";

    document.body.classList.add("activity-setup-open");

    const firstVisibleInput =
      !childNameSetupItem?.hidden
        ? activitySetupChildName
        : !parentPinSetupItem?.hidden
          ? activitySetupParentPin
          : null;

    if (firstVisibleInput) {
      setTimeout(() => firstVisibleInput.focus(), 80);
    }
  }

  function closeActivitySetup() {
    if (!activitySetupModal) return;

    activitySetupModal.classList.remove("active");
    activitySetupModal.setAttribute("aria-hidden", "true");
    activitySetupModal.style.display = "";
    activitySetupModal.style.visibility = "";
    activitySetupModal.style.opacity = "";
    activitySetupModal.style.pointerEvents = "";
    document.body.classList.remove("activity-setup-open");

    pendingActivityHref = null;
    setSetupMessage("");
    setMicrophoneError("");
  }

  async function handleActivityLaunch(
    activityHref,
    activityName
  ) {
    pendingActivityHref = activityHref;
    setSetupMessage("");

    /*
      Open immediately when account information is missing. This guarantees a
      visible response to the click without waiting on browser permission APIs.
    */
    if (!setupState.hasChildName || !setupState.hasParentPin) {
      refreshVisibleRequirements();
      openActivitySetup(activityHref, activityName);
      await refreshSetupState();
      return;
    }

    try {
      await refreshSetupState();

      if (allSetupReady()) {
        trackEvent("activity_launch_started", {
          activity_id: getActivityIdFromHref(activityHref),
          activity_name: activityName || "unknown",
          setup_required: false
        });

        window.location.assign(activityHref);
        return;
      }

      openActivitySetup(activityHref, activityName);
    } catch (error) {
      console.error("Activity launch setup check failed:", error);

      /*
        A readiness-check failure should show the setup gate, never leave the
        user with a button that appears to do nothing.
      */
      openActivitySetup(activityHref, activityName);
      setSetupMessage(
        "Please finish the setup steps below before starting.",
        "error"
      );
    }
  }

  activityLaunchLinks.forEach((link) => {
    link.addEventListener("click", async function (event) {
      event.preventDefault();

      const activityHref = this.href;

      if (!activityHref) {
        console.error("Activity launch link is missing its href.");
        return;
      }

      await handleActivityLaunch(
        activityHref,
        this.dataset.activityName || "this activity"
      );
    });
  });

  if (enableSetupAudioBtn) {
    enableSetupAudioBtn.addEventListener("click", async function () {
      const permissions = getPermissionsHelper();

      if (!permissions?.unlockAudio) {
        setSetupMessage(
          "Audio setup is unavailable. Refresh the page and try again.",
          "error"
        );
        return;
      }

      setSetupPermissionToggle(enableSetupAudioBtn, { busy: true });
      setSetupMessage("");

      try {
        const result = await permissions.unlockAudio();

        if (!result?.success || !result?.ready) {
          throw new Error(
            result?.message || "Your browser could not enable audio."
          );
        }

        setupState.audioReady = true;
        setSetupPermissionToggle(enableSetupAudioBtn, { enabled: true });
        updateStartButtonState();

        /* Let the user see the On state, then remove the completed row. */
        window.setTimeout(refreshVisibleRequirements, 350);
      } catch (error) {
        console.error("Audio setup error:", error);
        setupState.audioReady = false;
        setSetupPermissionToggle(enableSetupAudioBtn, { denied: true });
        setSetupMessage(
          error.message || "Audio could not be enabled. Please try again.",
          "error"
        );
        updateStartButtonState();
      }
    });
  }

  if (enableSetupMicrophoneBtn) {
    enableSetupMicrophoneBtn.addEventListener("click", async function () {
      const permissions = getPermissionsHelper();

      if (!permissions?.requestMicrophone) {
        setMicrophoneError(
          "Microphone setup is unavailable. Refresh the page and try again."
        );
        return;
      }

      setSetupPermissionToggle(enableSetupMicrophoneBtn, { busy: true });
      setMicrophoneError("");
      setSetupMessage("");

      try {
        const result = await permissions.requestMicrophone();

        if (!result?.success || !result?.ready) {
          const permissionError = new Error(
            result?.message || "Microphone permission was not granted."
          );
          permissionError.name = result?.errorName || permissionError.name;
          throw permissionError;
        }

        setupState.microphoneReady = true;
        setSetupPermissionToggle(enableSetupMicrophoneBtn, { enabled: true });
        updateStartButtonState();

        /* Let the user see the On state, then remove the completed row. */
        window.setTimeout(refreshVisibleRequirements, 350);
      } catch (error) {
        console.error("Microphone setup error:", error);

        trackEvent("activity_setup_microphone_failed", {
          activity_id: getActivityIdFromHref(
            pendingActivityHref || startActivityBtn?.href || ""
          ),
          error_type: getMicrophoneErrorType(error)
        });

        setupState.microphoneReady = false;
        setSetupPermissionToggle(enableSetupMicrophoneBtn, { denied: true });
        setMicrophoneError(
          error.message ||
          "Please allow microphone access in your browser and try again."
        );
        updateStartButtonState();
      }
    });
  }

  async function saveAccountSetup() {
    const needsChildName =
      !setupState.hasChildName;

    const needsParentPin =
      !setupState.hasParentPin;

    if (!needsChildName && !needsParentPin) {
      return true;
    }

    if (!validateVisibleFields({ showErrors: true })) {
      return false;
    }

    const saveUrl =
      activitySetupData?.dataset.saveUrl ||
      "/save-activity-setup";

    const payload = {};

    if (needsChildName) {
      payload.child_name =
        activitySetupChildName.value.trim();
    }

    if (needsParentPin) {
      payload.parent_pin =
        activitySetupParentPin.value;

      payload.parent_pin_confirm =
        activitySetupParentPinConfirm.value;
    }

    const response = await fetch(saveUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      credentials: "same-origin",
      body: JSON.stringify(payload)
    });

    let data = {};

    try {
      data = await response.json();
    } catch {
      throw new Error(
        "The server returned an invalid response."
      );
    }

    if (!response.ok || !data.success) {
      throw new Error(
        data.error ||
        "Your activity setup could not be saved."
      );
    }

    if (needsChildName) {
      setupState.hasChildName = true;

      if (startActivityBtn) {
        startActivityBtn.dataset.childName =
          data.child_name ||
          payload.child_name;
      }
    }

    if (needsParentPin) {
      setupState.hasParentPin = true;
    }

    return true;
  }

  async function completeActivitySetup() {
    if (!saveSetupAndStartBtn) return;

    const setupCompletedDetails = {
      childNameAdded: !setupState.hasChildName,
      parentPinAdded: !setupState.hasParentPin
    };

    if (!validateVisibleFields({ showErrors: true })) {
      return;
    }

    if (!setupState.audioReady) {
      setSetupMessage(
        "Please enable audio before starting.",
        "error"
      );
      return;
    }

    if (!setupState.microphoneReady) {
      setSetupMessage(
        "Please enable microphone access before starting.",
        "error"
      );
      return;
    }

    const originalText =
      saveSetupAndStartBtn.textContent;

    saveSetupAndStartBtn.disabled = true;
    saveSetupAndStartBtn.textContent = "Saving...";

    setSetupMessage("");

    try {
      const saved = await saveAccountSetup();

      if (!saved) {
        saveSetupAndStartBtn.disabled = false;
        saveSetupAndStartBtn.textContent = originalText;
        return;
      }

      const destination =
        pendingActivityHref ||
        startActivityBtn?.href ||
        "/dashboard";

      trackEvent("activity_setup_completed", {
        activity_id: getActivityIdFromHref(destination),
        child_name_added:
          setupCompletedDetails.childNameAdded,
        parent_pin_added:
          setupCompletedDetails.parentPinAdded,
        audio_ready: setupState.audioReady,
        microphone_ready: setupState.microphoneReady
      });

      trackEvent("activity_launch_started", {
        activity_id: getActivityIdFromHref(destination),
        setup_required: true
      });

      window.location.href = destination;
    } catch (error) {
      console.error(
        "Activity setup save error:",
        error
      );

      setSetupMessage(
        error.message ||
        "Something went wrong. Please try again.",
        "error"
      );

      saveSetupAndStartBtn.disabled = false;
      saveSetupAndStartBtn.textContent = originalText;
    }
  }

  if (saveSetupAndStartBtn) {
    saveSetupAndStartBtn.addEventListener(
      "click",
      completeActivitySetup
    );
  }

  [
    activitySetupChildName,
    activitySetupParentPin,
    activitySetupParentPinConfirm
  ].forEach((input) => {
    if (!input) return;

    input.addEventListener("input", function () {
      setSetupMessage("");
      updateStartButtonState();
    });

    input.addEventListener("keydown", function (event) {
      if (
        event.key === "Enter" &&
        !saveSetupAndStartBtn?.disabled
      ) {
        event.preventDefault();
        completeActivitySetup();
      }
    });
  });

  [
    activitySetupParentPin,
    activitySetupParentPinConfirm
  ].forEach((input) => {
    if (!input) return;

    input.addEventListener("input", function () {
      this.value =
        this.value.replace(/\D/g, "").slice(0, 4);
    });
  });

  if (closeActivitySetupBtn) {
    closeActivitySetupBtn.addEventListener(
      "click",
      closeActivitySetup
    );
  }

  if (cancelActivitySetupBtn) {
    cancelActivitySetupBtn.addEventListener(
      "click",
      closeActivitySetup
    );
  }

  if (activitySetupModal) {
    activitySetupModal.addEventListener(
      "click",
      function (event) {
        if (event.target === activitySetupModal) {
          closeActivitySetup();
        }
      }
    );
  }

  document.addEventListener("keydown", function (event) {
    if (
      event.key === "Escape" &&
      activitySetupModal?.classList.contains("active")
    ) {
      closeActivitySetup();
    }
  });

// ---------------------
// PROFILE DROPDOWN
// ---------------------
const profileDropdown = document.querySelector(".profile-dropdown");
const profileTrigger = document.getElementById("profileTrigger");
const dropdownMenu = document.getElementById("dropdownMenu");

if (profileDropdown && profileTrigger && dropdownMenu) {
  let closeTimer;

  function openDropdown() {
    clearTimeout(closeTimer);
    dropdownMenu.classList.add("active");
    profileDropdown.classList.add("open");
  }

  function closeDropdown() {
    closeTimer = setTimeout(() => {
      dropdownMenu.classList.remove("active");
      profileDropdown.classList.remove("open");
    }, 180);
  }

  profileDropdown.addEventListener("mouseenter", openDropdown);
  profileDropdown.addEventListener("mouseleave", closeDropdown);

  profileTrigger.addEventListener("click", function (event) {
    event.stopPropagation();

    const isOpen = dropdownMenu.classList.contains("active");

    if (isOpen) {
      dropdownMenu.classList.remove("active");
      profileDropdown.classList.remove("open");
    } else {
      openDropdown();
    }
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

    if (confirmUnlockBtn) {
      confirmUnlockBtn.disabled = true;
    }
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

      if (action === "restart") {
  const confirmRestart = confirm(
    "Restart this activity? This will make it behave like the first time opening it."
  );

  if (!confirmRestart) return;

  const activityUrl = this.dataset.activityUrl;

  try {
    this.disabled = true;

    const response = await fetch("/restart-activity", {
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
      window.location.href = activityUrl;
      return;
    }

    console.error(data.error || "Failed to restart activity");
    alert(data.error || "Something went wrong.");
    this.disabled = false;
  } catch (error) {
    console.error("Error restarting activity:", error);
    alert("Something went wrong. Check the console.");
    this.disabled = false;
  }

  return;
}

      if (action === "unlock") {
        pendingUnlockActivityId = activityId;
        pendingUnlockButton = this;

        const activityName = this.dataset.activityName || "this activity";
        const prereqActivityName = this.dataset.prereqActivityName || "the previous activity";
        const prereqCharacter = this.dataset.prereqCharacter || "the previous character";
        const prereqTime = this.dataset.prereqTime || "30";

        if (unlockModalTitle) {
          unlockModalTitle.textContent = `Unlock ${activityName}?`;
        }

        if (characterCheckText) {
          characterCheckText.textContent =
            `Is the child comfortable speaking to ${prereqCharacter}?`;
        }

        if (activityCheckText) {
          activityCheckText.textContent =
          `Can the child comfortably complete ${prereqActivityName}?`;
        }

        if (timeCheckText) {
          timeCheckText.textContent =
            `Has the child spent at least ${prereqTime} minutes on ${prereqActivityName}?`;
        }

        resetUnlockModal();

        if (unlockModal) {
          unlockModal.classList.add("active");
        }

        return;
      }

      console.error("Unknown action:", action);
    });
  });

  unlockChecks.forEach((check) => {
    check.addEventListener("change", function () {
      if (confirmUnlockBtn) {
        confirmUnlockBtn.disabled = !allUnlockChecksComplete();
      }
    });
  });

  if (cancelUnlockBtn && unlockModal) {
    cancelUnlockBtn.addEventListener("click", function () {
      unlockModal.classList.remove("active");
      pendingUnlockActivityId = null;
      pendingUnlockButton = null;
    });
  }

  if (confirmUnlockBtn && unlockModal) {
    confirmUnlockBtn.addEventListener("click", async function () {
      if (!pendingUnlockActivityId) return;

      unlockModal.classList.remove("active");

      await sendActivityAction(
        "/unlock-activity",
        pendingUnlockActivityId,
        pendingUnlockButton
      );
    });
  }

  // ---------------------
  // JOURNEY COLORS / CONNECTOR LINES
  // ---------------------
  function isLockedItem(item) {
    return item && item.classList.contains("journey-locked");
  }

  function readJourneyColorFromElement(element) {
    if (!element) return "";

    const computed = getComputedStyle(element);

    const color =
      element.dataset.color ||
      element.dataset.journeyColor ||
      computed.getPropertyValue("--journey-color").trim() ||
      computed.getPropertyValue("--activity-color").trim() ||
      computed.getPropertyValue("--node-color").trim() ||
      computed.backgroundColor;

    if (!color || color === "transparent" || color === "rgba(0, 0, 0, 0)") {
      return "";
    }

    return color;
  }

  function getJourneyColor(item, node) {
    if (isLockedItem(item)) {
      return "#d8d8e0";
    }

    return (
      readJourneyColorFromElement(item) ||
      readJourneyColorFromElement(node) ||
      "#8b5cf6"
    );
  }

  // ---------------------
// CURRENT ACTIVITY INSTRUCTIONS MODAL
// ---------------------
const instructionsByActivityId = {
    "1": `
  <h3>Purpose</h3>

  <p>
    Match Cards is designed to help your child become comfortable interacting
    with Star while playing a simple, familiar matching game.
  </p>

  <p>
    The activity begins as a traditional matching game between the child and
    parent. Over time, Star gradually becomes more involved, first by watching
    and commenting, then by gently including the child, and eventually by asking
    simple questions.
  </p>

  <p>
    There are <strong>12 official rounds</strong> in Match Cards. Your family
    does not need to complete all 12 rounds in one sitting. Some families may
    play a few rounds at a time, such as 3 rounds per day, while others may move
    more quickly or slowly. It is entirely up to you and your child.
  </p>

  <p>
    If your child ever seems uncomfortable, or if Star begins asking questions
    before your child feels ready, you can restart the activity from the
    dashboard. Restarting gives your child more time to become comfortable with
    Star's voice, presence, timing, and questions.
  </p>

  <p>
    The goal is for your child to feel comfortable responding to Star during
    Match Cards before moving on to the next game.
  </p>

  <h3>How to Play</h3>

  <ol>
    <li>Sit with your child and start the activity together.</li>
    <li>Take turns flipping over two cards at a time.</li>
    <li>Try to find matching pairs.</li>
    <li>Continue until all pairs have been found.</li>
    <li>As you play, Star will occasionally comment on the game or join the conversation.</li>
  </ol>

  <h3>Your Role</h3>

  <p>
    The most important thing is to keep the activity relaxed and enjoyable.
  </p>

  <p>
    When Star speaks, give your child a moment to respond on their own. Avoid
    repeating the same question multiple times or pressuring your child to
    answer.
  </p>

  <p>
    If a question is directed to both of you, or is phrased generally, you can
    casually involve your child by saying:
  </p>

  <ul>
    <li>"What do you think?"</li>
    <li>"Which one should we look for next?"</li>
    <li>"Hmm, what card do you think Star means?"</li>
  </ul>

  <p>
    If your child does not respond, simply continue playing. The goal is not to
    get your child to answer every question right away. The goal is to make
    conversations that include Star feel increasingly familiar and comfortable.
  </p>

  <h3>What to Expect During Each Round</h3>

  <h4>Rounds 1-3: Star Watches and Comments</h4>

  <p>
    During the first few rounds, Star acts like a friendly observer. Star may
    comment when matches are found, notice what is happening, or encourage the
    parent and child as a team.
  </p>

  <p>
    Star is not trying to get your child to answer questions yet. This stage
    helps your child get used to Star's voice, timing, and presence while
    focusing mainly on the matching game.
  </p>

  <p>
    <strong>Parent role:</strong> Simply play the game. There is no need to
    encourage responses to Star yet.
  </p>

  <h4>Rounds 4-6: Star Begins Including the Child</h4>

  <p>
    In these rounds, Star starts making comments that include your child more
    directly, but these are still gentle and do not require a response.
  </p>

  <p>
    These comments help your child become more comfortable being included in a
    conversation while Star is present.
  </p>

  <p>
    <strong>Parent role:</strong> You may casually respond or involve your child
    with simple comments such as "What do you think?" or "Hmm, I wonder too."
    Do not push for an answer. If your child does not respond, simply keep
    playing.
  </p>

  <h4>Rounds 7-9: Star Asks for Help</h4>

  <p>
    In these rounds, Star begins asking simple questions connected to the cards.
  </p>

  <p>
    This is the first stage where Star creates more direct opportunities for
    communication. The questions are simple and concrete because they are tied
    to what your child can already see on the screen.
  </p>

  <p>
    <strong>Parent role:</strong> Pause briefly after Star asks a question and
    give your child an opportunity to respond. If appropriate, casually involve
    your child by asking "What do you think?" or "Can you help Star?"
  </p>

  <p>
    Avoid making a big deal out of responses. Treat communication with Star as
    a normal part of the game.
  </p>

  <h4>Rounds 10-12: Star Asks Direct Questions</h4>

  <p>
    In these rounds, Star asks clearer and more direct questions.
  </p>

  <p>
    At this point, Star becomes a more active participant in the conversation
    rather than simply commenting on the game.
  </p>

  <p>
    <strong>Parent role:</strong> Allow your child the first opportunity to
    respond. Stay present and supportive without taking over the interaction.
    If needed, use a simple prompt such as "What do you think?"
  </p>

  <p>
    The goal is for Star and your child to begin interacting more naturally with
    one another.
  </p>

  <h4>Rounds 13 and Beyond: Optional Continued Practice</h4>

  <p>
    After round 12, the official round progression is complete.
  </p>

  <p>
    If your child wants to keep playing, they can continue. Star will interact
    in a similar style to rounds 10-12, with simple, direct questions and
    natural responses.
  </p>

  <p>
    These extra rounds are optional and simply provide more practice if your
    child is enjoying the activity.
  </p>

  <h4>If Your Child Does Not Respond</h4>

  <p>
    If your child does not answer, simply continue playing.
  </p>

  <p>
    Star is designed to keep the activity moving without making silence feel
    like a failure. More opportunities for communication will naturally come up
    as your child continues playing.
  </p>

  <p>
    Match Cards can be played or restarted until your child feels comfortable
    answering Star. Some children may feel comfortable after one session, while
    others may need to repeat the activity several times.
  </p>

  <p>
    The goal is not perfect participation in one session. The goal is for
    communication with Star to feel familiar, relaxed, and comfortable enough
    that your child is ready for the next activity.
  </p>
`,
    "2": `
  <h3>Purpose</h3>

  <p>
    Mystery Animal is designed to help your child become comfortable giving
    increasingly longer and less direct answers while talking with Star.
  </p>

  <p>
    Your child thinks of an animal, and Star asks questions to figure it out.
    As the activity progresses, Star gradually asks questions that require more
    information, moving from simple one-word responses to more descriptive and
    open-ended answers.
  </p>

  <p>
    There are <strong>9 official rounds</strong> in Mystery Animal. Your child
    does not need to complete all 9 rounds in one sitting. Some children may
    complete a few rounds at a time before taking a break, while others may
    continue for longer. The activity is designed to progress at whatever pace
    feels comfortable for your child.
  </p>

  <p>
    If your child ever seems uncomfortable, or if the questions become more
    difficult before they feel ready, you can restart the activity from the
    dashboard. Restarting gives your child more time practicing the earlier
    rounds before moving on.
  </p>

  <p>
    The goal is for your child to become comfortable giving increasingly longer
    and more descriptive answers before moving on to the next activity.
  </p>

  <h3>How to Play</h3>

  <ol>
    <li>Start the video call with Star.</li>
    <li>Have your child think of an animal silently in their head.</li>
    <li>Star asks questions about the animal.</li>
    <li>Your child answers Star out loud.</li>
    <li>Star uses the answers to guess the animal.</li>
    <li>After Star guesses correctly, your child can think of a new animal for the next round.</li>
  </ol>

  <h3>Your Role</h3>

  <p>
    In this activity, Star is your child's primary conversation partner. Unlike
    Match Cards, you do not need to actively participate in the game.
  </p>

  <p>
    Instead, stay nearby while your child plays so you can make sure they feel
    comfortable and supported. Whenever possible, allow the conversation to
    happen directly between your child and Star.
  </p>

  <p>
    If your child seems unsure, you can gently encourage them with simple prompts
    such as:
  </p>

  <ul>
    <li>"What do you think?"</li>
    <li>"Can you tell Star?"</li>
    <li>"Take your time."</li>
  </ul>

  <p>
    Try not to answer for your child or guide the conversation yourself. If your
    child does not respond, simply allow the activity to continue. The goal is to
    help speaking with Star feel natural and comfortable.
  </p>

  <h3>What to Expect During Each Round</h3>

  <h4>Rounds 1-3: Simple Answers</h4>

  <p>
    During the first few rounds, Star asks straightforward questions that can
    usually be answered with a single word or by choosing between two options.
  </p>

  <p>
    Questions might include whether the animal is big or small, whether it lives
    on land or in water, or whether it is a pet or a wild animal.
  </p>

  <p>
    <strong>Parent role:</strong> Stay nearby and allow your child time to
    answer independently. There is no need to help unless they seem
    uncomfortable.
  </p>

  <h4>Rounds 4-6: Descriptive Answers</h4>

  <p>
    In these rounds, Star begins asking follow-up questions that encourage your
    child to give a little more information rather than just a one-word answer.
  </p>

  <p>
    For example, Star might ask about the animal's color, appearance, habitat,
    or another simple detail.
  </p>

  <p>
    <strong>Parent role:</strong> Continue allowing your child to answer first.
    If needed, offer a gentle prompt such as "What do you think?" but avoid
    answering for them.
  </p>

  <h4>Rounds 7-9: Giving Hints</h4>

  <p>
    During the final rounds, Star occasionally asks more open-ended questions,
    such as asking your child to give a hint or share something important about
    their animal.
  </p>

  <p>
    Rather than simply answering a question, your child now decides what
    information would be most helpful for Star.
  </p>

  <p>
    <strong>Parent role:</strong> Stay nearby, but continue letting the
    conversation happen directly between your child and Star whenever possible.
  </p>

  <h4>Rounds 10 and Beyond: Optional Continued Practice</h4>

  <p>
    After round 9, the official round progression is complete.
  </p>

  <p>
    If your child wants to keep playing, they can continue. Star will continue
    asking questions in a similar style, providing additional opportunities to
    practice giving longer, descriptive answers.
  </p>

  <h4>If Your Child Does Not Respond</h4>

  <p>
    If your child does not answer, simply continue playing.
  </p>

  <p>
    Star is designed to keep the conversation moving without making silence feel
    like a failure. More opportunities to communicate will naturally come up as
    your child continues playing.
  </p>

  <p>
    Mystery Animal can be played or restarted until your child feels comfortable
    giving longer, more descriptive answers. Some children may be ready after one
    session, while others may benefit from repeating the activity several times.
  </p>

  <p>
    The goal is not perfect participation in one session. The goal is for your
    child to feel comfortable speaking directly with Star using increasingly
    detailed responses before moving on to the next activity.
  </p>
`,
    "3": `
  <h3>Purpose</h3>

  <p>
    Guessing Game helps your child practice asking questions and leading a
    conversation with Star.
  </p>

  <p>
    In Mystery Animal, Star asked the questions. In this activity, your child
    switches roles: Star thinks of an animal, and your child asks questions to
    figure out what it is.
  </p>

  <p>
    The goal is for your child to become more comfortable initiating
    conversation, deciding what to ask next, and using clues to make a guess.
  </p>

  <h3>How to Play</h3>

  <ol>
    <li>Star thinks of an animal.</li>
    <li>Your child asks Star questions.</li>
    <li>Star answers with clues.</li>
    <li>Your child uses the clues to figure out the animal.</li>
    <li>When ready, your child makes a guess.</li>
  </ol>

  <h3>Your Role</h3>

  <p>
    In this activity, your child is encouraged to lead the conversation. You do
    not need to actively participate.
  </p>

  <p>
    Stay nearby so your child feels supported, but allow the conversation to
    happen directly between your child and Star whenever possible.
  </p>

  <p>
    If your child gets stuck, you can gently remind them that they can ask about
    what the animal looks like, where it lives, what it eats, or whether it can
    fly, swim, or run.
  </p>

  <p>
    If your child is unsure what to ask, they can also ask Star for a hint.
  </p>

  <h3>What to Expect During the Rounds</h3>

  <h4>Rounds 1-2: Learning How to Ask</h4>

  <p>
    During the first rounds, Star gives more guidance and may suggest possible
    questions your child can ask.
  </p>

  <p>
    This helps your child learn the format of the game and become comfortable
    asking Star questions directly.
  </p>

  <h4>Rounds 3-4: Choosing Questions</h4>

  <p>
    In these rounds, Star gives less direct help. Your child is encouraged to
    think about what information would help them figure out the animal.
  </p>

  <p>
    The goal is for your child to begin choosing their own questions while still
    receiving support when needed.
  </p>

  <h4>Rounds 5-6: Leading the Conversation</h4>

  <p>
    During the final official rounds, your child is encouraged to decide what
    questions to ask, what clues are important, and when they are ready to make
    a guess.
  </p>

  <p>
    Star may still provide hints when asked, but your child is now leading most
    of the conversation.
  </p>

  <h4>Rounds 7 and Beyond: Optional Continued Practice</h4>

  <p>
    After round 6, the official round progression is complete.
  </p>

  <p>
    If your child wants to keep playing, they can continue. Star will keep
    playing in a similar style, giving your child more practice asking
    questions and guiding the conversation.
  </p>

  <h4>If Your Child Gets Stuck</h4>

  <p>
    If your child is unsure what to ask, encourage them to think about what
    information would help them learn more about the animal.
  </p>

  <p>
    They can also ask Star for a hint at any time.
  </p>

  <p>
    Guessing Game can be played or restarted until your child feels comfortable
    asking Star questions and leading the interaction.
  </p>

  <p>
    The goal is not to ask perfect questions. The goal is to practice starting
    and guiding a conversation with Star before moving on to the next activity.
  </p>
`,
  "4": `
<h3>Purpose</h3>

<p>
  Drawing Game helps your child practice speaking naturally while working on a
  creative activity with Star and the Teacher.
</p>

<p>
  At this point, your child should already be comfortable talking with Star.
  This activity introduces the Teacher while Star remains nearby as a familiar
  and supportive presence.
</p>

<p>
  This activity can be completed over multiple sessions. Your child does not
  need to finish every drawing scene in one sitting. They can stop and continue
  later whenever they feel ready.
</p>

<p>
  If your child ever seems uncomfortable, you can restart the activity from the
  dashboard to practice again. The goal is for your child to become comfortable
  speaking naturally with both Star and the Teacher before moving on.
</p>

<h3>How to Play</h3>

<ol>
  <li>Start the video call.</li>
  <li>Your child will complete four simple drawing scenes.</li>
  <li>Each scene is broken into four small drawing steps.</li>
  <li>Star and the Teacher will guide your child through each step.</li>
  <li>Your child can draw using any of the available colors and drawing tools.</li>
  <li>When a drawing step is finished, your child can say they are done or press the Done button.</li>
</ol>

<h4>The Drawing Scenes</h4>

<p>
  The activity includes four different drawing scenes:
</p>

<ul>
  <li><strong>Flower Garden:</strong> Draw a flower, grass, the sun, and a butterfly.</li>
  <li><strong>House:</strong> Draw a house, a yard, the sun, and a tree.</li>
  <li><strong>Farm:</strong> Draw a barn, grass, a cow, and a pig.</li>
  <li><strong>School:</strong> Draw a school, grass, the sun, and children outside.</li>
</ul>

<p>
  Each scene is completed one drawing step at a time. As your child draws, Star
  and the Teacher may comment on the picture, ask simple questions, or invite
  your child to make small choices about what they are drawing.
</p>

<h3>Your Role</h3>

<p>
  By this point, your child should be able to complete the activity mostly
  independently. You do not need to actively participate unless your child
  needs support.
</p>

<p>
  If your child seems unsure or uncomfortable, simply stay nearby and offer
  reassurance if needed. Whenever possible, allow the conversation to happen
  naturally between your child, Star, and the Teacher.
</p>

<p>
  The goal is not to create a perfect drawing. The goal is to help your child
  feel comfortable communicating while completing a fun, creative activity.
</p>

<h3>What to Expect</h3>

<h4>How Conversations Change</h4>

<p>
  As your child progresses through the activity, the conversations gradually
  become more natural. Early on, Star leads most of the interaction while the
  Teacher mainly observes or comments on the drawing.
</p>

<p>
  Later, the Teacher becomes more involved by asking simple questions and
  joining the conversation, while Star continues providing familiar support.
</p>

<p>
  By the final drawing scene, your child is encouraged to comfortably respond
  to both Star and the Teacher while continuing to enjoy the activity.
</p>

<h4>If Your Child Does Not Respond</h4>

<p>
  If your child does not answer, the activity can still continue.
</p>

<p>
  Star and the Teacher are designed to keep the experience calm and relaxed.
  Silence should not feel like a failure, and additional opportunities to
  communicate will naturally occur throughout the activity.
</p>

<p>
  Drawing Game can be played or restarted until your child feels comfortable
  speaking naturally with both Star and the Teacher before moving on to the
  next activity.
</p>
`,
   "5": `
  <h3>Purpose</h3>

  <p>
    Mystery Classroom Object helps your child continue practicing longer, more
    descriptive answers in a new setting.
  </p>

  <p>
    This activity works like Mystery Animal, but the object is something that
    might be found in a classroom or school. The Teacher asks questions, and
    your child gives clues to help the Teacher figure it out.
  </p>

  <p>
    The goal is for your child to become comfortable expanding their answers
    with a less familiar conversation partner and in a more school-like context.
  </p>

  <h3>How to Play</h3>

  <ol>
    <li>Start the video call with the Teacher.</li>
    <li>Have your child think of a classroom or school object silently in their head.</li>
    <li>The Teacher asks questions about the object.</li>
    <li>Your child answers out loud and gives clues.</li>
    <li>The Teacher uses the answers to guess the object.</li>
    <li>After the object is guessed correctly, your child can think of a new object for the next round.</li>
  </ol>

  <h3>Your Role</h3>

  <p>
    By this point, your child should be able to complete the activity mostly
    independently. You do not need to actively participate unless your child
    needs support.
  </p>

  <p>
    If your child seems unsure or uncomfortable, you can stay nearby and offer
    gentle reassurance. Whenever possible, allow the conversation to happen
    directly between your child and the Teacher.
  </p>

  <p>
    Try not to answer for your child. The goal is for your child to practice
    giving clues and descriptive answers on their own.
  </p>

  <h3>What to Expect During the Rounds</h3>

  <h4>Rounds 1-3: Simple Answers</h4>

  <p>
    During the first few rounds, the Teacher asks straightforward questions that
    can usually be answered with a single word or by choosing between options.
  </p>

  <p>
    Questions might include whether the object is big or small, what color it
    is, where it is usually found, or what it is used for.
  </p>

  <h4>Rounds 4-6: Descriptive Answers</h4>

  <p>
    In these rounds, the Teacher begins asking follow-up questions that
    encourage your child to give a little more information.
  </p>

  <p>
    For example, the Teacher might ask what the object looks like, who uses it,
    where it belongs, or why someone might need it.
  </p>

  <h4>Rounds 7-9: Giving Hints</h4>

  <p>
    During the final rounds, the Teacher may ask more open-ended questions, such
    as asking your child to give a hint or share something important about the
    object.
  </p>

  <p>
    This helps your child practice deciding what information would be useful for
    someone else to know.
  </p>

  <h4>Rounds 10 and Beyond: Optional Continued Practice</h4>

  <p>
    After round 9, the official round progression is complete. If your child
    wants to keep playing, they can continue for more practice.
  </p>

  <h4>If Your Child Does Not Respond</h4>

  <p>
    If your child does not answer, the activity can still continue.
  </p>

  <p>
    The Teacher is designed to keep the conversation calm and relaxed. Silence
    should not feel like a failure, and more opportunities to communicate will
    naturally come up as your child continues playing.
  </p>

  <p>
    Mystery Classroom Object can be played or restarted until your child feels
    comfortable giving longer, more descriptive answers to the Teacher before
    moving on to the next activity.
  </p>
`,
  "6": `
<h3>Purpose</h3>

<p>
  Classroom Guessing Game helps your child practice asking questions and
  leading a conversation with the Teacher.
</p>

<p>
  This activity works like Guessing Game, but instead of talking with Star,
  your child asks questions to the Teacher. The goal is to help your child
  become comfortable leading conversations with someone new in a school-like
  setting.
</p>

<p>
  The goal is for your child to become more comfortable initiating
  conversations, deciding what to ask next, and using clues to make a guess.
</p>

<h3>How to Play</h3>

<ol>
  <li>The Teacher thinks of a classroom or school object.</li>
  <li>Your child asks the Teacher questions.</li>
  <li>The Teacher answers with clues.</li>
  <li>Your child uses the clues to figure out the object.</li>
  <li>When ready, your child makes a guess.</li>
</ol>

<h3>Your Role</h3>

<p>
  By this point, your child should be able to complete the activity
  independently. You do not need to actively participate unless your child
  needs support.
</p>

<p>
  If your child gets stuck, you can gently remind them to think about questions
  they could ask, but try to let the conversation happen directly between your
  child and the Teacher whenever possible.
</p>

<p>
  The goal is for your child to confidently lead the conversation on their own.
</p>

<h3>What to Expect During the Rounds</h3>

<h4>Rounds 1-2: Learning How to Ask</h4>

<p>
  During the first rounds, the Teacher provides more guidance and may suggest
  possible questions your child can ask.
</p>

<p>
  This helps your child become comfortable asking questions in a new setting.
</p>

<h4>Rounds 3-4: Choosing Questions</h4>

<p>
  In these rounds, the Teacher gives less direct help. Your child is encouraged
  to think about what information would be most helpful for identifying the
  object.
</p>

<p>
  The goal is for your child to begin choosing their own questions while still
  receiving support when needed.
</p>

<h4>Rounds 5-6: Leading the Conversation</h4>

<p>
  During the final official rounds, your child decides what questions to ask,
  what clues are important, and when they are ready to make a guess.
</p>

<p>
  The Teacher may still provide hints when asked, but your child is now leading
  most of the conversation.
</p>

<h4>Rounds 7 and Beyond: Optional Continued Practice</h4>

<p>
  After round 6, the official round progression is complete.
</p>

<p>
  If your child wants to keep playing, they can continue. The Teacher will keep
  playing in a similar style, giving your child more opportunities to practice
  asking questions and leading conversations.
</p>

<h4>If Your Child Gets Stuck</h4>

<p>
  If your child is unsure what to ask, encourage them to think about what
  information would help them learn more about the object.
</p>

<p>
  They can also ask the Teacher for a hint at any time.
</p>

<p>
  Classroom Guessing Game can be played or restarted until your child feels
  comfortable asking questions, leading the conversation, and interacting
  confidently with the Teacher before moving on to the next activity.
</p>
`,
"7": `
<h3>Purpose</h3>

<p>
  Restaurant Worker Game helps your child become comfortable talking with a new
  conversation partner in a restaurant setting.
</p>

<p>
  During this activity, the Teacher remains nearby while gradually introducing
  the Restaurant Worker into the conversation. As your child becomes more
  comfortable, the Restaurant Worker takes a more active role while the Teacher
  slowly steps into the background.
</p>

<p>
  This activity can be completed over multiple sessions. Your child does not
  need to finish every restaurant order in one sitting. They can stop and
  continue later whenever they feel ready.
</p>

<p>
  If your child ever seems uncomfortable, you can restart the activity from the
  dashboard to practice again. The goal is for your child to become comfortable
  speaking naturally with the Restaurant Worker before moving on.
</p>

<h3>How to Play</h3>

<ol>
  <li>Start the restaurant activity.</li>
  <li>Your child will help prepare a variety of food and drink orders.</li>
  <li>Each order is broken into small, simple steps.</li>
  <li>The Teacher and Restaurant Worker will guide your child through each step.</li>
  <li>Your child completes each step using the items on the screen.</li>
  <li>When a step is finished, your child can say they are done or press the Done button.</li>
</ol>

<h4>The Restaurant Orders</h4>

<p>
  The activity includes several restaurant orders, including pizzas, a salad,
  grilled cheese, lemonade, an ice cream sundae, and a kids meal.
</p>

<p>
  As your child prepares each order, they will make simple choices, respond to
  questions, and follow directions from the Teacher and the Restaurant Worker.
</p>

<h3>Your Role</h3>

<p>
  By this point, your child should be able to complete the activity mostly
  independently. You do not need to actively participate unless your child
  needs support.
</p>

<p>
  If your child seems unsure or uncomfortable, you can stay nearby and offer
  reassurance if needed. Whenever possible, allow the conversation to happen
  naturally between your child, the Teacher, and the Restaurant Worker.
</p>

<p>
  The goal is not to prepare each order perfectly. The goal is for your child
  to feel comfortable communicating with a new person in a fun, real-world
  activity.
</p>

<h3>What to Expect</h3>

<h4>How Conversations Change</h4>

<p>
  Early in the activity, the Teacher leads most of the conversation while the
  Restaurant Worker mainly observes or makes occasional comments.
</p>

<p>
  As your child continues, the Restaurant Worker gradually becomes more
  involved, asking questions, giving directions, and interacting more directly
  with your child while the Teacher provides less support.
</p>

<p>
  By the final restaurant orders, your child is encouraged to comfortably
  respond to the Restaurant Worker with minimal support from the Teacher.
</p>

<h4>If Your Child Does Not Respond</h4>

<p>
  If your child does not answer, the activity can still continue.
</p>

<p>
  The Teacher and Restaurant Worker are designed to keep the experience calm
  and relaxed. Silence should not feel like a failure, and additional
  opportunities to communicate will naturally occur throughout the activity.
</p>

<p>
  Restaurant Worker Game can be played or restarted until your child feels
  comfortable communicating naturally with the Restaurant Worker before moving
  on to the next activity.
</p>
`,
"8": `
<h3>Purpose</h3>

<p>
  Mystery Food Item helps your child continue practicing longer, more
  descriptive answers in a restaurant setting.
</p>

<p>
  This activity works like Mystery Animal, but the object is a food item that
  might be found at a restaurant. The Restaurant Worker asks questions, and
  your child gives clues to help them figure it out.
</p>

<p>
  The goal is for your child to become comfortable expanding their answers with
  a less familiar conversation partner in a real-world setting.
</p>

<h3>How to Play</h3>

<ol>
  <li>Start the video call with the Restaurant Worker.</li>
  <li>Have your child think of a food item silently in their head.</li>
  <li>The Restaurant Worker asks questions about the food.</li>
  <li>Your child answers out loud and gives clues.</li>
  <li>The Restaurant Worker uses the answers to guess the food item.</li>
  <li>After the food item is guessed correctly, your child can think of a new one for the next round.</li>
</ol>

<h3>Your Role</h3>

<p>
  By this point, your child should be able to complete the activity mostly
  independently. You do not need to actively participate unless your child
  needs support.
</p>

<p>
  If your child seems unsure or uncomfortable, you can stay nearby and offer
  gentle reassurance. Whenever possible, allow the conversation to happen
  directly between your child and the Restaurant Worker.
</p>

<p>
  Try not to answer for your child. The goal is for your child to practice
  giving clues and descriptive answers on their own.
</p>

<h3>What to Expect During the Rounds</h3>

<h4>Rounds 1-3: Simple Answers</h4>

<p>
  During the first few rounds, the Restaurant Worker asks straightforward
  questions that can usually be answered with a single word or by choosing
  between options.
</p>

<p>
  Questions might include whether the food is sweet or savory, hot or cold,
  or whether it is usually eaten for a meal, dessert, or snack.
</p>

<h4>Rounds 4-6: Descriptive Answers</h4>

<p>
  In these rounds, the Restaurant Worker begins asking follow-up questions that
  encourage your child to give a little more information.
</p>

<p>
  For example, they might ask what the food looks like, what it tastes like,
  what ingredients it has, or when people usually eat it.
</p>

<h4>Rounds 7-9: Giving Hints</h4>

<p>
  During the final rounds, the Restaurant Worker may ask more open-ended
  questions, such as asking your child to give a hint or share something
  important about the food item.
</p>

<p>
  This helps your child practice deciding what information would be useful for
  someone else to know.
</p>

<h4>Rounds 10 and Beyond: Optional Continued Practice</h4>

<p>
  After round 9, the official round progression is complete. If your child
  wants to keep playing, they can continue for more practice.
</p>

<h4>If Your Child Does Not Respond</h4>

<p>
  If your child does not answer, the activity can still continue.
</p>

<p>
  The Restaurant Worker is designed to keep the conversation calm and relaxed.
  Silence should not feel like a failure, and more opportunities to communicate
  will naturally come up as your child continues playing.
</p>

<p>
  Mystery Food Item can be played or restarted until your child feels
  comfortable giving longer, more descriptive answers to the Restaurant Worker
  before moving on to the next activity.
</p>
`,
"9": `
  <h3>Instructions Coming Soon</h3>

  <p>
    This activity is currently in active development.
  </p>

  <p>
    We are continuing to refine the activity experience and will provide
    detailed instructions, parent guidance, and activity goals once development
    is complete.
  </p>
`,
};

const viewInstructionsBtn = document.getElementById("viewInstructionsBtn");
const instructionsModal = document.getElementById("instructionsModal");
const closeInstructionsBtn = document.getElementById("closeInstructionsBtn");
const instructionsTitle = document.getElementById("instructionsTitle");
const instructionsContent = document.getElementById("instructionsContent");

if (viewInstructionsBtn && instructionsModal && instructionsTitle && instructionsContent) {
  viewInstructionsBtn.addEventListener("click", function () {
    const activityId = this.dataset.activityId;
    const activityName = this.dataset.activityName || "Activity";

    instructionsTitle.textContent = `${activityName} Instructions`;
    const therapistNote = `
  <div class="activity-instructions-note">
    <strong>Important:</strong> These activities are intended for practice and are not a replacement for professional evaluation or treatment.
  </div>
`;

instructionsContent.innerHTML =
  therapistNote +
  (instructionsByActivityId[activityId] ||
    "<p>Follow the on-screen prompts and support your child through the activity.</p>");

    instructionsModal.classList.add("active");
  });
}

if (closeInstructionsBtn && instructionsModal) {
  closeInstructionsBtn.addEventListener("click", function () {
    instructionsModal.classList.remove("active");
  });
}

if (instructionsModal) {
  instructionsModal.addEventListener("click", function (event) {
    if (event.target === instructionsModal) {
      instructionsModal.classList.remove("active");
    }
  });
}

document.addEventListener("keydown", function (event) {
  if (event.key === "Escape" && instructionsModal) {
    instructionsModal.classList.remove("active");
  }
});

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

    svg.innerHTML = `<defs id="journeyGradientDefs"></defs>`;

    const defs = svg.querySelector("#journeyGradientDefs");

    for (let i = 0; i < nodes.length - 1; i++) {
      const currentItem = items[i];
      const nextItem = items[i + 1];

      const currentNode = nodes[i];
      const nextNode = nodes[i + 1];

      const currentRect = currentNode.getBoundingClientRect();
      const nextRect = nextNode.getBoundingClientRect();

      const startX = currentRect.left + currentRect.width / 2 - containerRect.left;
      const startY = currentRect.bottom - containerRect.top;

      const endX = nextRect.left + nextRect.width / 2 - containerRect.left;
      const endY = nextRect.top - containerRect.top + 7;

      const midY = (startY + endY) / 2;

      const fromColor = getJourneyColor(currentItem, currentNode);
      const toColor = getJourneyColor(nextItem, nextNode);

      const gradientId = `journey-gradient-${i}`;

      const gradient = document.createElementNS("http://www.w3.org/2000/svg", "linearGradient");
      gradient.setAttribute("id", gradientId);
      gradient.setAttribute("x1", startX);
      gradient.setAttribute("y1", startY);
      gradient.setAttribute("x2", endX);
      gradient.setAttribute("y2", endY);
      gradient.setAttribute("gradientUnits", "userSpaceOnUse");

      gradient.innerHTML = `
        <stop offset="0%" stop-color="${fromColor}" />
        <stop offset="100%" stop-color="${toColor}" />
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
// ---------------------
// FEEDBACK SURVEY
// ---------------------
const feedbackSystem = document.getElementById("feedbackSystem");

if (feedbackSystem) {
  const shouldShowFeedback =
    feedbackSystem.dataset.showFeedback === "1";

  const feedbackOverlay =
    document.getElementById("feedbackOverlay");
  const feedbackIntroPanel =
    document.getElementById("feedbackIntroPanel");
  const feedbackFormPanel =
    document.getElementById("feedbackFormPanel");

  const closeFeedbackBtn =
    document.getElementById("closeFeedbackBtn");
  const closeFeedbackFormBtn =
    document.getElementById("closeFeedbackFormBtn");

  const feedbackYesBtn =
    document.getElementById("feedbackYesBtn");
  const feedbackLaterBtn =
    document.getElementById("feedbackLaterBtn");
  const feedbackFormLaterBtn =
    document.getElementById("feedbackFormLaterBtn");
  const feedbackBackBtn =
    document.getElementById("feedbackBackBtn");

  const feedbackFloatingBtn =
    document.getElementById("feedbackFloatingBtn");
  const feedbackWidgetSurveyBtn =
    document.getElementById("feedbackWidgetSurveyBtn");
  const feedbackWidgetCloseBtn =
    document.getElementById("feedbackWidgetCloseBtn");

  const feedbackForm =
    document.getElementById("feedbackForm");
  const submitFeedbackBtn =
    document.getElementById("submitFeedbackBtn");
  const feedbackStatus =
    document.getElementById("feedbackStatus");
  const feedbackThanks =
    document.getElementById("feedbackThanks");

  const feedbackEnjoyed =
    document.getElementById("feedbackEnjoyed");
  const feedbackDidntWork =
    document.getElementById("feedbackDidntWork");
  const feedbackBetter =
    document.getElementById("feedbackBetter");

  const feedbackTextareas = [
    feedbackEnjoyed,
    feedbackDidntWork,
    feedbackBetter
  ].filter(Boolean);

const feedbackSessionKey =
    "bravesprouts_feedback_intro_login_key";

  const currentLoginKey = [
    feedbackSystem.dataset.userId || "user",
    feedbackSystem.dataset.loginCount || "0"
  ].join("-");

  const feedbackIntroShownForThisLogin =
    sessionStorage.getItem(feedbackSessionKey) ===
    currentLoginKey;

let feedbackSubmitted = false;

const feedbackDismissedSessionKey =
  "bravesprouts_feedback_dismissed_login_key";

let feedbackBubbleDismissedForSession =
  sessionStorage.getItem(feedbackDismissedSessionKey) ===
  currentLoginKey;

  function autoResizeTextarea(textarea) {
    if (!textarea) return;

    textarea.style.height = "0px";

    const maxHeight = 118;
    const newHeight = Math.min(
      textarea.scrollHeight,
      maxHeight
    );

    textarea.style.height = `${newHeight}px`;
    textarea.style.overflowY =
      textarea.scrollHeight > maxHeight
        ? "auto"
        : "hidden";
  }

  feedbackTextareas.forEach((textarea) => {
    autoResizeTextarea(textarea);

    textarea.addEventListener("input", function () {
      autoResizeTextarea(this);
    });
  });

  function setFeedbackPanel(panelName) {
    if (!feedbackIntroPanel || !feedbackFormPanel) return;

    if (panelName === "intro") {
      feedbackIntroPanel.hidden = false;
      feedbackFormPanel.hidden = true;

      feedbackIntroPanel.classList.add("active");
      feedbackFormPanel.classList.remove("active");
    } else {
      feedbackIntroPanel.hidden = true;
      feedbackFormPanel.hidden = false;

      feedbackIntroPanel.classList.remove("active");
      feedbackFormPanel.classList.add("active");
    }
  }

  function openFeedbackIntro() {
    if (!feedbackOverlay) return;

    hideFeedbackBubble();

    feedbackOverlay.classList.add("active");
    document.body.classList.add("feedback-open");

    setFeedbackPanel("intro");
  }

  function openFeedbackForm() {
    if (!feedbackOverlay) return;

    hideFeedbackBubble();

    feedbackOverlay.classList.add("active");
    document.body.classList.add("feedback-open");

    setFeedbackPanel("form");

    requestAnimationFrame(() => {
      feedbackTextareas.forEach(autoResizeTextarea);

      if (feedbackEnjoyed) {
        feedbackEnjoyed.focus();
      }
    });
  }

  function closeFeedbackOverlay() {
    if (feedbackOverlay) {
      feedbackOverlay.classList.remove("active");
    }

    document.body.classList.remove("feedback-open");
  }

  function showFeedbackBubble() {
  if (
    !feedbackFloatingBtn ||
    !shouldShowFeedback ||
    feedbackSubmitted ||
    feedbackBubbleDismissedForSession
  ) {
    return;
  }

  feedbackFloatingBtn.hidden = false;
  feedbackFloatingBtn.classList.remove("is-closing");
  feedbackFloatingBtn.classList.add("active");
}

  function hideFeedbackBubble() {
    if (!feedbackFloatingBtn) return;

    feedbackFloatingBtn.classList.remove("active");
  }

  function closeFeedbackBubbleForSession() {
  if (!feedbackFloatingBtn) return;

  feedbackBubbleDismissedForSession = true;

  sessionStorage.setItem(
    feedbackDismissedSessionKey,
    currentLoginKey
  );

  feedbackFloatingBtn.classList.add("is-closing");

  const finishClosing = () => {
    feedbackFloatingBtn.classList.remove(
      "active",
      "is-closing"
    );

    feedbackFloatingBtn.hidden = true;
  };

  const prefersReducedMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)"
  ).matches;

  if (prefersReducedMotion) {
    finishClosing();
    return;
  }

  window.setTimeout(finishClosing, 250);
}

  async function persistDismissedState() {
    try {
      await fetch("/dismiss-feedback-prompt", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        credentials: "same-origin",
        body: JSON.stringify({})
      });
    } catch (error) {
      console.error(
        "Could not save dismissed feedback state:",
        error
      );
    }
  }

  async function dismissFeedbackFlow() {
    closeFeedbackOverlay();

    if (!feedbackSubmitted) {
      showFeedbackBubble();
      await persistDismissedState();
    }
  }

  function showThankYouToast() {
    if (!feedbackThanks) return;

    feedbackThanks.classList.add("active");

    setTimeout(() => {
      feedbackThanks.classList.remove("active");
    }, 4200);
  }

  if (shouldShowFeedback) {
    if (!feedbackIntroShownForThisLogin) {
      sessionStorage.setItem(
        feedbackSessionKey,
        currentLoginKey
      );

      setTimeout(() => {
        openFeedbackIntro();
      }, 550);
    } else {
      showFeedbackBubble();
    }
  }

  if (closeFeedbackBtn) {
    closeFeedbackBtn.addEventListener(
      "click",
      dismissFeedbackFlow
    );
  }

  if (closeFeedbackFormBtn) {
    closeFeedbackFormBtn.addEventListener(
      "click",
      dismissFeedbackFlow
    );
  }

  if (feedbackLaterBtn) {
    feedbackLaterBtn.addEventListener(
      "click",
      dismissFeedbackFlow
    );
  }

  if (feedbackFormLaterBtn) {
    feedbackFormLaterBtn.addEventListener(
      "click",
      dismissFeedbackFlow
    );
  }

  if (feedbackYesBtn) {
    feedbackYesBtn.addEventListener(
      "click",
      function () {
        openFeedbackForm();
      }
    );
  }

  if (feedbackBackBtn) {
    feedbackBackBtn.addEventListener(
      "click",
      function () {
        dismissFeedbackFlow();
      }
    );
  }

  if (feedbackWidgetCloseBtn) {
    feedbackWidgetCloseBtn.addEventListener(
      "click",
      function (event) {
        event.preventDefault();
        event.stopPropagation();

        closeFeedbackBubbleForSession();
      }
    );

    feedbackWidgetCloseBtn.addEventListener(
      "keydown",
      function (event) {
        event.stopPropagation();
      }
    );
  }

  if (feedbackFloatingBtn) {
    feedbackFloatingBtn.addEventListener(
      "click",
      function (event) {
        if (
          event.target.closest(
            "#feedbackWidgetCloseBtn"
          )
        ) {
          return;
        }

        openFeedbackForm();
      }
    );

    feedbackFloatingBtn.addEventListener(
      "keydown",
      function (event) {
        if (event.target === feedbackWidgetCloseBtn) {
          return;
        }

        if (
          event.key === "Enter" ||
          event.key === " "
        ) {
          event.preventDefault();
          openFeedbackForm();
        }
      }
    );
  }

  if (feedbackWidgetSurveyBtn) {
    feedbackWidgetSurveyBtn.addEventListener(
      "click",
      function (event) {
        event.stopPropagation();
        openFeedbackForm();
      }
    );
  }

  if (feedbackOverlay) {
    feedbackOverlay.addEventListener(
      "click",
      function (event) {
        if (event.target === feedbackOverlay) {
          dismissFeedbackFlow();
        }
      }
    );
  }

  if (feedbackForm) {
    feedbackForm.addEventListener(
      "submit",
      async function (event) {
        event.preventDefault();

        const payload = {
          what_child_enjoyed: feedbackEnjoyed
            ? feedbackEnjoyed.value.trim()
            : "",

          what_didnt_work: feedbackDidntWork
            ? feedbackDidntWork.value.trim()
            : "",

          what_would_make_better: feedbackBetter
            ? feedbackBetter.value.trim()
            : ""
        };

        const allAnswersFilled =
          payload.what_child_enjoyed &&
          payload.what_didnt_work &&
          payload.what_would_make_better;

        if (!allAnswersFilled) {
          if (feedbackStatus) {
            feedbackStatus.textContent =
              "Please answer all 3 questions before submitting.";
          }

          return;
        }

        if (submitFeedbackBtn) {
          submitFeedbackBtn.disabled = true;
          submitFeedbackBtn.textContent =
            "Submitting...";
        }

        if (feedbackStatus) {
          feedbackStatus.textContent = "";
        }

        try {
          const response = await fetch(
            "/submit-feedback",
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json"
              },
              credentials: "same-origin",
              body: JSON.stringify(payload)
            }
          );

          const data = await response.json();

          if (!response.ok || !data.success) {
            throw new Error(
              data.error ||
                "Could not submit feedback."
            );
          }

          feedbackSubmitted = true;

          closeFeedbackOverlay();
          hideFeedbackBubble();
          showThankYouToast();
        } catch (error) {
          console.error(
            "Feedback submit error:",
            error
          );

          if (feedbackStatus) {
            feedbackStatus.textContent =
              error.message ||
              "Something went wrong. Please try again.";
          }

          if (submitFeedbackBtn) {
            submitFeedbackBtn.disabled = false;
            submitFeedbackBtn.textContent =
              "Submit feedback";
          }
        }
      }
    );
  }
  }
});