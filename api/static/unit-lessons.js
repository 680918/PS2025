(() => {
    "use strict";
    let submitting = false;
    document.querySelectorAll(".unit-summary-form").forEach((form) => {
        form.addEventListener("submit", (event) => {
            if (submitting) {
                event.preventDefault();
                return;
            }
            submitting = true;
            document.querySelectorAll("[data-unit-submit]").forEach((button) => { button.disabled = true; });
            form.setAttribute("aria-busy", "true");
            form.querySelector(".unit-summary-wait").hidden = false;
        });
    });
    window.addEventListener("pageshow", (event) => {
        if (event.persisted) window.location.reload();
    });
})();
