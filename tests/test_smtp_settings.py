from datetime import datetime
from pathlib import Path

import pytest

from security.email_verification import EmailVerificationMessage
from security.verification_mailer import (
    MailConfigurationError,
    SMTPSettings,
    build_verification_email,
    load_smtp_settings,
)


def test_settings_are_opt_in_and_hide_email_and_authorization_code(monkeypatch):
    monkeypatch.setenv("SMTP_ENABLED", "true")
    monkeypatch.setenv("SMTP_USERNAME", "test-only-sender@163.com")
    monkeypatch.setenv("SMTP_AUTH_CODE", "test-only-auth-code")
    monkeypatch.setenv("SMTP_TIMEOUT", "12.5")
    settings = load_smtp_settings()
    assert settings.username == "test-only-sender@163.com"
    assert settings.timeout == 12.5
    assert settings.username not in repr(settings)
    assert settings.authorization_code not in repr(settings)


@pytest.mark.parametrize(
    "values",
    [
        {"SMTP_ENABLED": "yes"},
        {"SMTP_ENABLED": "true"},
        {"SMTP_ENABLED": "true", "SMTP_USERNAME": "test-only-sender@163.com"},
        {"SMTP_ENABLED": "true", "SMTP_TIMEOUT": "invalid"},
    ],
)
def test_missing_or_malformed_settings_are_reported_without_values(values):
    with pytest.raises(MailConfigurationError):
        load_smtp_settings(values)


@pytest.mark.parametrize(
    "username",
    [
        "sender@example.com",
        "sender@vip.163.com",
        "",
        "bad",
        "a@163.com\nBcc:other@example.com",
    ],
)
def test_sender_is_limited_to_single_plain_163_account(username):
    with pytest.raises(MailConfigurationError):
        SMTPSettings(username, "test-only-code")


@pytest.mark.parametrize(
    "code", [None, "", "contains space", "has\nnewline", "中文授权码", "x" * 257]
)
def test_invalid_authorization_code_is_not_echoed(code):
    with pytest.raises(MailConfigurationError) as caught:
        SMTPSettings("test-only-sender@163.com", code)
    assert "客户端授权码" in str(caught.value)


@pytest.mark.parametrize("timeout", [0, -1, 61, float("nan"), float("inf"), True, "15"])
def test_timeout_must_be_finite_and_bounded(timeout):
    with pytest.raises(MailConfigurationError, match="超时"):
        SMTPSettings("test-only-sender@163.com", "test-only-code", timeout)


def test_naive_expiry_time_is_not_assumed_to_be_local_time():
    message = EmailVerificationMessage(
        "learner@example.com",
        "https://coach.example.com/verify?token=test",
        datetime(2026, 10, 16),
    )
    with pytest.raises(MailConfigurationError, match="时区"):
        build_verification_email(message, "test-only-sender@163.com")


def test_example_environment_has_no_credentials_and_defaults_to_disabled():
    example = Path(__file__).resolve().parents[1] / ".env.example"
    values = {}
    for line in example.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            name, value = line.split("=", 1)
            values[name] = value
    assert values["SMTP_ENABLED"] == "false"
    assert values["SMTP_USERNAME"] == values["SMTP_AUTH_CODE"] == ""
    assert load_smtp_settings(values) is None
