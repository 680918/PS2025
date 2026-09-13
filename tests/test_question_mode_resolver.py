from knowledge.question_mode_resolver import (
    resolve_question_mode,
)


def test_normal_question_should_be_focused():
    assert (
        resolve_question_mode(
            "怎样减少重复代码？"
        )
        == "focused"
    )


def test_difference_question_should_be_comparison():
    assert (
        resolve_question_mode(
            "变量和循环有什么区别？"
        )
        == "comparison"
    )


def test_compare_question_should_be_comparison():
    assert (
        resolve_question_mode(
            "比较一下函数和循环。"
        )
        == "comparison"
    )


def test_different_question_should_be_comparison():
    assert (
        resolve_question_mode(
            "函数和循环有什么不同？"
        )
        == "comparison"
    )

    