/*
 * static/js/forms.js - client-side form validation.
 *
 * WHY DO THIS IF PYTHON ALREADY VALIDATES?
 * -----------------------------------------
 * Because the server check only happens AFTER the page reloads. This
 * file catches the obvious mistakes instantly, while the user is still
 * looking at the field. The Python validation stays in place as the
 * real safety net - never rely on the browser alone.
 *
 * This file is deliberately small and dependency free. It does not use
 * AJAX; forms still submit normally, and the server does the real work.
 */

(function () {
    "use strict";

    /* Show a red message under a field. */
    function showError(field, message) {
        clearError(field);
        var box = document.createElement("small");
        box.className = "js-error";
        box.textContent = message;
        field.parentNode.appendChild(box);
        field.classList.add("input-error");
    }

    /* Remove any message under a field. */
    function clearError(field) {
        var old = field.parentNode.querySelector(".js-error");
        if (old) { old.remove(); }
        field.classList.remove("input-error");
    }

    function clearAll(form) {
        var marks = form.querySelectorAll(".js-error");
        for (var i = 0; i < marks.length; i++) { marks[i].remove(); }
        var bad = form.querySelectorAll(".input-error");
        for (var j = 0; j < bad.length; j++) { bad[j].classList.remove("input-error"); }
    }

    /* Check one field. Returns true when it is fine. */
    function validateField(field) {
        clearError(field);

        var value = (field.value || "").trim();
        var label = field.dataset.label || field.name || "This field";

        /* required */
        if (field.hasAttribute("required") && value === "") {
            showError(field, label + " is required.");
            return false;
        }

        /* password confirmation */
        if (field.type === "password" && field.dataset.confirmFor) {
            var other = document.getElementById(field.dataset.confirmFor);
            if (other && value !== (other.value || "").trim()) {
                showError(field, "The two passwords do not match.");
                return false;
            }
        }

        /* password length (server checks 6; warn early at 6 too) */
        if (field.type === "password" && field.name === "password"
                && value.length > 0 && value.length < 6) {
            showError(field, "Password must be at least 6 characters.");
            return false;
        }

        /* numbers */
        if (field.type === "number" && value !== "") {
            var num = Number(value);
            if (isNaN(num)) {
                showError(field, label + " must be a number.");
                return false;
            }
            var min = field.min !== "" ? Number(field.min) : null;
            if (min !== null && !isNaN(min) && num < min) {
                showError(field, label + " cannot be less than " + min + ".");
                return false;
            }
        }

        /* email */
        if (field.type === "email" && value !== "") {
            if (!/^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$/.test(value)) {
                showError(field, "Please enter a valid email address.");
                return false;
            }
        }

        /* date: must parse, and must not be a nonsense year */
        if (field.type === "date" && value !== "") {
            var parts = value.split("-");
            if (parts.length !== 3) {
                showError(field, label + " is not a valid date.");
                return false;
            }
            var year = Number(parts[0]);
            if (year < 1990 || year > 2100) {
                showError(field, label + " looks like the wrong year.");
                return false;
            }
        }

        return true;
    }

    function setupForm(form) {
        /* Clear the message as soon as the user starts fixing it. */
        var fields = form.querySelectorAll("input, select, textarea");
        for (var i = 0; i < fields.length; i++) {
            fields[i].addEventListener("input", function (ev) {
                clearError(ev.target);
            });
        }

        form.addEventListener("submit", function (ev) {
            clearAll(form);
            var ok = true;
            var list = form.querySelectorAll("input, select, textarea");

            for (var j = 0; j < list.length; j++) {
                if (!validateField(list[j])) { ok = false; }
            }

            if (!ok) {
                ev.preventDefault();          // stop the submit
                var firstBad = form.querySelector(".input-error");
                if (firstBad) { firstBad.focus(); }
                return;
            }

            /* Stop double-clicks creating two records. */
            var submit = form.querySelector("button[type=submit]");
            if (submit) {
                submit.disabled = true;
                submit.textContent = "Saving...";
                /* Re-enable if the browser restores the page from cache. */
                window.setTimeout(function () {
                    submit.disabled = false;
                    submit.textContent = submit.dataset.label || "Save";
                }, 8000);
            }
        });
    }

    function init() {
        var forms = document.querySelectorAll("form[method='POST']");
        for (var i = 0; i < forms.length; i++) {
            /* Skip forms that opt out with data-no-validate.

               The Log Out button in the navigation is a POST form too, but
               it is not a data-entry form. Attaching the handler to it made
               the button say "Saving..." and disabled itself, which is
               meaningless for logging out and can stop the submit. */
            if (forms[i].hasAttribute("data-no-validate")) { continue; }

            /* Record the original button text so it can be restored. */
            var btn = forms[i].querySelector("button[type=submit]");
            if (btn) { btn.dataset.label = btn.textContent.trim(); }
            setupForm(forms[i]);
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
