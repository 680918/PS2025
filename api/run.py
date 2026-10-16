"""Start the local web interface with ``python -m api.run``."""

import argparse
import sqlite3
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_port(value):
    try:
        port = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("端口必须是 1 到 65535 之间的整数") from error

    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("端口必须是 1 到 65535 之间的整数")

    return port


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="启动 Personal Growth AI Coach 本机网页"
    )
    parser.add_argument(
        "--port",
        type=parse_port,
        default=8000,
        help="网页端口，默认 8000",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=PROJECT_ROOT / "data",
        help="数据库目录，默认使用项目中的 data 文件夹",
    )
    args = parser.parse_args(argv)

    # Keep --help usable even before application dependencies are installed.
    try:
        import uvicorn
        from api.app import create_app
        from config import DEEPSEEK_API_KEY
    except ModuleNotFoundError:
        print(
            "启动失败：缺少运行依赖。请在项目目录执行：\n"
            "python -m pip install -r requirements.txt",
            file=sys.stderr,
        )
        return 1
    except ValueError:
        print(
            "启动失败：配置格式不正确。请检查 .env 中的超时、重试次数等数值设置。",
            file=sys.stderr,
        )
        return 1

    try:
        database_dir = args.data_dir.expanduser().resolve()
        app = create_app(database_dir=database_dir)
    except (OSError, sqlite3.Error):
        print(
            "启动失败：无法初始化数据库。请检查数据目录的路径、读写权限和磁盘空间。",
            file=sys.stderr,
        )
        return 1

    print(f"网页地址：http://127.0.0.1:{args.port}", flush=True)
    print(f"数据目录：{database_dir}", flush=True)
    print("停止服务：回到此窗口，按 Ctrl+C。", flush=True)

    if not DEEPSEEK_API_KEY:
        print(
            "提示：未配置 DEEPSEEK_API_KEY。首页可以打开；"
            "使用 AI 功能前，请配置项目中的 .env 并重新启动。",
            flush=True,
        )

    try:
        # Query strings contain one-time verification links. Keep them out of
        # access logs; startup and application error logs remain available.
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=args.port,
            log_level="info",
            access_log=False,
            proxy_headers=False,
        )
    except SystemExit as error:
        if error.code:
            print(
                "网页服务未能启动，请查看上方错误。若端口被占用，可换用：\n"
                "python -m api.run --port 8001",
                file=sys.stderr,
            )
            return 1
    except OSError:
        print(
            "网页服务未能启动，请检查端口及本机网络权限。可尝试：\n"
            "python -m api.run --port 8001",
            file=sys.stderr,
        )
        return 1
    except KeyboardInterrupt:
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
