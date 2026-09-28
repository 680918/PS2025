import json

from memory.retrieval_policy import get_memory_policy


def test_should_get_journey_completion_policy():

    policy = get_memory_policy("journey_completion:python")

    assert policy.name == "journey_completion"


def test_journey_completion_policy_should_include_matching_domain():
    memory = {
        "memory_key": "journey_completion:python",
        "content": json.dumps(
            {
                "journey_id": "python",
                "domain": "Python",
            }
        ),
    }

    policy = get_memory_policy(memory["memory_key"])

    assert (
        policy.should_include(
            memory,
            learning_domain="Python",
        )
        is True
    )


def test_journey_completion_policy_should_exclude_mismatched_domain():
    memory = {
        "memory_key": "journey_completion:english",
        "content": json.dumps(
            {
                "journey_id": "english",
                "domain": "English",
            }
        ),
    }

    policy = get_memory_policy(memory["memory_key"])

    assert (
        policy.should_include(
            memory,
            learning_domain="Python",
        )
        is False
    )


def test_journey_completion_policy_should_exclude_invalid_json():
    memory = {
        "memory_key": "journey_completion:broken",
        "content": "not-valid-json",
    }

    policy = get_memory_policy(memory["memory_key"])

    assert (
        policy.should_include(
            memory,
            learning_domain="Python",
        )
        is False
    )


def test_journey_completion_policy_should_include_when_learning_domain_is_none():
    memory = {
        "memory_key": "journey_completion:python",
        "content": "not-valid-json",
    }

    policy = get_memory_policy(memory["memory_key"])

    assert (
        policy.should_include(
            memory,
            learning_domain=None,
        )
        is True
    )
