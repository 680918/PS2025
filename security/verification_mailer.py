"""163 SMTP-over-TLS sender. Importing or loading settings never sends a message."""

import math
import os
import smtplib
import ssl
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.errors import HeaderParseError
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid
from html import escape
from urllib.parse import urlsplit

from security.email_verification import EmailVerificationMessage


_SMTP_HOST = "smtp.163.com"
_SMTP_PORT = 465
_BEIJING_TIME = timezone(timedelta(hours=8))


class MailConfigurationError(ValueError):
    pass


class MailDeliveryError(RuntimeError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def _mailbox(value):
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 254
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise MailConfigurationError("邮箱地址格式不正确。")
    try:
        address = Address(addr_spec=value)
        if not address.username or not address.domain:
            raise ValueError
    except (ValueError, HeaderParseError):
        raise MailConfigurationError("邮箱地址格式不正确。") from None
    return address


@dataclass(frozen=True)
class SMTPSettings:
    username: str = field(repr=False)
    authorization_code: str = field(repr=False)
    timeout: float = 15

    def __post_init__(self):
        address = _mailbox(self.username)
        if address.domain.lower() != "163.com" or not address.username.isascii():
            raise MailConfigurationError("本步请配置普通 163 邮箱作为发件人。")
        code = self.authorization_code
        if (
            not isinstance(code, str)
            or not 1 <= len(code) <= 256
            or any(not 33 <= ord(character) <= 126 for character in code)
        ):
            raise MailConfigurationError(
                "请配置有效的客户端授权码，不要使用邮箱登录密码。"
            )
        if (
            isinstance(self.timeout, bool)
            or not isinstance(self.timeout, (int, float))
            or not math.isfinite(self.timeout)
            or not 1 <= self.timeout <= 60
        ):
            raise MailConfigurationError("邮件连接超时应为 1 到 60 秒。")


def load_smtp_settings(values=None) -> SMTPSettings | None:
    """Read already-loaded environment values. Disabled by default; no network I/O."""
    values = os.environ if values is None else values
    enabled = values.get("SMTP_ENABLED", "false").strip().lower()
    if enabled == "false":
        return None
    if enabled != "true":
        raise MailConfigurationError("SMTP_ENABLED 只能填写 true 或 false。")
    try:
        timeout = float(values.get("SMTP_TIMEOUT", "15"))
    except (ValueError, TypeError):
        raise MailConfigurationError("邮件连接超时应为 1 到 60 秒。") from None
    return SMTPSettings(
        username=values.get("SMTP_USERNAME", ""),
        authorization_code=values.get("SMTP_AUTH_CODE", ""),
        timeout=timeout,
    )


def build_verification_email(
    verification: EmailVerificationMessage,
    sender: str,
    *,
    now: datetime | None = None,
) -> EmailMessage:
    """Prepare a plain-text + HTML message without sending or consuming its token."""
    sender_address = _mailbox(sender)
    recipient = _mailbox(verification.recipient)
    now = datetime.now(timezone.utc) if now is None else now
    expires = verification.expires_at
    if (
        not isinstance(now, datetime)
        or now.utcoffset() is None
        or not isinstance(expires, datetime)
        or expires.utcoffset() is None
    ):
        raise MailConfigurationError("邮件时间必须包含时区。")
    if expires <= now:
        raise MailConfigurationError("验证链接已过期，请重新申请。")
    link = verification.activation_url
    try:
        if (
            not isinstance(link, str)
            or len(link) > 4096
            or "\\" in link
            or any(character.isspace() or ord(character) < 32 for character in link)
        ):
            raise ValueError
        parsed = urlsplit(link)
        loopback = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if (
            not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
            or not parsed.query
            or (parsed.scheme != "https" and not (parsed.scheme == "http" and loopback))
        ):
            raise ValueError
    except ValueError:
        raise MailConfigurationError("验证链接格式不正确，请重新申请。") from None
    deadline = expires.astimezone(_BEIJING_TIME).strftime("%Y-%m-%d %H:%M:%S")
    message = EmailMessage()
    message["Subject"] = "验证你的知行成长教练账号"
    message["From"] = Address(
        display_name="知行成长教练", addr_spec=sender_address.addr_spec
    )
    message["To"] = recipient
    message["Date"] = format_datetime(now)
    message["Message-ID"] = make_msgid(domain="163.com")
    message.set_content(
        "你好，欢迎来到知行。\n\n"
        "请打开下面的链接，并在页面上确认验证邮箱：\n"
        f"{link}\n\n"
        f"有效期至北京时间 {deadline}（UTC+8）。链接只能使用一次，重新申请后旧链接失效。\n\n"
        "如果这不是你的操作，请忽略这封邮件。请勿将验证链接转发给他人。\n"
        "知行不会通过邮件索要你的密码或邮箱授权码。\n\n"
        "知行 · 为每一次想要成长的你\n"
    )
    safe_link = escape(link, quote=True)
    message.add_alternative(
        f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;background:#faf9f5;font-family:Arial,'Microsoft YaHei',sans-serif;color:#263f31;line-height:1.8">
<table role="presentation" style="width:100%;border-collapse:collapse"><tr><td style="padding:28px 16px">
<table role="presentation" style="width:100%;max-width:560px;margin:0 auto;background:#fff;border:1px solid #e0e5d9;border-radius:14px"><tr><td style="padding:30px">
<p style="margin:0 0 26px;color:#365e46;font-size:18px">知行 <span style="font-size:12px;color:#657267">/ AI 成长教练</span></p>
<h1 style="font-size:23px;font-weight:500;margin:0 0 16px">验证邮箱，开启自己的成长空间。</h1>
<p style="font-size:15px;margin:0 0 24px">你好，欢迎来到知行。请打开下方链接，并在页面上确认验证你的邮箱。</p>
<p style="margin:0 0 24px"><a href="{safe_link}" style="display:inline-block;padding:11px 24px;background:#365e46;color:#fff;text-decoration:none;border-radius:8px;font-size:15px">验证我的邮箱 →</a></p>
<p style="font-size:13px;color:#657267;margin:0 0 18px">有效期至北京时间 {deadline}（UTC+8）。<br>链接只能使用一次，重新申请后旧链接失效。</p>
<p style="font-size:12px;color:#657267;margin:0">按钮无法打开时，可复制下面的完整链接到浏览器：</p>
<p style="font-size:12px;overflow-wrap:anywhere;word-break:break-all;margin:8px 0 25px"><a href="{safe_link}" style="color:#365e46">{safe_link}</a></p>
<p style="border-top:1px solid #e0e5d9;padding-top:20px;font-size:12px;color:#657267;margin:0">如果这不是你的操作，请忽略这封邮件。请勿转发验证链接。<br>知行不会通过邮件索要你的密码或邮箱授权码。</p>
</td></tr></table><p style="text-align:center;font-size:12px;color:#657267;margin:18px 0 0">按自己的节奏，一点一点积累。</p>
</td></tr></table></body></html>""",
        subtype="html",
    )
    return message


def send_verification_email(
    verification: EmailVerificationMessage,
    settings: SMTPSettings | None,
    *,
    now: datetime | None = None,
) -> None:
    """Submit once to 163; success means server acceptance, not inbox delivery."""
    if not isinstance(settings, SMTPSettings):
        raise MailConfigurationError("邮件发送尚未启用，请先完成本机配置。")
    message = build_verification_email(verification, settings.username, now=now)
    _send_mail_message(message, verification.recipient, settings)


def _send_mail_message(message, recipient, settings):
    """Shared single-attempt TLS transport; messages are built by their purpose."""
    recipient = _mailbox(recipient).addr_spec
    sender = _mailbox(settings.username).addr_spec
    accepted = False
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(
            _SMTP_HOST, _SMTP_PORT, timeout=settings.timeout, context=context
        ) as client:
            client.login(settings.username, settings.authorization_code)
            refused = client.send_message(
                message, from_addr=sender, to_addrs=[recipient]
            )
            if refused:
                raise MailDeliveryError(
                    "recipient_refused", "收件地址被邮件服务器拒绝，请检查后重试。"
                )
            accepted = True
    except OSError as error:
        if accepted:
            # A failed QUIT after DATA acceptance must not trigger duplicate mail.
            return
        if isinstance(error, smtplib.SMTPAuthenticationError):
            code, detail = (
                "authentication_failed",
                "邮箱认证失败，请检查 SMTP 服务和客户端授权码。",
            )
        elif isinstance(error, ssl.SSLError):
            code, detail = "tls_failed", "邮件加密连接失败，请检查网络与证书配置。"
        elif isinstance(error, TimeoutError):
            code, detail = (
                "timeout",
                "邮件请求超时，投递结果未确认，请稍后查收再决定是否重试。",
            )
        elif isinstance(error, smtplib.SMTPRecipientsRefused):
            code, detail = (
                "recipient_refused",
                "收件地址被邮件服务器拒绝，请检查后重试。",
            )
        elif isinstance(error, (smtplib.SMTPDataError, smtplib.SMTPSenderRefused)):
            code, detail = (
                "rejected",
                "邮件服务器未接受本次邮件，请检查发信设置或稍后重试。",
            )
        elif isinstance(error, smtplib.SMTPNotSupportedError):
            code, detail = (
                "unsupported",
                "邮件服务器不支持本次发送要求，请检查收件地址格式。",
            )
        else:
            code, detail = (
                "connection_failed",
                "邮件连接中断，投递结果未确认，请稍后查收。",
            )
        raise MailDeliveryError(code, detail) from None
