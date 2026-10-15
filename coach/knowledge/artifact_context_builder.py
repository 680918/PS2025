def build_artifact_context(
    artifacts,
):

    sections = []

    for artifact in artifacts:
        sections.append(
            f"""
主题：
{artifact.topic}

标题：
{artifact.title}

内容：
{artifact.content}
"""
        )

    return "\n".join(sections)
