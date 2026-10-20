"""Literal calendar-day bounds for stored question timestamps in Beijing time."""

import re
from datetime import date, datetime, time, timedelta, timezone


ZONE = timezone(timedelta(hours=8))


def conversation_date_window(start_day="", end_day=""):
    bounds = []
    for value in (start_day, end_day):
        if not isinstance(value, str) or (
            value and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None
        ):
            raise ValueError("请使用有效日期，格式为年-月-日。")
        try:
            parsed = date.fromisoformat(value) if value else None
        except ValueError:
            raise ValueError("请检查日期是否真实存在。") from None
        bounds.append(
            int(datetime.combine(parsed, time(), ZONE).timestamp()) if parsed else None
        )
    lower, upper = bounds
    if lower is not None and upper is not None and lower > upper:
        raise ValueError("开始日期不能晚于结束日期。")
    return lower, upper + 86400 if upper is not None else None
