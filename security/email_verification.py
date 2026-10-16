"""Email verification primitives; callers control HTTP access and mail delivery."""

import hashlib
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlencode, urlsplit, urlunsplit
from uuid import uuid4


VERIFICATION_LIFETIME_SECONDS = 3600
RESEND_INTERVAL_SECONDS = 60
_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}")


@dataclass(frozen=True)
class EmailVerificationMessage:
    recipient: str = field(repr=False)
    activation_url: str = field(repr=False)
    expires_at: datetime


def _timestamp(now):
    if now is None:
        now = datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("verification time must include a timezone")
    return int(now.timestamp())


def _trusted_activation_url(activation_url):
    # This must be application configuration, never a submitted URL or Host header.
    if (
        not isinstance(activation_url, str)
        or not activation_url
        or len(activation_url) > 2048
        or "\\" in activation_url
        or any(
            character.isspace() or ord(character) < 32 for character in activation_url
        )
    ):
        raise ValueError("invalid configured activation URL")
    try:
        parsed = urlsplit(activation_url)
        port = parsed.port
        loopback = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if (
            not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or (parsed.scheme != "https" and not (parsed.scheme == "http" and loopback))
            or (port is not None and port < 1)
        ):
            raise ValueError
    except ValueError:
        raise ValueError("invalid configured activation URL") from None
    return parsed


def issue_email_verification(
    repository,
    user_id: str,
    activation_url: str,
    *,
    now: datetime | None = None,
) -> EmailVerificationMessage:
    """Prepare a message for the user's stored email, without sending or logging it."""
    parsed = _trusted_activation_url(activation_url)
    issued_at = _timestamp(now)
    expires_at = issued_at + VERIFICATION_LIFETIME_SECONDS
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
    recipient = repository.issue_email_verification_token(
        user_id=user_id,
        token_hash=token_hash,
        issued_at=issued_at,
        expires_at=expires_at,
        resend_interval=RESEND_INTERVAL_SECONDS,
    )
    link = urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urlencode({"token": token}), "")
    )
    return EmailVerificationMessage(
        recipient=recipient,
        activation_url=link,
        expires_at=datetime.fromtimestamp(expires_at, timezone.utc),
    )


def confirm_email_verification(
    repository,
    token: str,
    *,
    now: datetime | None = None,
) -> str | None:
    """Consume once and return the verified user ID; this is not a login session."""
    if (
        not isinstance(token, str)
        or len(token) != 43
        or _TOKEN_PATTERN.fullmatch(token) is None
    ):
        return None
    token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
    return repository.consume_email_verification_token(token_hash, _timestamp(now))


def _registration_token_hash(token):
    # A registration link must never act as an existing user's verification link.
    return hashlib.sha256(b"registration\0" + token.encode("ascii")).hexdigest()


def issue_registration_verification(
    repository, request_id: str, activation_url: str, *, now: datetime | None = None
) -> EmailVerificationMessage:
    """Prepare a draft's one-time link for a TRUSTED internal caller; no SMTP.

    The configured URL must target a registration-specific confirmation handler.
    This primitive is not a public resend API or proof of mailbox ownership.
    """
    parsed = _trusted_activation_url(activation_url)
    if (
        not isinstance(request_id, str)
        or re.fullmatch(r"registration_[0-9a-f]{32}", request_id) is None
    ):
        raise ValueError("registration verification unavailable")
    token = secrets.token_urlsafe(32)
    recipient, expires_at = repository.issue_registration_verification_token(
        request_id=request_id,
        token_hash=_registration_token_hash(token),
        issued_at=_timestamp(now),
        lifetime=VERIFICATION_LIFETIME_SECONDS,
        resend_interval=RESEND_INTERVAL_SECONDS,
    )
    return EmailVerificationMessage(
        recipient=recipient,
        activation_url=urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, urlencode({"token": token}), "")
        ),
        expires_at=datetime.fromtimestamp(expires_at, timezone.utc),
    )


def confirm_registration_verification(
    repository, token: str, *, now: datetime | None = None
) -> str | None:
    """Create the verified account atomically, once. Does not log the user in."""
    if not isinstance(token, str) or _TOKEN_PATTERN.fullmatch(token) is None:
        return None
    return repository.consume_registration_verification_token(
        token_hash=_registration_token_hash(token),
        now=_timestamp(now),
        user_id=str(uuid4()),
    )
