"""Local usage help; reports explicit app settings without reading credentials."""

from html import escape
from pathlib import Path
import re

from fastapi.responses import HTMLResponse

from api.public_pages import _render_layout


def register_usage_help(app, *, kind="preview"):
    app.state.usage_environment = {"kind": kind, "ai": False, "mail": False}

    @app.get("/web/help", response_class=HTMLResponse, include_in_schema=False)
    def usage_help():
        environment = app.state.usage_environment
        kind = environment["kind"]
        if kind == "local":
            title = "本机日常使用"
            detail = (
                "这是保留账户与学习记录的本机空间。已有账户直接登录，无须每天重新注册。"
            )
            ai = (
                "已启用 · 主动发送或生成时可能计费"
                if environment["ai"]
                else "未启用 · 可查阅已有记录"
            )
            mail = (
                "已启用 · 仅限本次配置的本人邮箱"
                if environment["mail"]
                else "未启用 · 已验证账户仍可登录"
            )
        elif kind == "simulated":
            title = "模拟体验"
            detail = "邮件与 AI 回答均为模拟。模拟账户、资料和记录与日常空间分开，不能用来判断真实回答质量。"
            ai, mail = "模拟回复 · 不调用真实 AI", "模拟收件箱 · 不发送真实邮件"
        else:
            title = "旧开发入口" if kind == "legacy" else "开发预览"
            detail = "用于检查页面和功能，可能采用独立测试资料。请按本机日常入口使用自己的账户。"
            ai = mail = "以本次开发配置为准，请核对启动说明"

        recovery_step = (
            '<a href="/web/forgot-password">邮箱找回密码</a> 主动申请。'
            if kind != "legacy"
            else "请回到本机日常入口后，再使用邮箱找回密码。"
        )

        version = "本机开发版"
        try:
            lines = (
                (Path(__file__).resolve().parents[1] / "VERSION")
                .read_text(encoding="utf-8")
                .splitlines()
            )
            version = next(
                line.strip()
                for line in reversed(lines)
                if re.fullmatch(r"\d+\.\d+\.\d+", line.strip())
            )
        except (OSError, UnicodeError, StopIteration):
            pass
        content = f"""<main id="main-content" class="usage-help">
            <p class="eyebrow">使用帮助</p>
            <h1>安心继续，每一次积累都在。</h1>
            <section class="usage-panel" aria-labelledby="usage-environment">
                <h2 id="usage-environment">当前环境 · {escape(title)}</h2>
                <p>{escape(detail)}</p>
                <dl class="usage-status">
                    <div><dt>AI 对话</dt><dd>{escape(ai)}</dd></div>
                    <div><dt>注册与找回邮件</dt><dd>{escape(mail)}</dd></div>
                    <div><dt>版本</dt><dd>{escape(version)} · 本机试用，尚未公开开放</dd></div>
                </dl>
                <a class="button button-primary" href="/web/login">返回登录</a>
                {('<a class="button button-outline" href="/web/welcome">回到成长空间</a>' if kind != "legacy" else "")}
                {('<a class="button button-outline" href="/web/trial-mailbox">打开模拟收件箱</a>' if kind == "simulated" else "")}
            </section>
            <div class="usage-grid">
                <section class="usage-panel"><h2>日常从哪里进入？</h2>
                    <p>日常入口固定为 <strong>http://127.0.0.1:8785/web/login</strong>，建议收藏。启动窗口需要保持运行；网页打不开时，先检查服务是否已启动。</p>
                    <p>模拟入口使用 8784；其他端口以对应启动窗口为准。不要把不同测试空间的登录结果混在一起判断。</p>
                </section>
                <section class="usage-panel"><h2>怎样继续学习？</h2>
                    <p>聊天、主题学习、资料讨论都在一个对话框。右侧查看当前主题与位置，点击“继续上次学习”；书籍原文从“阅读全书”进入。</p>
                    <p>扫描页可以直接阅读原图；需要 Coach 按正文讲解时，先识别并核对保存相应页面的文字。</p>
                </section>
                <section class="usage-panel"><h2>停止后，记录还在吗？</h2>
                    <p>日常入口默认保留原来的本机账户、对话、资料、教案和学习位置。停止服务不会清空记录；重新启动时使用同一数据目录。</p>
                    <p>左侧“知识资产沉淀”集中管理教案、重温和导出。重要内容请定期导出，并按项目说明备份整个空间；只下载原书不等于备份全部学习记录。</p>
                </section>
                <section class="usage-panel"><h2>登录失败时怎么办？</h2>
                    <p>先核对地址与数据空间，再确认邮箱验证、密码和邮件是否来自同一次试用。不要重复注册来覆盖已有账户。</p>
                    <p>需要找回密码时，启动本次邮件能力后再操作。反馈问题只需说明页面提示和操作步骤，无须提供密码、授权码或邮件验证链接。</p>
                </section>
            </div>
            <section class="usage-panel usage-troubleshooting"><h2>遇到问题，先这样做</h2>
                <ol>
                    <li><strong>网页打不开：</strong>确认启动知行的 PowerShell 窗口仍在运行；先使用该窗口显示的地址。日常入口通常是 8785，模拟体验通常是 8784，不要混用两个空间。</li>
                    <li><strong>无法登录：</strong>先核对邮箱验证和数据空间，不要重新注册。确实忘记密码时，先确认本次已启用邮件服务，再从 {recovery_step}</li>
                    <li><strong>发送后暂未回复：</strong>先在对话页核对发送状态或刷新查看记录；系统不会自动重试，也不要连续重复发送。需要再次发出前，可以修改原文字，并在 AI 用量页核对当天额度。</li>
                    <li><strong>书籍不能直接讲解：</strong>先确认已选中资料和具体片段。扫描 PDF 可以先阅读原页；需要按正文讲解时，先识别并核对保存该页文字。</li>
                </ol>
                <p>仍需协助时，只需记录“进行了哪一步、页面提示什么、希望怎样”，不要发送密码、邮箱授权码、AI 密钥或邮件链接。</p>
            </section>
        </main>"""
        return HTMLResponse(
            _render_layout("使用帮助与当前环境 · 知行", content),
            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
        )
