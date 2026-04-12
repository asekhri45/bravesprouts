document.addEventListener("DOMContentLoaded", function () {
  // --- Profile Icon ---
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
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: new URLSearchParams({ icon: selectedIcon }),
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
 
  // --- Carousel ---
  const track = document.getElementById("dashboardCarouselTrack");
  const prevBtn = document.getElementById("carouselPrevBtn");
  const nextBtn = document.getElementById("carouselNextBtn");
  const carouselWrapper = document.querySelector(".dashboard-carousel-wrapper");
  const activityButtons = document.querySelectorAll(".activity-action-btn");
  const activityIndicator = document.querySelector(".current-activity-indicator");
 
  let currentSlide = carouselWrapper
    ? parseInt(carouselWrapper.dataset.defaultSlide || "0", 10)
    : 0;
 
  // Index of the slide that contains the current activity panel
  const currentActivitySlideIndex = (() => {
    if (!track) return -1;
    const slides = track.querySelectorAll(".dashboard-panel-slide");
    for (let i = 0; i < slides.length; i++) {
      if (slides[i].querySelector(".dashboard-panel-current")) return i;
    }
    return -1;
  })();
 
  function updateIndicatorColor() {
    if (!activityIndicator) return;
    if (currentSlide === currentActivitySlideIndex) {
      activityIndicator.classList.remove("indicator-hidden");
    } else {
      activityIndicator.classList.add("indicator-hidden");
    }
  }
 
  function updateCarouselPosition() {
    if (!track) return;
    track.style.transform = `translateX(-${currentSlide * 100}%)`;
    updateIndicatorColor();
  }
 
  function moveCarousel(direction) {
    if (!track) return;
    const totalSlides = track.querySelectorAll(".dashboard-panel-slide").length;
    if (totalSlides === 0) return;
    currentSlide = (currentSlide + direction + totalSlides) % totalSlides;
    updateCarouselPosition();
  }
 
  updateCarouselPosition();
 
  if (prevBtn) prevBtn.addEventListener("click", () => moveCarousel(-1));
  if (nextBtn) nextBtn.addEventListener("click", () => moveCarousel(1));
 
  // --- Activity Buttons ---
  activityButtons.forEach((button) => {
    button.addEventListener("click", async function () {
      const action = this.dataset.action;
      const activityId = this.dataset.activityId;
 
      if (action === "open") {
        window.location.href = "/welcome-activity";
        return;
      }
 
      if (action === "set-current") {
        try {
          const response = await fetch("/set-current", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ activity_id: activityId }),
          });
          const data = await response.json();
          if (data.success) location.reload();
          else console.error(data.error || "Failed to set current activity");
        } catch (error) {
          console.error("Error setting current activity:", error);
        }
      }
 
      if (action === "unlock") {
        try {
          const response = await fetch("/unlock-activity", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ activity_id: activityId }),
          });
          const data = await response.json();
          if (data.success) location.reload();
          else console.error(data.error || "Failed to unlock activity");
        } catch (error) {
          console.error("Error unlocking activity:", error);
        }
      }
    });
  });
});