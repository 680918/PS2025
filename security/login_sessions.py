"""Verified email login and opaque, revocable eight-hour browser sessions."""

import hashlib
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone

from security.passwords import verify_password
from security.registration_validation import validate_registration_fields


SESSION_LIFETIME = 8 * 3600


@dataclass(frozen=True)
class LoginReceipt:
    token: str = field(repr=False)
    expires_at: datetime


@dataclass(frozen=True)
class SignedInAccount:
    user_id: str = field(repr=False)
    name: str = field(repr=False)
    email: str = field(repr=False)
    expires_at: datetime


def _timestamp(now):
    now = datetime.now(timezone.utc) if now is None else now
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("login time must include a timezone")
    return int(now.timestamp())


def session_token_hash(token):
    if not isinstance(token, str) or re.fullmatch(r"[A-Za-z0-9_-]{43}", token) is None:
        return None
    return hashlib.sha256(b"login-session\0" + token.encode("ascii")).hexdigest()


def sign_in(repository, email, password, *, dummy_hash, previous_token=None, now=None):
    """One generic failure for missing credentials, bad passwords and unverified email."""
    if not isinstance(email, str) or not isinstance(password, str):
        return None
    checked = validate_registration_fields("", email, password)
    user = repository.get_by_email(checked["email"]) if not checked["errors"] else None
    stored = repository.get_password_hash(user.user_id) if user is not None else None
    matches = verify_password(password, stored if stored is not None else dummy_hash)
    if (
        user is None
        or stored is None
        or not matches
        or not repository.is_email_verified(user.user_id)
    ):
        return None
    timestamp = _timestamp(now)
    token = secrets.token_urlsafe(32)
    expiry = timestamp + SESSION_LIFETIME
    repository.save_login_session(
        session_token_hash(token),
        user.user_id,
        timestamp,
        expiry,
        session_token_hash(previous_token),
    )
    return LoginReceipt(token, datetime.fromtimestamp(expiry, timezone.utc))


def signed_in_account(repository, token, *, now=None):
    digest = session_token_hash(token)
    if digest is None:
        return None
    row = repository.get_login_session(digest, _timestamp(now))
    return (
        SignedInAccount(
            row[0], row[1], row[2], datetime.fromtimestamp(row[3], timezone.utc)
        )
        if row
        else None
    )


def sign_out(repository, token, *, now=None):
    digest = session_token_hash(token)
    if digest is not None:
        repository.revoke_login_session(digest, _timestamp(now))
