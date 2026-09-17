from evaluation.agent_evaluation import (
    evaluate_agent_response,
)
from evaluation.agent_evaluation_pipeline import (
    run_agent_evaluation_pipeline,
)


def build_agent_evaluation_input(
    state,
    response,
):
    return {
        "user_message": state.user_message,
        "response": response,
        "memory_context": state.memory_context,
        "knowledge_context": state.knowledge_context,
    }


def evaluate_agent_state_response(
    state,
    response,
):
    evaluation_input = build_agent_evaluation_input(
        state=state,
        response=response,
    )

    return evaluate_agent_response(
        **evaluation_input,
    )


def run_agent_state_evaluation_pipeline(
    state,
    response,
    output_dir,
):
    evaluation_input = build_agent_evaluation_input(
        state=state,
        response=response,
    )

    return run_agent_evaluation_pipeline(
        output_dir=output_dir,
        **evaluation_input,
    )
