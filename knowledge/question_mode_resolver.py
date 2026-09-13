def resolve_question_mode(query):
    comparison_markers = [
        "有什么区别",
        "有什么不同",
        "比较一下",
        "比较",
        "区别",
        "不同",
    ]

    for marker in comparison_markers:
        if marker in query:
            return "comparison"

    return "focused"