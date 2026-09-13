from dataclasses import dataclass
import math


@dataclass
class TopicMatch:
    topic: str
    score: float


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


def cosine_similarity(vector_a, vector_b):
    dot_product = sum(a * b for a, b in zip(vector_a, vector_b))

    norm_a = math.sqrt(sum(a * a for a in vector_a))

    norm_b = math.sqrt(sum(b * b for b in vector_b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)


def resolve_semantic_topics(
    query,
    embedding_provider,
    min_score=0.62,
    min_margin=0.03,
):
    query_vector = embedding_provider.embed(query)

    matches = []

    for topic, prototypes in TOPIC_PROTOTYPES.items():
        prototype_scores = []

        for prototype in prototypes:
            prototype_vector = embedding_provider.embed(prototype)

            score = cosine_similarity(
                query_vector,
                prototype_vector,
            )

            prototype_scores.append(score)

        topic_score = max(prototype_scores)

        matches.append(
            TopicMatch(
                topic=topic,
                score=topic_score,
            )
        )

    matches.sort(
        key=lambda match: match.score,
        reverse=True,
    )

    if not matches:
        return []

    best_match = matches[0]

    if best_match.score < min_score:
        return []

    if len(matches) > 1:
        second_match = matches[1]

        margin = best_match.score - second_match.score

        if margin < min_margin:
            return []

    return [best_match]
