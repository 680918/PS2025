import re
from knowledge.models import KnowledgeChunk


def chunk_document(
    document,
    chunk_size=500,
    overlap=0,
):
    if chunk_size <= 0:
        raise ValueError("chunk_size 必须大于 0")

    if overlap < 0:
        raise ValueError("overlap 不能小于 0")

    if overlap >= chunk_size:
        raise ValueError("overlap 必须小于 chunk_size")

    content = document.content.strip()

    if not content:
        return []

    base_chunks = build_sentence_chunks(
        content,
        chunk_size,
    )

    if overlap == 0:
        chunk_contents = base_chunks
    else:
        chunk_contents = add_overlap(
            base_chunks,
            overlap,
        )

    chunks = []

    for index, chunk_content in enumerate(chunk_contents):
        chunks.append(
            KnowledgeChunk(
                document_id=document.id,
                content=chunk_content,
                chunk_index=index,
                source=document.source,
            )
        )

    return chunks


def split_sentences(text):
    if not text.strip():
        return []

    parts = re.split(
        r"(?<=[。！？.!?])\s*",
        text.strip(),
    )

    return [part.strip() for part in parts if part.strip()]


def build_sentence_chunks(
    text,
    chunk_size,
):
    sentences = split_sentences(text)

    if not sentences:
        return []

    chunks = []
    current = ""

    for sentence in sentences:
        if len(sentence) > chunk_size:
            if current:
                chunks.append(current)
                current = ""

            for start in range(
                0,
                len(sentence),
                chunk_size,
            ):
                chunks.append(sentence[start : start + chunk_size])

            continue

        candidate = current + sentence

        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                chunks.append(current)

            current = sentence

    if current:
        chunks.append(current)

    return chunks


def add_overlap(
    chunks,
    overlap,
):
    if not chunks:
        return []

    if overlap <= 0:
        return list(chunks)

    result = [chunks[0]]

    for index in range(1, len(chunks)):
        previous = chunks[index - 1]
        current = chunks[index]

        prefix = previous[-overlap:]

        result.append(prefix + current)

    return result
