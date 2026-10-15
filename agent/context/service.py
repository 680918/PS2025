from agent.context.source_selector import (
    select_context_sources,
)


class ContextIntelligenceService:
    def __init__(
        self,
        providers,
    ):

        self.providers = providers

    def build_context(
        self,
        user_query,
    ):

        selected_sources = select_context_sources(user_query)

        from agent.context.runtime import (
            ContextRuntime,
        )

        runtime = ContextRuntime(
            providers=self.providers,
        )

        assembled_context = runtime.build(selected_sources)

        return {
            "selected_sources": selected_sources,
            "assembled_context": assembled_context,
        }
