from dataclasses import dataclass


@dataclass
class ContextIntelligenceResult:
    context: object

    conflicts: dict

    resolutions: dict

    report: object
