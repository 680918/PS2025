def build_user_context(
    user_repository,
    user_id,
):
    user = user_repository.get_by_id(
        user_id,
    )

    if user is None:
        return {}

    return {
        "user_id": user.user_id,
        "name": user.name,
        "email": user.email,
    }
