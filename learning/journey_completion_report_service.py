from learning.journey_completion_commentary_service import (
    generate_journey_completion_commentary,
)
from learning.journey_completion_report import (
    JourneyCompletionReport,
)


def get_or_create_journey_completion_report(
    repository,
    summary,
    user_id,
    commentary_generator,
):
    journey_id = summary["journey_id"]

    existing_report = repository.get_by_journey_for_user(
        journey_id=journey_id,
        user_id=user_id,
    )

    if existing_report is not None:
        return existing_report

    commentary = generate_journey_completion_commentary(
        summary=summary,
        commentary_generator=commentary_generator,
    )

    report = JourneyCompletionReport(
        journey_id=journey_id,
        user_id=user_id,
        summary=summary,
        commentary=commentary,
    )

    repository.save(report)

    return report
