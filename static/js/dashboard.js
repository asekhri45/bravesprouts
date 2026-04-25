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

  activityButtons.forEach((button) => {
    button.addEventListener("click", async function () {
      const action = this.dataset.action;
      const activityId = this.dataset.activityId;

      if (!action || !activityId) {
        console.error("Missing action or activity ID");
        return;
      }

      let endpoint = "";

      if (action === "set-current") {
        endpoint = "/set-current";
      } else if (action === "unlock") {
        endpoint = "/unlock-activity";
      } else {
        console.error("Unknown action:", action);
        return;
      }

      try {
        this.disabled = true;

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
          this.disabled = false;
        }
      } catch (error) {
        console.error("Fetch error:", error);
        alert("Something went wrong. Check the console.");
        this.disabled = false;
      }
    });
  });
});