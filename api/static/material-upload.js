/* Native multipart upload stays usable without JavaScript. No AI or network calls. */
(() => {
    "use strict";
    const form = document.getElementById("material-upload");
    if (!form) return;
    const fileInput = form.querySelector('input[type="file"]');
    const button = form.querySelector('button[type="submit"]');
    const status = document.getElementById("upload-status");
    const maximum = Number(form.dataset.maxBytes);
    if (!fileInput || !button || !status || !Number.isSafeInteger(maximum) || maximum < 1) return;
    let submitting = false;
    const reset = () => {
        submitting = false;
        button.disabled = false;
        form.removeAttribute("aria-busy");
        status.textContent = "";
    };
    window.addEventListener("pageshow", reset);
    fileInput.addEventListener("change", reset);
    form.addEventListener("submit", (event) => {
        if (submitting) {
            event.preventDefault();
            return;
        }
        const file = fileInput.files[0];
        if (!file || file.size === 0 || file.size > maximum) {
            event.preventDefault();
            status.textContent = !file || file.size === 0
                ? "请选择有内容的书籍文件。"
                : "文件超过单本 100 MB 上限，请按章节拆分后上传。";
            return;
        }
        submitting = true;
        button.disabled = true;
        form.setAttribute("aria-busy", "true");
        status.textContent = "正在上传并提取文字，请稍候。大书可能需要更久；此过程不调用 AI，请勿重复提交。";
    });
})();
