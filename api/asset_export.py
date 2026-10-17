"""Bounded, read-only personal export; no credentials, AI calls or stored ZIPs."""

import json
import re
import sqlite3
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from tempfile import SpooledTemporaryFile
from time import time
from urllib.parse import quote
from zipfile import ZipFile, ZIP_DEFLATED

from api.coach_markdown import coach_markdown


SCOPES = {
    "saved": "已保存教案",
    "drafts": "教案草稿",
    "chat": "聊天记录与学习位置",
    "materials": "原始资料",
}
PERIODS = {"all": "全部时间", "30": "最近 30 天", "90": "最近 90 天"}
MAX_BYTES = 100 * 1024**2
MAX_ENTRIES = 5000
LOCAL_ZONE = timezone(timedelta(hours=8))
STYLE = """body{font:16px/1.85 system-ui,'Microsoft YaHei',sans-serif;color:#263f31;background:#faf9f5;margin:0}main{max-width:960px;margin:auto;padding:30px 20px}a{color:#365e46}h1{font-size:26px}h2{font-size:21px;margin-top:30px}p,ul,ol{margin:14px 0}.note,.meta{color:#657267;font-size:13px}.card,article{background:white;border:1px solid #e0e5d9;border-radius:10px;padding:20px;margin:20px 0;overflow-wrap:anywhere}.markdown-table-scroll{overflow-x:auto}table{border-collapse:collapse;min-width:100%;font-size:14px}th,td{border:1px solid #dce3d5;padding:10px;text-align:left;min-width:100px}th{background:#edf2e7}pre{white-space:pre;overflow-x:auto;background:#edf2e7;padding:14px;border-radius:8px;font:13px/1.8 Consolas,monospace}code{font-family:Consolas,monospace}.code-block{border:1px solid #dce3d5;border-radius:8px;margin:18px 0;overflow:hidden}.code-block-label{background:#e3ebdb;padding:6px 12px;font-size:12px}.code-block pre{margin:0}.plain,.citation{white-space:pre-wrap;overflow-wrap:anywhere}.citation{font-size:13px;background:#f3f5ef;padding:12px}blockquote{border-left:3px solid #a5b5a0;padding-left:16px}.user{background:#edf2e7}details{margin:15px 0}summary{cursor:pointer}li{margin:8px 0}"""


class ExportError(ValueError):
    pass


@contextmanager
def _read(path):
    db = sqlite3.connect(
        Path(path).resolve().as_uri() + "?mode=ro", uri=True, timeout=5
    )
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        yield db
    finally:
        db.close()


def _date(value):
    return (
        datetime.fromtimestamp(value, LOCAL_ZONE).strftime("%Y-%m-%d %H:%M:%S")
        if value
        else "未记录"
    )


def _stem(title):
    text = unicodedata.normalize("NFKC", str(title))
    text = "".join(
        char for char in text if unicodedata.category(char) not in {"Cc", "Cf"}
    )
    text = re.sub(r'[<>:"/\\|?*]', "_", text).strip(" .")[:60]
    if not text or text in {".", ".."}:
        text = "未命名资料"
    return text


def _html(title, body, *, home=False):
    navigation = (
        "" if home else '<p><a href="../../打开这里.html">← 返回导出目录</a></p>'
    )
    return (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
        "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'\">"
        "<title>"
        + escape(title)
        + "</title><style>"
        + STYLE
        + "</style></head><body><main>"
        + navigation
        + "<h1>"
        + escape(title)
        + "</h1>"
        + body
        + "</main></body></html>"
    )


def _sources(raw):
    sources = json.loads(raw)
    if not isinstance(sources, list):
        raise ExportError("引用记录暂时无法读取，请稍后重试。")
    return [
        {key: str(item.get(key, "")) for key in ("title", "locator", "excerpt")}
        for item in sources
        if isinstance(item, dict)
    ]


def _citations(sources):
    return "".join(
        "<details><summary>引用依据："
        + escape(item["title"] + " · " + item["locator"])
        + '</summary><div class="citation">'
        + escape(item["excerpt"])
        + "</div></details>"
        for item in sources
    )


def _citation_text(sources):
    return "".join(
        "\n\n引用依据："
        + item["title"]
        + " · "
        + item["locator"]
        + "\n"
        + item["excerpt"]
        for item in sources
    )


def export_summary(dialogue_path, materials_path, user_id):
    with _read(dialogue_path) as coach, _read(materials_path) as materials:
        counts = {key: 0 for key in SCOPES}
        for row in coach.execute(
            "SELECT status,COUNT(*) AS n FROM coach_knowledge WHERE user_id=? AND status IN ('saved','pending') GROUP BY status",
            (user_id,),
        ):
            counts["saved" if row["status"] == "saved" else "drafts"] = row["n"]
        counts["chat"] = coach.execute(
            "SELECT COUNT(*) FROM coach_turns WHERE user_id=?", (user_id,)
        ).fetchone()[0]
        counts["learning"] = bool(
            coach.execute(
                "SELECT 1 FROM coach_learning WHERE user_id=?", (user_id,)
            ).fetchone()
        )
        row = materials.execute(
            "SELECT COUNT(*),COALESCE(SUM(length(raw)),0) FROM materials WHERE user_id=?",
            (user_id,),
        ).fetchone()
        counts["materials"], counts["material_bytes"] = row[0], row[1]
        return counts


@dataclass
class ExportArchive:
    file: object = field(repr=False)
    filename: str
    size: int

    def close(self):
        self.file.close()

    def chunks(self):
        try:
            while block := self.file.read(128 * 1024):
                yield block
        finally:
            self.close()


class _Writer:
    def __init__(self, archive):
        self.archive = archive
        self.size = 0
        self.entries = 0

    def add(self, name, pieces):
        self.entries += 1
        if self.entries > MAX_ENTRIES:
            raise ExportError("本次导出文件较多，请按内容类型分别导出。")
        with self.archive.open(name, "w") as output:
            for piece in pieces:
                raw = piece.encode("utf-8") if isinstance(piece, str) else piece
                self.size += len(raw)
                if self.size > MAX_BYTES:
                    raise ExportError(
                        "所选内容超过单次 100 MB 上限，请分类型导出，或缩短聊天时间范围。"
                    )
                output.write(raw)

    def text(self, name, text):
        self.add(name, [text])


def build_export(
    dialogue_path, materials_path, user_id, scopes, *, period="all", now=None
):
    if (
        not isinstance(scopes, (list, tuple, set))
        or not scopes
        or len(scopes) != len(set(scopes))
        or not set(scopes) <= SCOPES.keys()
        or period not in PERIODS
    ):
        raise ExportError("请选择需要导出的内容，并检查聊天时间范围。")
    now = int(time()) if now is None else now
    cutoff = 0 if period == "all" else now - int(period) * 86400
    buffer = SpooledTemporaryFile(max_size=1024**2, mode="w+b")
    counts = {key: 0 for key in scopes}
    listing = {key: [] for key in SCOPES}
    has_learning = False
    try:
        with (
            _read(dialogue_path) as coach,
            _read(materials_path) as materials,
            ZipFile(buffer, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive,
        ):
            writer = _Writer(archive)
            for scope, status in (("saved", "saved"), ("drafts", "pending")):
                if scope not in scopes:
                    continue
                folder = "教案/已保存" if scope == "saved" else "教案/待确认草稿"
                for index, row in enumerate(
                    coach.execute(
                        "SELECT title,topic,content,citations_json,created_at,saved_at FROM coach_knowledge WHERE user_id=? AND status=? ORDER BY created_at,knowledge_id",
                        (user_id, status),
                    ),
                    1,
                ):
                    sources = _sources(row["citations_json"])
                    stem = f"{folder}/{index:04d}-{_stem(row['title'])}"
                    label = (
                        "已确认保存"
                        if scope == "saved"
                        else "待确认草稿，尚未保存到知识库"
                    )
                    body = (
                        '<p class="meta">'
                        + escape(
                            label
                            + " · 主题："
                            + row["topic"]
                            + " · 创建："
                            + _date(row["created_at"])
                        )
                        + "</p><section>"
                        + coach_markdown(row["content"])
                        + "</section>"
                        + _citations(sources)
                    )
                    writer.text(stem + ".html", _html(row["title"], body))
                    writer.text(
                        stem + ".md",
                        label + "\n\n" + row["content"] + _citation_text(sources),
                    )
                    listing[scope].append(
                        '<li><a href="'
                        + quote(stem + ".html", safe="/")
                        + '">'
                        + escape(row["title"])
                        + '</a> <span class="note">'
                        + label
                        + "</span></li>"
                    )
                    counts[scope] += 1

            if "chat" in scopes:
                query = "SELECT user_content,assistant_content,status,created_at,citations_json FROM coach_turns WHERE user_id=? AND created_at>=? ORDER BY turn_id"
                parameters = (user_id, cutoff)

                def chat_html():
                    yield _html(
                        "聊天记录",
                        '<p class="meta">聊天时间范围：' + PERIODS[period] + "</p>",
                    )[: -len("</main></body></html>")]
                    for row in coach.execute(query, parameters):
                        counts["chat"] += 1
                        yield (
                            '<article><p class="meta">'
                            + _date(row["created_at"])
                            + '</p><div class="user card"><strong>你</strong><div class="plain">'
                            + escape(row["user_content"])
                            + "</div></div><strong>知行 · 成长教练</strong>"
                        )
                        if row["status"] == "complete":
                            yield coach_markdown(row["assistant_content"]) + _citations(
                                _sources(row["citations_json"])
                            )
                        else:
                            yield (
                                '<p class="note">'
                                + (
                                    "这条消息尚未取得回复。"
                                    if row["status"] == "pending"
                                    else "这次未能取得回复，原消息已保留。"
                                )
                                + "</p>"
                            )
                        yield "</article>"
                    yield "</main></body></html>"

                writer.add("对话/记录/聊天记录.html", chat_html())

                def chat_text():
                    yield "聊天时间范围：" + PERIODS[period] + "\n"
                    for row in coach.execute(query, parameters):
                        yield (
                            "\n\n时间："
                            + _date(row["created_at"])
                            + "\n你：\n"
                            + row["user_content"]
                            + "\n知行 · 成长教练：\n"
                        )
                        yield (
                            (
                                row["assistant_content"]
                                + _citation_text(_sources(row["citations_json"]))
                            )
                            if row["status"] == "complete"
                            else "尚未取得完整回复。"
                        )

                writer.add("对话/记录/聊天记录.txt", chat_text())
                listing["chat"].append(
                    '<li><a href="'
                    + quote("对话/记录/聊天记录.html", safe="/")
                    + '">聊天记录与引用说明</a> <span class="note">'
                    + PERIODS[period]
                    + "</span></li>"
                )
                learning = coach.execute(
                    "SELECT topic,progress,next_step,updated_at FROM coach_learning WHERE user_id=?",
                    (user_id,),
                ).fetchone()
                if learning:
                    has_learning = True
                    writer.text(
                        "对话/当前学习位置.txt",
                        "当前学习主题："
                        + learning["topic"]
                        + "\n已讨论："
                        + learning["progress"]
                        + "\n下一步："
                        + learning["next_step"]
                        + "\n更新时间："
                        + _date(learning["updated_at"]),
                    )
                    listing["chat"].append(
                        '<li><a href="'
                        + quote("对话/当前学习位置.txt", safe="/")
                        + '">当前学习位置</a></li>'
                    )

            if "materials" in scopes:
                for index, row in enumerate(
                    materials.execute(
                        "SELECT title,filename,kind,raw,created_at FROM materials WHERE user_id=? ORDER BY created_at,material_id",
                        (user_id,),
                    ),
                    1,
                ):
                    extension = (
                        ".pdf"
                        if row["kind"] == "pdf"
                        else ".md"
                        if row["kind"] == "md"
                        else ".txt"
                    )
                    filename = f"原始资料/{index:04d}-{_stem(Path(row['filename']).stem)}{extension}"
                    writer.text(filename, row["raw"])
                    listing["materials"].append(
                        '<li><a href="'
                        + quote(filename, safe="/")
                        + '">'
                        + escape(row["title"])
                        + '</a> <span class="note">原始资料</span></li>'
                    )
                    counts["materials"] += 1

            if not any(counts.values()) and not has_learning:
                raise ExportError(
                    "所选范围内还没有可导出的内容，请更换选择或聊天时间范围。"
                )
            labels = "、".join(
                SCOPES[key]
                + " "
                + str(counts[key])
                + (" 轮" if key == "chat" else " 份")
                for key in SCOPES
                if key in counts
            )
            note = (
                "导出时间："
                + _date(now)
                + "（北京时间）\n包含："
                + labels
                + "\n\n请先完整解压，再打开“打开这里.html”。\n这是下载时的个人阅读副本，修改本地文件不会自动同步到 Coach。\nCoach 内原内容仍然保留，教案草稿仍需在 Coach 中确认保存。\n本包不包含系统登录凭据、邮箱授权码、AI 配置或其他账户资料。\n此包用于个人阅读与留存，不提供整库恢复或账户迁移。\n"
            )
            writer.text("使用说明.txt", note)
            writer.text(
                "打开这里.html",
                _html(
                    "我的学习资料",
                    '<p class="note">'
                    + escape("导出时间：" + _date(now) + "（北京时间）")
                    + "</p><p>"
                    + escape(labels)
                    + "</p><p>请完整解压后打开本页。下载副本不会删除或更改 Coach 内的内容。</p>"
                    + "".join(
                        "<h2>"
                        + SCOPES[key]
                        + "</h2><ul>"
                        + "".join(listing[key])
                        + "</ul>"
                        for key in SCOPES
                        if listing[key]
                    )
                    + '<p class="note">本地修改不会自动同步到 Coach。原始 PDF、TXT、Markdown 文件按原样保留，打开方式取决于你的电脑软件。</p>',
                    home=True,
                ),
            )
        size = buffer.tell()
        if size > MAX_BYTES + 2 * 1024**2:
            raise ExportError("导出包过大，请按类型分别导出。")
        buffer.seek(0)
        return ExportArchive(
            buffer,
            "知行学习资料-"
            + datetime.fromtimestamp(now, LOCAL_ZONE).strftime("%Y%m%d-%H%M%S")
            + ".zip",
            size,
        )
    except Exception:
        buffer.close()
        raise
