from coach.context_models import CoachContext

from coach.context_providers.user_context_provider import (
    build_user_context,
)

from coach.context_providers.learning_context_provider import (
    build_learning_context,
)

from coach.context_providers.memory_context_provider import (
    build_memory_context,
)


def build_coach_context(
    *,
    user_id,
    user_message,
    user_repository,
    journey_repository,
    memory_service,
    journey_id=None,
):
    user_context = build_user_context(
        user_repository,
        user_id,
    )

    learning_context = build_learning_context(
        journey_repository,
        journey_id,
    )

    memory_context = build_memory_context(
        memory_service,
        user_message,
    )

    return CoachContext(
        user_context=user_context,
        learning_context=learning_context,
        memory_context=memory_context,
    )
