class InMemoryLearningSessionRepository:
    def __init__(self):
        self._sessions = []

    def save(self, session):
        self._sessions.append(session)

    def get_latest_by_journey(
        self,
        journey_id,
    ):
        matching_sessions = [
            session for session in self._sessions if session.journey_id == journey_id
        ]

        if not matching_sessions:
            return None

        return matching_sessions[-1]
