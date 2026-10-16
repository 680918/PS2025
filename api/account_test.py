"""Local, disposable registration/login/logout trial; credentials stay in memory."""

import argparse
import gc
import getpass
import socket
import sqlite3
import sys
import tempfile
import warnings
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from api.run import parse_port
from security.verification_mailer import MailConfigurationError, SMTPSettings


def create_trial_app(
    directory,
    *,
    settings=None,
    simulated=False,
    activation_url="http://127.0.0.1:8782/web/verify-registration",
    dialogue_responder=None,
    dialogue_label="",
):
    from fastapi import Request
    from fastapi.responses import HTMLResponse

    from api.account_app import create_account_app
    from api.public_pages import _render_layout
    from api.registration_pages import RegistrationMailConfig
    from security.pending_registration import registration_browser_secret_hash
    from user.sqlite_repository import SQLiteUserRepository

    messages = []

    def simulated_sender(message, settings, *, now=None):
        messages.append(message)

    if simulated:
        settings = SMTPSettings("preview-only@163.com", "fake-authorization-code")
        config = RegistrationMailConfig(
            activation_url, settings, simulated=True, sender=simulated_sender
        )
    else:
        if not isinstance(settings, SMTPSettings):
            raise MailConfigurationError("请在本机终端准备发件邮箱。")
        config = RegistrationMailConfig(
            activation_url,
            settings,
            allowed_recipient=settings.username.strip().lower(),
        )
    app = create_account_app(
        directory,
        registration_mail=config,
        dialogue_responder=dialogue_responder,
        dialogue_label=dialogue_label,
    )
    if not simulated:
        return app
    repository = SQLiteUserRepository(Path(directory) / "users.db")

    @app.get("/web/trial-mailbox", include_in_schema=False)
    def mailbox(request: Request):
        parts = request.cookies.get("coach_registration_application", "").split(".")
        row = None
        try:
            if (
                len(parts) == 2
                and registration_browser_secret_hash(parts[1]) is not None
            ):
                row = repository.get_browser_registration(
                    parts[0],
                    registration_browser_secret_hash(parts[1]),
                    int(datetime.now(timezone.utc).timestamp()),
                )
        except sqlite3.Error:
            return HTMLResponse(
                "模拟收件箱暂时不可用。",
                status_code=503,
                headers={"Cache-Control": "no-store"},
            )
        links = []
        if row is not None:
            links = [
                f'<a class="button button-primary button-full" href="{escape(message.activation_url, quote=True)}">打开模拟验证邮件 →</a>'
                for message in messages
                if message.recipient == row[2]
            ]
        content = '<main id="main-content" class="verification-layout"><section class="verification-card"><p class="mail-simulation-notice">本机模拟 · 不会发送真实邮件</p><h1>模拟收件箱</h1><p>仅显示当前浏览器申请的虚构邮件。确认后创建临时账户，可继续登录与退出。</p>'
        content += (
            "".join(links)
            if links
            else "<p>当前没有可查看的模拟邮件，请先保存申请并点击模拟发送。</p>"
        )
        content += '<a class="back-link" href="/web/register/pending">← 返回申请进度</a></section></main>'
        return HTMLResponse(
            _render_layout("模拟收件箱 · 知行", content),
            headers={
                "Cache-Control": "no-store",
                "Referrer-Policy": "no-referrer",
                "X-Frame-Options": "DENY",
                "Content-Security-Policy": "default-src 'none'; style-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
            },
        )

    return app


def _completed(directory):
    with sqlite3.connect(Path(directory) / "users.db") as connection:
        return (
            connection.execute(
                """SELECT 1 FROM users AS account
               JOIN user_email_verifications AS verified ON verified.user_id = account.user_id
               JOIN login_sessions AS session ON session.user_id = account.user_id
               WHERE verified.email = account.email AND verified.verified_at IS NOT NULL
                 AND session.revoked_at IS NOT NULL LIMIT 1"""
            ).fetchone()
            is not None
        )


def _run_trial(port, *, settings=None, simulated=False):
    import uvicorn

    with tempfile.TemporaryDirectory(prefix="coach-account-trial-") as directory:
        try:
            # Bind before any browser can submit mail; fail without sending on port conflict.
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
                listener.bind(("127.0.0.1", port))
                listener.listen(64)
                app = create_trial_app(
                    Path(directory),
                    settings=settings,
                    simulated=simulated,
                    activation_url=f"http://127.0.0.1:{port}/web/verify-registration",
                )
                print(f"账户试用页面：http://127.0.0.1:{port}/web/register", flush=True)
                if simulated:
                    print(
                        f"模拟收件箱：http://127.0.0.1:{port}/web/trial-mailbox",
                        flush=True,
                    )
                print(
                    "操作顺序：注册 → 点击发送 → 邮件中确认 → 登录 → 退出。", flush=True
                )
                print(
                    "完成退出后回到此窗口，按 Ctrl+C 查看验收结果并清理临时数据。",
                    flush=True,
                )
                server = uvicorn.Server(
                    uvicorn.Config(
                        app,
                        host="127.0.0.1",
                        port=port,
                        access_log=False,
                        proxy_headers=False,
                        log_level="error",
                    )
                )
                try:
                    server.run(sockets=[listener])
                except KeyboardInterrupt:
                    pass
                completed = _completed(directory)
                print(
                    "测试通过：临时账户已完成邮箱验证、登录与主动退出。"
                    if completed
                    else "试用已结束，尚未完成全部步骤。",
                    flush=True,
                )
                print("临时数据将清理；现有 .env、账户和学习资料保持不变。", flush=True)
                return 0 if completed else 1
        finally:
            gc.collect()


def main(argv=None):
    parser = argparse.ArgumentParser(description="知行本机账户完整试用（仅临时数据）")
    parser.add_argument("--port", type=parse_port, default=8782)
    parser.add_argument(
        "--simulate", action="store_true", help="模拟邮件，不连接 SMTP、不询问授权码"
    )
    args = parser.parse_args(argv)
    try:
        if args.simulate:
            print("模拟模式：不发送真实邮件，使用虚构资料即可。", flush=True)
            return _run_trial(args.port, simulated=True)
        if not sys.stdin.isatty():
            print(
                "请在自己的 PowerShell 终端运行；不要通过聊天、命令参数或管道发送授权码。"
            )
            return 1
        print("本次使用临时账户，只向你确认的本人 163 邮箱发送注册验证邮件。")
        username = input("你的完整 163 邮箱地址：").strip().lower()
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            code = getpass.getpass("163 客户端授权码（输入不显示）：")
        settings = SMTPSettings(username, code)
        del code
        print(f"本次允许的收件人与发件人均为：{settings.username}")
        if (
            input(
                "由你在网页点击发送；确认开启本次试用请输入“开始”，其他输入取消："
            ).strip()
            != "开始"
        ):
            print("已取消，没有发送邮件。")
            return 0
        return _run_trial(args.port, settings=settings)
    except getpass.GetPassWarning:
        print("当前终端不能隐藏输入，已停止。请在自己的 PowerShell 中重试。")
        return 1
    except MailConfigurationError as error:
        print(str(error))
        return 1
    except (OSError, sqlite3.Error):
        print("账户试用无法启动或访问临时数据。请检查端口及权限，或使用 --port 8783。")
        return 1
    except (KeyboardInterrupt, EOFError):
        print("\n已停止；不会自动重新发送邮件。")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
