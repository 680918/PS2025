(() => {
    "use strict";
    const form = document.querySelector("[data-recovery-form]");
    const status = document.getElementById("recovery-status");
    if (!form || !status) return;
    const button = form.querySelector('button[type="submit"]');
    let busy = false;
    form.addEventListener("submit", async event => {
        event.preventDefault();
        if (busy) return;
        const fields = new URLSearchParams(new FormData(form));
        busy = true;
        button.disabled = true;
        form.setAttribute("aria-busy", "true");
        status.replaceChildren();
        const dots = document.createElement("span");
        dots.className = "waiting-dots";
        dots.setAttribute("aria-hidden", "true");
        for (let i = 0; i < 3; i++) dots.append(document.createElement("i"));
        status.append(dots, document.createTextNode(form.dataset.wait));
        try {
            const response = await fetch(form.getAttribute("action"), {
                method: "POST", credentials: "same-origin", cache: "no-store",
                headers: {"Accept": "application/json"}, body: fields,
            });
            const result = await response.json();
            if (response.ok && ["/web/forgot-password/submitted", "/web/password-reset-complete"].includes(result.redirect)) {
                window.location.assign(result.redirect);
                return;
            }
            status.textContent = typeof result.error === "string" ? result.error : "暂时无法完成操作，请稍后重试。";
        } catch (_) {
            status.textContent = "网络中断，结果暂未确认。申请邮件后请先查收；保存新密码后可尝试用新密码登录。请勿反复点击。";
        } finally {
            busy = false;
            button.disabled = false;
            form.removeAttribute("aria-busy");
        }
    });
})();
