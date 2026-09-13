from knowledge.local_embedding_provider import (
    LocalEmbeddingProvider,
)
from knowledge.semantic_topic_resolver import (
    cosine_similarity,
)


provider = LocalEmbeddingProvider()


TOPIC_PROTOTYPES = {
    "函数": [
        "封装一段可以重复使用的代码逻辑",
        "把一段逻辑组织起来供以后调用",
        "定义一个可以多次调用的代码单元",
    ],
    "变量": [
        "保存程序运行过程中的数据",
        "存储计算产生的值供后续使用",
        "给数据或计算结果一个名字并保存",
    ],
    "循环": [
        "重复执行同一个操作",
        "让一段代码连续运行多次",
        "对相同任务进行多次重复执行",
    ],
}


queries = [
    (
        "有一段逻辑以后还要多次使用，应该怎么组织？",
        "函数",
    ),
    (
        "程序算出来的值以后还要继续使用，应该放到哪里？",
        "变量",
    ),
    (
        "同样的操作需要反复做几十次，有什么合适的方法？",
        "循环",
    ),
    (
        "Python异常处理有什么作用？",
        None,
    ),
    (
        "Python类有什么作用？",
        None,
    ),
    (
        "数据库事务有什么作用？",
        None,
    ),
    (
        "一段代码以后可能重复使用，应该怎么组织？",
        "函数",
    ),
    (
        "运行过程中有个值需要暂时记住，应该用什么？",
        "变量",
    ),
]


for query, expected_topic in queries:
    query_vector = provider.embed(query)

    scores = []

    for topic, prototypes in (
        TOPIC_PROTOTYPES.items()
    ):
        prototype_scores = []

        for prototype in prototypes:
            prototype_vector = provider.embed(
                prototype
            )

            score = cosine_similarity(
                query_vector,
                prototype_vector,
            )

            prototype_scores.append(score)

        topic_score = max(
            prototype_scores
        )

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
        print(
            f"{topic}: {score:.4f}"
        )