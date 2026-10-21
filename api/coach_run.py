"""Persistent, loopback-only account and unified dialogue entry."""

import argparse
import getpass
import importlib
import socket
import sqlite3
import sys
import warnings
from pathlib import Path

from core.local_data_lock import (
    data_directory_lock,
    DataDirectoryBusy,
    RestoreIncomplete,
)
from api.run import parse_port
from security.verification_mailer import MailConfigurationError, SMTPSettings


ROOT = Path(__file__).resolve().parents[1]


def check_ready(directory, port, *, simulated=False, ai=False, register=False):
    """Read-only local checks: never create an app, prompt, or call a provider."""
    print("启动前检查：不启动服务、不创建账户、不发邮件、不调用 AI。")
    ready = True
    missing = []
    for module in (
        "fastapi",
        "uvicorn",
        "jinja2",
        "python_multipart",
        "argon2",
        "markdown_it",
        "pypdf",
        "requests",
        "dotenv",
    ):
        try:
            importlib.import_module(module)
        except Exception:
            # Never print import exceptions, which can contain local configuration.
            missing.append(module)
    if missing:
        ready = False
        print("[需处理] 运行依赖无法加载：" + "、".join(missing))
        print("使用同一个 Python 执行：python -m pip install -r requirements.txt")
    else:
        print("[通过] 网页、密码、资料和 PDF 运行依赖可加载。")

    try:
        if (directory / ".coach-restore-incomplete").exists():
            raise ValueError
        if directory.exists() and not directory.is_dir():
            raise ValueError
        marker = directory / ".coach-mode"
        if marker.exists():
            with marker.open(encoding="utf-8") as stream:
                mode = stream.read(16)
            if mode != ("simulated" if simulated else "real"):
                raise ValueError
        print("[通过] 数据目录路径与已有模式兼容；实际写入权限在启动时确认。")
    except (OSError, ValueError, UnicodeError):
        ready = False
        print(
            "[需处理] 数据目录不可读取、模式冲突或恢复未完成；请核对目录。模拟与真实数据请使用不同目录。"
        )

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", port))
        print(f"[通过] 本机端口 {port} 当前可用；正式启动时会再次检查。")
    except OSError:
        ready = False
        print(f"[需处理] 本机端口 {port} 无法使用；先核对该地址是否已有知行运行。")
        print("日常建议保持固定入口；独立测试才用 --port 指定其他端口。")

    if ai:
        try:
            from coach.dialogue import real_responder

            real_responder()  # Builds a callable only; does not send an API request.
            print("[通过] AI 密钥已配置，超时配置可用；密钥值不显示。")
        except Exception:
            ready = False
            print("[需处理] AI 配置无法加载；在本机检查 .env 中的密钥和 1–60 秒超时。")
        print("未联网验证密钥有效性、账户余额、模型可用性或回答质量。")
    else:
        print(
            "[说明] 模拟模式不读取 AI 配置。"
            if simulated
            else "[说明] 未指定 --ai，本次不读取 AI 配置。"
        )
    if register:
        print("[说明] 本次不索取 163 授权码；正式启动 --register 时再于终端隐藏输入。")
    print(
        "本机检查通过，可以按同一参数去掉 --check 启动。"
        if ready
        else "检查尚未通过，请先处理上述提示，再运行同一检查。"
    )
    return 0 if ready else 1


def build_app(directory, port, *, simulated=False, settings=None, responder=None):
    if simulated:
        from coach.dialogue import simulated_responder

        responder = simulated_responder
    label = (
        "模拟体验 · 邮件与 AI 回复均为模拟，不产生服务调用费用"
        if simulated
        else (
            "AI 对话已启用 · 消息及相关资料片段会发送至已配置的 AI 服务"
            if responder
            else "AI 对话未启用 · 可管理资料、查阅已保存教案与已有记录"
        )
    )
    if simulated or settings is not None:
        from api.account_test import create_trial_app

        app = create_trial_app(
            directory,
            simulated=simulated,
            settings=settings,
            activation_url=f"http://127.0.0.1:{port}/web/verify-registration",
            dialogue_responder=responder,
            dialogue_label=label,
        )
    else:
        from api.account_app import create_account_app

        app = create_account_app(
            directory, dialogue_responder=responder, dialogue_label=label
        )
    app.state.usage_environment = {
        "kind": "simulated" if simulated else "local",
        "ai": responder is not None,
        "mail": settings is not None,
    }
    return app


def _serve(directory, port, *, simulated=False, settings=None, responder=None):
    import uvicorn

    # A port conflict cannot start an account or provider request.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", port))
        listener.listen(64)
        directory.mkdir(parents=True, exist_ok=True)
        with data_directory_lock(directory):
            if (directory / ".coach-restore-incomplete").exists():
                raise RestoreIncomplete
            marker = directory / ".coach-mode"
            mode = "simulated" if simulated else "real"
            if marker.exists() and marker.read_text(encoding="utf-8") != mode:
                raise ValueError("模拟和真实模式需要使用不同的数据目录。")
            marker.write_text(mode, encoding="utf-8")
            app = build_app(
                directory,
                port,
                simulated=simulated,
                settings=settings,
                responder=responder,
            )
            print(
                "当前环境：" + ("模拟体验" if simulated else "本机日常使用"), flush=True
            )
            print(f"使用帮助：http://127.0.0.1:{port}/web/help", flush=True)
            print(f"成长空间：http://127.0.0.1:{port}/web/login", flush=True)
            print(f"记录保存在本机：{directory}；停止服务后仍保留。", flush=True)
            if simulated:
                print(
                    f"模拟收件箱：http://127.0.0.1:{port}/web/trial-mailbox", flush=True
                )
            print(
                "资料保存在本机；教案需在页面预览并确认后收入知识库。停止服务请按 Ctrl+C。",
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
            server.run(sockets=[listener])
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="知行本机持续对话（记录保留，不公开部署）"
    )
    parser.add_argument("--port", type=parse_port, help="日常默认 8785；模拟默认 8784")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument(
        "--check",
        action="store_true",
        help="仅检查本机依赖、目录、端口和所选 AI 配置；不启动或调用外部服务",
    )
    parser.add_argument(
        "--simulate", action="store_true", help="仅模拟邮件与 AI，使用独立数据"
    )
    parser.add_argument(
        "--register",
        action="store_true",
        help="本次开启本人 163 注册与密码找回邮件，在终端隐藏输入授权码",
    )
    parser.add_argument(
        "--ai",
        action="store_true",
        help="启用已配置 AI；点击发送才调用，可能产生 API 费用",
    )
    args = parser.parse_args(argv)
    if args.simulate and (args.register or args.ai):
        parser.error("--simulate 不能与 --register 或 --ai 同时使用")
    args.port = (
        args.port if args.port is not None else (8784 if args.simulate else 8785)
    )
    directory = (
        (
            args.data_dir
            or ROOT / "data" / ("coach-simulated" if args.simulate else "coach-local")
        )
        .expanduser()
        .resolve()
    )
    if args.check:
        return check_ready(
            directory,
            args.port,
            simulated=args.simulate,
            ai=args.ai,
            register=args.register,
        )
    try:
        settings, responder = None, None
        if args.simulate:
            from coach.dialogue import simulated_responder

            responder = simulated_responder
        elif args.ai:
            from coach.dialogue import real_responder

            responder = real_responder()
            print(
                "已启用真实 AI：只在你点击发送或继续学习时调用；不会自动重试。",
                flush=True,
            )
        if args.register:
            if not sys.stdin.isatty():
                print(
                    "请在自己的 PowerShell 中运行；不要通过聊天、参数或管道传递授权码。"
                )
                return 1
            username = (
                input("本次注册或找回密码使用的本人完整 163 邮箱：").strip().lower()
            )
            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                code = getpass.getpass("163 客户端授权码（输入不显示）：")
            settings = SMTPSettings(username, code)
            del code
            print(
                "仅允许向该本人邮箱发送注册、密码找回及重置完成通知；由你在网页操作触发。授权码不会写入文件。"
            )
        return _serve(
            directory,
            args.port,
            simulated=args.simulate,
            settings=settings,
            responder=responder,
        )
    except DataDirectoryBusy:
        print(
            "数据目录正在使用，请先停止占用同一数据目录的服务或备份操作；不要删除锁文件。"
        )
        return 1
    except RestoreIncomplete:
        print("恢复尚未完成，不能启动此目录。请保留原空间，使用另一个新目录重新恢复。")
        return 1
    except (MailConfigurationError, ValueError) as error:
        # Only locally constructed, fixed configuration messages reach this branch.
        print(
            str(error)
            if isinstance(error, MailConfigurationError)
            else "无法启动：检查 AI 配置（密钥、1–60 秒超时）及数据目录模式。"
        )
        return 1
    except getpass.GetPassWarning:
        print("终端无法隐藏输入，请换到自己的 PowerShell 重试。")
        return 1
    except ModuleNotFoundError:
        print(
            "缺少运行依赖，请在项目目录执行 python -m pip install -r requirements.txt。"
        )
        return 1
    except (OSError, sqlite3.Error):
        print("无法启动或保存数据，请检查端口、目录权限和磁盘空间。")
        return 1
    except (KeyboardInterrupt, EOFError):
        print("\n已停止；已有对话保留，不会自动重新发送。")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
