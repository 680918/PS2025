import pytest
from memory.context_selector import (
    select_relevant_memory_context,
)


def test_selector_should_rank_profile_memory():
    memory_context = {
        "profile": [
            {
                "memory_key": "profile:cooking",
                "content": "User likes cooking",
            },
            {
                "memory_key": "profile:ai",
                "content": "User likes AI Agent learning",
            },
        ],
        "skill": [],
        "learning": [],
        "project": [],
        "experience": [],
    }

    result = select_relevant_memory_context(
        memory_context,
        query="AI Agent",
    )

    assert result["profile"][0]["memory_key"] == "profile:ai"


def test_selector_should_rank_skill_memory():
    memory_context = {
        "profile": [],
        "skill": [
            {
                "memory_key": "skill:cooking",
                "content": "Cooking skill",
            },
            {
                "memory_key": "skill:python",
                "content": "Python programming skill",
            },
        ],
        "learning": [],
        "project": [],
        "experience": [],
    }

    result = select_relevant_memory_context(
        memory_context,
        query="Python programming",
    )

    assert result["skill"][0]["memory_key"] == "skill:python"


def test_selector_should_rank_project_memory():
    memory_context = {
        "profile": [],
        "skill": [],
        "learning": [],
        "project": [
            {
                "memory_key": "project:reading",
                "content": "Reading habit project",
            },
            {
                "memory_key": "project:agent",
                "content": "AI Agent memory retrieval project",
            },
        ],
        "experience": [],
    }

    result = select_relevant_memory_context(
        memory_context,
        query="AI Agent memory retrieval",
    )

    assert result["project"][0]["memory_key"] == "project:agent"


def test_selector_should_rank_experience_memory():
    memory_context = {
        "profile": [],
        "skill": [],
        "learning": [],
        "project": [],
        "experience": [
            {
                "memory_key": "experience:reading",
                "content": "Reflected on reading habit progress",
            },
            {
                "memory_key": "experience:agent",
                "content": "Learned lessons from AI Agent memory retrieval",
            },
        ],
    }

    result = select_relevant_memory_context(
        memory_context,
        query="AI Agent memory retrieval",
    )

    assert result["experience"][0]["memory_key"] == "experience:agent"


def test_selector_should_limit_profile_memory_by_type_top_k():
    memory_context = {
        "profile": [
            {
                "memory_key": "profile:cooking",
                "content": "User likes cooking",
            },
            {
                "memory_key": "profile:python",
                "content": "User is learning Python",
            },
            {
                "memory_key": "profile:agent",
                "content": "User likes AI Agent development",
            },
        ],
        "skill": [],
        "learning": [],
        "project": [],
        "experience": [],
    }

    result = select_relevant_memory_context(
        memory_context,
        query="AI Agent",
        memory_top_k_by_type={
            "profile": 1,
        },
    )

    assert len(result["profile"]) == 1
    assert result["profile"][0]["memory_key"] == "profile:agent"


def test_selector_should_keep_all_profile_memory_when_type_top_k_is_not_set():
    memory_context = {
        "profile": [
            {
                "memory_key": "profile:cooking",
                "content": "User likes cooking",
            },
            {
                "memory_key": "profile:python",
                "content": "User is learning Python",
            },
            {
                "memory_key": "profile:agent",
                "content": "User likes AI Agent development",
            },
        ],
        "skill": [],
        "learning": [],
        "project": [],
        "experience": [],
    }

    result = select_relevant_memory_context(
        memory_context,
        query="AI Agent",
    )

    assert len(result["profile"]) == 3


@pytest.mark.parametrize(
    ("memory_type", "relevant_key", "irrelevant_key"),
    [
        (
            "skill",
            "skill:python",
            "skill:cooking",
        ),
        (
            "project",
            "project:agent",
            "project:reading",
        ),
        (
            "experience",
            "experience:agent",
            "experience:reading",
        ),
    ],
)
def test_selector_should_limit_memory_by_type_top_k(
    memory_type,
    relevant_key,
    irrelevant_key,
):
    memory_context = {
        "profile": [],
        "skill": [],
        "learning": [],
        "project": [],
        "experience": [],
    }

    memory_context[memory_type] = [
        {
            "memory_key": irrelevant_key,
            "content": "Cooking and reading notes",
        },
        {
            "memory_key": relevant_key,
            "content": "AI Agent Python memory retrieval",
        },
    ]

    result = select_relevant_memory_context(
        memory_context,
        query="AI Agent Python memory retrieval",
        memory_top_k_by_type={
            memory_type: 1,
        },
    )

    assert len(result[memory_type]) == 1
    assert result[memory_type][0]["memory_key"] == relevant_key


def test_selector_should_limit_learning_memory_by_type_top_k():
    memory_context = {
        "profile": [],
        "skill": [],
        "learning": [
            {
                "memory_key": "learning:reading",
                "content": "Reading habit practice",
            },
            {
                "memory_key": "learning:agent",
                "content": "AI Agent memory retrieval practice",
            },
        ],
        "project": [],
        "experience": [],
    }

    result = select_relevant_memory_context(
        memory_context,
        query="AI Agent memory retrieval",
        memory_top_k_by_type={
            "learning": 1,
        },
    )

    assert len(result["learning"]) == 1
    assert result["learning"][0]["memory_key"] == "learning:agent"


def test_selector_should_keep_supporting_legacy_learning_top_k():
    memory_context = {
        "profile": [],
        "skill": [],
        "learning": [
            {
                "memory_key": "learning:reading",
                "content": "Reading habit practice",
            },
            {
                "memory_key": "learning:agent",
                "content": "AI Agent memory retrieval practice",
            },
        ],
        "project": [],
        "experience": [],
    }

    result = select_relevant_memory_context(
        memory_context,
        query="AI Agent memory retrieval",
        learning_top_k=1,
    )

    assert len(result["learning"]) == 1
    assert result["learning"][0]["memory_key"] == "learning:agent"


def test_selector_should_prefer_type_top_k_over_legacy_learning_top_k():
    memory_context = {
        "profile": [],
        "skill": [],
        "learning": [
            {
                "memory_key": "learning:reading",
                "content": "Reading habit practice",
            },
            {
                "memory_key": "learning:python",
                "content": "Python practice",
            },
            {
                "memory_key": "learning:agent",
                "content": "AI Agent memory retrieval practice",
            },
        ],
        "project": [],
        "experience": [],
    }

    result = select_relevant_memory_context(
        memory_context,
        query="AI Agent memory retrieval",
        learning_top_k=2,
        memory_top_k_by_type={
            "learning": 1,
        },
    )

    assert len(result["learning"]) == 1
    assert result["learning"][0]["memory_key"] == "learning:agent"
