from coach.knowledge.policy import (
    KnowledgeCurationPolicy,
)


def test_policy_should_have_default_curation_rules():

    policy = KnowledgeCurationPolicy()

    assert policy.min_learning_count == 3

    assert policy.min_understanding_score == 80

    assert policy.require_completion is False
