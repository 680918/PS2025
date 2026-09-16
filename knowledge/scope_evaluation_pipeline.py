from pathlib import Path
from knowledge.scope_batch_evaluation import (
    evaluate_scope_cases,
)
from knowledge.scope_evaluation_report import (
    build_scope_evaluation_report,
)
from knowledge.scope_tuning import (
    tune_scope_parameters,
)
from knowledge.scope_evaluation_history import (
    compare_latest_scope_evaluation_reports,
    save_latest_scope_evaluation_comparison,
    save_scope_evaluation_history_bundle,
)


def run_scope_evaluation_pipeline(
    cases,
    available_documents,
    output_dir,
):
    output_dir = Path(output_dir)

    batch_result = evaluate_scope_cases(
        cases=cases,
        available_documents=available_documents,
        top_n=2,
        min_score=2,
        min_relative_score=0.6,
    )

    tuning_result = tune_scope_parameters(
        cases=cases,
        available_documents=available_documents,
        top_n_values=[1, 2],
        min_score_values=[1, 2],
        min_relative_score_values=[
            None,
            0.5,
            0.6,
            0.75,
        ],
    )

    report = build_scope_evaluation_report(
        batch_result=batch_result,
        tuning_result=tuning_result,
    )

    history_paths = save_scope_evaluation_history_bundle(
        report,
        output_dir,
    )

    comparison = compare_latest_scope_evaluation_reports(
        output_dir,
    )

    comparison_path = save_latest_scope_evaluation_comparison(
        output_dir=output_dir,
        comparison_path=(output_dir / "latest_scope_comparison.txt"),
    )

    return {
        "batch_result": batch_result,
        "tuning_result": tuning_result,
        "report": report,
        "history_paths": history_paths,
        "comparison": comparison,
        "comparison_path": comparison_path,
    }
