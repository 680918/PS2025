/* Explicit, current-page OCR. Models stay on-site; reviewed text alone is saved. */
export function initBookOCR({getCurrentPage, renderForOCR, jump}) {
    const panel = document.getElementById("book-ocr");
    if (!panel) return;
    const start = document.getElementById("ocr-start");
    const view = document.getElementById("ocr-view");
    const cancel = document.getElementById("ocr-cancel");
    const save = document.getElementById("ocr-save");
    const discard = document.getElementById("ocr-discard");
    const original = document.getElementById("ocr-original");
    const study = document.getElementById("ocr-study");
    const text = document.getElementById("ocr-text");
    const language = document.getElementById("ocr-language");
    const status = document.getElementById("ocr-status");
    const confidence = document.getElementById("ocr-confidence");
    const label = document.getElementById("ocr-result-label");
    let generation = 0, worker = null, pendingWorker = null, timer = null;
    let busy = false, dirty = false, saving = false, resultPage = null, digest = "", score = 0;
    const show = message => {status.textContent = message;};
    const open = () => {panel.hidden = false; view.hidden = false; panel.scrollIntoView({block: "start"});};
    const controls = () => {
        start.disabled = busy || dirty || saving;
        language.disabled = busy || saving || dirty;
        cancel.hidden = !busy;
        discard.hidden = !dirty || saving;
        save.disabled = busy || saving || !dirty || !text.value.trim();
        original.disabled = resultPage === null;
    };
    const stopWorker = async () => {
        clearTimeout(timer);
        if (worker) { const current = worker; worker = null; await current.terminate().catch(() => {}); }
    };
    async function responseJSON(response) {
        if (response.redirected || !response.headers.get("content-type")?.includes("application/json")) throw new Error("请复制识别结果后重新登录，再打开阅读页。");
        const value = await response.json();
        if (!response.ok) throw new Error(typeof value.error === "string" ? value.error : "这一页暂时无法处理。");
        return value;
    }
    async function recognize() {
        if (busy || dirty || saving) return;
        const turn = ++generation;
        busy = true;
        resultPage = getCurrentPage();
        study.hidden = true;
        text.value = ""; text.disabled = true; text.readOnly = false;
        confidence.textContent = "";
        label.textContent = "PDF 文件第 " + resultPage + " 页 · 识别结果（保存前可修改）";
        controls(); open();
        show("正在核对第 " + resultPage + " 页…");
        let canvas = null;
        let phase = "核对页码";
        timer = setTimeout(() => {
            if (!busy || turn !== generation) return;
            generation++;
            busy = false;
            void stopWorker(); controls();
            show("本页识别用时较长，已停止等待。可稍后重试，或补充文字版资料；本次未保存。");
        }, 90000);
        try {
            const page = await responseJSON(await fetch(panel.dataset.statusUrl + "?page=" + resultPage, {credentials: "same-origin", cache: "no-store"}));
            if (turn !== generation) return;
            digest = page.digest;
            if (page.state !== "missing") {
                text.value = page.text; text.disabled = false; text.readOnly = true;
                study.href = page.preview_url; study.hidden = false;
                show(page.state === "confirmed" ? "这一页已有核对保存的识别文字，本次没有重复处理。" : "这一页已有可引用文字，无需重复识别。请到正文缺失的页面识别。");
                return;
            }
            show("正在准备第 " + resultPage + " 页图像…");
            phase = "准备页图";
            canvas = await renderForOCR(resultPage);
            if (turn !== generation) return;
            phase = "加载识别组件";
            const {default: Tesseract} = await import("./vendor/tesseract/js/dist/tesseract.esm.min.js");
            const {createWorker} = Tesseract;
            const selectedLanguage = language.value === "chi_tra" ? "chi_tra" : "chi_sim";
            pendingWorker = createWorker([selectedLanguage, "eng"], 1, {
                workerPath: "/static/vendor/tesseract/js/dist/worker.min.js",
                corePath: "/static/vendor/tesseract/core",
                langPath: "/static/vendor/tesseract/lang",
                workerBlobURL: false,
                cacheMethod: "none",
                logger: message => {
                    if (turn !== generation) return;
                    const percent = Math.max(0, Math.min(100, Math.round(Number(message.progress || 0) * 100)));
                    show(message.status === "recognizing text"
                        ? "正在识别第 " + resultPage + " 页 · " + percent + "%（未调用 AI）"
                        : "正在准备本地识别组件和语言模型，请稍候…");
                },
            });
            phase = "准备语言模型";
            const instance = await pendingWorker;
            pendingWorker = null;
            if (turn !== generation) { await instance.terminate(); return; }
            worker = instance;
            phase = "识别正文";
            await worker.setParameters({user_defined_dpi: "200", preserve_interword_spaces: "1"});
            const {data} = await worker.recognize(canvas);
            if (turn !== generation) return;
            const value = typeof data.text === "string" ? data.text.trim() : "";
            if (!value || value.length > 40000) throw new Error("未取得可保存的正文，或本页超过4万字。请核对页面、语言和图像清晰度，再决定是否重试。");
            text.value = value; text.disabled = false;
            score = Number.isFinite(data.confidence) ? Math.max(0, Math.min(100, Math.round(data.confidence))) : 0;
            confidence.textContent = "机器识别置信度：" + score + "% · 不是学习评分；请对照原页检查错字、标点和段落顺序。";
            dirty = true;
            show("第 " + resultPage + " 页识别完成，尚未保存。请核对或修改文字，再明确保存。");
        } catch (error) {
            panel.dataset.failure = phase + ":" + error.name;
            if (turn === generation) show(error.message?.startsWith("请") || error.message?.startsWith("未取得") ? error.message : "本地识别暂时未完成。可重新尝试；本次没有保存文字，也没有调用 AI。");
        } finally {
            if (canvas) canvas.width = canvas.height = 0;
            if (turn === generation) {busy = false; await stopWorker(); controls();}
        }
    }
    start.addEventListener("click", () => {void recognize();});
    view.addEventListener("click", open);
    original.addEventListener("click", () => {if (resultPage !== null) jump(resultPage);});
    text.addEventListener("input", controls);
    discard.addEventListener("click", () => {
        if (busy || saving) return;
        dirty = false; text.value = ""; text.disabled = true; study.hidden = true;
        confidence.textContent = ""; controls(); show("已放弃这次未保存结果，原书和已保存文字不变。");
    });
    cancel.addEventListener("click", () => {
        if (!busy) return;
        generation++; busy = false; void stopWorker(); controls();
        show("已取消本次识别，未保存文字。若组件仍在准备，准备结束后会自动释放。");
    });
    save.addEventListener("click", async () => {
        if (busy || saving || !dirty || resultPage === null || !text.value.trim()) return;
        saving = true; text.readOnly = true; controls();
        show("正在保存核对后的第 " + resultPage + " 页文字…");
        try {
            const data = await responseJSON(await fetch(panel.dataset.statusUrl, {
                method: "POST", credentials: "same-origin", cache: "no-store",
                headers: {Accept: "application/json"},
                body: new URLSearchParams({csrf: panel.dataset.csrf, page: String(resultPage), text: text.value, confidence: String(score), digest}),
            }));
            if (data.status !== "saved" || data.page !== resultPage) throw new Error("invalid save");
            dirty = false;
            text.value = data.text;
            study.href = data.preview_url; study.hidden = false;
            show("第 " + resultPage + " 页文字已保存，可选段提问。原 PDF 和已有学习位置保持不变；刷新页面可更新文字覆盖统计。");
        } catch (error) {
            text.readOnly = false;
            show(error.message && !error.message.includes("invalid") ? error.message + " 文字仍保留在此处，请先复制留存。" : "保存结果暂未确认，文字仍保留。请先复制后刷新核对，系统不会自动重试。");
        } finally {saving = false; controls();}
    });
    window.addEventListener("beforeunload", event => {
        if (!dirty && !busy && !saving) return;
        event.preventDefault(); event.returnValue = "";
    });
    window.addEventListener("pagehide", () => {generation++; busy = false; void stopWorker();});
    controls();
}
