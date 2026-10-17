(() => {
    "use strict";
    const workspace = document.querySelector(".coach-workspace");
    if (!workspace) return;
    const handles = [...workspace.querySelectorAll(".workspace-resizer")];
    const reset = workspace.querySelector(".workspace-layout-reset");
    const status = workspace.querySelector(".workspace-layout-status");
    if (handles.length !== 2 || !reset || !status) return;

    const desktop = window.matchMedia("(min-width: 1001px)");
    const defaults = {left: 190, right: 250};
    const minimum = {left: 150, right: 210};
    const maximum = {left: 310, right: 380};
    const storageKey = "coach.workspace.widths.v1";
    let widths = {...defaults};
    let drag = null;
    try {
        const saved = JSON.parse(localStorage.getItem(storageKey));
        if (saved && Number.isInteger(saved.left) && Number.isInteger(saved.right) &&
            saved.left >= minimum.left && saved.left <= maximum.left &&
            saved.right >= minimum.right && saved.right <= maximum.right) {
            widths = {left: saved.left, right: saved.right};
        }
    } catch (_) { /* Storage may be disabled; resizing still works. */ }

    function limit(side) {
        const other = side === "left" ? "right" : "left";
        // Keep at least 320px for chat, plus two 12px drag handles.
        return Math.max(minimum[side], Math.min(maximum[side], workspace.clientWidth - 344 - widths[other]));
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
        widths.left = Math.round(Math.max(minimum.left, Math.min(widths.left, limit("left"))));
        widths.right = Math.round(Math.max(minimum.right, Math.min(widths.right, limit("right"))));
        workspace.style.setProperty("--coach-left", `${widths.left}px`);
        workspace.style.setProperty("--coach-right", `${widths.right}px`);
        if (anchor) history.scrollTop += anchor.getBoundingClientRect().top - anchorTop;
        for (const handle of handles) {
            const side = handle.dataset.side;
            handle.setAttribute("aria-valuemin", String(minimum[side]));
            handle.setAttribute("aria-valuemax", String(Math.floor(limit(side))));
            handle.setAttribute("aria-valuenow", String(widths[side]));
            handle.setAttribute("aria-valuetext", `${side === "left" ? "左栏" : "学习栏"}宽度 ${widths[side]} 像素`);
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
            const side = handle.dataset.side;
            widths[side] = drag.widths[side] + (event.clientX - drag.x) * (side === "left" ? 1 : -1);
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
            const side = handle.dataset.side;
            if (event.key === "Home") widths[side] = minimum[side];
            else if (event.key === "End") widths[side] = limit(side);
            else widths[side] += (event.key === "ArrowRight" ? 1 : -1) * (side === "left" ? 1 : -1) * (event.shiftKey ? 30 : 10);
            apply();
            save();
        });
    }
    reset.addEventListener("click", restore);
    desktop.addEventListener("change", () => { finish(true); apply(); });
    new ResizeObserver(apply).observe(workspace);
    apply();
})();
