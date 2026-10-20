(() => {
    "use strict";
    let copying = false;

    function replyText(body) {
        // Read visible text, including table tabs and code indentation, without
        // copying controls or their status messages. Restore before any paint.
        const controls = [...body.querySelectorAll(".content-copy-tools")];
        const hidden = controls.map(element => element.hidden);
        try {
            for (const element of controls) element.hidden = true;
            return body.innerText;
        } finally {
            controls.forEach((element, index) => { element.hidden = hidden[index]; });
        }
    }

    function tools(label, read, success) {
        const wrapper = document.createElement("div");
        wrapper.className = "content-copy-tools";
        const button = document.createElement("button");
        button.type = "button";
        button.className = "content-copy-button";
        button.textContent = label;
        const status = document.createElement("span");
        status.className = "content-copy-status";
        status.setAttribute("role", "status");
        button.addEventListener("click", async () => {
            if (copying) return;
            if (!navigator.clipboard || typeof navigator.clipboard.writeText !== "function") {
                status.textContent = "浏览器无法自动复制，请选中文字后手动复制。";
                return;
            }
            copying = true;
            button.disabled = true;
            status.textContent = "正在复制…";
            try {
                const text = read();
                if (!text.trim()) {
                    status.textContent = "这段内容为空，暂时无法复制。";
                    return;
                }
                await navigator.clipboard.writeText(text);
                status.textContent = success;
            } catch (_) {
                status.textContent = "未能自动复制，请选中文字后手动复制。";
            } finally {
                copying = false;
                button.disabled = false;
            }
        });
        wrapper.append(button, status);
        return wrapper;
    }

    function enhance() {
        const selector = ".dialogue-coach > .markdown-content, .conversation-record-answer > .markdown-content";
        for (const body of document.querySelectorAll(selector)) {
            if (!body.dataset.copyReady && body.textContent.trim()) {
                body.dataset.copyReady = "true";
                body.after(tools("复制回复", () => replyText(body), "回复文字已复制（不含引用）。"));
            }
            for (const pre of body.querySelectorAll("pre")) {
                if (pre.dataset.copyReady) continue;
                pre.dataset.copyReady = "true";
                const control = tools("复制代码", () => (pre.querySelector("code") || pre).textContent, "代码已复制，换行和缩进已保留。");
                const label = pre.previousElementSibling;
                if (label && label.classList.contains("code-block-label")) {
                    label.append(control);
                } else {
                    pre.before(control);
                }
            }
        }
    }

    // History enhancement runs synchronously before the chat computes its new
    // scroll height. Completed new answers use the existing full-page refresh.
    document.addEventListener("coach-content-ready", enhance);
    enhance();
})();
