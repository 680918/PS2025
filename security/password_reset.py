"""Single-use password recovery for existing verified accounts; no implicit mail."""

import hashlib
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid
from html import escape
from urllib.parse import urlencode, urlsplit, urlunsplit

from security.email_verification import _timestamp, _trusted_activation_url
from security.passwords import hash_password
from security.verification_mailer import (
    MailConfigurationError,
    SMTPSettings,
    _mailbox,
    _send_mail_message,
)


RESET_LIFETIME = 1800
RESET_COOLDOWN = 60


@dataclass(frozen=True)
class PasswordResetMessage:
    recipient: str = field(repr=False)
    activation_url: str = field(repr=False)
    expires_at: datetime


@dataclass(frozen=True)
class PasswordChangedMessage:
    recipient: str = field(repr=False)


def reset_token_hash(token):
    if not isinstance(token, str) or re.fullmatch(r"[A-Za-z0-9_-]{43}", token) is None:
        return None
    return hashlib.sha256(b"password-reset\0" + token.encode("ascii")).hexdigest()


def issue_password_reset(repository, email, reset_url, *, now=None):
    """Trusted internal caller; unknown/unverified/legacy accounts return None."""
    parsed = _trusted_activation_url(reset_url)
    timestamp = _timestamp(now)
    token = secrets.token_urlsafe(32)
    recipient = repository.issue_password_reset_token(
        email,
        reset_token_hash(token),
        timestamp,
        timestamp + RESET_LIFETIME,
        cooldown=RESET_COOLDOWN,
    )
    if recipient is None:
        return None
    return PasswordResetMessage(
        recipient,
        urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, urlencode({"token": token}), "")
        ),
        datetime.fromtimestamp(timestamp + RESET_LIFETIME, timezone.utc),
    )


def reset_available(repository, token, *, now=None):
    digest = reset_token_hash(token)
    return digest is not None and repository.password_reset_available(
        digest, _timestamp(now)
    )


def complete_password_reset(repository, token, password, *, now=None):
    """Recheck in the write transaction after hashing, consume once, revoke sessions."""
    digest = reset_token_hash(token)
    if digest is None or not repository.password_reset_available(
        digest, _timestamp(now)
    ):
        return False
    password_hash = hash_password(password)
    # Actual wall time is checked AFTER potentially slow Argon2 work.
    return repository.consume_password_reset_token(
        digest, password_hash, _timestamp(now)
    )


def build_password_reset_email(reset, sender, *, now=None):
    now = datetime.now(timezone.utc) if now is None else now
    recipient = _mailbox(reset.recipient)
    sender_address = _mailbox(sender)
    if (
        not isinstance(now, datetime)
        or now.utcoffset() is None
        or not isinstance(reset.expires_at, datetime)
        or reset.expires_at.utcoffset() is None
        or reset.expires_at <= now
    ):
        raise MailConfigurationError("重置链接已过期，请重新申请。")
    # Validate both the configured base and the exact, purpose-specific token query.
    if not isinstance(reset.activation_url, str) or any(
        char.isspace() or ord(char) < 32 or ord(char) == 127
        for char in reset.activation_url
    ):
        raise MailConfigurationError("重置链接格式不正确。")
    parsed = urlsplit(reset.activation_url)
    base = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    _trusted_activation_url(base)
    if not re.fullmatch(r"token=[A-Za-z0-9_-]{43}", parsed.query) or parsed.fragment:
        raise MailConfigurationError("重置链接格式不正确。")
    deadline = reset.expires_at.astimezone(timezone(timedelta(hours=8))).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    link = reset.activation_url
    message = EmailMessage()
    message["Subject"] = "重新设置你的知行密码"
    message["From"] = Address(
        display_name="知行成长教练", addr_spec=sender_address.addr_spec
    )
    message["To"] = recipient
    message["Date"] = format_datetime(now)
    message["Message-ID"] = make_msgid(domain="163.com")
    message.set_content(
        "你好，我们收到了重新设置知行密码的请求。\n\n"
        f"请打开链接，填写并确认新密码：\n{link}\n\n"
        f"有效期至北京时间 {deadline}（UTC+8）。链接只能使用一次，重新发送后旧链接失效。\n"
        "重置成功后，原来的登录状态会失效，学习记录、教案和资料会保留。\n\n"
        "如果这不是你的操作，请忽略邮件，你的密码不会改变。请勿转发链接。\n"
        "知行不会通过邮件索要密码或邮箱授权码。\n"
    )
    safe = escape(link, quote=True)
    message.add_alternative(
        '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><body style="font-family:Arial,sans-serif;line-height:1.8;color:#263f31;padding:28px;max-width:560px;margin:auto">'
        '<p>知行 / AI 成长教练</p><h1 style="font-size:24px">重新设置密码，回到自己的成长空间。</h1>'
        "<p>我们收到了密码重置请求。请打开下方链接，在页面填写并确认新密码。</p>"
        f'<p><a href="{safe}" style="display:inline-block;background:#365e46;color:white;padding:12px 24px;border-radius:8px">设置新密码 →</a></p>'
        f"<p>有效期至北京时间 {deadline}（UTC+8）。链接只能使用一次，重新发送后旧链接失效。</p>"
        "<p>重置成功后，原来的登录状态会失效，学习记录、教案和资料会保留。</p>"
        f'<p style="overflow-wrap:anywhere">按钮无法打开时，复制完整链接到浏览器：<br>{safe}</p>'
        "<p>如果这不是你的操作，请忽略邮件，你的密码不会改变。请勿转发链接。<br>知行不会通过邮件索要密码或邮箱授权码。</p></body></html>",
        subtype="html",
    )
    return message


def send_password_reset_email(message, settings, *, now=None):
    if not isinstance(settings, SMTPSettings):
        raise MailConfigurationError("邮件发送尚未启用。")
    mail = build_password_reset_email(message, settings.username, now=now)
    _send_mail_message(mail, message.recipient, settings)


def send_password_changed_email(message, settings, *, now=None):
    if not isinstance(settings, SMTPSettings):
        raise MailConfigurationError("邮件发送尚未启用。")
    now = datetime.now(timezone.utc) if now is None else now
    mail = EmailMessage()
    mail["Subject"] = "你的知行密码已重新设置"
    mail["From"] = Address(
        display_name="知行成长教练", addr_spec=_mailbox(settings.username).addr_spec
    )
    mail["To"] = _mailbox(message.recipient)
    mail["Date"] = format_datetime(now)
    mail["Message-ID"] = make_msgid(domain="163.com")
    mail.set_content(
        "你的知行密码已重新设置，之前所有登录状态已失效。\n"
        "学习记录、教案和资料会继续保留，请用新密码重新登录。\n\n"
        "如果这不是你的操作，请尽快保护注册邮箱，并通过知行登录页的‘忘记密码’重新设置密码。\n"
        "知行不会通过邮件索要密码或邮箱授权码。\n"
    )
    _send_mail_message(mail, message.recipient, settings)
