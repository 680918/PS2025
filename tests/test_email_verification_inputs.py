from datetime import datetime
from urllib.parse import urlsplit

import pytest

from security.email_verification import (
    confirm_email_verification,
    issue_email_verification,
)


class NoDatabaseCalls:
    def issue_email_verification_token(self, **kwargs):
        raise AssertionError("invalid input must not issue a token")

    def consume_email_verification_token(self, *args):
        raise AssertionError("invalid input must not reach the database")


@pytest.mark.parametrize(
    "token",
    [
        None,
        b"a" * 43,
        "",
        "a" * 42,
        "a" * 44,
        "中" * 43,
        "/" * 43,
        "=" * 43,
        "\x00" * 43,
    ],
)
def test_invalid_token_format_is_rejected_before_database_access(token):
    assert confirm_email_verification(NoDatabaseCalls(), token) is None


@pytest.mark.parametrize(
    "url",
    [
        None,
        "",
        "//coach.example.com/verify",
        "javascript:alert(1)",
        "http://coach.example.com/verify",
        "https:///verify",
        "https://name:secret@coach.example.com/verify",
        "https://coach.example.com/verify?next=elsewhere",
        "https://coach.example.com/verify#section",
        "https://coach.example.com/verify\n",
        "https://coach.example.com:99999/verify",
        "https://coach.example.com:0/verify",
        "https://coach.example.com\\other/verify",
    ],
)
def test_untrusted_or_malformed_configured_url_cannot_issue_link(url):
    with pytest.raises(ValueError, match="invalid configured activation URL"):
        issue_email_verification(NoDatabaseCalls(), "user", url)


@pytest.mark.parametrize(
    "url",
    [
        "https://coach.example.com/web/verify-email",
        "http://localhost:8000/web/verify-email",
        "http://127.0.0.1:8000/web/verify-email",
        "http://[::1]:8000/web/verify-email",
    ],
)
def test_https_and_local_development_urls_are_accepted(url):
    class Repository:
        def issue_email_verification_token(self, **kwargs):
            return "learner@example.com"

    message = issue_email_verification(Repository(), "user", url)
    assert urlsplit(message.activation_url).netloc == urlsplit(url).netloc
    assert message.activation_url.startswith(url + "?token=")


def test_naive_time_is_rejected_instead_of_assuming_local_timezone():
    with pytest.raises(ValueError, match="timezone"):
        issue_email_verification(
            NoDatabaseCalls(),
            "user",
            "https://coach.example.com/verify",
            now=datetime(2026, 10, 16),
        )
    with pytest.raises(ValueError, match="timezone"):
        confirm_email_verification(
            NoDatabaseCalls(), "a" * 43, now=datetime(2026, 10, 16)
        )
