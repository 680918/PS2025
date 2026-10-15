from dataclasses import dataclass


@dataclass
class ContextDecisionTrace:
    field_name: str

    selected_source: str

    selected_value: object

    reason: str

    policy: str
