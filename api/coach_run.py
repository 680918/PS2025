"""Persistent, loopback-only account and unified dialogue entry."""

import argparse
import getpass
import socket
import sqlite3
import sys
import warnings
from pathlib import Path

from api.run import parse_port
from security.verification_mailer import MailConfigurationError, SMTPSettings


ROOT = Path(__file__).resolve().parents[1]


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

        return create_trial_app(
            directory,
            simulated=simulated,
            settings=settings,
            activation_url=f"http://127.0.0.1:{port}/web/verify-registration",
            dialogue_responder=responder,
            dialogue_label=label,
        )
    from api.account_app import create_account_app

    return create_account_app(
        directory, dialogue_responder=responder, dialogue_label=label
    )


def _serve(directory, port, *, simulated=False, settings=None, responder=None):
    import uvicorn

    # A port conflict cannot start an account or provider request.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", port))
        listener.listen(64)
        directory.mkdir(parents=True, exist_ok=True)
        marker = directory / ".coach-mode"
        mode = "simulated" if simulated else "real"
        if marker.exists() and marker.read_text(encoding="utf-8") != mode:
            raise ValueError("模拟和真实模式需要使用不同的数据目录。")
        marker.write_text(mode, encoding="utf-8")
        app = build_app(
            directory, port, simulated=simulated, settings=settings, responder=responder
        )
        print(f"成长空间：http://127.0.0.1:{port}/web/login", flush=True)
        print(f"记录保存在本机：{directory}；停止服务后仍保留。", flush=True)
        if simulated:
            print(f"模拟收件箱：http://127.0.0.1:{port}/web/trial-mailbox", flush=True)
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
    parser.add_argument("--port", type=parse_port, default=8784)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument(
        "--simulate", action="store_true", help="仅模拟邮件与 AI，使用独立数据"
    )
    parser.add_argument(
        "--register",
        action="store_true",
        help="本次开启本人 163 邮件注册，在终端隐藏输入授权码",
    )
    parser.add_argument(
        "--ai",
        action="store_true",
        help="启用已配置 AI；点击发送才调用，可能产生 API 费用",
    )
    args = parser.parse_args(argv)
    if args.simulate and (args.register or args.ai):
        parser.error("--simulate 不能与 --register 或 --ai 同时使用")
    directory = (
        (
            args.data_dir
            or ROOT / "data" / ("coach-simulated" if args.simulate else "coach-local")
        )
        .expanduser()
        .resolve()
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
            username = input("本次注册使用的本人完整 163 邮箱：").strip().lower()
            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                code = getpass.getpass("163 客户端授权码（输入不显示）：")
            settings = SMTPSettings(username, code)
            del code
            print("仅允许向该本人邮箱发送，由你在网页点击发送。授权码不会写入文件。")
        return _serve(
            directory,
            args.port,
            simulated=args.simulate,
            settings=settings,
            responder=responder,
        )
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
