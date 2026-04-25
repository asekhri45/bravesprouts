document.addEventListener("DOMContentLoaded", function () {
  const closenessText = document.getElementById("closenessText");
  const encouragementText = document.getElementById("encouragementText");
  const closenessStars = document.getElementById("closenessStars");

  window.setClosenessProgress = function (progress) {
    const safeProgress = Math.max(0, Math.min(5, progress));
    const stars = closenessStars.querySelectorAll("span");

    stars.forEach((star, index) => {
      if (index < safeProgress) {
        star.classList.add("filled");
      } else {
        star.classList.remove("filled");
      }
    });

    if (safeProgress === 0) {
      closenessText.textContent = "Let’s start guessing!";
      encouragementText.textContent = "✨ Try asking a question!";
    } else if (safeProgress === 1) {
      closenessText.textContent = "Good question!";
      encouragementText.textContent = "✨ You’re starting to figure it out!";
    } else if (safeProgress === 2) {
      closenessText.textContent = "You’re getting closer!";
      encouragementText.textContent = "✨ Keep asking great questions!";
    } else if (safeProgress === 3) {
      closenessText.textContent = "You’re getting closer!";
      encouragementText.textContent = "✨ Keep asking great questions!";
    } else if (safeProgress === 4) {
      closenessText.textContent = "Almost there!";
      encouragementText.textContent = "✨ You’re so close!";
    } else {
      closenessText.textContent = "You got it!";
      encouragementText.textContent = "⭐ Amazing job!";
    }
  };

  setClosenessProgress(3);
});