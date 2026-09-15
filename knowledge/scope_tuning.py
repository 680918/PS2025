from knowledge.scope_batch_evaluation import evaluate_scope_cases


def tune_scope_parameters(
    cases,
    available_documents,
    top_n_values,
    min_score_values,
):
    trials = []

    best_parameters = None
    best_score = None

    for top_n in top_n_values:
        for min_score in min_score_values:
            evaluation = evaluate_scope_cases(
                cases=cases,
                available_documents=available_documents,
                top_n=top_n,
                min_score=min_score,
            )

            score = evaluation["average_f1"]

            trial = {
                "top_n": top_n,
                "min_score": min_score,
                "score": score,
                "evaluation": evaluation,
            }

            trials.append(trial)

            is_better = False

            if best_score is None:
                is_better = True
            elif score > best_score:
                is_better = True
            elif score == best_score:
                if top_n < best_parameters["top_n"]:
                    is_better = True
                elif (
                    top_n == best_parameters["top_n"]
                    and min_score > best_parameters["min_score"]
                ):
                    is_better = True
            if is_better:
                best_score = score
                best_parameters = {
                    "top_n": top_n,
                    "min_score": min_score,
                }

    return {
        "best_parameters": best_parameters,
        "best_score": best_score,
        "trials": trials,
    }
