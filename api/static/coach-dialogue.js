(() => {
    "use strict";
    const history = document.getElementById("dialogue-history");
    const messages = document.getElementById("dialogue-messages");
    const load = document.getElementById("history-load");
    const status = document.getElementById("history-load-status");
    if (!history || !messages || !load || !status) return;

    let loading = false;
    let autoLoadBlocked = false;

    function message(role, content) {
        const article = document.createElement("article");
        article.className = `dialogue-message dialogue-${role}`;
        const author = document.createElement("p");
        author.className = "message-author";
        author.textContent = role === "user" ? "你" : "知行 · 成长教练";
        const body = document.createElement("div");
        body.className = "message-content";
        body.textContent = content;
        article.append(author, body);
        return article;
    }

    async function older() {
        const before = load.dataset.before;
        if (loading || !before) return;
        loading = true;
        load.disabled = true;
        status.textContent = "正在加载…";
        history.setAttribute("aria-busy", "true");
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 10000);
        try {
            const response = await fetch(`/web/coach/history?before=${encodeURIComponent(before)}`, {
                credentials: "same-origin",
                cache: "no-store",
                signal: controller.signal,
                headers: {"Accept": "application/json"},
            });
            if (!response.ok) throw new Error("history unavailable");
            const page = await response.json();
            if (!Array.isArray(page.turns) || page.turns.length > 40 ||
                !(page.before === null || (Number.isSafeInteger(page.before) && page.before > 0 && page.before < Number(before)))) {
                throw new Error("invalid history page");
            }
            const fragment = document.createDocumentFragment();
            for (const turn of page.turns) {
                if (typeof turn.user_content !== "string" || !["complete", "failed", "pending"].includes(turn.status) ||
                    (turn.status === "complete" && typeof turn.assistant_content !== "string")) {
                    throw new Error("invalid history turn");
                }
                fragment.append(message("user", turn.user_content));
                if (turn.status === "complete") {
                    fragment.append(message("coach", turn.assistant_content));
                } else {
                    const note = document.createElement("p");
                    note.className = "dialogue-state";
                    note.textContent = turn.status === "pending" ? "这条消息尚在处理中。" : "这次未能取得回复，原消息已保留。";
                    fragment.append(note);
                }
            }
            const height = history.scrollHeight;
            const top = history.scrollTop;
            messages.prepend(fragment);
            load.dataset.before = page.before === null ? "" : String(page.before);
            load.hidden = page.before === null;
            status.textContent = "";
            // Preserve the message being read while inserting older content above it.
            history.scrollTop = top + history.scrollHeight - height;
        } catch (_) {
            autoLoadBlocked = true;
            status.textContent = "暂时无法加载，请点击重试；若已退出，请重新登录。";
            load.textContent = "重新加载历史对话";
        } finally {
            clearTimeout(timeout);
            loading = false;
            load.disabled = false;
            history.removeAttribute("aria-busy");
        }
    }

    load.addEventListener("click", () => {
        autoLoadBlocked = false;
        older();
    });
    history.addEventListener("scroll", () => {
        if (history.scrollTop <= 24 && !autoLoadBlocked) older();
    }, {passive: true});
    // New visits and full-page form submissions open at the newest message.
    requestAnimationFrame(() => { history.scrollTop = history.scrollHeight; });
})();
