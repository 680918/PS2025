from dataclasses import dataclass


@dataclass
class EvaluationReport:
    passed: bool

    evaluations: dict

    summary: dict
