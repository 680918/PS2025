_REQUIRED_FIELDS = {
    "case_id",
    "category",
    "domain",
    "description",
    "query",
    "memory_context",
    "expected_effect",
    "evaluation_criteria",
    "rule_scoring",
    "benchmark_answers",
}

_VALID_CATEGORIES = {
    "helpful",
    "neutral",
    "harmful",
    "ambiguous",
}

_VALID_EFFECTS = {
    "positive",
    "neutral",
    "negative",
}


def validate_memory_calibration_case(
    case,
):
    missing_fields = _REQUIRED_FIELDS - set(case)

    if missing_fields:
        raise ValueError(f"missing required fields: {sorted(missing_fields)}")

    if case["category"] not in (_VALID_CATEGORIES):
        raise ValueError(f"invalid category: {case['category']}")

    if case["expected_effect"] not in (_VALID_EFFECTS):
        raise ValueError(f"invalid expected_effect: {case['expected_effect']}")

    if not isinstance(
        case["memory_context"],
        list,
    ):
        raise ValueError("memory_context must be a list")

    criteria = case["evaluation_criteria"]

    reference_context = case.get("reference_context")

    if reference_context is not None:
        if (
            not isinstance(
                reference_context,
                list,
            )
            or not reference_context
        ):
            raise ValueError("reference_context must be a non-empty list")

        for fact in reference_context:
            if not isinstance(fact, str) or not fact.strip():
                raise ValueError("reference_context must contain non-empty strings")

    if not isinstance(criteria, list) or not criteria:
        raise ValueError("evaluation_criteria must be a non-empty list")

    rules = case["rule_scoring"]

    if not isinstance(rules, dict):
        raise ValueError("rule_scoring must be a dict")

    for field_name in (
        "required_phrases",
        "forbidden_phrases",
    ):
        if not isinstance(
            rules.get(field_name),
            list,
        ):
            raise ValueError(f"{field_name} must be a list")

    answers = case["benchmark_answers"]

    if not isinstance(answers, dict):
        raise ValueError("benchmark_answers must be a dict")

    for answer_name in (
        "without_memory",
        "with_memory",
    ):
        answer = answers.get(answer_name)

        if not isinstance(answer, str) or not answer.strip():
            raise ValueError(
                f"{answer_name} benchmark answer must be a non-empty string"
            )

    return True


def get_memory_calibration_cases():
    cases = [
        {
            "case_id": "helpful-tool-calling-practice",
            "category": "helpful",
            "domain": "ai_agent",
            "description": (
                "Existing Tool Calling knowledge "
                "should let the learner move "
                "directly into practice."
            ),
            "query": "Continue learning Tool Calling",
            "memory_context": [
                {
                    "memory_key": ("learning:tool-calling"),
                    "content": (
                        "The learner understands "
                        "basic Tool Calling concepts "
                        "and should move to practice."
                    ),
                },
            ],
            "expected_effect": "positive",
            "evaluation_criteria": [
                ("Continue from existing Tool Calling knowledge."),
                ("Move toward practical tool execution."),
            ],
            "rule_scoring": {
                "required_phrases": [
                    "practical",
                    "tool",
                ],
                "forbidden_phrases": [
                    "start from zero",
                ],
            },
            "benchmark_answers": {
                "without_memory": (
                    "Tool Calling allows a model to invoke external tools."
                ),
                "with_memory": ("Let's build a practical Tool Calling workflow."),
            },
        },
        {
            "case_id": "helpful-python-list-continuity",
            "category": "helpful",
            "domain": "python",
            "description": (
                "Prior Python foundations should avoid restarting from basics."
            ),
            "query": "Continue learning Python lists",
            "memory_context": [
                {
                    "memory_key": ("learning:python-foundations"),
                    "content": (
                        "The learner already understands variables and functions."
                    ),
                },
            ],
            "expected_effect": "positive",
            "evaluation_criteria": [
                ("Build on existing Python foundations."),
                ("Explain list behavior and indexing."),
            ],
            "rule_scoring": {
                "required_phrases": [
                    "list",
                    "indexing",
                ],
                "forbidden_phrases": [
                    "variables from the beginning",
                ],
            },
            "benchmark_answers": {
                "without_memory": (
                    "Let's review variables from the beginning before lists."
                ),
                "with_memory": ("A Python list stores items and supports indexing."),
            },
        },
        {
            "case_id": "helpful-investing-existing-system",
            "category": "helpful",
            "domain": "investing",
            "description": (
                "Existing quantitative system "
                "context should produce concrete "
                "optimization advice."
            ),
            "query": ("How should I improve my stock selection system?"),
            "memory_context": [
                {
                    "memory_key": ("project:stock-selection"),
                    "content": (
                        "The system already uses "
                        "Tushare, hotspot scanning, "
                        "and ranked stock pools."
                    ),
                },
            ],
            "expected_effect": "positive",
            "evaluation_criteria": [
                (
                    "Use the existing system "
                    "rather than propose a new "
                    "system from scratch."
                ),
                ("Recommend concrete evaluation or backtest improvements."),
            ],
            "rule_scoring": {
                "required_phrases": [
                    "tushare",
                    "backtest",
                ],
                "forbidden_phrases": [
                    "start from scratch",
                ],
            },
            "benchmark_answers": {
                "without_memory": (
                    "Quantitative investing can use many different factors."
                ),
                "with_memory": (
                    "Keep your Tushare pipeline and add factor backtest evaluation."
                ),
            },
        },
        {
            "case_id": "neutral-study-time-dictionary",
            "category": "neutral",
            "domain": "python",
            "description": (
                "Study-time preference should not change a technical answer."
            ),
            "query": "Explain Python dictionaries",
            "memory_context": [
                {
                    "memory_key": ("profile:study-time"),
                    "content": ("The learner prefers afternoon study."),
                },
            ],
            "expected_effect": "neutral",
            "evaluation_criteria": [
                ("Explain dictionaries accurately."),
            ],
            "rule_scoring": {
                "required_phrases": [
                    "dictionary",
                    "key",
                ],
                "forbidden_phrases": [
                    "afternoon",
                ],
            },
            "benchmark_answers": {
                "without_memory": ("A Python dictionary stores key-value pairs."),
                "with_memory": ("A Python dictionary stores key-value pairs."),
            },
        },
        {
            "case_id": "neutral-thinking-style-database-index",
            "category": "neutral",
            "domain": "database",
            "description": (
                "A thinking-style preference "
                "may change presentation but "
                "should not change correctness."
            ),
            "query": "What is a database index?",
            "memory_context": [
                {
                    "memory_key": ("profile:thinking-style"),
                    "content": ("The learner prefers systems thinking."),
                },
            ],
            "expected_effect": "neutral",
            "evaluation_criteria": [
                ("Explain what an index does for database queries."),
            ],
            "rule_scoring": {
                "required_phrases": [
                    "index",
                    "query",
                ],
                "forbidden_phrases": [],
            },
            "benchmark_answers": {
                "without_memory": ("A database index speeds up query lookup."),
                "with_memory": ("A database index speeds up query lookup."),
            },
        },
        {
            "case_id": "neutral-windows-rest-api",
            "category": "neutral",
            "domain": "api",
            "description": (
                "Operating-system information "
                "should not alter a general "
                "REST API explanation."
            ),
            "query": "Explain REST APIs",
            "memory_context": [
                {
                    "memory_key": ("profile:operating-system"),
                    "content": ("The learner uses Windows."),
                },
            ],
            "expected_effect": "neutral",
            "evaluation_criteria": [
                ("Explain REST resources and HTTP interaction."),
            ],
            "rule_scoring": {
                "required_phrases": [
                    "http",
                    "resource",
                ],
                "forbidden_phrases": [
                    "windows",
                ],
            },
            "benchmark_answers": {
                "without_memory": ("REST APIs expose resources through HTTP requests."),
                "with_memory": ("REST APIs expose resources through HTTP requests."),
            },
        },
        {
            "case_id": "harmful-false-python-mastery",
            "category": "harmful",
            "domain": "python",
            "description": (
                "Incorrect mastery memory should cause harmful learning advice."
            ),
            "query": "Continue learning Python",
            "memory_context": [
                {
                    "memory_key": ("learning:python-mastery"),
                    "content": ("The learner has fully mastered Python."),
                },
            ],
            "expected_effect": "negative",
            "evaluation_criteria": [
                ("Preserve useful practice when learning is incomplete."),
            ],
            "reference_context": [
                (
                    "The learner has not fully mastered "
                    "Python and still needs foundational "
                    "practice."
                ),
            ],
            "rule_scoring": {
                "required_phrases": [
                    "practice",
                ],
                "forbidden_phrases": [
                    "fully mastered",
                    "skip basics",
                ],
            },
            "benchmark_answers": {
                "without_memory": ("Continue practice with small Python exercises."),
                "with_memory": ("You have fully mastered Python, so skip basics."),
            },
        },
        {
            "case_id": "harmful-stale-memory-project-state",
            "category": "harmful",
            "domain": "ai_agent",
            "description": (
                "Stale project state should not "
                "make the system redesign a "
                "Memory capability that exists."
            ),
            "query": ("How should I improve Agent Memory?"),
            "memory_context": [
                {
                    "memory_key": ("project:stale-memory-state"),
                    "content": ("The project has no Memory module."),
                },
            ],
            "expected_effect": "negative",
            "evaluation_criteria": [
                ("Improve the existing Memory system."),
                ("Do not incorrectly restart Memory implementation."),
            ],
            "rule_scoring": {
                "required_phrases": [
                    "retrieval",
                ],
                "forbidden_phrases": [
                    "no memory module",
                    "build memory from scratch",
                ],
            },
            "benchmark_answers": {
                "without_memory": ("Improve Memory retrieval quality and evaluation."),
                "with_memory": (
                    "There is no memory module, so build memory from scratch."
                ),
            },
        },
        {
            "case_id": "harmful-wrong-investment-preference",
            "category": "harmful",
            "domain": "investing",
            "description": (
                "Incorrect strategy preference should distort investment advice."
            ),
            "query": "How should I analyze stocks?",
            "memory_context": [
                {
                    "memory_key": ("profile:investment-style"),
                    "content": ("The user only cares about limit-up stocks."),
                },
            ],
            "expected_effect": "negative",
            "evaluation_criteria": [
                ("Preserve risk-aware multi-factor analysis."),
            ],
            "rule_scoring": {
                "required_phrases": [
                    "risk",
                    "multi-factor",
                ],
                "forbidden_phrases": [
                    "limit-up only",
                ],
            },
            "benchmark_answers": {
                "without_memory": (
                    "Use multi-factor analysis with explicit risk controls."
                ),
                "with_memory": ("Focus on limit-up only and ignore other signals."),
            },
        },
        {
            "case_id": "ambiguous-first-principles-neural-network",
            "category": "ambiguous",
            "domain": "ai",
            "description": (
                "A preferred reasoning style may "
                "improve presentation without "
                "changing answer quality."
            ),
            "query": "Explain neural networks",
            "memory_context": [
                {
                    "memory_key": ("profile:reasoning-style"),
                    "content": ("The learner prefers first-principles explanations."),
                },
            ],
            "expected_effect": "neutral",
            "evaluation_criteria": [
                ("Explain neural networks accurately and clearly."),
            ],
            "rule_scoring": {
                "required_phrases": [
                    "neural network",
                ],
                "forbidden_phrases": [],
            },
            "benchmark_answers": {
                "without_memory": (
                    "A neural network transforms inputs through connected layers."
                ),
                "with_memory": (
                    "From first principles, a "
                    "neural network transforms "
                    "inputs through connected layers."
                ),
            },
        },
        {
            "case_id": "ambiguous-learning-style-ai-plan",
            "category": "ambiguous",
            "domain": "learning",
            "description": (
                "Learning-style memory may improve "
                "personalization without changing "
                "factual correctness."
            ),
            "query": "How should I learn AI?",
            "memory_context": [
                {
                    "memory_key": ("profile:learning-style"),
                    "content": ("The learner prefers concepts before practice."),
                },
            ],
            "expected_effect": "positive",
            "evaluation_criteria": [
                ("Provide an actionable learning sequence."),
                ("Respect the learner's preferred progression."),
            ],
            "rule_scoring": {
                "required_phrases": [
                    "concept",
                    "practice",
                ],
                "forbidden_phrases": [],
            },
            "benchmark_answers": {
                "without_memory": ("Study courses and build some AI projects."),
                "with_memory": (
                    "Learn each core concept first, then reinforce it with practice."
                ),
            },
        },
        {
            "case_id": "ambiguous-management-database-design",
            "category": "ambiguous",
            "domain": "database",
            "description": (
                "Management experience may change "
                "framing but should not substitute "
                "for technical database design."
            ),
            "query": "How should I design a database?",
            "memory_context": [
                {
                    "memory_key": ("profile:management-experience"),
                    "content": ("The user has management experience."),
                },
            ],
            "expected_effect": "neutral",
            "evaluation_criteria": [
                ("Give technically sound database design guidance."),
            ],
            "rule_scoring": {
                "required_phrases": [
                    "database",
                ],
                "forbidden_phrases": [],
            },
            "benchmark_answers": {
                "without_memory": (
                    "Design the database around "
                    "entities, relationships, "
                    "and access patterns."
                ),
                "with_memory": (
                    "Design the database around "
                    "entities, relationships, "
                    "and access patterns while "
                    "considering stakeholders."
                ),
            },
        },
    ]
    for case in cases:
        validate_memory_calibration_case(case)
    return cases
