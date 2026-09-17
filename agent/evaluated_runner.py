from agent.controller import run_agent_runtime
from evaluation.agent_evaluation_adapter import (
    run_agent_state_evaluation_pipeline,
)


def build_evaluated_agent_result(
    response,
    state,
    evaluation_result,
):
    return {
        "response": response,
        "state": state,
        "evaluation_result": evaluation_result,
    }


def run_agent_with_evaluation(
    user_message,
    output_dir,
    memory_service=None,
    knowledge_service=None,
    document_ids=None,
):
    state, response = run_agent_runtime(
        user_message=user_message,
        memory_service=memory_service,
        knowledge_service=knowledge_service,
        document_ids=document_ids,
    )

    evaluation = run_agent_state_evaluation_pipeline(
        state=state,
        response=response,
        output_dir=output_dir,
    )

    result = build_evaluated_agent_result(
        response=response,
        state=state,
        evaluation_result=evaluation["evaluation_result"],
    )

    result["history_path"] = evaluation["history_path"]
    result["comparison"] = evaluation["comparison"]
    result["comparison_path"] = evaluation["comparison_path"]

    return result
