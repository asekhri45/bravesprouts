const password = document.getElementById("password");
const confirmPassword = document.getElementById("confirm_password");

function checkPasswords() {
    if (password.value !== confirmPassword.value) {
        confirmPassword.setCustomValidity("Passwords do not match");
    } else {
        confirmPassword.setCustomValidity("");
    }
}

password.addEventListener("input", checkPasswords);
confirmPassword.addEventListener("input", checkPasswords);