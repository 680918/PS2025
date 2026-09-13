import re
from knowledge.models import RetrievalResult


def normalize_query(query):
    query = query.lower().strip()

    query = re.sub(
        r"[？?！!，,。.;；:：]",
        " ",
        query,
    )

    return query


def retrieve_chunks(
    query,
    store,
    top_k=3,
    min_score=1.0,
):
    if not query.strip():
        return []

    query_terms = extract_query_terms(query)

    scored_chunks = []

    for chunk in store.list_all():
        score = score_chunk(
            query,
            query_terms,
            chunk.content,
        )

        if score >= min_score:
            scored_chunks.append((score, chunk))

    scored_chunks.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    return [
        RetrievalResult(
            chunk=chunk,
            score=score,
        )
        for score, chunk in scored_chunks[:top_k]
    ]


def extract_query_terms(query):
    normalized = normalize_query(query)

    terms = [term for term in normalized.split() if term]

    expanded_terms = []

    question_patterns = [
        "是什么",
        "有什么作用",
        "是干什么的",
    ]

    for term in terms:
        expanded_terms.append(term)

        for pattern in question_patterns:
            if pattern in term:
                cleaned = term.replace(
                    pattern,
                    "",
                )

                if cleaned:
                    expanded_terms.append(cleaned)

    return expanded_terms


def score_chunk(query, query_terms, content):
    normalized_content = content.lower()

    score = 0.0

    normalized_query = normalize_query(query).replace(
        " ",
        "",
    )

    compact_content = normalized_content.replace(
        " ",
        "",
    )

    if normalized_query and normalized_query in compact_content:
        score += 3.0

    matched_terms = 0

    for term in query_terms:
        if term in normalized_content:
            score += 1.0
            matched_terms += 1

    if query_terms:
        coverage = matched_terms / len(query_terms)
        score += coverage

    return score
