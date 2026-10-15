from agent.context.assembler import (
    assemble_context,
)


class ContextRuntime:
    def __init__(
        self,
        providers,
    ):

        self.providers = providers

    def build(
        self,
        selected_sources,
    ):

        contexts = {}

        for source in selected_sources:
            provider = self.providers.get(source)

            if provider is None:
                continue

            contexts[source] = provider.get_context()

        return assemble_context(contexts)
