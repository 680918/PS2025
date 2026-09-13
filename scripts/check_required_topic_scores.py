from knowledge.local_embedding_provider import (
    LocalEmbeddingProvider,
)
from knowledge.semantic_topic_resolver import (
    cosine_similarity,
)


provider = LocalEmbeddingProvider()

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


cases = [
    (
        "怎样减少重复代码？",
        ["函数", "变量", "循环"],
    ),
    (
        "变量和循环有什么区别？",
        ["变量", "循环"],
    ),
    (
        "变量和循环我已经了解了，现在怎样减少重复代码？",
        ["函数", "变量", "循环"],
    ),
]


for query, topics in cases:
    query_vector = provider.embed(query)

    scores = []

    for topic in topics:
        prototype_scores = []

        for prototype in REQUIRED_TOPIC_PROTOTYPES[topic]:
            prototype_vector = provider.embed(
                prototype
            )

            score = cosine_similarity(
                query_vector,
                prototype_vector,
            )

            prototype_scores.append(score)

        score = max(prototype_scores)

        scores.append(
            (
                topic,
                score,
            )
        )

    scores.sort(
        key=lambda item: item[1],
        reverse=True,
    )

    print()
    print("=" * 60)
    print("Query:", query)

    for topic, score in scores:
        print(
            f"{topic}: {score:.4f}"
        )

    if len(scores) >= 2:
        margin = (
            scores[0][1]
            - scores[1][1]
        )

        print(
            f"top1-top2 margin: {margin:.4f}"
        )