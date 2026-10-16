"""Internal credential operations, deliberately not connected to HTTP routes.

Callers must independently verify account ownership before initializing a password.
A password match alone is not an email activation, session, or access permission.
"""

from security.passwords import hash_password, verify_password


def initialize_user_password(repository, user_id: str, password: str) -> None:
    """Initialize once after ownership verification; never reset an existing hash."""
    password_hash = hash_password(password)
    repository.save_initial_password_hash(user_id, password_hash)


def verify_user_password(repository, user_id: str, password: str) -> bool:
    """Verify by stable user ID without creating or changing any account."""
    return verify_password(password, repository.get_password_hash(user_id))
