"""Private, persistent original materials and bounded local text retrieval."""

import hashlib
import importlib.util
import json
import os
import re
import sqlite3
import subprocess
import sys
import unicodedata
from contextlib import closing
from pathlib import Path
from time import time
from uuid import uuid4

from coach.knowledge_search import match_contexts, search_query


MAX_FILE_BYTES = 10 * 1024**2
MAX_MATERIALS = 20
MAX_LIBRARY_BYTES = 50 * 1024**2
MAX_TEXT = 500000


class MaterialError(ValueError):
    pass


def parse_material(filename, raw, *, pasted=False):
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_FILE_BYTES:
        raise MaterialError("文件不能为空，单份资料最多 10 MB。")
    filename = str(filename).replace("\\", "/").rsplit("/", 1)[-1][:180]
    extension = Path(filename).suffix.lower()
    if extension not in {".pdf", ".txt", ".md"}:
        raise MaterialError("目前支持文字型 PDF、TXT 和 Markdown 文件。")
    if extension == ".pdf":
        if not raw.startswith(b"%PDF-"):
            raise MaterialError("这份文件不是可识别的 PDF。")
        if importlib.util.find_spec("pypdf") is None:
            raise MaterialError(
                "本机尚未安装 PDF 依赖，请按项目说明安装 requirements.txt。"
            )
        environment = {
            key: os.environ[key]
            for key in ("SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP")
            if key in os.environ
        }
        environment["PYTHONPATH"] = os.pathsep.join(
            str(Path(value).resolve())
            for value in sys.path
            if value and Path(value).is_dir()
        )
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        try:
            result = subprocess.run(
                [sys.executable, str(Path(__file__).with_name("pdf_text.py"))],
                input=raw,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=20,
                env=environment,
                creationflags=0x08000000 if sys.platform == "win32" else 0,
                check=False,
            )
            parsed = json.loads(result.stdout)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            raise MaterialError(
                "PDF 未能在本机完成处理，请尝试较小文件或粘贴相关文字。"
            ) from None
        errors = {
            "encrypted": "暂不支持加密 PDF，请使用可直接打开的文字版。",
            "pages": "PDF 最多支持 500 页。",
            "scan": "未提取到可读文字，可能是扫描版；目前可先粘贴相关文字。",
            "complex": "这份 PDF 页面过于复杂，请尝试较小文件或粘贴文字。",
            "text_size": "提取文字超过本版限制，请按章节分成较小文件。",
        }
        if parsed.get("error") or not parsed.get("pages"):
            raise MaterialError(
                errors.get(
                    parsed.get("error"), "PDF 无法解析，请检查文件或改用文字资料。"
                )
            )
        return filename, "pdf", parsed["pages"], parsed["page_count"]
    try:
        text = raw.decode(
            "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
        )
    except UnicodeError:
        try:
            text = raw.decode("gb18030")
        except UnicodeError:
            raise MaterialError(
                "无法读取文字编码，请使用 UTF-8 文件或直接粘贴。"
            ) from None
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if (
        not text
        or len(text) > (50000 if pasted else MAX_TEXT)
        or any(ord(char) < 32 and char not in "\n\t" for char in text)
    ):
        raise MaterialError("请提供可读文字；粘贴最多 5 万字，文字文件最多 50 万字。")
    return (
        filename,
        "paste" if pasted else extension[1:],
        [{"page": None, "text": text}],
        1,
    )


def _terms(text):
    words = set(re.findall(r"[a-z0-9]{2,}", text.lower()))
    for run in re.findall(r"[\u3400-\u9fff]+", text):
        words.update(run[i : i + 2] for i in range(len(run) - 1))
    return words


class MaterialRepository:
    def __init__(self, database_path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS materials (
                    material_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, title TEXT NOT NULL,
                    filename TEXT NOT NULL, kind TEXT NOT NULL, raw BLOB NOT NULL,
                    digest TEXT NOT NULL, page_count INTEGER NOT NULL, readable_pages INTEGER NOT NULL,
                    char_count INTEGER NOT NULL, created_at INTEGER NOT NULL, UNIQUE(user_id,digest)
                );
                CREATE TABLE IF NOT EXISTS material_chunks (
                    chunk_id TEXT PRIMARY KEY, material_id TEXT NOT NULL REFERENCES materials(material_id),
                    chunk_index INTEGER NOT NULL, locator TEXT NOT NULL, content TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS material_chunk_owner ON material_chunks(material_id,chunk_index);
                CREATE TABLE IF NOT EXISTS selected_material (user_id TEXT PRIMARY KEY, material_id TEXT NOT NULL REFERENCES materials(material_id));
            """)

    def _connect(self):
        db = sqlite3.connect(self.database_path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def add(self, user_id, filename, raw, *, title="", pasted=False):
        if not isinstance(title, str) or len(title.strip()) > 120:
            raise MaterialError("资料名称最多 120 字。")
        if not isinstance(raw, bytes) or len(raw) > MAX_FILE_BYTES:
            raise MaterialError("单份资料最多 10 MB。")
        digest = hashlib.sha256((b"paste\0" if pasted else b"file\0") + raw).hexdigest()
        with closing(self._connect()) as db:
            existing = db.execute(
                "SELECT material_id FROM materials WHERE user_id=? AND digest=?",
                (user_id, digest),
            ).fetchone()
        if existing:
            return existing[0]
        filename, kind, pages, page_count = parse_material(filename, raw, pasted=pasted)
        material_id, chunks = uuid4().hex, []
        for page in pages:
            for start in range(0, len(page["text"]), 800):
                content = page["text"][start : start + 1000]
                index = len(chunks) + 1
                locator = (
                    f"PDF 第 {page['page']} 页 · 片段 {index}"
                    if page["page"]
                    else f"片段 {index}"
                )
                chunks.append((uuid4().hex, material_id, index, locator, content))
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT material_id FROM materials WHERE user_id=? AND digest=?",
                (user_id, digest),
            ).fetchone()
            if existing:
                return existing[0]
            count, used = db.execute(
                "SELECT COUNT(*),COALESCE(SUM(length(raw)),0) FROM materials WHERE user_id=?",
                (user_id,),
            ).fetchone()
            if count >= MAX_MATERIALS or used + len(raw) > MAX_LIBRARY_BYTES:
                raise MaterialError("本机试用每个账户最多 20 份资料、合计 50 MB。")
            db.execute(
                "INSERT INTO materials VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    material_id,
                    user_id,
                    title.strip() or Path(filename).stem[:120] or "文字资料",
                    filename,
                    kind,
                    raw,
                    digest,
                    page_count,
                    len(pages),
                    sum(len(page["text"]) for page in pages),
                    int(time()),
                ),
            )
            db.executemany("INSERT INTO material_chunks VALUES(?,?,?,?,?)", chunks)
        return material_id

    def list(self, user_id):
        with closing(self._connect()) as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT material_id,title,filename,kind,page_count,readable_pages,char_count,created_at,length(raw) AS raw_bytes FROM materials WHERE user_id=? ORDER BY created_at DESC,material_id",
                    (user_id,),
                )
            ]

    def get(self, user_id, material_id):
        return next(
            (item for item in self.list(user_id) if item["material_id"] == material_id),
            None,
        )

    def rename(self, user_id, material_id, title, *, expected_title):
        """Update only an owned title; False means a stale editor must be reviewed."""
        if (
            not isinstance(title, str)
            or not 1 <= len(title.strip()) <= 120
            or any(unicodedata.category(char) in {"Cc", "Cs"} for char in title)
            or not isinstance(expected_title, str)
        ):
            raise MaterialError("请填写 1 至 120 字的资料名称，不含换行或控制字符。")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT title FROM materials WHERE user_id=? AND material_id=?",
                (user_id, material_id),
            ).fetchone()
            if row is None:
                raise MaterialError("找不到这份资料。")
            if row[0] != expected_title:
                return False
            db.execute(
                "UPDATE materials SET title=? WHERE user_id=? AND material_id=?",
                (title.strip(), user_id, material_id),
            )
        return True

    def find_chunks(self, user_id, query, *, material_id=None, page=1):
        """Return at most 21 owned literal hits; the last is a next-page sentinel."""
        query = search_query(query)
        if type(page) is not int or not 1 <= page <= 10000:
            raise ValueError("请输入有效的查找结果页码。")
        if material_id is not None and (
            not isinstance(material_id, str)
            or re.fullmatch(r"[a-f0-9]{32}", material_id) is None
        ):
            raise ValueError("查找范围无法读取。")
        if not query:
            return []
        scope = " AND m.material_id=?" if material_id is not None else ""
        values = [user_id, query]
        if material_id is not None:
            values.append(material_id)
        values.append((page - 1) * 20)
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT m.material_id,m.title,m.kind,c.chunk_id,c.chunk_index,c.locator,c.content "
                "FROM material_chunks c JOIN materials m ON c.material_id=m.material_id "
                "WHERE m.user_id=? AND instr(lower(c.content),lower(?))>0"
                + scope
                + " ORDER BY m.created_at DESC,m.material_id,c.chunk_index LIMIT 21 OFFSET ?",
                values,
            ).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            match = match_contexts(item.pop("content"), query, limit=1)
            item["search_match"] = {
                "fields": ["原文"],
                "excerpt": match["contexts"][0],
            }
            results.append(item)
        return results

    def select(self, user_id, material_id=None):
        with closing(self._connect()) as db, db:
            if material_id is None:
                db.execute("DELETE FROM selected_material WHERE user_id=?", (user_id,))
            elif db.execute(
                "SELECT 1 FROM materials WHERE user_id=? AND material_id=?",
                (user_id, material_id),
            ).fetchone():
                db.execute(
                    "INSERT INTO selected_material VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET material_id=excluded.material_id",
                    (user_id, material_id),
                )
            else:
                raise MaterialError("找不到这份资料。")

    def selected(self, user_id):
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT material_id FROM selected_material WHERE user_id=?", (user_id,)
            ).fetchone()
        return self.get(user_id, row[0]) if row else None

    def chunks(self, user_id, material_id):
        with closing(self._connect()) as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT c.chunk_id,c.chunk_index,c.locator,c.content FROM material_chunks c JOIN materials m ON c.material_id=m.material_id WHERE m.user_id=? AND m.material_id=? ORDER BY c.chunk_index",
                    (user_id, material_id),
                )
            ]

    def retrieve(self, user_id, query, *, material_id=None):
        material = (
            self.get(user_id, material_id) if material_id else self.selected(user_id)
        )
        if not material:
            return []
        chunks = self.chunks(user_id, material["material_id"])
        terms = _terms(query)
        ranked = sorted(
            chunks,
            key=lambda item: (
                -len(terms & _terms(item["content"])),
                item["chunk_index"],
            ),
        )[:6]
        if (
            ranked
            and not (terms & _terms(ranked[0]["content"]))
            and not re.search(
                r"资料|这本|这份|书|核心|概要|总结|教案|片段|第.{1,8}章|知识点|重温|学习|解释|继续",
                query,
            )
        ):
            return []
        return [
            {
                "source_id": item["chunk_id"],
                "material_id": material["material_id"],
                "title": material["title"],
                "locator": item["locator"],
                "excerpt": item["content"],
            }
            for item in ranked
        ]

    def chunk(self, user_id, material_id, chunk_id):
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT c.chunk_id,c.chunk_index,c.locator,c.content FROM material_chunks c JOIN materials m ON m.material_id=c.material_id WHERE m.user_id=? AND m.material_id=? AND c.chunk_id=?",
                (user_id, material_id, chunk_id),
            ).fetchone()
        return dict(row) if row else None
