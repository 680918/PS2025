from knowledge.local_embedding_provider import (
    LocalEmbeddingProvider,
)
from knowledge.semantic_topic_resolver import (
    TOPIC_PROTOTYPES,
    cosine_similarity,
)


provider = LocalEmbeddingProvider()


queries = [
    (
        "怎样把经常使用的一段处理过程整理成可以再次使用的东西？",
        "函数",
    ),
    (
        "很多地方都需要用到相同的处理过程，应该如何整理？",
        "函数",
    ),
    (
        "同样的处理流程不想重复写很多遍，该怎么办？",
        "函数",
    ),
    (
        "我不想每次都重新写同一套处理步骤。",
        "函数",
    ),
]


for query, expected_topic in queries:
    query_vector = provider.embed(query)

    scores = []

    for topic, prototypes in TOPIC_PROTOTYPES.items():
        prototype_scores = []

        for prototype in prototypes:
            prototype_vector = provider.embed(prototype)

            score = cosine_similarity(
                query_vector,
                prototype_vector,
            )

            prototype_scores.append(score)

        topic_score = max(prototype_scores)

        scores.append(
            (
                topic,
                topic_score,
            )
        )

    scores.sort(
        key=lambda item: item[1],
        reverse=True,
    )

    print("\nQuery:", query)
    print(
        "Expected:",
        expected_topic,
    )

    for topic, score in scores:
        print(f"{topic}: {score:.4f}")

    top1_topic, top1_score = scores[0]
    top2_topic, top2_score = scores[1]

    print("Top1:", top1_topic)
    print("Top1 score:", f"{top1_score:.4f}")
    print("Top2:", top2_topic)
    print(
        "Margin:",
        f"{top1_score - top2_score:.4f}",
    )
