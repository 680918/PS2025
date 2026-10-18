"""Bounded summaries of actually explained book passages, with explicit approval."""

import hashlib
import hmac
import json
import re
from time import time

from coach.book_study import unit_chunks, range_label
from coach.dialogue import CoachAnswer, _draft


BATCH_SIZE = 6


def unit_lesson_plan(repository, materials, user_id, material_id, unit_id):
    material = materials.get(user_id, material_id)
    unit = next(
        (
            row
            for row in repository.book_units(user_id, material_id)
            if row["unit_id"] == unit_id
        ),
        None,
    )
    if material is None or unit is None:
        raise ValueError("找不到这份本人资料或学习单元。")
    chunks = unit_chunks(
        material,
        materials.chunks(user_id, material_id),
        unit["start_pos"],
        unit["end_pos"],
    )
    coverage = repository.book_coverage(user_id, material_id)
    covered = {row["chunk_id"] for row in coverage}
    explained = [chunk for chunk in chunks if chunk["chunk_id"] in covered]
    stamp = hashlib.sha256(
        json.dumps(
            {"unit": unit, "chunks": explained}, ensure_ascii=False, sort_keys=True
        ).encode()
    ).hexdigest()
    batches = []
    for offset in range(0, len(explained), BATCH_SIZE):
        number = offset // BATCH_SIZE + 1
        batches.append(
            {
                "number": number,
                "digest": hashlib.sha256(
                    (stamp + "." + str(number)).encode()
                ).hexdigest(),
                "sources": [
                    {
                        "source_id": chunk["chunk_id"],
                        "material_id": material_id,
                        "title": material["title"],
                        "locator": chunk["locator"],
                        "excerpt": chunk["content"],
                    }
                    for chunk in explained[offset : offset + BATCH_SIZE]
                ],
            }
        )
    return {
        "material": material,
        "unit": unit,
        "total": len(chunks),
        "explained": len(explained),
        "batches": batches,
        "guard": {
            "material_id": material_id,
            "unit_id": unit_id,
            "revision": unit["revision"],
            "coverage_ids": sorted(covered),
        },
    }


def unit_scope_text(scope):
    return (
        "整理范围说明\n书籍："
        + scope["material_title"]
        + "\n学习单元："
        + scope["unit_title"]
        + "\n单元原始范围："
        + scope["range"]
        + "\n生成时本单元已讲解："
        + str(scope["explained"])
        + " / "
        + str(scope["total"])
        + " 段"
        + "\n本次为第 "
        + str(scope["batch"])
        + " / "
        + str(scope["batch_count"])
        + " 批，提供的原文位置："
        + "、".join(row["locator"] for row in scope["sources"])
        + "\n仅整理本批已讲解的可读片段，不代表全章、全书或已掌握；引用记录不代表人工核实。后续目录调整不改变这份生成时的范围记录。"
    )


def send_unit_lesson(
    repository,
    materials,
    user_id,
    material_id,
    unit_id,
    batch,
    digest,
    nonce,
    *,
    responder,
    now=None,
):
    if (
        not isinstance(nonce, str)
        or re.fullmatch(r"[A-Za-z0-9_-]{43}", nonce) is None
        or type(batch) is not int
        or not isinstance(digest, str)
        or re.fullmatch(r"[a-f0-9]{64}", digest) is None
    ):
        raise ValueError("整理请求无法读取。")
    plan = unit_lesson_plan(repository, materials, user_id, material_id, unit_id)
    if not 1 <= batch <= len(plan["batches"]):
        raise ValueError("这个范围还没有可整理的讲解记录。")
    selected = plan["batches"][batch - 1]
    if not hmac.compare_digest(selected["digest"], digest):
        raise ValueError("学习单元或讲解范围已变化，请重新打开整理页面核对。")
    clock = (lambda: int(time())) if now is None else (lambda: now)
    unit, material = plan["unit"], plan["material"]
    scope = {
        "material_id": material_id,
        "material_title": material["title"],
        "unit_id": unit_id,
        "unit_title": unit["title"],
        "unit_revision": unit["revision"],
        "range": range_label(material, unit["start_pos"], unit["end_pos"]),
        "batch": batch,
        "batch_count": len(plan["batches"]),
        "explained": plan["explained"],
        "total": plan["total"],
        "sources": [
            {"chunk_id": source["source_id"], "locator": source["locator"]}
            for source in selected["sources"]
        ],
    }
    message = (
        "请把「"
        + unit["title"]
        + "」已讲解内容的第 "
        + str(batch)
        + " 批整理为可重温的教案草稿，先由我确认保存。"
    )
    claimed = repository.claim(
        user_id, nonce, message, now=clock(), detached=True, unit_guard=plan["guard"]
    )
    if claimed != "claimed":
        return claimed
    try:
        context = {
            "sources": selected["sources"],
            "material": material,
            "selected_part": None,
            "unit_lesson": scope,
            "review": None,
            "draft_requested": True,
            "can_suggest_draft": False,
            "learning_memories": [
                {"content": row["content"]} for row in repository.list_memories(user_id)
            ],
        }
        answer = responder([], message, None, context=context)
        if not isinstance(answer, CoachAnswer):
            raise ValueError("invalid unit lesson reply")
        draft = _draft(answer.knowledge_draft)
        used = (
            set(value for value in answer.used_source_ids[:6] if isinstance(value, str))
            if isinstance(answer.used_source_ids, list)
            else set()
        )
        sources = selected["sources"]
        if draft is None or not {source["source_id"] for source in sources} <= used:
            draft = None
        if draft:
            draft["topic"] = "研读《" + material["title"][:100] + "》"
        reply = (
            "本批教案草稿已生成，待你预览和确认保存；它只涵盖本批列出的已讲解片段。"
            if draft
            else "本次未能生成带完整选段引用的教案草稿，尚未保存。请回到单元整理页面核对范围，需要时再次点击整理。"
        )
        finished = repository.finish(
            user_id,
            nonce,
            reply,
            None,
            now=clock(),
            citations=sources if draft else [],
            draft=draft,
            unit_summary=scope if draft else None,
        )
        return "complete" if finished else "interrupted"
    except Exception:
        repository.fail(user_id, nonce, now=clock())
        return "failed"
