import smtplib
import ssl
import traceback
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import pytest

from security.email_verification import (
    EmailVerificationMessage,
    confirm_email_verification,
    issue_email_verification,
)
from security.verification_mailer import (
    MailConfigurationError,
    MailDeliveryError,
    SMTPSettings,
    build_verification_email,
    load_smtp_settings,
    send_verification_email,
)
from user.model import User
from user.sqlite_repository import SQLiteUserRepository


NOW = datetime(2026, 10, 16, 8, 0, tzinfo=timezone.utc)
SECRET = "test-only-authorization-code"
TOKEN = "a" * 43


@pytest.fixture
def verification():
    return EmailVerificationMessage(
        recipient="learner@example.com",
        activation_url=f"https://coach.example.com/web/verify-email?token={TOKEN}",
        expires_at=NOW + timedelta(hours=1),
    )


@pytest.fixture
def settings():
    return SMTPSettings("test-only-sender@163.com", SECRET)


@pytest.fixture(autouse=True)
def transport(monkeypatch):
    events = []
    behavior = {}

    class SMTP:
        def __init__(self, host, port, *, timeout, context):
            events.append(("connect", host, port, timeout, context))
            if "connect_error" in behavior:
                raise behavior["connect_error"]

        def __enter__(self):
            return self

        def __exit__(self, *args):
            events.append(("close",))
            if "close_error" in behavior:
                raise behavior["close_error"]

        def login(self, username, authorization_code):
            events.append(("login", username, authorization_code))
            if "login_error" in behavior:
                raise behavior["login_error"]

        def send_message(self, message, *, from_addr, to_addrs):
            events.append(("send", message, from_addr, to_addrs))
            if "send_error" in behavior:
                raise behavior["send_error"]
            return behavior.get("refused", {})

    def plaintext_is_forbidden(*args, **kwargs):
        raise AssertionError("plaintext SMTP must never be used")

    monkeypatch.setattr(smtplib, "SMTP_SSL", SMTP)
    monkeypatch.setattr(smtplib, "SMTP", plaintext_is_forbidden)
    return events, behavior


def test_message_has_text_html_chinese_content_and_no_credentials(verification):
    message = build_verification_email(
        verification, "test-only-sender@163.com", now=NOW
    )
    assert str(message["Subject"]) == "验证你的知行成长教练账号"
    assert message["To"].addresses[0].addr_spec == "learner@example.com"
    assert message["From"].addresses[0].display_name == "知行成长教练"
    assert message["Message-ID"]
    assert message["Date"]
    plain = message.get_body(preferencelist=("plain",)).get_content()
    html = message.get_body(preferencelist=("html",)).get_content()
    assert verification.activation_url in plain
    assert verification.activation_url in html
    assert "2026-10-16 17:00:00" in plain
    assert "不是你的操作" in plain
    assert "请勿转发" in html
    assert "密码或邮箱授权码" in plain
    assert SECRET not in message.as_string()
    assert "<script" not in html
    assert "<img" not in html


def test_link_is_escaped_in_html(verification):
    link = 'https://coach.example.com/verify?token=a&extra="<bad>"'
    mail = EmailVerificationMessage(
        verification.recipient, link, verification.expires_at
    )
    message = build_verification_email(mail, "test-only-sender@163.com", now=NOW)
    html = message.get_body(preferencelist=("html",)).get_content()
    assert "&amp;extra=&quot;&lt;bad&gt;&quot;" in html
    assert "<bad>" not in html


def test_tls_auth_and_explicit_single_recipient_submission(
    verification, settings, transport, capsys
):
    events, _ = transport
    assert send_verification_email(verification, settings, now=NOW) is None
    assert [event[0] for event in events] == ["connect", "login", "send", "close"]
    _, host, port, timeout, context = events[0]
    assert (host, port, timeout) == ("smtp.163.com", 465, 15)
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    assert context.minimum_version >= ssl.TLSVersion.TLSv1_2
    assert events[1] == ("login", settings.username, SECRET)
    assert events[2][2:] == (settings.username, [verification.recipient])
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""


@pytest.mark.parametrize(
    "stage,error,code",
    [
        (
            "login_error",
            smtplib.SMTPAuthenticationError(535, f"raw {SECRET}".encode()),
            "authentication_failed",
        ),
        (
            "connect_error",
            ssl.SSLCertVerificationError("raw certificate error"),
            "tls_failed",
        ),
        ("connect_error", OSError("raw network address"), "connection_failed"),
        ("send_error", TimeoutError(f"raw {TOKEN}"), "timeout"),
        (
            "send_error",
            smtplib.SMTPRecipientsRefused(
                {"learner@example.com": (550, b"raw rejection")}
            ),
            "recipient_refused",
        ),
        ("send_error", smtplib.SMTPDataError(554, f"raw {TOKEN}".encode()), "rejected"),
        (
            "send_error",
            smtplib.SMTPSenderRefused(550, b"raw", "test-only-sender@163.com"),
            "rejected",
        ),
        ("send_error", smtplib.SMTPNotSupportedError("raw extension"), "unsupported"),
        (
            "send_error",
            smtplib.SMTPServerDisconnected(f"raw {TOKEN}"),
            "connection_failed",
        ),
    ],
)
def test_delivery_failures_are_redacted_and_not_retried(
    verification, settings, transport, stage, error, code
):
    events, behavior = transport
    behavior[stage] = error
    with pytest.raises(MailDeliveryError) as caught:
        send_verification_email(verification, settings, now=NOW)
    assert caught.value.code == code
    formatted = "".join(traceback.format_exception(caught.value))
    for secret in [
        SECRET,
        TOKEN,
        "raw",
        "learner@example.com",
        "test-only-sender@163.com",
    ]:
        assert secret not in formatted
    assert len([event for event in events if event[0] == "connect"]) == 1
    assert len([event for event in events if event[0] == "send"]) <= 1


def test_refused_recipient_return_value_is_not_success(
    verification, settings, transport
):
    _, behavior = transport
    behavior["refused"] = {"learner@example.com": (550, b"refused")}
    with pytest.raises(MailDeliveryError) as caught:
        send_verification_email(verification, settings, now=NOW)
    assert caught.value.code == "recipient_refused"


def test_failed_quit_after_acceptance_does_not_resend_or_report_submission_failure(
    verification, settings, transport
):
    events, behavior = transport
    behavior["close_error"] = smtplib.SMTPServerDisconnected(
        "connection closed after acceptance"
    )
    send_verification_email(verification, settings, now=NOW)
    assert len([event for event in events if event[0] == "send"]) == 1


def test_disabled_or_unconfigured_sender_never_connects(verification, transport):
    events, _ = transport
    assert load_smtp_settings({}) is None
    assert load_smtp_settings({"SMTP_ENABLED": "false", "SMTP_USERNAME": "bad"}) is None
    with pytest.raises(MailConfigurationError, match="尚未启用"):
        send_verification_email(verification, None, now=NOW)
    assert events == []


@pytest.mark.parametrize("seconds", [0, -1])
def test_expired_message_is_not_sent(verification, settings, transport, seconds):
    events, _ = transport
    message = EmailVerificationMessage(
        verification.recipient,
        verification.activation_url,
        NOW + timedelta(seconds=seconds),
    )
    with pytest.raises(MailConfigurationError, match="过期"):
        send_verification_email(message, settings, now=NOW)
    assert events == []


@pytest.mark.parametrize(
    "recipient",
    [
        "bad",
        "",
        "first@example.com,second@example.com",
        "Name <learner@example.com>",
        "learner@example.com\r\nBcc:other@example.com",
    ],
)
def test_invalid_or_injected_recipient_never_connects(
    verification, settings, transport, recipient
):
    events, _ = transport
    message = EmailVerificationMessage(
        recipient, verification.activation_url, verification.expires_at
    )
    with pytest.raises(MailConfigurationError):
        send_verification_email(message, settings, now=NOW)
    assert events == []


@pytest.mark.parametrize(
    "link",
    [
        "javascript:alert(1)",
        "http://coach.example.com/verify?token=a",
        "https://name:secret@coach.example.com/verify?token=a",
        "https://coach.example.com/verify",
        "https://coach.example.com/verify?token=a\n",
    ],
)
def test_invalid_link_never_connects(verification, settings, transport, link):
    events, _ = transport
    message = EmailVerificationMessage(
        verification.recipient, link, verification.expires_at
    )
    with pytest.raises(MailConfigurationError, match="链接格式"):
        send_verification_email(message, settings, now=NOW)
    assert events == []


@pytest.mark.parametrize("fails", [False, True])
def test_mail_submission_never_consumes_verification_or_changes_password(
    tmp_path, settings, transport, fails
):
    repository = SQLiteUserRepository(tmp_path / "users.db")
    user = User(name="成长者", email="learner@example.com")
    repository.save(user)
    message = issue_email_verification(
        repository, user.user_id, "https://coach.example.com/web/verify-email", now=NOW
    )
    if fails:
        transport[1]["send_error"] = TimeoutError("not confirmed")
        with pytest.raises(MailDeliveryError):
            send_verification_email(message, settings, now=NOW)
    else:
        send_verification_email(message, settings, now=NOW)
    assert not repository.is_email_verified(user.user_id)
    assert repository.get_password_hash(user.user_id) is None
    token = parse_qs(urlsplit(message.activation_url).query)["token"][0]
    assert confirm_email_verification(repository, token, now=NOW) == user.user_id
