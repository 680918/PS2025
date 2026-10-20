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
    const latest = document.getElementById("dialogue-latest");
    function updateReadingControl() {
        if (!latest) return;
        latest.hidden = false;
        latest.disabled = !messages.querySelector(".dialogue-message");
    }
    if (latest) {
        latest.addEventListener("click", () => {
            const target = messages.lastElementChild;
            if (!target || latest.disabled) return;
            history.focus({preventScroll: true});
            showBeginning(target);
        });
    }
    updateReadingControl();

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

    function failedMessage() {
        const wrapper = document.createElement("div");
        wrapper.className = "dialogue-state dialogue-failed";
        const text = document.createElement("p");
        text.textContent = "这次未能取得回复，原消息已保留。系统不会自动重试。";
        const button = document.createElement("button");
        button.type = "button";
        button.className = "dialogue-recover";
        button.textContent = "放回输入框修改";
        const input = document.getElementById("coach-message");
        button.disabled = !input || input.disabled || input.readOnly || sending;
        const note = document.createElement("p");
        note.className = "dialogue-recovery-note";
        note.setAttribute("role", "status");
        wrapper.append(text, button, note);
        return wrapper;
    }

    messages.addEventListener("click", event => {
        const button = event.target.closest("button.dialogue-recover");
        if (!button || !messages.contains(button)) return;
        const wrapper = button.closest(".dialogue-failed");
        const note = wrapper.querySelector(".dialogue-recovery-note");
        const input = document.getElementById("coach-message");
        if (!input || input.disabled || input.readOnly || sending) {
            note.textContent = "当前暂不能编辑。请先核对发送状态，或刷新查看记录。";
            return;
        }
        const previous = wrapper.previousElementSibling;
        const body = previous && previous.classList.contains("dialogue-user") && previous.querySelector(".message-content");
        const text = body && body.textContent;
        if (typeof text !== "string" || text.length < 1 || text.length > 2000) return;
        if (input.value && input.value !== text) {
            note.textContent = "输入框已有文字。请先保留或清空现有填写，再放回这条消息。";
            return;
        }
        input.value = text;
        input.focus();
        note.textContent = "已放回输入框。请核对当前主题与资料，修改后再发送。";
    });

    function addStatusCheck(container, nonce) {
        if (!/^[A-Za-z0-9_-]{43}$/.test(nonce || "")) return;
        const button = document.createElement("button");
        button.type = "button";
        button.className = "dialogue-check-status";
        button.textContent = "核对发送状态";
        const note = document.createElement("p");
        note.className = "dialogue-check-note";
        note.setAttribute("role", "status");
        button.addEventListener("click", async () => {
            button.disabled = true;
            note.textContent = "正在核对已保存的状态…";
            const controller = new AbortController();
            const timeout = setTimeout(() => controller.abort(), 15000);
            try {
                const response = await fetch("/web/coach/status?" + new URLSearchParams({nonce}), {
                    credentials: "same-origin", cache: "no-store", signal: controller.signal,
                    headers: {"Accept": "application/json"},
                });
                if (response.status === 401) {
                    note.textContent = "登录已过期。请先复制尚未发送的文字，再重新登录。";
                    const link = container.querySelector(".dialogue-refresh");
                    if (link) { link.href = "/web/login"; link.textContent = " 复制文字后重新登录 →"; }
                    return;
                }
                if (response.status === 429) {
                    note.textContent = "核对较频繁，请稍后再试；核对不会重新发送。";
                    return;
                }
                if (!response.ok) throw new Error("state unavailable");
                const result = await response.json();
                if (result.status === "complete") { window.location.reload(); return; }
                const notes = {
                    pending: "这条消息仍在处理。稍后可再次核对，核对不会重新发送。",
                    failed: "这次已受理，但未能取得回复。刷新后可将原消息放回输入框修改；再次发送将按新请求处理。",
                    expired: "原请求已超过处理时限。请先刷新查看记录，需要时再重新编辑。",
                    missing: "尚未查到这次请求，不能据此确认未发送。请稍后再核对，或复制文字后刷新。",
                };
                if (!Object.hasOwn(notes, result.status)) throw new Error("invalid state");
                note.textContent = notes[result.status];
            } catch (_) {
                note.textContent = "暂时无法核对。请保留文字，稍后再试；系统不会自动重发。";
            } finally {
                clearTimeout(timeout);
                button.disabled = false;
            }
        });
        container.append(button, note);
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
                    for (const [index, source] of (turn.citations || []).entries()) {
                        const details = document.createElement("details");
                        details.className = "citation";
                        const summary = document.createElement("summary");
                        summary.textContent = `引用依据：${source.title} · ${source.locator}`;
                        const excerpt = document.createElement("p");
                        excerpt.textContent = source.excerpt;
                        details.append(summary, excerpt);
                        const href = (turn.citation_links || [])[index];
                        if (typeof href === "string" && /^\/web\/conversations\/[1-9][0-9]{0,18}\/sources\/[1-9][0-9]{0,2}$/.test(href)) {
                            const link = document.createElement("a");
                            link.className = "text-link";
                            link.href = href;
                            link.target = "_blank";
                            link.rel = "noopener";
                            link.textContent = "核对原文（新标签页） →";
                            details.append(link);
                        }
                        reply.append(details);
                    }
                    fragment.append(reply);
                } else {
                    const note = turn.status === "pending" ? document.createElement("p") : failedMessage();
                    if (turn.status === "pending") {
                        note.className = "dialogue-state";
                        note.textContent = "这条消息尚在处理中。";
                    }
                    fragment.append(note);
                }
            }
            const height = history.scrollHeight;
            const top = history.scrollTop;
            messages.prepend(fragment);
            document.dispatchEvent(new Event("coach-content-ready"));
            updateReadingControl();
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
        const shortcutInput = form.querySelector('textarea[name="message"]');
        if (shortcutInput) {
            const help = document.getElementById("coach-input-help");
            if (help) help.hidden = false;
            shortcutInput.setAttribute("aria-keyshortcuts", "Control+Enter Meta+Enter");
            shortcutInput.addEventListener("keydown", event => {
                if (event.key !== "Enter" || !(event.ctrlKey || event.metaKey) ||
                    event.shiftKey || event.altKey || event.isComposing || event.keyCode === 229 || event.repeat) return;
                event.preventDefault();
                if (sending || shortcutInput.disabled || shortcutInput.readOnly) return;
                const submit = form.querySelector('button[type="submit"]');
                if (submit && !submit.disabled) form.requestSubmit(submit);
            });
        }
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
            for (const button of document.querySelectorAll('form[action="/web/coach/message"] button[type="submit"]')) {
                button.disabled = true;
            }
            for (const button of messages.querySelectorAll(".dialogue-recover")) button.disabled = true;
            const waiting = document.createElement("article");
            waiting.className = "dialogue-message dialogue-coach dialogue-waiting";
            waiting.setAttribute("role", "status");
            const dots = document.createElement("span");
            dots.className = "waiting-dots";
            dots.setAttribute("aria-hidden", "true");
            for (let index = 0; index < 3; index++) dots.append(document.createElement("i"));
            waiting.append(dots, document.createTextNode("成长教练正在思考，请稍候…"));
            messages.append(waiting);
            updateReadingControl();
            history.setAttribute("aria-busy", "true");
            showBeginning(waiting);
            const controller = new AbortController();
            const timeout = setTimeout(() => controller.abort(), 60000);
            let loginRequired = false;
            try {
                // The hidden field named "action" shadows form.action in browsers.
                const response = await fetch(form.getAttribute("action"), {
                    method: "POST",
                    credentials: "same-origin",
                    cache: "no-store",
                    headers: {"Accept": "application/json"},
                    body: fields,
                    signal: controller.signal,
                });
                if (response.redirected && new URL(response.url).pathname === "/web/login") {
                    loginRequired = true;
                    throw new Error("login expired");
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
                        for (const button of document.querySelectorAll('form[action="/web/coach/message"] button[type="submit"]')) button.disabled = false;
                        for (const button of messages.querySelectorAll(".dialogue-recover")) button.disabled = false;
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
                waiting.textContent = loginRequired ? "登录已过期。输入仍保留，请先复制文字，再重新登录。" : "本次请求结果尚未确认。输入仍保留，可以先核对状态或复制后刷新查看记录，避免重复发送。";
                const link = document.createElement("a");
                link.className = "text-link dialogue-refresh";
                link.href = loginRequired ? "/web/login" : "/web/welcome#coach-dialog";
                link.textContent = loginRequired ? " 复制文字后重新登录 →" : " 复制文字后刷新查看记录 →";
                link.addEventListener("click", event => {
                    if (new URL(link.href).pathname === "/web/login") return;
                    event.preventDefault();
                    window.location.reload();
                });
                waiting.append(link);
                if (!loginRequired) addStatusCheck(waiting, fields.get("nonce"));
                showBeginning(waiting);
            } finally {
                clearTimeout(timeout);
            }
        });
    }
    // Start reading each newest reply from its first line, including long replies.
    requestAnimationFrame(() => { showBeginning(document.getElementById("latest-reply")); });
})();
