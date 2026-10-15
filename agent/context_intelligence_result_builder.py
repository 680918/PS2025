from agent.context_intelligence_result import (
    ContextIntelligenceResult,
)


def build_context_intelligence_result(
    trace,
):

    return ContextIntelligenceResult(
        context=(trace.assembled_context),
        conflicts=(trace.conflicts),
        resolutions=(trace.resolutions),
        report=(trace.report),
    )
