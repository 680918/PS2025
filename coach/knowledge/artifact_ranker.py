def rank_artifacts(
    artifacts,
    query,
):

    scored = []

    for artifact in artifacts:
        score = 0

        if query.lower() in artifact.topic.lower():
            score += 10

        if query.lower() in artifact.title.lower():
            score += 5

        scored.append(
            (
                score,
                artifact,
            )
        )

    scored.sort(
        key=lambda x: x[0],
        reverse=True,
    )

    return [item[1] for item in scored]
