"""Local operator-only AI admission limits. No web setting changes or external calls."""

import argparse
import sqlite3
from contextlib import closing
from pathlib import Path
from time import time

from coach.ai_usage import USAGE_SCHEMA, read_limits, validate_limits, budget

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="查看或调整本机成长空间的每日AI请求次数上限；不是账单工具"
    )
    parser.add_argument("operation", choices=("show", "set"))
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data/coach-local")
    parser.add_argument("--per-user", type=int)
    parser.add_argument("--total", type=int)
    args = parser.parse_args(argv)
    if args.operation == "set":
        try:
            validate_limits(args.per_user, args.total)
        except ValueError as error:
            parser.error(str(error))
    elif args.per_user is not None or args.total is not None:
        parser.error("show不接受次数设置；调整时请使用set。")
    directory = args.data_dir.expanduser().resolve()
    database = directory / "coach_conversations.db"
    try:
        if (
            not database.is_file()
            or database.is_symlink()
            or (directory / ".coach-restore-incomplete").exists()
            or (directory / ".coach-mode").stat().st_size > 16
            or (directory / ".coach-mode").read_text(encoding="utf-8")
            not in {"real", "simulated"}
        ):
            raise ValueError
        with closing(
            sqlite3.connect(
                database.as_uri()
                + "?mode="
                + ("rw" if args.operation == "set" else "ro"),
                uri=True,
                timeout=5,
            )
        ) as db:
            if not db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='coach_turns'"
            ).fetchone():
                raise ValueError
            exists = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='coach_ai_usage'"
            ).fetchone()
            if args.operation == "set":
                db.executescript(USAGE_SCHEMA)
                with db:
                    db.execute("BEGIN IMMEDIATE")
                    db.execute(
                        "INSERT INTO coach_ai_limits VALUES(1,?,?) ON CONFLICT(singleton) DO UPDATE SET user_limit=excluded.user_limit,space_limit=excluded.space_limit",
                        (args.per_user, args.total),
                    )
                exists = True
            if exists:
                personal, total = read_limits(db)
                day = budget(db, "", int(time()))["day"]
                count = db.execute(
                    "SELECT COUNT(*) FROM coach_ai_usage WHERE day=?", (day,)
                ).fetchone()[0]
            else:
                from coach.ai_usage import DEFAULT_USER_LIMIT, DEFAULT_SPACE_LIMIT

                personal, total = DEFAULT_USER_LIMIT, DEFAULT_SPACE_LIMIT
                count = 0
        print(
            (
                "设置已保存；不清零已有记录。"
                if args.operation == "set"
                else "当前本机AI请求上限："
            )
        )
        print(
            f"每账户每日 {personal} 次；本空间合计每日 {total} 次；今日本空间已受理 {count} 次。"
        )
        print(
            "北京时间零点按新一天计算。0表示暂停相应AI受理；已有记录仍可阅读、修订和导出。"
        )
        print("仅约束此数据目录中启用本功能的请求；次数不代表实际计费金额。")
        return 0
    except (OSError, sqlite3.Error, ValueError, UnicodeError):
        print("未完成：请核对已使用的数据目录、运行模式与数据库；未创建新空间。")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
