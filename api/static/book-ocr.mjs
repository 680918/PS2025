/* Local PDF OCR, at most five pages per explicit job. Only reviewed pages are saved. */
export function ocrPageRange(first, last, total) {
    if (![first, last, total].every(Number.isSafeInteger) || first < 1 || last < first || last > total || total > 1500) throw new Error("请输入原书范围内的起止文件页码。");
    if (last - first + 1 > 5) throw new Error("每批最多识别5页，请缩小范围后再开始。");
    return Array.from({length: last - first + 1}, (_, index) => first + index);
}
export function initBookOCR({getCurrentPage, renderForOCR, jump}) {
    const panel = document.getElementById("book-ocr");
    if (!panel) return;
    const byId = id => document.getElementById(id);
    const start = byId("ocr-start"), view = byId("ocr-view"), cancel = byId("ocr-cancel");
    const save = byId("ocr-save"), discard = byId("ocr-discard"), original = byId("ocr-original");
    const study = byId("ocr-study"), text = byId("ocr-text"), language = byId("ocr-language");
    const status = byId("ocr-status"), confidence = byId("ocr-confidence"), label = byId("ocr-result-label");
    const rangeOpen = byId("ocr-range-open"), rangeForm = byId("ocr-range-form");
    const rangeStart = byId("ocr-range-start"), rangeEnd = byId("ocr-range-end"), rangeGo = byId("ocr-range-go");
    const queue = byId("ocr-results"), summary = byId("ocr-queue-summary");
    const previous = byId("ocr-result-previous"), next = byId("ocr-result-next");
    const total = Number(byId("book-reader").dataset.total);
    let entries = [], selected = -1, activeJob = null, saving = false;
    const show = message => {status.textContent = message;};
    const dirty = () => entries.some(entry => entry.state === "review");
    const current = () => entries[selected];
    const open = () => {
        panel.hidden = false; view.hidden = false;
        const toolbar = document.querySelector(".reader-toolbar");
        const offset = getComputedStyle(toolbar).position === "sticky" ? toolbar.getBoundingClientRect().height + 12 : 12;
        window.scrollTo({top: window.scrollY + panel.getBoundingClientRect().top - offset, behavior:"instant"});
    };
    const stateLabels = {waiting:"待处理", working:"正在识别", review:"待核对", existing:"已有文字", saved:"已保存", failed:"未完成", cancelled:"未处理", discarded:"已放弃"};
    function controls() {
        const busy = !!activeJob, entry = current();
        start.disabled = rangeGo.disabled = rangeOpen.disabled = busy || saving || dirty();
        rangeStart.disabled = rangeEnd.disabled = language.disabled = busy || saving || dirty();
        rangeStart.max = rangeEnd.max = String(total);
        cancel.hidden = !busy;
        cancel.disabled = !!activeJob?.cancelled;
        discard.hidden = !dirty() || busy || saving;
        save.disabled = busy || saving || entry?.state !== "review" || !entry.text.trim();
        original.disabled = !entry;
        text.disabled = busy || saving || !entry || !["review", "existing", "saved"].includes(entry.state);
        text.readOnly = saving || entry?.state !== "review";
        previous.disabled = busy || saving || selected <= 0;
        next.disabled = busy || saving || selected < 0 || selected >= entries.length - 1;
        for (const button of queue.querySelectorAll("button")) button.disabled = busy || saving;
    }
    function render() {
        const entry = current();
        queue.replaceChildren();
        entries.forEach((item, index) => {
            const button = document.createElement("button");
            button.type = "button"; button.className = "button button-outline";
            button.textContent = "第" + item.page + "页 · " + stateLabels[item.state];
            button.setAttribute("aria-pressed", String(index === selected));
            button.addEventListener("click", () => select(index));
            queue.append(button);
        });
        summary.textContent = entries.length ? "本批 " + entries.length + " 页 · 待核对 " + entries.filter(item => item.state === "review").length + " 页 · 可引用 " + entries.filter(item => ["existing", "saved"].includes(item.state)).length + " 页。未核对文字不会自动入库。" : "每批最多5页；逐页核对后分别保存，已有文字不覆盖。";
        label.textContent = entry ? "PDF 文件第 " + entry.page + " 页 · 识别结果（保存前可修改）" : "识别结果（保存前可修改）";
        text.value = entry?.text || "";
        confidence.textContent = entry?.state === "review" ? "机器识别置信度：" + entry.score + "% · 不是学习评分；请对照原页检查错字、标点和段落顺序。" : "";
        study.hidden = !entry || !["existing", "saved"].includes(entry.state);
        if (!study.hidden) study.href = entry.url;
        else study.removeAttribute("href");
        controls();
    }
    function select(index) {
        if (activeJob || saving || index < 0 || index >= entries.length) return;
        selected = index; render();
        const entry = current();
        show(entry.state === "review" ? "第 " + entry.page + " 页识别完成，尚未保存。请核对或修改文字，再明确保存。" : entry.state === "saved" ? "第 " + entry.page + " 页已核对保存，可选段学习。" : entry.state === "existing" ? "这一页已有可引用文字，本次没有重复识别或覆盖。" : "这一页没有新的识别结果，可重新选择范围后处理。");
    }
    async function responseJSON(response) {
        if (response.status === 429) throw new Error("操作较频繁，请稍后再试；已完成结果仍保留。");
        if (response.redirected) throw new Error("请复制未保存结果后重新登录，再打开阅读页。");
        if (!response.headers.get("content-type")?.includes("application/json")) throw new Error(response.status >= 500 ? "服务暂时无法处理这一页，已完成结果仍保留。" : "页面响应无法确认，请先复制未保存结果后重新打开阅读页。");
        const value = await response.json();
        if (!response.ok) throw new Error(typeof value.error === "string" ? value.error : "这一页暂时无法处理。");
        return value;
    }
    async function release(job) {
        if (job.worker) {const worker = job.worker; job.worker = null; await worker.terminate().catch(() => {});}
    }
    function cancelJob(reason) {
        const job = activeJob;
        if (!job || job.cancelled) return;
        job.cancelled = true; job.reason = reason; job.stop(); job.controller.abort();
        void release(job); controls();
        show(reason + " 正在释放组件；已完成的未保存结果将保留。");
    }
    async function workerFor(job) {
        if (job.worker) return job.worker;
        const {default: Tesseract} = await import("./vendor/tesseract/js/dist/tesseract.esm.min.js");
        if (job.cancelled) throw new Error("cancelled");
        const instance = await Tesseract.createWorker([job.language, "eng"], 1, {
            workerPath: "/static/vendor/tesseract/js/dist/worker.min.js",
            corePath: "/static/vendor/tesseract/core", langPath: "/static/vendor/tesseract/lang",
            workerBlobURL: false, cacheMethod: "none",
            logger: message => {
                if (activeJob !== job || job.cancelled) return;
                const percent = Math.max(0, Math.min(100, Math.round(Number(message.progress || 0) * 100)));
                show(message.status === "recognizing text" ? "本批 " + (job.index + 1) + " / " + entries.length + " · 正在识别 PDF 第 " + entries[job.index].page + " 页 · " + percent + "%（未调用 AI）" : "正在准备本地识别组件和语言模型，请稍候…");
            },
        });
        if (job.cancelled) {await instance.terminate(); throw new Error("cancelled");}
        job.worker = instance;
        await instance.setParameters({user_defined_dpi:"200", preserve_interword_spaces:"1"});
        return instance;
    }
    async function recognize(numbers) {
        if (activeJob || saving || dirty()) return;
        entries = numbers.map(page => ({page, state:"waiting", text:"", score:0, digest:"", url:""}));
        selected = 0;
        let stop;
        const stopped = new Promise(resolve => {stop = resolve;});
        const job = {worker:null, cancelled:false, controller:new AbortController(), language:language.value === "chi_tra" ? "chi_tra" : "chi_sim", index:0, reason:"", stop, stopped};
        activeJob = job; render(); open();
        try {
            for (let index = 0; index < entries.length && !job.cancelled; index++) {
                job.index = index;
                const entry = entries[index];
                let canvas = null;
                entry.state = "working"; render();
                show("本批 " + (index + 1) + " / " + entries.length + " · 正在核对 PDF 第 " + entry.page + " 页…");
                const timer = setTimeout(() => cancelJob("本页识别等待超过90秒，已停止本批处理。"), 90000);
                try {
                    const page = await responseJSON(await fetch(panel.dataset.statusUrl + "?page=" + entry.page, {credentials:"same-origin", cache:"no-store", signal:job.controller.signal}));
                    if (job.cancelled) break;
                    if (page.page !== entry.page || typeof page.digest !== "string") throw new Error("invalid page");
                    entry.digest = page.digest;
                    if (page.state !== "missing") {
                        entry.state = "existing"; entry.text = page.text; entry.url = page.preview_url;
                        continue;
                    }
                    canvas = await renderForOCR(entry.page);
                    if (job.cancelled) break;
                    const worker = await workerFor(job);
                    if (job.cancelled) break;
                    // Terminating a worker need not settle its pending recognition promise.
                    const result = await Promise.race([worker.recognize(canvas), job.stopped]);
                    if (job.cancelled || !result) break;
                    const {data} = result;
                    const value = typeof data.text === "string" ? data.text.trim() : "";
                    if (!value || value.length > 40000) throw new Error("未取得可保存的正文，或本页超过4万字。请核对页码、语言和图像清晰度。");
                    entry.text = value;
                    entry.score = Number.isFinite(data.confidence) ? Math.max(0, Math.min(100, Math.round(data.confidence))) : 0;
                    entry.state = "review";
                } finally {clearTimeout(timer); if (canvas) canvas.width = canvas.height = 0;}
            }
        } catch (error) {
            if (!job.cancelled) {
                entries[job.index].state = "failed";
                job.reason = /[\u3400-\u9fff]/.test(error.message || "") ? error.message : "本地识别暂未完成，已停止本批处理。";
            }
        } finally {
            await release(job);
            for (const entry of entries) if (["waiting", "working"].includes(entry.state)) entry.state = "cancelled";
            activeJob = null;
            const review = entries.findIndex(entry => entry.state === "review");
            select(review >= 0 ? review : 0);
            if (job.reason) show(job.reason + " 已完成的结果仍保留，请核对后分别保存；未完成页不会自动重试。");
        }
    }
    start.addEventListener("click", () => {void recognize([getCurrentPage()]);});
    rangeOpen.addEventListener("click", () => {
        if (activeJob || saving || dirty()) return;
        rangeStart.value = String(getCurrentPage()); rangeEnd.value = String(Math.min(total, getCurrentPage() + 4));
        open(); rangeStart.focus({preventScroll:true});
    });
    rangeForm.addEventListener("submit", event => {
        event.preventDefault();
        try {void recognize(ocrPageRange(Number(rangeStart.value), Number(rangeEnd.value), total));}
        catch (error) {show(error.message);}
    });
    view.addEventListener("click", open);
    original.addEventListener("click", () => {if (current()) jump(current().page);});
    previous.addEventListener("click", () => select(selected - 1));
    next.addEventListener("click", () => select(selected + 1));
    text.addEventListener("input", () => {if (current()?.state === "review") current().text = text.value; controls();});
    discard.addEventListener("click", () => {
        if (activeJob || saving) return;
        for (const entry of entries) if (entry.state === "review") {entry.state = "discarded"; entry.text = "";}
        render(); show("已放弃本批全部未保存结果，原书和已保存文字不变。");
    });
    cancel.addEventListener("click", () => cancelJob("已取消本批识别。"));
    save.addEventListener("click", async () => {
        const entry = current();
        if (activeJob || saving || entry?.state !== "review" || !entry.text.trim()) return;
        saving = true; controls(); show("正在保存核对后的第 " + entry.page + " 页文字…");
        const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 15000);
        try {
            const data = await responseJSON(await fetch(panel.dataset.statusUrl, {
                method:"POST", credentials:"same-origin", cache:"no-store", signal:controller.signal,
                headers:{Accept:"application/json"}, body:new URLSearchParams({csrf:panel.dataset.csrf, page:String(entry.page), text:entry.text, confidence:String(entry.score), digest:entry.digest}),
            }));
            if (data.status !== "saved" || data.page !== entry.page) throw new Error("invalid save");
            entry.state = "saved"; entry.text = data.text; entry.url = data.preview_url;
            show("第 " + entry.page + " 页文字已保存，可选段提问。原 PDF 和已有学习位置保持不变；刷新页面可更新文字覆盖统计。");
        } catch (error) {
            show((/[\u3400-\u9fff]/.test(error.message || "") ? error.message : "保存结果暂未确认。") + " 文字仍保留，请先复制留存，再刷新核对；系统不会自动重试。");
        } finally {clearTimeout(timeout); saving = false; render();}
    });
    window.addEventListener("beforeunload", event => {if (dirty() || activeJob || saving) {event.preventDefault(); event.returnValue = "";}});
    window.addEventListener("pagehide", () => cancelJob("页面已离开，本批识别停止。"));
    rangeStart.value = String(getCurrentPage()); rangeEnd.value = String(Math.min(total, getCurrentPage() + 4));
    render();
}
