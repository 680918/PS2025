"""Trusted internal registration drafts. No users, email tokens or sessions."""

import hashlib
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from security.passwords import hash_password
from security.registration_validation import (
    masked_registration_email,
    validate_registration_fields,
)


PENDING_REGISTRATION_LIFETIME_SECONDS = 3600
_REQUEST_ID = re.compile(r"registration_[0-9a-f]{32}")
_BROWSER_SECRET = re.compile(r"[A-Za-z0-9_-]{43}")


class PendingRegistrationUnavailable(ValueError):
    """One generic result for existing accounts, active duplicates or ID collision."""


@dataclass(frozen=True)
class PendingRegistrationReceipt:
    request_id: str = field(repr=False)
    expires_at: datetime


@dataclass(frozen=True)
class BrowserRegistrationReceipt:
    # Trusted handoff only. Never serialize this object into a page or log.
    request_id: str = field(repr=False)
    browser_secret: str = field(repr=False)
    expires_at: datetime


@dataclass(frozen=True)
class BrowserRegistrationStatus:
    masked_email: str = field(repr=False)
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
    """Legacy internal draft only; future web callers must use the bound flow."""
    return _begin_pending_registration(
        repository, email=email, password=password, name=name, now=now
    )


def registration_browser_secret_hash(value):
    """Internal domain-separated digest, or None for malformed credentials."""
    if not isinstance(value, str) or _BROWSER_SECRET.fullmatch(value) is None:
        return None
    return hashlib.sha256(b"registration-browser\0" + value.encode("ascii")).hexdigest()


def begin_browser_registration(repository, *, email, password, name="", now=None):
    """Atomically create a fresh draft and its immutable browser binding.

    Caller must enforce CSRF and rate limits before hashing, then deliver the
    secret only via a dedicated HttpOnly cookie. No HTTP or mail action here.
    """
    secret = secrets.token_urlsafe(32)
    digest = registration_browser_secret_hash(secret)
    if digest is None:
        raise PendingRegistrationUnavailable("registration request unavailable")
    receipt = _begin_pending_registration(
        repository,
        email=email,
        password=password,
        name=name,
        now=now,
        browser_token_hash=digest,
    )
    return BrowserRegistrationReceipt(receipt.request_id, secret, receipt.expires_at)


def _begin_pending_registration(
    repository, *, email, password, name="", now=None, browser_token_hash=None
):
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
            browser_token_hash=browser_token_hash,
        )
    except ValueError:
        raise PendingRegistrationUnavailable(
            "registration request unavailable"
        ) from None
    return PendingRegistrationReceipt(
        request_id, datetime.fromtimestamp(expires_at, timezone.utc)
    )


def get_browser_registration(repository, request_id, browser_secret, *, now=None):
    """Return only active request ID and expiry; never email or password hash."""
    row = _browser_registration_row(repository, request_id, browser_secret, now)
    if row is None:
        return None
    return PendingRegistrationReceipt(
        row[0], datetime.fromtimestamp(row[1], timezone.utc)
    )


def get_browser_registration_status(
    repository, request_id, browser_secret, *, now=None
):
    """Browser-authorized display data only, with the stored email masked."""
    row = _browser_registration_row(repository, request_id, browser_secret, now)
    if row is None:
        return None
    return BrowserRegistrationStatus(
        masked_registration_email(row[2]), datetime.fromtimestamp(row[1], timezone.utc)
    )


def _browser_registration_row(repository, request_id, browser_secret, now):
    if not isinstance(request_id, str) or _REQUEST_ID.fullmatch(request_id) is None:
        return None
    digest = registration_browser_secret_hash(browser_secret)
    if digest is None:
        return None
    return repository.get_browser_registration(request_id, digest, _timestamp(now))


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
