"""Explicitly reviewed page text. Original bytes and existing chunk identities stay intact."""

import re
import unicodedata
from contextlib import closing
from time import time
from uuid import uuid4

from coach.material_limits import MAX_TEXT
from coach.materials import MaterialError


def page_number(locator):
    match = re.fullmatch(r"PDF 第 ([1-9][0-9]*) 页 · 片段 [1-9][0-9]*", locator)
    if not match:
        raise MaterialError("已有资料位置无法核对，请先核对原件。")
    return int(match[1])


def page_status(repository, user_id, material_id, number):
    with closing(repository._connect()) as db:
        item = db.execute(
            "SELECT kind,page_count,digest FROM materials WHERE user_id=? AND material_id=?",
            (user_id, material_id),
        ).fetchone()
        if item is None or item["kind"] != "pdf":
            return None
        if type(number) is not int or not 1 <= number <= item["page_count"]:
            raise MaterialError("请输入这本 PDF 范围内的文件页码。")
        rows = db.execute(
            "SELECT chunk_id,chunk_index,content FROM material_chunks WHERE material_id=? AND locator LIKE ? ORDER BY chunk_index",
            (material_id, f"PDF 第 {number} 页 · 片段 %"),
        ).fetchall()
        ocr = db.execute(
            "SELECT confidence,created_at FROM material_ocr_pages WHERE material_id=? AND page_number=?",
            (material_id, number),
        ).fetchone()
    return {
        "state": "confirmed" if ocr else "native" if rows else "missing",
        "page": number,
        "digest": item["digest"],
        "text": "".join(
            row["content"][:800] if index < len(rows) - 1 else row["content"]
            for index, row in enumerate(rows)
        ),
        "confidence": ocr["confidence"] if ocr else None,
        "preview_url": f"/web/materials/{material_id}?page={number}",
        "reader_url": f"/web/materials/{material_id}/read?page={number}",
    }


def save_page(repository, user_id, material_id, number, text, confidence, digest):
    if type(number) is not int or not isinstance(text, str):
        raise MaterialError("请核对识别页码和正文文字。")
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not 1 <= len(text) <= 40000 or any(
        unicodedata.category(char) in {"Cc", "Cs"} and char not in "\n\t"
        for char in text
    ):
        raise MaterialError("核对后的正文需要 1 至 40000 字，不含无效控制字符。")
    if type(confidence) is not int or not 0 <= confidence <= 100:
        raise MaterialError("识别置信度无法读取，请重新识别或核对页面。")
    with closing(repository._connect()) as db, db:
        db.execute("BEGIN IMMEDIATE")
        item = db.execute(
            "SELECT kind,page_count,digest,char_count FROM materials WHERE user_id=? AND material_id=?",
            (user_id, material_id),
        ).fetchone()
        if item is None or item["kind"] != "pdf":
            return "missing"
        if not 1 <= number <= item["page_count"] or digest != item["digest"]:
            raise MaterialError("原书或页码无法核对，请重新打开阅读页。")
        existing = db.execute(
            "SELECT 1 FROM material_chunks WHERE material_id=? AND locator LIKE ? LIMIT 1",
            (material_id, f"PDF 第 {number} 页 · 片段 %"),
        ).fetchone()
        if existing:
            return "existing"
        if item["char_count"] + len(text) > MAX_TEXT:
            raise MaterialError("这份书籍已达到 200 万字提取上限，本页尚未保存。")
        old = db.execute(
            "SELECT chunk_id,chunk_index,locator FROM material_chunks WHERE material_id=? ORDER BY chunk_index",
            (material_id,),
        ).fetchall()
        # Validate old positions before doing any writes. References use UUIDs,
        # and those existing IDs, locator strings and content are never changed.
        ordered = [
            (page_number(row["locator"]), row["chunk_index"], row["chunk_id"])
            for row in old
        ]
        new = []
        for offset in range(0, len(text), 800):
            identity = uuid4().hex
            local = offset // 800 + 1
            new.append(
                (
                    identity,
                    material_id,
                    0,
                    f"PDF 第 {number} 页 · 片段 {local}",
                    text[offset : offset + 1000],
                )
            )
            ordered.append((number, local, identity))
        db.executemany("INSERT INTO material_chunks VALUES(?,?,?,?,?)", new)
        db.executemany(
            "UPDATE material_chunks SET chunk_index=? WHERE material_id=? AND chunk_id=?",
            [
                (index, material_id, identity)
                for index, (_, _, identity) in enumerate(sorted(ordered), 1)
            ],
        )
        db.execute(
            "INSERT INTO material_ocr_pages VALUES(?,?,?,?,?)",
            (
                material_id,
                number,
                confidence,
                "tesseract-browser-reviewed",
                int(time()),
            ),
        )
        db.execute(
            "UPDATE materials SET readable_pages=readable_pages+1,char_count=char_count+? WHERE user_id=? AND material_id=?",
            (len(text), user_id, material_id),
        )
    return "saved"
