from user.model import User


def register_user(
    repository,
    name,
    email,
):
    normalized_email = email.strip().lower()

    if not normalized_email:
        raise ValueError("email is required")

    if (
        "@" not in normalized_email
        or normalized_email.startswith("@")
        or normalized_email.endswith("@")
    ):
        raise ValueError("invalid email")

    existing_user = repository.get_by_email(normalized_email)

    if existing_user is not None:
        raise ValueError("email already registered")

    user = User(
        name=name,
        email=normalized_email,
    )

    repository.save(user)

    return user
