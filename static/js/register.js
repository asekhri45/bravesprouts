const form = document.getElementById("signupForm");

const password = document.getElementById("password");
const confirmPassword = document.getElementById("confirm_password");

function showError(message) {
    let errorBox = document.querySelector(".error-message");

    if (!errorBox) {
        errorBox = document.createElement("div");
        errorBox.className = "error-message";

        const termsBox = document.querySelector(".terms-checked");
        form.insertBefore(errorBox, termsBox);
    }

    errorBox.textContent = "* " + message;
}

function clearError() {
    const errorBox = document.querySelector(".error-message");

    if (errorBox) {
        errorBox.textContent = "";
    }
}

function getPasswordError(value) {
    if (value.length < 8) {
        return "The password must be at least 8 characters";
    }

    if (!/[A-Z]/.test(value)) {
        return "Must have an uppercase letter";
    }

    if (!/[a-z]/.test(value)) {
        return "Must have a lowercase letter";
    }

    if (!/[!@#$%^&*(),.?/<>|=+\-_^~`]/.test(value)) {
        return "Must have a special character";
    }

    return "";
}

function checkPasswords() {
    clearError();

    const passwordError = getPasswordError(password.value);

    if (passwordError) {
        password.setCustomValidity(passwordError);
        showError(passwordError);
        return false;
    } else {
        password.setCustomValidity("");
    }

    if (password.value !== confirmPassword.value) {
        confirmPassword.setCustomValidity("Passwords do not match");
        showError("Passwords do not match");
        return false;
    } else {
        confirmPassword.setCustomValidity("");
    }

    return true;
}

password.addEventListener("input", checkPasswords);
confirmPassword.addEventListener("input", checkPasswords);

form.addEventListener("submit", function (e) {
    if (!checkPasswords()) {
        e.preventDefault();
    }
});