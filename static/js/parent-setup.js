document.addEventListener("DOMContentLoaded", function () {
    var form = document.getElementById("parentSetupForm");
    if (!form) return;

    var nameInput = document.getElementById("parent_name");
    var pinInput = document.getElementById("parent_pin");
    var submitBtn = document.getElementById("submitBtn");
    var nameError = document.getElementById("nameError");
    var pinError = document.getElementById("pinError");

    function focusInvalid(el) {
        el.scrollIntoView({ block: "center", behavior: "auto" });
        el.focus();
    }

    var serverError = document.getElementById("formError");
    if (serverError) {
        focusInvalid(serverError);
    }

    // Step 1 redirects here with ?new=1 exactly once, right after a real
    // account is created -- fire account_created then strip the param so
    // a later refresh of this same page can't fire it again.
    if (window.location.search.indexOf("new=1") !== -1) {
        if (window.trackEvent) {
            window.trackEvent("account_created", {});
        }
        var cleanUrl = window.location.pathname;
        window.history.replaceState({}, document.title, cleanUrl);
    }

    pinInput.addEventListener("input", function () {
        // Numeric-only, matches the server's exact 4-digit rule (leading
        // zeros are valid and must be preserved as typed).
        pinInput.value = pinInput.value.replace(/\D/g, "").slice(0, 4);
        pinError.textContent = "";
    });

    nameInput.addEventListener("input", function () {
        nameError.textContent = "";
    });

    var submitting = false;

    form.addEventListener("submit", function (e) {
        var nameOk = nameInput.value.trim().length > 0;
        var pinOk = /^\d{4}$/.test(pinInput.value);

        if (!nameOk) {
            e.preventDefault();
            nameError.textContent = "Parent name is required";
            focusInvalid(nameInput);
            return;
        }

        if (!pinOk) {
            e.preventDefault();
            pinError.textContent = "Parent PIN must be exactly 4 digits";
            focusInvalid(pinInput);
            return;
        }

        if (submitting) {
            e.preventDefault();
            return;
        }
        submitting = true;
        submitBtn.disabled = true;
    });
});
