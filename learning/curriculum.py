from dataclasses import dataclass


@dataclass
class CurriculumItem:
    position: int
    topic: str


@dataclass
class LearningCurriculum:
    journey_id: str
    items: list[CurriculumItem]

    def get_next_topic(self, current_topic):
        ordered_items = sorted(
            self.items,
            key=lambda item: item.position,
        )

        for index, item in enumerate(ordered_items):
            if item.topic == current_topic:
                if index + 1 < len(ordered_items):
                    return ordered_items[index + 1].topic

                return None

        return None
