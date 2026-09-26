from learning.curriculum import CurriculumItem, LearningCurriculum


def test_curriculum_item_should_preserve_position_and_topic():
    item = CurriculumItem(
        position=4,
        topic="Python函数",
    )

    assert item.position == 4
    assert item.topic == "Python函数"


def test_learning_curriculum_should_belong_to_journey_and_hold_items():
    items = [
        CurriculumItem(
            position=1,
            topic="Python变量",
        ),
        CurriculumItem(
            position=2,
            topic="Python条件判断",
        ),
    ]

    curriculum = LearningCurriculum(
        journey_id="journey_001",
        items=items,
    )

    assert curriculum.journey_id == "journey_001"
    assert len(curriculum.items) == 2
    assert curriculum.items[0].topic == "Python变量"
    assert curriculum.items[1].topic == "Python条件判断"


def test_curriculum_should_find_next_topic_in_its_own_items():
    curriculum = LearningCurriculum(
        journey_id="journey_001",
        items=[
            CurriculumItem(position=1, topic="Python变量"),
            CurriculumItem(position=2, topic="Python条件判断"),
            CurriculumItem(position=3, topic="Python循环"),
        ],
    )

    next_topic = curriculum.get_next_topic("Python条件判断")

    assert next_topic == "Python循环"


def test_curriculum_should_follow_position_not_list_order():
    curriculum = LearningCurriculum(
        journey_id="journey_001",
        items=[
            CurriculumItem(position=3, topic="Python循环"),
            CurriculumItem(position=1, topic="Python变量"),
            CurriculumItem(position=2, topic="Python条件判断"),
        ],
    )

    next_topic = curriculum.get_next_topic("Python条件判断")

    assert next_topic == "Python循环"


def test_curriculum_should_return_none_at_end_of_path():
    curriculum = LearningCurriculum(
        journey_id="journey_001",
        items=[
            CurriculumItem(position=1, topic="Python变量"),
            CurriculumItem(position=2, topic="Python条件判断"),
        ],
    )

    assert curriculum.get_next_topic("Python条件判断") is None


def test_curriculum_should_return_none_for_unknown_topic():
    curriculum = LearningCurriculum(
        journey_id="journey_001",
        items=[
            CurriculumItem(position=1, topic="Python变量"),
            CurriculumItem(position=2, topic="Python条件判断"),
        ],
    )

    assert curriculum.get_next_topic("英语听力") is None


def test_curriculum_should_identify_last_topic():
    curriculum = LearningCurriculum(
        journey_id="journey_001",
        items=[
            CurriculumItem(position=1, topic="Python变量"),
            CurriculumItem(position=2, topic="Python条件判断"),
        ],
    )

    assert curriculum.is_last_topic("Python条件判断") is True


def test_curriculum_should_not_treat_non_last_topic_as_last():
    curriculum = LearningCurriculum(
        journey_id="journey_001",
        items=[
            CurriculumItem(position=1, topic="Python变量"),
            CurriculumItem(position=2, topic="Python条件判断"),
        ],
    )

    assert curriculum.is_last_topic("Python变量") is False


def test_curriculum_should_not_treat_unknown_topic_as_last():
    curriculum = LearningCurriculum(
        journey_id="journey_001",
        items=[
            CurriculumItem(position=1, topic="Python变量"),
            CurriculumItem(position=2, topic="Python条件判断"),
        ],
    )

    assert curriculum.is_last_topic("英语听力") is False


def test_empty_curriculum_should_have_no_last_topic():
    curriculum = LearningCurriculum(
        journey_id="journey_001",
        items=[],
    )

    assert curriculum.is_last_topic("Python变量") is False
