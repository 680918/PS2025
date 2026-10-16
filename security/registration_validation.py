"""Read-only form checks; never create users, retain passwords or send mail."""

from email.errors import HeaderParseError
from email.headerregistry import Address
import re

from security.passwords import MIN_PASSWORD_LENGTH, MAX_PASSWORD_LENGTH


def validate_registration_fields(name, email, password):
    """Return editable fields and fixed errors. Never include the password."""
    name = name.strip()
    email = email.strip().lower()
    errors = {}
    if len(name) > 40 or any(ord(char) < 32 or ord(char) == 127 for char in name):
        errors["name"] = "称呼请控制在 40 个字符以内，不含换行等控制字符。"
    try:
        if (
            not 1 <= len(email) <= 254
            or not email.isascii()
            or any(
                char.isspace() or ord(char) < 32 or ord(char) == 127 for char in email
            )
        ):
            raise ValueError
        address = Address(addr_spec=email)
        labels = address.domain.split(".")
        if (
            not address.username
            or len(address.username) > 64
            or address.addr_spec != email
            or len(labels) < 2
            or any(
                not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                for label in labels
            )
            or labels[-1].isdigit()
        ):
            raise ValueError
    except (ValueError, HeaderParseError):
        errors["email"] = "请输入完整、常用的邮箱地址，例如 name@163.com。"
    try:
        password.encode("utf-8")
        if (
            not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH
            or password.isspace()
        ):
            raise ValueError
    except (ValueError, UnicodeError):
        errors["password"] = (
            "密码需要 15–128 个字符，可以使用中文、空格或一段好记的话，不能全是空白。"
        )
    return {
        "name": name[:40] if "name" not in errors else "",
        "email": email[:254]
        if not any(ord(char) < 32 or ord(char) == 127 for char in email)
        else "",
        "errors": errors,
    }


def masked_registration_email(email):
    local, domain = email.rsplit("@", 1)
    return f"{local[0]}***@{domain}"
