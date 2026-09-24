import pytest
from learning.curriculum_generation_service import (
    generate_curriculum_topics,
)


def test_generate_curriculum_topics_should_use_domain_and_goal():
    class FakeCurriculumGenerator:
        def __init__(self):
            self.received = None

        def generate(self, domain, goal):
            self.received = (domain, goal)

            return [
                "Python变量",
                "Python条件判断",
                "Python函数",
            ]

    generator = FakeCurriculumGenerator()

    topics = generate_curriculum_topics(
        domain="Python",
        goal="能够独立编写简单程序",
        generator=generator,
    )

    assert generator.received == (
        "Python",
        "能够独立编写简单程序",
    )

    assert topics == [
        "Python变量",
        "Python条件判断",
        "Python函数",
    ]


@pytest.mark.parametrize(
    "invalid_topics",
    [
        "Python变量",
        123,
        ["Python变量", 123],
    ],
)
def test_generate_curriculum_topics_should_reject_invalid_topics(
    invalid_topics,
):
    class FakeCurriculumGenerator:
        def generate(self, domain, goal):
            return invalid_topics

    with pytest.raises(
        ValueError,
        match="curriculum topics must be a list of strings",
    ):
        generate_curriculum_topics(
            domain="Python",
            goal="能够独立编写简单程序",
            generator=FakeCurriculumGenerator(),
        )


@pytest.mark.parametrize(
    "domain, goal, expected_message",
    [
        ("   ", "能够独立编写简单程序", "domain is required"),
        ("Python", "   ", "goal is required"),
    ],
)
def test_generate_curriculum_topics_should_reject_blank_inputs(
    domain,
    goal,
    expected_message,
):
    class FakeCurriculumGenerator:
        def __init__(self):
            self.called = False

        def generate(self, domain, goal):
            self.called = True
            return ["Python变量"]

    generator = FakeCurriculumGenerator()

    with pytest.raises(ValueError, match=expected_message):
        generate_curriculum_topics(
            domain=domain,
            goal=goal,
            generator=generator,
        )

    assert generator.called is False


@pytest.mark.parametrize(
    "invalid_topics",
    [
        [""],
        ["   "],
        ["Python变量", "   "],
    ],
)
def test_generate_curriculum_topics_should_reject_blank_topics(
    invalid_topics,
):
    class FakeCurriculumGenerator:
        def generate(self, domain, goal):
            return invalid_topics

    with pytest.raises(
        ValueError,
        match="curriculum topics must not contain blank strings",
    ):
        generate_curriculum_topics(
            domain="Python",
            goal="能够独立编写简单程序",
            generator=FakeCurriculumGenerator(),
        )
