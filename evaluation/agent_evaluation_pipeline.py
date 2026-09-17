from pathlib import Path

from evaluation.agent_evaluation import (
    evaluate_agent_response,
)
from evaluation.agent_evaluation_history import (
    compare_latest_agent_evaluations,
    save_agent_evaluation_history,
)
from evaluation.agent_evaluation_report import (
    save_agent_evaluation_comparison_report,
)


def run_agent_evaluation_pipeline(
    user_message,
    response,
    memory_context=None,
    knowledge_context=None,
    output_dir=None,
):
    output_dir = Path(output_dir)

    evaluation_result = evaluate_agent_response(
        user_message=user_message,
        response=response,
        memory_context=memory_context,
        knowledge_context=knowledge_context,
    )

    history_path = save_agent_evaluation_history(
        evaluation_result,
        output_dir,
    )

    comparison = compare_latest_agent_evaluations(
        output_dir,
    )

    comparison_path = None

    if comparison is not None:
        comparison_path = output_dir / "latest_agent_evaluation_comparison.txt"

        comparison_path = save_agent_evaluation_comparison_report(
            comparison,
            comparison_path,
        )

    return {
        "evaluation_result": evaluation_result,
        "history_path": history_path,
        "comparison": comparison,
        "comparison_path": comparison_path,
    }
