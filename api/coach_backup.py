"""Local operator backup tool, independent of web and AI dependencies."""

import argparse
import sqlite3
from pathlib import Path
from zipfile import BadZipFile

from coach.local_backup import (
    ROOT,
    BackupError,
    create_backup,
    check_backup,
    restore_backup,
    default_backup_path,
)
from core.local_data_lock import DataDirectoryBusy, RestoreIncomplete


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="知行本机完整备份、检查和恢复（先停止本机服务）"
    )
    actions = parser.add_subparsers(dest="action", required=True)
    create = actions.add_parser("create", help="先停止服务，再创建新的私人备份包")
    create.add_argument("--data-dir", type=Path, default=ROOT / "data/coach-local")
    create.add_argument("--output", type=Path)
    check = actions.add_parser("check", help="只检查备份，不恢复或改写现有空间")
    check.add_argument("archive", type=Path)
    restore = actions.add_parser("restore", help="验证后恢复到不存在的新目录")
    restore.add_argument("archive", type=Path)
    restore.add_argument("--target", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == "create":
            result = create_backup(args.data_dir, args.output or default_backup_path())
            print("备份已创建并通过校验：" + str(result))
            print(
                "这是包含账户和学习资料的私人完整备份；请保管在自己的磁盘，不上传 GitHub 或分享。"
            )
        elif args.action == "check":
            summary = check_backup(args.archive)
            print(
                "备份检查通过：3 个数据库、文件校验和运行模式均通过；未恢复或改写现有空间。"
            )
            print("解包数据大小：" + str(summary["bytes"]) + " 字节。")
        else:
            summary = restore_backup(args.archive, args.target)
            print("已恢复到新目录：" + str(args.target.expanduser().absolute()))
            print(
                "请使用 --data-dir 指向新目录启动，再用备份时的邮箱和密码登录。旧登录和临时邮件链接已失效；未完成对话不会自动重试。"
            )
            if summary["mode"] == "simulated":
                print("此备份来自模拟空间，启动时还需加 --simulate。")
        return 0
    except DataDirectoryBusy:
        print(
            "数据目录正在使用。请在原服务窗口按 Ctrl+C 停止服务，再重新执行；不要删除锁文件。"
        )
    except RestoreIncomplete:
        print("这是未完成的恢复目录。请保留原空间，改用另一个新目录重新恢复。")
    except BackupError as error:
        print(str(error))
    except (
        OSError,
        sqlite3.Error,
        BadZipFile,
        UnicodeError,
        ValueError,
        RuntimeError,
        NotImplementedError,
    ):
        print(
            "操作未完成：检查文件、目录权限、备份格式及磁盘空间。原成长空间未被覆盖；恢复失败请换一个新目录，不启动未完成目录。"
        )
    except (KeyboardInterrupt, EOFError):
        print("已停止。原成长空间未被覆盖；请勿使用未完成的恢复目录。")
        return 130
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
