/* Local, lazy PDF/text reading. Browsing never calls Coach or writes learning progress. */
const root = document.getElementById("book-reader");
const pagesNode = document.getElementById("reader-pages");
const status = document.getElementById("reader-status");
const input = document.getElementById("reader-page-number");
const previous = document.getElementById("reader-previous");
const next = document.getElementById("reader-next");
const retry = document.getElementById("reader-retry");
const progress = document.getElementById("reader-progress");
const direct = document.getElementById("reader-direct");
const total = Number(root?.dataset.total);
const initial = Number(root?.dataset.initial);
const isPDF = root?.dataset.kind === "pdf";
let pdf = null;
let pdfjs = null;
let current = initial;
let zoom = 1;
let running = false;
let stopped = false;
let readerReady = false;
let loadingPhase = "准备阅读组件";
let firstViewport = {width: 600, height: 850};
const sheets = new Map();
const ready = new Map();
const queue = new Set();
const batches = new Map();

function announce(text) { status.textContent = text; }
function position(number) {
    current = number;
    input.value = String(number);
    previous.disabled = number <= 1;
    next.disabled = number >= total;
    if (direct) direct.hash = "page=" + number;
    announce("当前第 " + number + " / " + total + " 页 · 向下滚动继续阅读；阅读不会计为已讲解。");
    const url = new URL(location.href);
    url.searchParams.set("page", String(number));
    history.replaceState(null, "", url);
}
function fitWidth() {
    return Math.min(960, Math.max(180, pagesNode.clientWidth - 24)) * zoom;
}
function trim() {
    // At most five rasterized pages remain; the lightweight placeholders keep scrolling stable.
    if (!isPDF) return;
    for (const [number, entry] of ready) {
        if (Math.abs(number - current) <= 2) continue;
        entry.canvas.width = entry.canvas.height = 0;
        entry.frame.replaceChildren();
        entry.page.cleanup();
        ready.delete(number);
        delete sheets.get(number).dataset.loaded;
    }
}
function enqueue(number) {
    if (number < 1 || number > total || ready.has(number)) return;
    queue.add(number);
    void drain();
}
function textBatch(number) {
    const start = Math.floor((number - 1) / 5) * 5 + 1;
    if (!batches.has(start)) {
        const pending = fetch(root.dataset.textPages + "?start=" + start, {
            credentials: "same-origin", cache: "no-store", headers: {Accept: "application/json"},
        }).then(async response => {
            if (!response.ok || !response.headers.get("content-type")?.includes("application/json")) {
                throw new Error("Reading unavailable");
            }
            const data = await response.json();
            if (data.page_count !== total || !Array.isArray(data.pages) || data.pages.length > 5) {
                throw new Error("Invalid pages");
            }
            return data.pages;
        }).catch(error => { batches.delete(start); throw error; });
        batches.set(start, pending);
    }
    return batches.get(start);
}
async function render(number) {
    const sheet = sheets.get(number);
    if (!sheet || ready.has(number)) return;
    sheet.setAttribute("aria-busy", "true");
    const frame = sheet.querySelector(".reader-page-content");
    if (!isPDF) {
        const batch = await textBatch(number);
        const value = batch.find(page => page.number === number);
        if (!value || typeof value.text !== "string" || value.text.length > 2600) throw new Error("Invalid text");
        const content = document.createElement("p");
        content.className = "reader-plain-text";
        content.textContent = value.text;
        frame.replaceChildren(content);
        ready.set(number, {frame});
    } else {
        const page = await pdf.getPage(number);
        const unit = page.getViewport({scale: 1});
        const width = fitWidth();
        const viewport = page.getViewport({scale: width / unit.width});
        const density = Math.min(2, window.devicePixelRatio || 1, Math.sqrt(6000000 / (viewport.width * viewport.height)));
        const canvas = document.createElement("canvas");
        canvas.setAttribute("aria-label", "PDF 文件第 " + number + " 页原图");
        canvas.width = Math.max(1, Math.floor(viewport.width * density));
        canvas.height = Math.max(1, Math.floor(viewport.height * density));
        canvas.style.width = viewport.width + "px";
        canvas.style.height = viewport.height + "px";
        frame.style.width = viewport.width + "px";
        frame.style.height = viewport.height + "px";
        sheet.style.minHeight = (viewport.height + 54) + "px";
        frame.replaceChildren(canvas);
        await page.render({
            canvasContext: canvas.getContext("2d"), viewport,
            transform: density === 1 ? null : [density, 0, 0, density, 0, 0],
            annotationMode: pdfjs.AnnotationMode.DISABLE,
        }).promise;
        const layer = document.createElement("div");
        layer.className = "textLayer";
        layer.style.setProperty("--scale-factor", String(viewport.scale));
        layer.style.setProperty("--total-scale-factor", String(viewport.scale));
        frame.append(layer);
        const textLayer = new pdfjs.TextLayer({textContentSource: page.streamTextContent(), container: layer, viewport});
        try { await textLayer.render(); } catch (_) { layer.remove(); }
        ready.set(number, {frame, canvas, page});
    }
    sheet.removeAttribute("aria-busy");
    sheet.dataset.loaded = "true";
}
async function drain() {
    if (running || stopped) return;
    running = true;
    try {
        while (queue.size && !stopped) {
            const number = [...queue].sort((a, b) => Math.abs(a - current) - Math.abs(b - current))[0];
            queue.delete(number);
            if (isPDF && Math.abs(number - current) > 2) continue;
            await render(number);
            trim();
        }
        retry.hidden = true;
        root.dataset.state = "ready";
        announce("当前第 " + current + " / " + total + " 页 · 向下滚动继续阅读；阅读不会计为已讲解。");
    } catch (_) {
        const sheet = sheets.get(current);
        sheet?.removeAttribute("aria-busy");
        retry.hidden = false;
        root.dataset.state = "error";
        announce("这一页暂时无法显示。可重试当前页，或下载原件阅读；原书和学习记录保留。登录过期时请重新登录。");
    } finally { running = false; }
}
function jump(number) {
    if (!Number.isSafeInteger(number) || number < 1 || number > total) return;
    position(number);
    enqueue(number);
    sheets.get(number).scrollIntoView({block: "start", behavior: "instant"});
}
retry.addEventListener("click", () => {
    if (!readerReady) { location.reload(); return; }
    queue.clear(); enqueue(current);
});
async function setup() {
    if (!root || !Number.isSafeInteger(total) || total < 1 || total > 1500 || initial < 1 || initial > total) {
        throw new Error("Invalid reader");
    }
    if (isPDF) {
        announce("正在准备原书阅读组件；书页显示不需要先识别文字…");
        pdfjs = await import("./vendor/pdfjs/legacy/build/pdf.min.mjs");
        pdfjs.GlobalWorkerOptions.workerSrc = "/static/vendor/pdfjs/legacy/build/pdf.worker.min.mjs";
        loadingPhase = "读取原始 PDF";
        const task = pdfjs.getDocument({
            url: root.dataset.source, withCredentials: true,
            disableRange: true, isEvalSupported: false, enableXfa: false,
            cMapUrl: "/static/vendor/pdfjs/cmaps/", cMapPacked: true,
            standardFontDataUrl: "/static/vendor/pdfjs/standard_fonts/",
            wasmUrl: "/static/vendor/pdfjs/wasm/",
        });
        task.onProgress = ({loaded, total: bytes}) => {
            if (bytes) { progress.max = bytes; progress.value = loaded; }
            announce(bytes ? "正在读取原书 " + Math.min(100, Math.round(loaded / bytes * 100)) + "%…" : "正在读取原书…");
        };
        pdf = await task.promise;
        loadingPhase = "打开原书页面";
        if (pdf.numPages !== total) throw new Error("Page count mismatch");
        firstViewport = (await pdf.getPage(1)).getViewport({scale: 1});
    }
    const fragment = document.createDocumentFragment();
    for (let number = 1; number <= total; number++) {
        const sheet = document.createElement("article");
        sheet.className = "reader-sheet";
        sheet.dataset.page = String(number);
        sheet.id = "reading-page-" + number;
        const title = document.createElement("h2");
        title.textContent = (isPDF ? "PDF 文件第 " : "阅读第 ") + number + " 页";
        const frame = document.createElement("div");
        frame.className = "reader-page-content";
        sheet.append(title, frame);
        if (isPDF) sheet.style.minHeight = (fitWidth() * firstViewport.height / firstViewport.width + 54) + "px";
        sheets.set(number, sheet);
        fragment.append(sheet);
    }
    pagesNode.append(fragment);
    const observer = new IntersectionObserver(entries => {
        for (const entry of entries) {
            if (entry.isIntersecting) enqueue(Number(entry.target.dataset.page));
        }
    }, {rootMargin: "500px 0px"});
    let scrollFrame = false;
    window.addEventListener("scroll", () => {
        if (scrollFrame) return;
        scrollFrame = true;
        requestAnimationFrame(() => {
            scrollFrame = false;
            let nearest = current, distance = Infinity;
            for (const [number, sheet] of sheets) {
                const rect = sheet.getBoundingClientRect();
                const gap = Math.abs(rect.top - 140);
                if (rect.bottom > 120 && gap < distance) { nearest = number; distance = gap; }
            }
            if (nearest !== current) { position(nearest); enqueue(nearest); trim(); }
        });
    }, {passive: true});
    document.getElementById("reader-locate").addEventListener("submit", event => {event.preventDefault(); jump(Number(input.value));});
    previous.addEventListener("click", () => jump(current - 1));
    next.addEventListener("click", () => jump(current + 1));
    const zoomInput = document.getElementById("reader-zoom");
    let resizeTimer = null;
    const resize = () => {
        if (!isPDF) return;
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(() => {
            if (running) { resize(); return; }
            for (const entry of ready.values()) {
                entry.canvas.width = entry.canvas.height = 0;
                entry.frame.replaceChildren();
                entry.page.cleanup();
            }
            ready.clear(); queue.clear();
            for (const sheet of sheets.values()) sheet.style.minHeight = (fitWidth() * firstViewport.height / firstViewport.width + 54) + "px";
            jump(current);
        }, 200);
    };
    zoomInput?.addEventListener("change", () => { zoom = Number(zoomInput.value); resize(); });
    window.addEventListener("resize", resize);
    window.addEventListener("pagehide", () => {stopped = true;});
    window.addEventListener("pageshow", event => {if (event.persisted) {stopped = false; enqueue(current);}});
    position(initial);
    loadingPhase = "显示原书第 " + initial + " 页";
    announce("正在显示原书第 " + initial + " / " + total + " 页…");
    await render(initial);
    readerReady = true;
    root.dataset.state = "ready";
    progress.hidden = true;
    sheets.get(initial).scrollIntoView({block: "start", behavior: "instant"});
    for (const sheet of sheets.values()) observer.observe(sheet);
    if (isPDF) {
        try {
            const {initBookOCR} = await import("./book-ocr.mjs");
            initBookOCR({getCurrentPage: () => current, jump, renderForOCR: async number => {
                const page = await pdf.getPage(number);
                const unit = page.getViewport({scale: 1});
                const scale = Math.min(1800 / unit.width, Math.sqrt(5000000 / (unit.width * unit.height)));
                const viewport = page.getViewport({scale});
                const canvas = document.createElement("canvas");
                canvas.width = Math.max(1, Math.floor(viewport.width));
                canvas.height = Math.max(1, Math.floor(viewport.height));
                await page.render({canvasContext: canvas.getContext("2d", {alpha: false}), viewport, annotationMode: pdfjs.AnnotationMode.DISABLE}).promise;
                return canvas;
            }});
        } catch (_) {
            const button = document.getElementById("ocr-start");
            if (button) button.textContent = "识别组件暂不可用";
        }
    }
    void drain();
}
setup().catch(() => {
    root.dataset.state = "error";
    progress.hidden = true;
    announce("原书暂未显示（" + loadingPhase + "）。可以重新加载原书，或" + (isPDF ? "点击“直接打开原始 PDF”" : "下载原件阅读") + "；文字识别不影响原书阅读。登录过期时请重新登录。");
    retry.textContent = "重新加载原书";
    retry.hidden = false;
});
