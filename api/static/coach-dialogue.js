(() => {
    "use strict";
    const history = document.getElementById("dialogue-history");
    const messages = document.getElementById("dialogue-messages");
    const load = document.getElementById("history-load");
    const status = document.getElementById("history-load-status");
    if (!history || !messages || !load || !status) return;

    let loading = false;
    let autoLoadBlocked = false;
    let sending = false;

    function message(role, content, rendered) {
        const article = document.createElement("article");
        article.className = `dialogue-message dialogue-${role}`;
        const author = document.createElement("p");
        author.className = "message-author";
        author.textContent = role === "user" ? "你" : "知行 · 成长教练";
        const body = document.createElement("div");
        body.className = "message-content";
        if (role === "coach" && typeof rendered === "string") {
            // Only the same-origin history endpoint supplies this server-rendered,
            // HTML-disabled Markdown. User messages always remain plain text.
            body.classList.add("markdown-content");
            body.innerHTML = rendered;
        } else {
            body.textContent = content;
        }
        article.append(author, body);
        return article;
    }

    async function older() {
        const before = load.dataset.before;
        if (loading || sending || !before) return;
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
                    (turn.status === "complete" && (typeof turn.assistant_content !== "string" || typeof turn.assistant_html !== "string"))) {
                    throw new Error("invalid history turn");
                }
                fragment.append(message("user", turn.user_content));
                if (turn.status === "complete") {
                    const reply = message("coach", turn.assistant_content, turn.assistant_html);
                    for (const source of (turn.citations || [])) {
                        const details = document.createElement("details");
                        details.className = "citation";
                        const summary = document.createElement("summary");
                        summary.textContent = `引用依据：${source.title} · ${source.locator}`;
                        const excerpt = document.createElement("p");
                        excerpt.textContent = source.excerpt;
                        details.append(summary, excerpt);
                        reply.append(details);
                    }
                    fragment.append(reply);
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
    function showBeginning(element) {
        if (!element) return;
        history.scrollTop += element.getBoundingClientRect().top - history.getBoundingClientRect().top - 8;
    }

    for (const form of document.querySelectorAll('form[action="/web/coach/message"]')) {
        form.addEventListener("submit", async event => {
            event.preventDefault();
            if (sending) {
                return;
            }
            sending = true;
            // Keep the existing form fields, nonce, CSRF and server protections.
            // Stay on this page while awaiting the one request, so waiting is visible.
            const fields = new URLSearchParams(new FormData(form));
            const input = form.querySelector('textarea[name="message"]');
            let optimistic = null;
            if (input) {
                input.readOnly = true;
                optimistic = message("user", input.value);
                messages.append(optimistic);
            }
            for (const button of document.querySelectorAll('form[action="/web/coach/message"] button')) {
                button.disabled = true;
            }
            const waiting = document.createElement("article");
            waiting.className = "dialogue-message dialogue-coach dialogue-waiting";
            waiting.setAttribute("role", "status");
            const dots = document.createElement("span");
            dots.className = "waiting-dots";
            dots.setAttribute("aria-hidden", "true");
            for (let index = 0; index < 3; index++) dots.append(document.createElement("i"));
            waiting.append(dots, document.createTextNode("成长教练正在思考，请稍候…"));
            messages.append(waiting);
            history.setAttribute("aria-busy", "true");
            showBeginning(waiting);
            try {
                // The hidden field named "action" shadows form.action in browsers.
                const response = await fetch(form.getAttribute("action"), {
                    method: "POST",
                    credentials: "same-origin",
                    cache: "no-store",
                    headers: {"Accept": "application/json"},
                    body: fields,
                });
                if (response.redirected && new URL(response.url).pathname === "/web/login") {
                    window.location.assign("/web/login");
                    return;
                }
                if ((response.status === 429 || response.status === 409) && (response.headers.get("content-type") || "").includes("application/json")) {
                    const rejection = await response.json();
                    if (((response.status === 429 && rejection.code === "daily_ai_limit") || (response.status === 409 && rejection.code === "review_state_changed")) && rejection.sent === false && typeof rejection.error === "string" && rejection.error.length <= 400) {
                        if (optimistic) optimistic.remove();
                        history.removeAttribute("aria-busy");
                        waiting.className = "dialogue-message dialogue-coach dialogue-state";
                        waiting.textContent = rejection.error;
                        const usage = document.createElement("a");
                        usage.className = "text-link";
                        usage.href = response.status === 409 ? "/web/welcome#coach-dialog" : "/web/usage";
                        usage.textContent = response.status === 409 ? " 复制填写后刷新对话 →" : " 查看 AI 用量 →";
                        if (response.status === 409) usage.addEventListener("click", event => {
                            event.preventDefault();
                            window.location.reload();
                        });
                        waiting.append(usage);
                        if (input) input.readOnly = false;
                        for (const button of document.querySelectorAll('form[action="/web/coach/message"] button')) button.disabled = false;
                        sending = false;
                        showBeginning(waiting);
                        return;
                    }
                    throw new Error("request not completed");
                }
                if (!response.ok) throw new Error("request not completed");
                const result = await response.json();
                if (result.redirect !== "/web/welcome#coach-dialog") throw new Error("invalid response");
                // The current URL may already have this fragment. Assigning it
                // again would keep the old waiting page, so reload the GET view.
                window.location.reload();
            } catch (_) {
                history.removeAttribute("aria-busy");
                waiting.classList.remove("dialogue-waiting");
                waiting.classList.add("dialogue-state");
                waiting.textContent = "本次请求结果尚未确认。请先刷新查看已有记录，避免重复发送；若已退出，请重新登录。";
                const link = document.createElement("a");
                link.className = "text-link";
                link.href = "/web/welcome#coach-dialog";
                link.textContent = " 刷新查看记录 →";
                link.addEventListener("click", event => {
                    event.preventDefault();
                    window.location.reload();
                });
                waiting.append(link);
                showBeginning(waiting);
            }
        });
    }
    // Start reading each newest reply from its first line, including long replies.
    requestAnimationFrame(() => { showBeginning(document.getElementById("latest-reply")); });
})();
