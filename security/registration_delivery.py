"""Internal, synchronous registration mail delivery. No HTTP route or auto-retry."""

import re
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlencode, urlunsplit
from uuid import uuid4

from security.email_verification import (
    EmailVerificationMessage,
    RESEND_INTERVAL_SECONDS,
    VERIFICATION_LIFETIME_SECONDS,
    _registration_token_hash,
    _timestamp,
    _trusted_activation_url,
)
from security.pending_registration import registration_browser_secret_hash
from security.verification_mailer import (
    MailConfigurationError,
    MailDeliveryError,
    SMTPSettings,
    send_verification_email,
)


@dataclass(frozen=True)
class RegistrationDeliveryStatus:
    state: str
    retry_after_seconds: int = 0


def _owner_hash(request_id, browser_secret):
    digest = registration_browser_secret_hash(browser_secret)
    if (
        not isinstance(request_id, str)
        or re.fullmatch(r"registration_[0-9a-f]{32}", request_id) is None
        or digest is None
    ):
        raise ValueError("registration verification unavailable")
    return digest


def get_registration_delivery_status(
    repository, request_id, browser_secret, *, now: datetime | None = None
) -> RegistrationDeliveryStatus | None:
    try:
        digest = _owner_hash(request_id, browser_secret)
    except ValueError:
        return None
    timestamp = _timestamp(now)
    row = repository.get_registration_delivery_status(request_id, digest, timestamp)
    if row is None:
        return None
    state, issued_at = row
    wait = (
        max(0, issued_at + RESEND_INTERVAL_SECONDS - timestamp)
        if state == "failed"
        else 0
    )
    return RegistrationDeliveryStatus(state, wait)


def send_registration_verification(
    repository,
    request_id,
    activation_url,
    settings: SMTPSettings | None,
    *,
    browser_secret,
    retry_failed: bool = False,
    now: datetime | None = None,
    sender=None,
    allowed_recipient=None,
) -> RegistrationDeliveryStatus:
    """Claim before SMTP; only an explicit retry of a definite failure is allowed.

    Trusted callers provide configuration, never submitted URLs/credentials.
    A crash leaves 'sending' locked; timeout/unknown results must not be retried
    automatically. No raw link, recipient, or SMTP error is returned or stored.
    """
    if not isinstance(settings, SMTPSettings):
        raise MailConfigurationError("邮件发送尚未启用，请先完成本机配置。")
    if not isinstance(retry_failed, bool):
        raise ValueError("registration verification unavailable")
    if sender is not None and not callable(sender):
        raise MailConfigurationError("邮件发送配置无效。")
    digest = _owner_hash(request_id, browser_secret)
    parsed = _trusted_activation_url(activation_url)
    issued_at = _timestamp(now)
    attempt_id = uuid4().hex
    token = secrets.token_urlsafe(32)
    recipient, expires_at = repository.issue_registration_verification_token(
        request_id=request_id,
        token_hash=_registration_token_hash(token),
        issued_at=issued_at,
        lifetime=VERIFICATION_LIFETIME_SECONDS,
        resend_interval=RESEND_INTERVAL_SECONDS,
        browser_token_hash=digest,
        delivery_attempt_id=attempt_id,
        retry_failed=retry_failed,
    )
    message = EmailVerificationMessage(
        recipient=recipient,
        activation_url=urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, urlencode({"token": token}), "")
        ),
        expires_at=datetime.fromtimestamp(expires_at, timezone.utc),
    )
    try:
        if allowed_recipient is not None and recipient != allowed_recipient:
            raise MailConfigurationError("本次测试仅允许向已确认的本人邮箱发送。")
        # No database transaction is held while waiting for the mail server.
        (sender if sender is not None else send_verification_email)(
            message, settings, now=now
        )
    except MailConfigurationError:
        state = "failed"  # Message validation fails before any SMTP connection.
    except MailDeliveryError as error:
        state = (
            "failed"
            if error.code
            in {"authentication_failed", "recipient_refused", "rejected", "unsupported"}
            else "unknown"
        )
    except Exception:
        # Unexpected sender errors may follow DATA submission; preserve the link.
        state = "unknown"
    else:
        state = "accepted"  # Server accepted; this does not prove inbox arrival.
    try:
        saved = repository.finish_registration_delivery(request_id, attempt_id, state)
    except sqlite3.Error:
        saved = False
    # An interrupted final write leaves 'sending' durable and blocks duplicates.
    wait = (
        max(0, issued_at + RESEND_INTERVAL_SECONDS - _timestamp(now))
        if saved and state == "failed"
        else 0
    )
    return RegistrationDeliveryStatus(state if saved else "unknown", wait)
