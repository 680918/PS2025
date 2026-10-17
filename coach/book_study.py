"""Local book ranges and honest explanation coverage; no model calls."""

import re


def position(chunk, material):
    if material["kind"] == "pdf":
        match = re.fullmatch(
            r"PDF 第 ([1-9][0-9]*) 页 · 片段 [1-9][0-9]*", chunk["locator"]
        )
        return int(match[1]) if match else None
    return chunk["chunk_index"]


def unit_chunks(material, chunks, start, end):
    maximum = material["page_count"] if material["kind"] == "pdf" else len(chunks)
    if (
        type(start) is not int
        or type(end) is not int
        or not 1 <= start <= end <= maximum
    ):
        raise ValueError("请输入资料范围内的起止页码或片段编号，起点不能晚于终点。")
    return [
        chunk
        for chunk in chunks
        if (value := position(chunk, material)) is not None and start <= value <= end
    ]


def range_label(material, start, end):
    return (
        ("PDF 第 " if material["kind"] == "pdf" else "文字片段 ")
        + f"{start}–{end}"
        + (" 页" if material["kind"] == "pdf" else "")
    )


def study_directory(material, chunks, units, coverage, current_id=None):
    explained = {row["chunk_id"] for row in coverage}
    current = next((chunk for chunk in chunks if chunk["chunk_id"] == current_id), None)
    cards = []
    for unit in units:
        selected = unit_chunks(material, chunks, unit["start_pos"], unit["end_pos"])
        ids = {chunk["chunk_id"] for chunk in selected}
        cards.append(
            {
                **unit,
                "chunks": selected,
                "label": range_label(material, unit["start_pos"], unit["end_pos"]),
                "total": len(selected),
                "explained": len(ids & explained),
                "current": current_id in ids,
                "resume": next(
                    (chunk for chunk in selected if chunk["chunk_id"] not in explained),
                    selected[0] if selected else None,
                ),
            }
        )
    active = next((card for card in cards if card["current"]), None)
    scope = active["chunks"] if active else chunks
    following = next(
        (
            chunk
            for chunk in scope
            if current and chunk["chunk_index"] > current["chunk_index"]
        ),
        None,
    )
    return {
        "units": cards,
        "unit": active,
        "current": current,
        "next": following,
        "total": len(chunks),
        "explained": sum(chunk["chunk_id"] in explained for chunk in chunks),
        "current_explained": current_id in explained if current else False,
    }
