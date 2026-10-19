"""Persistent request budgets; counts are conservative admission records, not bills."""

from datetime import datetime, timedelta, timezone

ZONE = timezone(timedelta(hours=8))
DEFAULT_USER_LIMIT = 100
DEFAULT_SPACE_LIMIT = 500
USAGE_SCHEMA = """
CREATE TABLE IF NOT EXISTS coach_ai_limits (
    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
    user_limit INTEGER NOT NULL CHECK(user_limit BETWEEN 0 AND 10000),
    space_limit INTEGER NOT NULL CHECK(space_limit BETWEEN 0 AND 1000000)
);
CREATE TABLE IF NOT EXISTS coach_ai_usage (
    user_id TEXT NOT NULL, nonce TEXT NOT NULL, day TEXT NOT NULL,
    kind TEXT NOT NULL CHECK(kind IN ('dialogue','unit_lesson')),
    started_at INTEGER NOT NULL, PRIMARY KEY(user_id,nonce)
);
CREATE INDEX IF NOT EXISTS coach_ai_usage_day ON coach_ai_usage(day,user_id,kind);
"""


def validate_limits(user_limit, space_limit):
    if (
        type(user_limit) is not int
        or not 0 <= user_limit <= 10000
        or type(space_limit) is not int
        or not 0 <= space_limit <= 1000000
        or (user_limit and space_limit and user_limit > space_limit)
    ):
        raise ValueError(
            "个人上限需为0–10000，本空间上限需为0–1000000；均非零时本空间上限不能小于个人上限。"
        )
    return user_limit, space_limit


def read_limits(db):
    row = db.execute(
        "SELECT user_limit,space_limit FROM coach_ai_limits WHERE singleton=1"
    ).fetchone()
    return tuple(row) if row else (DEFAULT_USER_LIMIT, DEFAULT_SPACE_LIMIT)


def budget(db, user_id, now):
    day = datetime.fromtimestamp(now, ZONE).date()
    reset = datetime.combine(day + timedelta(days=1), datetime.min.time(), ZONE)
    user_limit, space_limit = read_limits(db)
    used, total = db.execute(
        "SELECT COUNT(CASE WHEN user_id=? THEN 1 END),COUNT(*) FROM coach_ai_usage WHERE day=?",
        (user_id, day.isoformat()),
    ).fetchone()
    reason = (
        "personal" if used >= user_limit else "space" if total >= space_limit else ""
    )
    return {
        "day": day.isoformat(),
        "used": used,
        "user_limit": user_limit,
        "space_limit": space_limit,
        "reason": reason,
        "retry_after": max(1, int(reset.timestamp()) - now),
    }


def usage_message(snapshot, *, rejected=True):
    notice = "本次尚未受理，未调用 AI。" if rejected else "新的 AI 请求暂不受理。"
    if not snapshot["reason"]:
        return (
            "本次尚未受理，未调用 AI。使用上限或日期可能已更新，请查看用量后重新发送。"
        )
    if snapshot["user_limit"] == 0 or snapshot["space_limit"] == 0:
        return (
            "AI 请求当前已暂停。"
            + notice
            + "可继续阅读、管理和导出已有资料，由本机维护者调整上限后恢复。"
        )
    return (
        (
            "你今天的 AI 请求次数已达到个人上限。"
            if snapshot["reason"] == "personal"
            else "本成长空间今天的 AI 请求额度已用尽。"
        )
        + notice
        + "可继续阅读、管理和导出已有资料，北京时间明日零点后再试。"
    )
