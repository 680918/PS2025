"""Password hashing primitives; these functions do not establish a login session."""

from argon2 import PasswordHasher, Type, extract_parameters
from argon2.exceptions import VerificationError


MIN_PASSWORD_LENGTH = 15
MAX_PASSWORD_LENGTH = 128
_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)


def _valid_password_input(password):
    if not isinstance(password, str) or not 0 < len(password) <= MAX_PASSWORD_LENGTH:
        return False
    try:
        password.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def hash_password(password: str) -> str:
    """Use Argon2id and a fresh library-generated salt; preserve the exact input."""
    if (
        not _valid_password_input(password)
        or len(password) < MIN_PASSWORD_LENGTH
        or password.isspace()
    ):
        raise ValueError("password must contain 15 to 128 characters and not be blank")
    return _HASHER.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Check a stored internal hash. Missing or malformed credentials fail closed."""
    if (
        not _valid_password_input(password)
        or not isinstance(password_hash, str)
        or not 0 < len(password_hash) <= 512
    ):
        return False
    try:
        parameters = extract_parameters(password_hash)
        # Bound work even if an internal database record has been corrupted.
        if (
            parameters.type != Type.ID
            or parameters.version != 19
            or not 1 <= parameters.time_cost <= 10
            or not 8 <= parameters.memory_cost <= 262144
            or not 1 <= parameters.parallelism <= 16
            or not 16 <= parameters.salt_len <= 64
            or not 16 <= parameters.hash_len <= 64
        ):
            return False
        return _HASHER.verify(password_hash, password)
    except (ValueError, VerificationError):
        return False
