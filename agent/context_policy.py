COMPLETED_LEARNING_POLICY = [
    "memory",
    "conversation",
]


USER_PREFERENCE_POLICY = [
    "conversation",
    "memory",
]


LEARNING_POLICY = [
    "conversation",
    "learning_continuity",
    "memory",
]


DEFAULT_POLICY = [
    "conversation",
    "learning_continuity",
    "memory",
]


FIELD_POLICY_RULES = [
    (
        "learning.completed_",
        "COMPLETED_LEARNING_POLICY",
        COMPLETED_LEARNING_POLICY,
    ),
    (
        "user.preference.",
        "USER_PREFERENCE_POLICY",
        USER_PREFERENCE_POLICY,
    ),
    (
        "learning.",
        "LEARNING_POLICY",
        LEARNING_POLICY,
    ),
]

FIELD_POLICY_NAMES = [
    (
        "learning.completed_",
        "COMPLETED_LEARNING_POLICY",
    ),
    (
        "user.preference.",
        "USER_PREFERENCE_POLICY",
    ),
    (
        "learning.",
        "LEARNING_POLICY",
    ),
]


def get_conflict_priority(
    field_name,
):

    for prefix, _, policy in FIELD_POLICY_RULES:
        if field_name.startswith(prefix):
            return policy

    return DEFAULT_POLICY


def get_policy_name(
    field_name,
):

    for prefix, name, _ in FIELD_POLICY_RULES:
        if field_name.startswith(prefix):
            return name

    return "DEFAULT_POLICY"


def get_conflict_policy_name(
    field_name,
):

    for prefix, name in FIELD_POLICY_NAMES:
        if field_name.startswith(prefix):
            return name

    return "DEFAULT_POLICY"
