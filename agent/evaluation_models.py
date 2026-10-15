from dataclasses import dataclass


@dataclass
class EvaluationResult:
    metric: str

    passed: bool

    details: dict
