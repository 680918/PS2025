class InMemoryConversationRepository:
    def __init__(self):
        self._messages = []

    def save(self, message):
        self._messages.append(message)

    def list_by_journey(
        self,
        journey_id,
        user_id,
    ):
        return [
            message
            for message in self._messages
            if message.journey_id == journey_id and message.user_id == user_id
        ]
