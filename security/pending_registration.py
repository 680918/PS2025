"""Trusted internal registration drafts. No users, email tokens or sessions."""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from security.passwords import hash_password
from security.registration_validation import validate_registration_fields


PENDING_REGISTRATION_LIFETIME_SECONDS = 3600
_REQUEST_ID = re.compile(r"registration_[0-9a-f]{32}")


class PendingRegistrationUnavailable(ValueError):
    """One generic result for existing accounts, active duplicates or ID collision."""


@dataclass(frozen=True)
class PendingRegistrationReceipt:
    request_id: str = field(repr=False)
    expires_at: datetime


@dataclass(frozen=True)
class PendingRegistration:
    # Internal record: repr is redacted, but this object must never be serialized
    # into an HTTP response (including via dataclasses.asdict).
    request_id: str = field(repr=False)
    name: str = field(repr=False)
    email: str = field(repr=False)
    password_hash: str = field(repr=False)
    created_at: datetime
    expires_at: datetime


def _timestamp(now):
    now = datetime.now(timezone.utc) if now is None else now
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("registration time must include a timezone")
    return int(now.timestamp())


def begin_pending_registration(repository, *, email, password, name="", now=None):
    """Persist a draft hash only. Caller must be a trusted, rate-limited flow."""
    if not all(isinstance(value, str) for value in (name, email, password)):
        raise ValueError("invalid registration details")
    checked = validate_registration_fields(name, email, password)
    if checked["errors"]:
        raise ValueError("invalid registration details")
    created_at = _timestamp(now)
    expires_at = created_at + PENDING_REGISTRATION_LIFETIME_SECONDS
    request_id = "registration_" + uuid4().hex
    password_hash = hash_password(password)
    try:
        repository.save_pending_registration(
            request_id=request_id,
            name=checked["name"] or "成长者",
            email=checked["email"],
            password_hash=password_hash,
            created_at=created_at,
            expires_at=expires_at,
        )
    except ValueError:
        raise PendingRegistrationUnavailable(
            "registration request unavailable"
        ) from None
    return PendingRegistrationReceipt(
        request_id, datetime.fromtimestamp(expires_at, timezone.utc)
    )


def get_pending_registration(repository, request_id, *, now=None):
    """Read an unexpired INTERNAL record, never proof of mailbox ownership."""
    if not isinstance(request_id, str) or _REQUEST_ID.fullmatch(request_id) is None:
        return None
    row = repository.get_pending_registration(request_id, _timestamp(now))
    if row is None:
        return None
    return PendingRegistration(
        request_id=row[0],
        name=row[1],
        email=row[2],
        password_hash=row[3],
        created_at=datetime.fromtimestamp(row[4], timezone.utc),
        expires_at=datetime.fromtimestamp(row[5], timezone.utc),
    )
