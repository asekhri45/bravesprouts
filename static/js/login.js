document.addEventListener("DOMContentLoaded", function () {
  const passwordInput = document.getElementById("password");
  const togglePasswordBtn = document.getElementById("togglePassword");
  const togglePasswordIcon = document.getElementById("togglePasswordIcon");

  const emailInput = document.getElementById("email");
  const rememberMeCheckbox = document.getElementById("rememberMe");
  const loginForm = document.getElementById("loginForm");

  const savedEmailKey = "bravesproutsRememberedEmail";

  if (
    !passwordInput ||
    !togglePasswordBtn ||
    !togglePasswordIcon ||
    !emailInput ||
    !rememberMeCheckbox ||
    !loginForm
  ) {
    return;
  }

  const savedEmail = localStorage.getItem(savedEmailKey);
  if (savedEmail) {
    emailInput.value = savedEmail;
    rememberMeCheckbox.checked = true;
  }

  togglePasswordBtn.addEventListener("click", function () {
    const isHidden = passwordInput.type === "password";
    passwordInput.type = isHidden ? "text" : "password";

    togglePasswordBtn.setAttribute(
      "aria-label",
      isHidden ? "Hide password" : "Show password"
    );

    togglePasswordIcon.alt = isHidden ? "Hide password" : "Show password";

    const eyeOpen = togglePasswordIcon.dataset.eyeOpen;
    const eyeClosed = togglePasswordIcon.dataset.eyeClosed;

    if (eyeOpen && eyeClosed) {
      togglePasswordIcon.src = isHidden ? eyeOpen : eyeClosed;
    }
  });

  loginForm.addEventListener("submit", function () {
    const emailValue = emailInput.value.trim();

    if (rememberMeCheckbox.checked && emailValue) {
      localStorage.setItem(savedEmailKey, emailValue);
    } else {
      localStorage.removeItem(savedEmailKey);
    }
  });

  rememberMeCheckbox.addEventListener("change", function () {
    if (!rememberMeCheckbox.checked) {
      localStorage.removeItem(savedEmailKey);
    }
  });
});