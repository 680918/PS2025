from datetime import datetime, timezone

RECENCY_HALF_LIFE_DAYS = 30.0


def _normalize_datetime(value):
    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc,
        )

    return value.astimezone(
        timezone.utc,
    )


def calculate_recency_score(
    updated_at,
    reference_time,
):
    if reference_time is None:
        raise ValueError("reference_time is required")

    if updated_at is None:
        return 0.0

    updated_at = _normalize_datetime(
        updated_at,
    )
    reference_time = _normalize_datetime(
        reference_time,
    )

    if updated_at >= reference_time:
        return 1.0

    age = reference_time - updated_at
    age_days = age.total_seconds() / 86400

    return 0.5 ** (age_days / RECENCY_HALF_LIFE_DAYS)


def _normalize_datetime(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))

    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc,
        )

    return value.astimezone(
        timezone.utc,
    )
