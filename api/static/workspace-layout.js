(() => {
    "use strict";
    const workspace = document.querySelector(".coach-workspace");
    if (!workspace) return;
    const handles = [...workspace.querySelectorAll(".workspace-resizer")];
    const reset = workspace.querySelector(".workspace-layout-reset");
    const status = workspace.querySelector(".workspace-layout-status");
    if (handles.length !== 1 || !reset || !status) return;

    const desktop = window.matchMedia("(min-width: 1001px)");
    const defaults = {left: 240};
    const minimum = {left: 190};
    const maximum = {left: 360};
    const storageKey = "coach.workspace.left-width.v3";
    let widths = {...defaults};
    let drag = null;
    try {
        const saved = JSON.parse(localStorage.getItem(storageKey));
        if (saved && Number.isInteger(saved.left) &&
            saved.left >= minimum.left && saved.left <= maximum.left) {
            widths = {left: saved.left};
        }
    } catch (_) { /* Storage may be disabled; resizing still works. */ }

    function limit() {
        // Keep at least 420px for the primary conversation space.
        return Math.max(minimum.left, Math.min(maximum.left, workspace.clientWidth - 432));
    }

    function apply() {
        reset.hidden = !desktop.matches;
        if (!desktop.matches) return;
        const history = document.getElementById("dialogue-history");
        const top = history?.getBoundingClientRect().top;
        const anchor = history && [...history.querySelectorAll(".dialogue-message")].find(
            element => element.getBoundingClientRect().bottom > top + 8
        );
        const anchorTop = anchor?.getBoundingClientRect().top;
        widths.left = Math.round(Math.max(minimum.left, Math.min(widths.left, limit())));
        workspace.style.setProperty("--coach-left", `${widths.left}px`);
        if (anchor) history.scrollTop += anchor.getBoundingClientRect().top - anchorTop;
        for (const handle of handles) {
            handle.setAttribute("aria-valuemin", String(minimum.left));
            handle.setAttribute("aria-valuemax", String(Math.floor(limit())));
            handle.setAttribute("aria-valuenow", String(widths.left));
            handle.setAttribute("aria-valuetext", `左栏宽度 ${widths.left} 像素`);
        }
    }

    function save() {
        try { localStorage.setItem(storageKey, JSON.stringify(widths)); } catch (_) { /* Optional. */ }
    }

    function finish(cancel = false) {
        if (!drag) return;
        const previous = drag;
        drag = null;
        workspace.classList.remove("is-resizing");
        if (previous.handle.hasPointerCapture(previous.pointerId)) previous.handle.releasePointerCapture(previous.pointerId);
        if (cancel) {
            widths = previous.widths;
            apply();
        } else save();
    }

    function restore() {
        finish(true);
        widths = {...defaults};
        try { localStorage.removeItem(storageKey); } catch (_) { /* Optional. */ }
        apply();
        status.textContent = "已恢复默认布局。";
    }

    for (const handle of handles) {
        handle.addEventListener("pointerdown", event => {
            if (!desktop.matches || event.button !== 0 || !event.isPrimary || drag) return;
            event.preventDefault();
            handle.focus();
            drag = {handle, pointerId: event.pointerId, x: event.clientX, widths: {...widths}};
            handle.setPointerCapture(event.pointerId);
            workspace.classList.add("is-resizing");
        });
        handle.addEventListener("pointermove", event => {
            if (!drag || drag.handle !== handle || drag.pointerId !== event.pointerId) return;
            widths.left = drag.widths.left + (event.clientX - drag.x);
            apply();
        });
        handle.addEventListener("pointerup", () => finish());
        handle.addEventListener("pointercancel", () => finish(true));
        handle.addEventListener("lostpointercapture", () => finish(true));
        handle.addEventListener("dblclick", restore);
        handle.addEventListener("keydown", event => {
            if (event.key === "Escape") { finish(true); return; }
            if (!desktop.matches || !["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
            event.preventDefault();
            if (event.key === "Home") widths.left = minimum.left;
            else if (event.key === "End") widths.left = limit();
            else widths.left += (event.key === "ArrowRight" ? 1 : -1) * (event.shiftKey ? 30 : 10);
            apply();
            save();
        });
    }
    reset.addEventListener("click", restore);
    desktop.addEventListener("change", () => { finish(true); apply(); });
    new ResizeObserver(apply).observe(workspace);
    apply();
})();
