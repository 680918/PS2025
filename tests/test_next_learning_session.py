from learning.session_service import get_or_create_learning_session


def test_should_reuse_uncompleted_learning_session():
    class FakeSession:
        def __init__(self):
            self.session_id = "session-001"
            self.journey_id = "journey-001"
            self.user_id = "user-001"
            self.topic = "英语听力"
            self.completed = False

    class FakeSessionRepository:
        def __init__(self):
            self.existing_session = FakeSession()
            self.saved_sessions = []

        def get_latest_by_journey(self, journey_id):
            assert journey_id == "journey-001"
            return self.existing_session

        def save(self, session):
            self.saved_sessions.append(session)

    repository = FakeSessionRepository()

    session = get_or_create_learning_session(
        repository=repository,
        journey_id="journey-001",
        user_id="user-001",
        topic="英语听力",
    )

    assert session.session_id == "session-001"
    assert session.completed is False
    assert repository.saved_sessions == []


def test_should_create_new_session_after_previous_session_completed():
    class FakeSession:
        def __init__(self):
            self.session_id = "session-001"
            self.journey_id = "journey-001"
            self.user_id = "user-001"
            self.topic = "英语听力"
            self.completed = True
            self.understanding_score = 80
            self.difficulty = "听力速度较快"
            self.next_step = "练习慢速英语听力"

    class FakeSessionRepository:
        def __init__(self):
            self.existing_session = FakeSession()
            self.saved_sessions = []

        def get_latest_by_journey(self, journey_id):
            assert journey_id == "journey-001"
            return self.existing_session

        def save(self, session):
            self.saved_sessions.append(session)

    repository = FakeSessionRepository()

    new_session = get_or_create_learning_session(
        repository=repository,
        journey_id="journey-001",
        user_id="user-001",
        topic="慢速英语听力",
    )

    # 新一节必须有新的 Session ID。
    assert new_session.session_id != "session-001"

    # 新一节属于同一个用户和 Journey。
    assert new_session.journey_id == "journey-001"
    assert new_session.user_id == "user-001"

    # 新一节尚未完成，反馈从空白开始。
    assert new_session.topic == "慢速英语听力"
    assert new_session.completed is False
    assert new_session.understanding_score is None
    assert new_session.difficulty is None
    assert new_session.next_step is None

    # 新 Session 必须被保存。
    assert repository.saved_sessions == [new_session]

    # 上一节的反馈不能被修改。
    previous_session = repository.existing_session

    assert previous_session.completed is True
    assert previous_session.understanding_score == 80
    assert previous_session.difficulty == "听力速度较快"
    assert previous_session.next_step == "练习慢速英语听力"


def test_should_create_first_session_when_journey_has_no_sessions():
    class FakeSessionRepository:
        def __init__(self):
            self.saved_sessions = []

        def get_latest_by_journey(self, journey_id):
            assert journey_id == "journey-001"
            return None

        def save(self, session):
            self.saved_sessions.append(session)

    repository = FakeSessionRepository()

    session = get_or_create_learning_session(
        repository=repository,
        journey_id="journey-001",
        user_id="user-001",
        topic="英语基础",
    )

    assert session.journey_id == "journey-001"
    assert session.user_id == "user-001"
    assert session.topic == "英语基础"

    assert session.completed is False
    assert session.understanding_score is None
    assert session.difficulty is None
    assert session.next_step is None

    assert repository.saved_sessions == [session]


def test_should_query_latest_session_with_user_scope():
    class FakeSessionRepository:
        def __init__(self):
            self.calls = []
            self.saved_sessions = []

        def get_latest_by_journey_for_user(
            self,
            journey_id,
            user_id,
        ):
            self.calls.append((journey_id, user_id))
            return None

        def save(self, session):
            self.saved_sessions.append(session)

    repository = FakeSessionRepository()

    session = get_or_create_learning_session(
        repository=repository,
        journey_id="journey-001",
        user_id="user-001",
        topic="英语基础",
    )

    assert repository.calls == [("journey-001", "user-001")]

    assert session.user_id == "user-001"
    assert session.journey_id == "journey-001"


def test_should_not_reuse_session_owned_by_different_user():
    class FakeSession:
        def __init__(self):
            self.session_id = "session-user-b"
            self.journey_id = "journey-001"
            self.user_id = "user-b"
            self.topic = "英语听力"
            self.completed = False

    class FakeSessionRepository:
        def __init__(self):
            self.other_user_session = FakeSession()
            self.saved_sessions = []

        def get_latest_by_journey(self, journey_id):
            assert journey_id == "journey-001"
            return self.other_user_session

        def save(self, session):
            self.saved_sessions.append(session)

    repository = FakeSessionRepository()

    session = get_or_create_learning_session(
        repository=repository,
        journey_id="journey-001",
        user_id="user-a",
        topic="英语基础",
    )

    assert session.session_id != "session-user-b"
    assert session.user_id == "user-a"
    assert session.journey_id == "journey-001"
    assert session.topic == "英语基础"

    assert repository.saved_sessions == [session]

    assert repository.other_user_session.user_id == "user-b"
    assert repository.other_user_session.completed is False
