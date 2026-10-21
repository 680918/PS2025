"""Run one self-addressed email test with transient credentials and test data."""

import argparse
import gc
import getpass
import socket
import sqlite3
import sys
import tempfile
import threading
import time
import warnings
from pathlib import Path

from api.run import parse_port
from security.verification_mailer import (
    MailConfigurationError,
    MailDeliveryError,
    SMTPSettings,
    send_verification_email,
)


def _create_test_app(repository):
    # This test harness deliberately avoids importing config or the AI runtime.
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    from fastapi.staticfiles import StaticFiles

    from api.email_verification_pages import register_email_verification_pages
    from api.public_pages import PUBLIC_STATIC_DIRECTORY, render_public_page
    from api.usage_help import register_usage_help

    app = FastAPI()
    register_usage_help(app, kind="legacy")
    app.mount("/static", StaticFiles(directory=PUBLIC_STATIC_DIRECTORY), name="static")
    register_email_verification_pages(app, repository)

    @app.get("/", response_class=HTMLResponse)
    def home():
        return render_public_page("home")

    @app.get("/web/login", response_class=HTMLResponse)
    def login():
        return render_public_page("login")

    @app.get("/web/register", response_class=HTMLResponse)
    def register():
        return render_public_page("register")

    return app


def _run_test(settings, port):
    import uvicorn

    from security.email_verification import issue_email_verification
    from user.model import User
    from user.sqlite_repository import SQLiteUserRepository

    with tempfile.TemporaryDirectory(prefix="coach-mail-test-") as directory:
        try:
            repository = SQLiteUserRepository(Path(directory) / "users.db")
            user = User(name="邮箱验证测试账号", email=settings.username)
            repository.save(user)
            app = _create_test_app(repository)
            # Reserve the loopback socket before generating or sending any link.
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
                listener.bind(("127.0.0.1", port))
                listener.listen(64)
                server = uvicorn.Server(
                    uvicorn.Config(
                        app,
                        host="127.0.0.1",
                        port=port,
                        log_level="error",
                        access_log=False,
                        lifespan="off",
                    )
                )
                thread = threading.Thread(
                    target=server.run, kwargs={"sockets": [listener]}, daemon=True
                )
                thread.start()
                try:
                    deadline = time.monotonic() + 10
                    while not server.started:
                        if not thread.is_alive() or time.monotonic() >= deadline:
                            print("测试页面未能启动，没有发送邮件。请稍后重试。")
                            return 1
                        thread.join(0.05)
                    message = issue_email_verification(
                        repository,
                        user.user_id,
                        f"http://127.0.0.1:{port}/web/verify-email",
                    )
                    try:
                        send_verification_email(message, settings)
                        print(
                            "邮件服务器已接受本次邮件，请查收；是否到达收件箱需要你确认。",
                            flush=True,
                        )
                    except MailDeliveryError as error:
                        print(str(error), flush=True)
                        if error.code not in {"timeout", "connection_failed"}:
                            return 1
                        # An acknowledgement can be lost after successful delivery.
                        # Keep the link alive; never resend automatically.
                        print(
                            "本次不会自动重发。如果收到邮件，仍可继续点击验证。",
                            flush=True,
                        )
                    print(
                        "请保持此窗口运行，在这台电脑打开 163 网页邮箱，点击邮件里的验证按钮。",
                        flush=True,
                    )
                    print(
                        "若没看到邮件，也请检查垃圾邮件。停止测试可按 Ctrl+C。",
                        flush=True,
                    )
                    deadline = time.monotonic() + 3600
                    while thread.is_alive():
                        if repository.is_email_verified(user.user_id):
                            print(
                                "测试通过：已收到网页确认，临时账号的邮箱验证成功。",
                                flush=True,
                            )
                            print(
                                "测试服务即将关闭。正式注册、登录仍未开放。", flush=True
                            )
                            return 0
                        if time.monotonic() >= deadline:
                            print(
                                "本次验证已超时，测试结束。需要重新运行后获取新邮件。"
                            )
                            return 1
                        thread.join(0.5)
                    print("测试页面服务已停止，未完成验证。")
                    return 1
                finally:
                    server.should_exit = True
                    thread.join(5)
        finally:
            # Existing repository connections may be released by cyclic GC.
            # Release them before TemporaryDirectory cleanup on Windows.
            gc.collect()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="给自己的 163 邮箱发送一封验证测试邮件"
    )
    parser.add_argument(
        "--port", type=parse_port, default=8774, help="本机测试端口，默认 8774"
    )
    args = parser.parse_args(argv)
    if not sys.stdin.isatty():
        print(
            "请在你自己的 PowerShell 终端运行本命令，邮箱授权码不能通过聊天或管道输入。"
        )
        return 1
    print("本次仅向你输入的普通 163 邮箱自己发送一封测试邮件。")
    print("邮箱授权码仅在本次运行中使用，不写入文件；现有 .env 和正式数据保持不变。")
    try:
        username = input("你的完整 163 邮箱地址：").strip()
        # Stop rather than let getpass fall back to an echoed password prompt.
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            code = getpass.getpass("163 客户端授权码（输入不显示，直接粘贴后回车）：")
        settings = SMTPSettings(username, code)
        del code
        print(f"收件人和发件人均为：{settings.username}")
        if (
            input("确认发送一封测试邮件，请输入“发送”；其他输入取消：").strip()
            != "发送"
        ):
            print("已取消，没有发送邮件。")
            return 0
        return _run_test(settings, args.port)
    except getpass.GetPassWarning:
        print(
            "当前终端不能隐藏授权码输入，测试已停止，没有发送邮件。请换用 PowerShell。"
        )
        return 1
    except MailConfigurationError as error:
        print(str(error))
        return 1
    except (OSError, sqlite3.Error):
        print(
            "测试服务无法启动或访问临时数据。若端口被占用，请使用 --port 8775 后重试。"
        )
        return 1
    except (KeyboardInterrupt, EOFError):
        print("\n测试已停止；本机验证页面也会关闭。已发邮件不会自动重新发送。")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
