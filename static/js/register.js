document.addEventListener("DOMContentLoaded", function () {
    var form = document.getElementById("signupForm");
    if (!form) return;

    var emailInput = document.getElementById("email");
    var passwordInput = document.getElementById("password");
    var termsCheck = document.getElementById("termsCheck");
    var submitBtn = document.getElementById("submitBtn");

    var emailError = document.getElementById("emailError");
    var termsError = document.getElementById("termsError");
    var requirementItems = document.querySelectorAll("#passwordRequirements li");

    var togglePasswordBtn = document.getElementById("togglePassword");
    var togglePasswordIcon = document.getElementById("togglePasswordIcon");

    var EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

    function checkPasswordRules(value) {
        var rules = {
            length: value.length >= 8,
            upper: /[A-Z]/.test(value),
            lower: /[a-z]/.test(value),
            special: /[!@#$%^&*(),.?/<>|=+\-_^~`]/.test(value)
        };
        requirementItems.forEach(function (item) {
            var rule = item.getAttribute("data-rule");
            item.classList.toggle("valid", !!rules[rule]);
        });
        return Object.keys(rules).every(function (key) { return rules[key]; });
    }

    function validateEmail() {
        var value = emailInput.value.trim();
        if (!value) {
            emailError.textContent = "";
            return true; // don't nag before the user has typed anything
        }
        if (!EMAIL_RE.test(value)) {
            emailError.textContent = "Please enter a valid email address";
            emailInput.closest(".input-group").classList.add("has-error");
            return false;
        }
        emailError.textContent = "";
        emailInput.closest(".input-group").classList.remove("has-error");
        return true;
    }

    // Show/hide password (mirrors login.js's proven pattern).
    if (togglePasswordBtn && togglePasswordIcon && passwordInput) {
        togglePasswordBtn.addEventListener("click", function () {
            var isHidden = passwordInput.type === "password";
            passwordInput.type = isHidden ? "text" : "password";
            togglePasswordBtn.setAttribute("aria-label", isHidden ? "Hide password" : "Show password");
            togglePasswordIcon.alt = isHidden ? "Hide password" : "Show password";
            var eyeOpen = togglePasswordIcon.dataset.eyeOpen;
            var eyeClosed = togglePasswordIcon.dataset.eyeClosed;
            if (eyeOpen && eyeClosed) {
                togglePasswordIcon.src = isHidden ? eyeOpen : eyeClosed;
            }
        });
    }

    emailInput.addEventListener("input", validateEmail);
    emailInput.addEventListener("blur", validateEmail);
    passwordInput.addEventListener("input", function () {
        checkPasswordRules(passwordInput.value);
    });

    function focusInvalid(el) {
        el.scrollIntoView({ block: "center", behavior: "auto" });
        el.focus();
    }

    // On load, if the server re-rendered this page with an error, move
    // focus to it so screen-reader and keyboard users see it immediately.
    // Any error present here came from a server round-trip (duplicate
    // email, a CSRF failure, terms rejected server-side, etc.) rather than
    // client-side validation, which is why it's tagged as the "server"
    // event rather than "validation" -- the client-side branches below
    // cover the cases caught before a request was even sent.
    var serverError = document.getElementById("formError");
    if (serverError) {
        focusInvalid(serverError);
        if (window.trackEvent) {
            window.trackEvent("signup_server_error", {});
        }
    }

    // Fire once, on the first time the visitor actually interacts with the
    // form (not just on page load, which is already signup_page_view).
    var startedFired = false;
    function fireStartedOnce() {
        if (startedFired) return;
        startedFired = true;
        if (window.trackEvent) {
            window.trackEvent("signup_started", {});
        }
    }
    [emailInput, passwordInput, termsCheck].forEach(function (el) {
        el.addEventListener("input", fireStartedOnce, { once: true });
        el.addEventListener("change", fireStartedOnce, { once: true });
    });

    var submitting = false;

    form.addEventListener("submit", function (e) {
        var emailOk = validateEmail() && emailInput.value.trim();
        var passwordOk = checkPasswordRules(passwordInput.value);
        var termsOk = termsCheck.checked;

        if (!emailOk) {
            e.preventDefault();
            if (!emailInput.value.trim()) {
                emailError.textContent = "Email is required";
            }
            focusInvalid(emailInput);
            if (window.trackEvent) {
                window.trackEvent("signup_validation_error", { field: "email" });
            }
            return;
        }

        if (!passwordOk) {
            e.preventDefault();
            focusInvalid(passwordInput);
            if (window.trackEvent) {
                window.trackEvent("signup_validation_error", { field: "password" });
            }
            return;
        }

        if (!termsOk) {
            e.preventDefault();
            termsError.textContent = "You must accept the Terms of Use and Privacy Policy to continue";
            focusInvalid(termsCheck);
            if (window.trackEvent) {
                window.trackEvent("signup_validation_error", { field: "terms" });
            }
            return;
        }

        // Prevent double-submit (double form POST from a repeated tap/click)
        // without blocking the actual submission -- disabling a submit
        // button on the same event that submits it still lets that click's
        // submission through in every evergreen browser.
        if (submitting) {
            e.preventDefault();
            return;
        }
        submitting = true;
        submitBtn.disabled = true;
    });
});
