from dataclasses import dataclass

from knowledge.semantic_topic_resolver import (
    cosine_similarity,
)


@dataclass
class RequiredTopicMatch:
    topic: str
    score: float


REQUIRED_TOPIC_PROTOTYPES = {
    "函数": [
        "怎样减少重复代码",
        "怎样复用一段逻辑",
        "怎样把重复逻辑封装起来重复调用",
        "一段逻辑以后还要使用应该怎么组织",
    ],
    "变量": [
        "怎样保存程序中的数据",
        "计算结果应该存放在哪里",
        "怎样保存一个值供后续使用",
        "程序运行中的数据应该怎么保存",
    ],
    "循环": [
        "怎样重复执行一段代码",
        "同一个操作需要执行很多次怎么办",
        "怎样让程序反复执行相同操作",
        "代码需要连续运行多次应该怎么做",
    ],
}


def resolve_semantic_required_topics(
    query,
    mentioned_topics,
    embedding_provider,
    selection_margin=0.05,
):
    if not mentioned_topics:
        return []

    query_vector = embedding_provider.embed(query)

    matches = []

    for topic in mentioned_topics:
        prototypes = REQUIRED_TOPIC_PROTOTYPES.get(
            topic,
            [topic],
        )

        prototype_scores = []

        for prototype in prototypes:
            prototype_vector = embedding_provider.embed(prototype)

            score = cosine_similarity(
                query_vector,
                prototype_vector,
            )

            prototype_scores.append(score)

        best_topic_score = max(prototype_scores)

        matches.append(
            RequiredTopicMatch(
                topic=topic,
                score=best_topic_score,
            )
        )

    matches.sort(
        key=lambda match: match.score,
        reverse=True,
    )

    best_score = matches[0].score

    selected_topics = [
        match.topic for match in matches if best_score - match.score <= selection_margin
    ]

    return selected_topics
