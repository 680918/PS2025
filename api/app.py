from fastapi import FastAPI, status, HTTPException

from user.service import register_user
from user.sqlite_repository import SQLiteUserRepository
from learning.journey_service import (
    create_learning_journey,
    start_learning_journey,
)
from learning.sqlite_journey_repository import (
    SQLiteLearningJourneyRepository,
)
from learning.sqlite_session_repository import (
    SQLiteLearningSessionRepository,
)
from learning.continuity import (
    build_learning_continuity_context,
)


def create_app(
    database_dir,
):
    app = FastAPI()

    user_repository = SQLiteUserRepository(database_dir / "users.db")

    journey_repository = SQLiteLearningJourneyRepository(database_dir / "journeys.db")

    session_repository = SQLiteLearningSessionRepository(database_dir / "sessions.db")

    @app.post(
        "/users",
        status_code=status.HTTP_201_CREATED,
    )
    def create_user(payload: dict):
        user = register_user(
            repository=user_repository,
            name=payload["name"],
            email=payload["email"],
        )

        return {
            "user_id": user.user_id,
            "name": user.name,
            "email": user.email,
        }

    @app.post(
        "/journeys",
        status_code=status.HTTP_201_CREATED,
    )
    def create_journey(payload: dict):
        journey = create_learning_journey(
            repository=journey_repository,
            user_repository=user_repository,
            user_id=payload["user_id"],
            domain=payload["domain"],
            goal=payload["goal"],
        )

        return {
            "journey_id": journey.journey_id,
            "user_id": journey.user_id,
            "domain": journey.domain,
            "goal": journey.goal,
            "status": journey.status,
        }

    @app.post(
        "/journeys/{journey_id}/start",
        status_code=status.HTTP_200_OK,
    )
    def start_journey(journey_id: str):
        journey = journey_repository.get_by_id(journey_id)

        if journey is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="journey not found",
            )

        try:
            session = start_learning_journey(
                repository=journey_repository,
                journey=journey,
                session_repository=session_repository,
            )
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(error),
            ) from error

        return {
            "journey_id": journey.journey_id,
            "status": journey.status,
            "session_id": session.session_id,
        }

    @app.get(
        "/journeys/{journey_id}/continue",
        status_code=status.HTTP_200_OK,
    )
    def continue_journey(
        journey_id: str,
        user_id: str,
    ):
        journey = journey_repository.get_by_id_for_user(
            journey_id=journey_id,
            user_id=user_id,
        )

        if journey is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="journey not found",
            )

        continuity = build_learning_continuity_context(
            journey_id=journey_id,
            user_id=user_id,
            repository=session_repository,
        )

        return continuity

    return app
