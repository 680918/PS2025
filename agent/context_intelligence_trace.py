from dataclasses import dataclass


@dataclass
class ContextIntelligenceTrace:
    assembled_context: object

    conflicts: dict

    resolutions: dict

    evaluations: dict

    report: object
