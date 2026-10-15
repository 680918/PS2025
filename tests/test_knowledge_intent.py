from coach.knowledge.intent import (
    is_knowledge_creation_request,
)


def test_should_detect_tutorial_request():

    assert is_knowledge_creation_request("把刚才学习的内容整理成教程")


def test_should_detect_summary_request():

    assert is_knowledge_creation_request("帮我总结一下刚才的知识，保存以后查看")


def test_should_detect_note_request():

    assert is_knowledge_creation_request("把这个知识点整理成笔记")


def test_should_not_detect_normal_learning_question():

    assert not is_knowledge_creation_request("Memory Retrieval是什么")
