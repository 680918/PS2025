(() => {
    "use strict";
    for (const form of document.querySelectorAll("[data-study-resume]")) {
        let busy = false;
        form.addEventListener("submit", event => {
            if (busy) { event.preventDefault(); return; }
            busy = true;
            form.setAttribute("aria-busy", "true");
            form.querySelector('button[type="submit"]').disabled = true;
            const status = form.querySelector(".study-wait");
            status.hidden = false;
            const dots = document.createElement("span");
            dots.className = "waiting-dots";
            dots.setAttribute("aria-hidden", "true");
            for (let i = 0; i < 3; i++) dots.append(document.createElement("i"));
            status.replaceChildren(dots, document.createTextNode("正在接回这个主题，请稍候…"));
        });
        window.addEventListener("pageshow", () => {
            if (!busy) return;
            busy = false;
            form.removeAttribute("aria-busy");
            form.querySelector('button[type="submit"]').disabled = false;
            form.querySelector(".study-wait").hidden = true;
        });
    }
})();
