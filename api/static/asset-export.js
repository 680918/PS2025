(() => {
    "use strict";
    const form = document.getElementById("asset-export-form");
    const status = document.getElementById("asset-export-status");
    if (!form || !status) return;
    const button = form.querySelector('button[type="submit"]');
    let busy = false;
    form.addEventListener("submit", async event => {
        event.preventDefault();
        if (busy) return;
        if (!form.querySelector('input[name="scope"]:checked')) {
            status.textContent = "请至少选择一类要导出的内容。";
            return;
        }
        const fields = new URLSearchParams(new FormData(form));
        busy = true;
        button.disabled = true;
        form.setAttribute("aria-busy", "true");
        status.classList.add("export-busy");
        status.textContent = "正在整理所选资料，请稍候…";
        try {
            const response = await fetch(form.getAttribute("action"), {
                method: "POST", credentials: "same-origin", cache: "no-store",
                headers: {"Accept": "application/json"}, body: fields,
            });
            if (response.redirected && new URL(response.url).pathname === "/web/login") {
                status.textContent = "登录已过期，请重新登录后再导出。";
                const login = document.createElement("a");
                login.className = "text-link";
                login.href = "/web/login";
                login.textContent = " 前往登录 →";
                status.append(login);
                return;
            }
            if (!response.ok) {
                let message = "资料包暂时无法生成，请稍后重试。";
                if ((response.headers.get("content-type") || "").includes("application/json")) {
                    const error = await response.json();
                    if (typeof error.error === "string") message = error.error;
                }
                status.textContent = message;
                return;
            }
            if (!(response.headers.get("content-type") || "").startsWith("application/zip")) throw new Error("unexpected download");
            status.textContent = "资料已整理，正在接收下载包…";
            const blob = await response.blob();
            const header = response.headers.get("content-disposition") || "";
            const match = header.match(/filename\*=UTF-8''([^;]+)/i);
            const filename = match ? decodeURIComponent(match[1]) : "知行学习资料.zip";
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = filename;
            document.body.append(link);
            link.click();
            link.remove();
            setTimeout(() => URL.revokeObjectURL(url), 30000);
            status.textContent = "资料包已交给浏览器下载。请查看下载列表，完整解压后打开“打开这里.html”。Coach 内的内容继续保留。";
        } catch (_) {
            status.textContent = "下载未能完成，请检查网络后重试。Coach 内的内容继续保留。";
        } finally {
            busy = false;
            button.disabled = false;
            form.removeAttribute("aria-busy");
            status.classList.remove("export-busy");
        }
    });
})();
