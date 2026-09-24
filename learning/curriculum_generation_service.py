def generate_curriculum_topics(
    domain,
    goal,
    generator,
):
    domain = domain.strip()
    goal = goal.strip()

    if not domain:
        raise ValueError("domain is required")

    if not goal:
        raise ValueError("goal is required")

    topics = generator.generate(
        domain=domain,
        goal=goal,
    )

    if not isinstance(topics, list) or not all(
        isinstance(topic, str) for topic in topics
    ):
        raise ValueError("curriculum topics must be a list of strings")

    if any(not topic.strip() for topic in topics):
        raise ValueError("curriculum topics must not contain blank strings")

    return topics
