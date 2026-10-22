/* A reading bookmark is separate from Coach learning progress. No AI requests. */
export function initReadingPosition(root, getCurrent) {
    const form = document.getElementById("reader-bookmark");
    const status = document.getElementById("bookmark-status");
    if (!form || !status) return () => {};
    let revision = Number(form.elements.revision.value);
    let saved = Number(root.dataset.savedPage);
    let timer = null, busy = false, blocked = false, stopped = false;
    const show = value => { status.textContent = value; };
    const confirmed = () => {
        const label = document.getElementById("reader-saved-summary");
        if (label && saved > 0) label.textContent = "已记住第 " + saved + " 页";
    };
    const sync = () => {
        form.elements.page.value = String(getCurrent());
        form.elements.revision.value = String(revision);
    };
    async function save(explicit = false) {
        clearTimeout(timer); sync();
        if (busy || stopped || (blocked && !explicit)) return;
        const page = getCurrent();
        if (page === saved && !blocked) return;
        busy = true;
        show("正在记住第 " + page + " 页阅读位置…");
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 10000);
        try {
            const response = await fetch(form.action, {
                method: "POST", credentials: "same-origin", cache: "no-store",
                headers: {Accept: "application/json"}, signal: controller.signal,
                body: new URLSearchParams({csrf: form.elements.csrf.value, page: String(page), revision: String(revision)}),
            });
            if (response.status === 429) throw new Error("保存较频繁，请稍后再点击记住当前页。");
            if (response.redirected || !response.headers.get("content-type")?.includes("application/json")) throw new Error("请重新登录后打开阅读页，再记住位置。");
            const data = await response.json();
            if (response.status === 409 && Number.isSafeInteger(data.revision) && Number.isSafeInteger(data.page)) {
                revision = data.revision; saved = data.page; blocked = true; sync(); confirmed();
                show("另一个阅读窗口已记到第 " + saved + " 页；没有覆盖。若要改记本页，请点击“记住当前页”。");
                return;
            }
            if (!response.ok) throw new Error(typeof data.error === "string" ? data.error : "阅读位置暂未确认，请稍后手动记住当前页。");
            if (data.status !== "saved" || data.page !== page || !Number.isSafeInteger(data.revision)) throw new Error("阅读位置暂未确认，请刷新核对；本页仍可阅读。");
            revision = data.revision; saved = page; blocked = false; sync(); confirmed();
            show("已记住阅读第 " + page + " 页 · 不计为已讲解或已掌握。");
        } catch (error) {
            blocked = true;
            show(error.name === "AbortError" ? "保存结果暂未确认，请刷新核对；不会自动重试。" : /[\u3400-\u9fff]/.test(error.message || "") ? error.message : "阅读位置暂时无法保存，可稍后手动记住当前页；本页仍可阅读。");
        } finally {
            clearTimeout(timeout); busy = false;
            if (!blocked && !stopped && getCurrent() !== saved) timer = setTimeout(() => {void save();}, 1500);
        }
    }
    form.addEventListener("submit", event => {event.preventDefault(); void save(true);});
    window.addEventListener("pagehide", () => {stopped = true; clearTimeout(timer);});
    window.addEventListener("pageshow", () => {stopped = false;});
    return () => {
        sync(); clearTimeout(timer);
        if (blocked || stopped) return;
        if (getCurrent() === saved) {show("已记住阅读第 " + saved + " 页 · 不计为已讲解或已掌握。"); return;}
        show("停留后自动记住阅读页，也可点击“记住当前页”。");
        timer = setTimeout(() => {void save();}, 1500);
    };
}
