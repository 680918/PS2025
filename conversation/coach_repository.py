"""Account-owned dialogue and learning anchors, independent of legacy journeys."""

import sqlite3
import re
from datetime import datetime, timedelta, timezone
from coach.booklets import (
    booklet_title,
    booklet_ids,
    booklet_snapshot,
    booklet_search,
    booklet_position,
    MAX_BOOKLETS,
    MAX_CHAPTERS,
)
import json
from uuid import uuid4
from contextlib import closing
from pathlib import Path
from coach.learning_memory import MAX_MEMORIES, validate_memory
from time import time
from coach.learning_topics import (
    topic_key,
    validate_topic_title,
    TopicBusy,
    validate_topic_record,
    topic_edit_version,
)
from coach.knowledge_search import (
    search_query,
    lesson_match,
    match_contexts,
    lesson_topic,
)
from coach.ai_usage import USAGE_SCHEMA, budget
from coach.conversation_dates import conversation_date_window
from coach.draft_edit import draft_version, draft_text


PENDING_LIFETIME = 180
HISTORY_PAGE_SIZE = 40

_REVIEW_FROM = (
    " FROM coach_turns AS turn "
    "LEFT JOIN coach_turn_topics AS tag ON tag.turn_id=turn.turn_id AND tag.user_id=turn.user_id "
    "LEFT JOIN coach_topics AS topic ON topic.topic_id=tag.topic_id AND topic.user_id=turn.user_id "
)
_REVIEW_FIELDS = (
    "turn.turn_id,turn.user_content,turn.assistant_content,turn.status,turn.created_at,"
    "topic.topic_id,topic.title AS topic_title"
)


def _review_scope(topic_id):
    if not isinstance(topic_id, str) or (
        topic_id not in {"", "unfiled"}
        and re.fullmatch(r"[a-f0-9]{32}", topic_id) is None
    ):
        raise ValueError("请选择有效的对话主题。")
    if topic_id == "unfiled":
        return " AND topic.topic_id IS NULL", []
    return (" AND topic.topic_id=?", [topic_id]) if topic_id else ("", [])


class CoachRepository:
    def __init__(self, database_path, *, materials=None):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS coach_turns (
                    turn_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    nonce TEXT NOT NULL,
                    user_content TEXT NOT NULL,
                    assistant_content TEXT,
                    status TEXT NOT NULL CHECK(status IN ('pending','complete','failed')),
                    created_at INTEGER NOT NULL,
                    completed_at INTEGER,
                    UNIQUE(user_id, nonce)
                );
                CREATE UNIQUE INDEX IF NOT EXISTS coach_one_pending
                    ON coach_turns(user_id) WHERE status = 'pending';
                CREATE INDEX IF NOT EXISTS coach_history
                    ON coach_turns(user_id, turn_id DESC);
                CREATE TABLE IF NOT EXISTS coach_learning (
                    user_id TEXT PRIMARY KEY,
                    topic TEXT NOT NULL,
                    progress TEXT NOT NULL,
                    next_step TEXT NOT NULL,
                    updated_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS coach_knowledge (
                    knowledge_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, turn_id INTEGER NOT NULL,
                    title TEXT NOT NULL, topic TEXT NOT NULL, content TEXT NOT NULL,
                    citations_json TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('pending','saved','dismissed')),
                    created_at INTEGER NOT NULL, saved_at INTEGER, UNIQUE(user_id,turn_id)
                );
                CREATE TABLE IF NOT EXISTS coach_draft_restores (
                    user_id TEXT NOT NULL, knowledge_id TEXT NOT NULL,
                    generation INTEGER NOT NULL CHECK(generation>0),
                    PRIMARY KEY(user_id,knowledge_id)
                );
                CREATE TABLE IF NOT EXISTS coach_lesson_favorites (
                    user_id TEXT NOT NULL, knowledge_id TEXT NOT NULL,
                    selected INTEGER NOT NULL CHECK(selected IN (0,1)),
                    revision INTEGER NOT NULL CHECK(revision>0),
                    PRIMARY KEY(user_id,knowledge_id)
                );
                CREATE TABLE IF NOT EXISTS coach_review (user_id TEXT PRIMARY KEY, knowledge_id TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS coach_review_versions (
                    user_id TEXT PRIMARY KEY, revision INTEGER NOT NULL CHECK(revision>0)
                );
                CREATE TABLE IF NOT EXISTS coach_knowledge_versions (
                    user_id TEXT NOT NULL, knowledge_id TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>0),
                    title TEXT NOT NULL, content TEXT NOT NULL, created_at INTEGER NOT NULL,
                    restored_from INTEGER, PRIMARY KEY(user_id,knowledge_id,revision)
                );
                CREATE TABLE IF NOT EXISTS coach_topics (
                    topic_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, topic_key TEXT NOT NULL,
                    title TEXT NOT NULL, progress TEXT NOT NULL, next_step TEXT NOT NULL,
                    material_id TEXT, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL,
                    UNIQUE(user_id,topic_key)
                );
                CREATE TABLE IF NOT EXISTS coach_active_topic (user_id TEXT PRIMARY KEY, topic_id TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS coach_topic_parts (
                    user_id TEXT NOT NULL, topic_id TEXT NOT NULL, material_id TEXT NOT NULL,
                    chunk_id TEXT NOT NULL, updated_at INTEGER NOT NULL, PRIMARY KEY(user_id,topic_id)
                );
                CREATE TABLE IF NOT EXISTS coach_booklets (
                    booklet_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, title TEXT NOT NULL,
                    lesson_ids_json TEXT NOT NULL, revision INTEGER NOT NULL,
                    created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS coach_booklet_owner ON coach_booklets(user_id,updated_at,booklet_id);
                CREATE TABLE IF NOT EXISTS coach_booklet_positions (
                    user_id TEXT NOT NULL, booklet_id TEXT NOT NULL,
                    knowledge_id TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>0),
                    updated_at INTEGER NOT NULL, PRIMARY KEY(user_id,booklet_id)
                );
                CREATE TABLE IF NOT EXISTS coach_knowledge_units (
                    knowledge_id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                    material_id TEXT NOT NULL, unit_id TEXT NOT NULL, scope_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS coach_unit_knowledge_owner ON coach_knowledge_units(user_id,material_id,unit_id);
                CREATE TABLE IF NOT EXISTS coach_book_units (
                    unit_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, material_id TEXT NOT NULL,
                    title TEXT NOT NULL, start_pos INTEGER NOT NULL, end_pos INTEGER NOT NULL,
                    revision INTEGER NOT NULL, updated_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS coach_book_unit_owner ON coach_book_units(user_id,material_id,start_pos);
                CREATE TABLE IF NOT EXISTS coach_book_coverage (
                    user_id TEXT NOT NULL, material_id TEXT NOT NULL, chunk_id TEXT NOT NULL,
                    turn_id INTEGER NOT NULL, explained_at INTEGER NOT NULL,
                    PRIMARY KEY(user_id,material_id,chunk_id)
                );
                CREATE TABLE IF NOT EXISTS coach_turn_topics (turn_id INTEGER PRIMARY KEY, user_id TEXT NOT NULL, topic_id TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS coach_topic_history ON coach_turn_topics(user_id,topic_id,turn_id);
                CREATE TABLE IF NOT EXISTS coach_memories (
                    memory_id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                    content TEXT NOT NULL CHECK(length(content) BETWEEN 1 AND 300),
                    revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0),
                    created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL,
                    UNIQUE(user_id,content)
                );
            """)
            connection.executescript(USAGE_SCHEMA)
            if "citations_json" not in {
                row[1] for row in connection.execute("PRAGMA table_info(coach_turns)")
            }:
                connection.execute(
                    "ALTER TABLE coach_turns ADD COLUMN citations_json TEXT NOT NULL DEFAULT '[]'"
                )

            # Copy only the last reliably known learning position. Old chat stays
            # intact; do not guess a topic for earlier, unclassified dialogue.
            old_positions = connection.execute(
                "SELECT * FROM coach_learning WHERE user_id NOT IN (SELECT user_id FROM coach_active_topic)"
            ).fetchall()
            for old in old_positions:
                selected = (
                    materials.selected(old["user_id"])
                    if materials is not None
                    else None
                )
                self._store_topic(
                    connection,
                    old["user_id"],
                    dict(old),
                    old["updated_at"],
                    selected["material_id"]
                    if selected
                    else ("" if materials is not None else None),
                )

    def list_booklets(self, user_id, *, query="", offset=0, limit=21):
        with closing(self._connect()) as db, db:
            db.execute("BEGIN")
            rows = db.execute(
                "SELECT booklet_id,title,lesson_ids_json,revision,updated_at FROM coach_booklets WHERE user_id=? AND instr(lower(title),lower(?))>0 ORDER BY updated_at DESC,booklet_id LIMIT ? OFFSET ?",
                (user_id, query, limit, offset),
            ).fetchall()
            result = []
            for row in rows:
                ids = booklet_ids(row["lesson_ids_json"])
                result.append(
                    {
                        **dict(row),
                        "chapter_count": len(ids),
                        "reading_position": booklet_position(
                            db, user_id, row["booklet_id"], ids
                        ),
                    }
                )
            return result

    def booklet(self, user_id, identity, *, chapter=None):
        with closing(self._connect()) as db, db:
            db.execute("BEGIN")
            return booklet_snapshot(db, user_id, identity, chapter=chapter)

    def find_booklet(self, user_id, identity, query, *, page=1):
        with closing(self._connect()) as db, db:
            db.execute("BEGIN")
            return booklet_search(db, user_id, identity, query, page=page)

    def create_booklet(self, user_id, identity, title, *, now=None):
        title = booklet_title(title)
        if (
            not isinstance(identity, str)
            or re.fullmatch(r"[a-f0-9]{32}", identity) is None
        ):
            raise ValueError("手册编号无法读取。")
        now = int(time()) if now is None else now
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute(
                "SELECT user_id FROM coach_booklets WHERE booklet_id=?", (identity,)
            ).fetchone()
            if old:
                return "unchanged" if old[0] == user_id else "missing"
            if (
                db.execute(
                    "SELECT COUNT(*) FROM coach_booklets WHERE user_id=?", (user_id,)
                ).fetchone()[0]
                >= MAX_BOOKLETS
            ):
                raise ValueError("当前每个账户最多 50 本手册，可继续维护已有手册。")
            db.execute(
                "INSERT INTO coach_booklets VALUES(?,?,?,'[]',1,?,?)",
                (identity, user_id, title, now, now),
            )
        return "saved"

    def remember_booklet_position(
        self, user_id, identity, revision, knowledge_id, position_revision, *, now=None
    ):
        if (
            type(revision) is not int
            or not 1 <= revision <= 1000000000
            or type(position_revision) is not int
            or not 0 <= position_revision <= 1000000000
            or not isinstance(knowledge_id, str)
            or re.fullmatch(r"[a-f0-9]{32}", knowledge_id) is None
        ):
            raise ValueError("续读位置无法核对，请重新打开章节。")
        now = int(time()) if now is None else now
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            book = db.execute(
                "SELECT revision,lesson_ids_json FROM coach_booklets WHERE user_id=? AND booklet_id=?",
                (user_id, identity),
            ).fetchone()
            if book is None:
                return "missing"
            if book["revision"] != revision:
                return "conflict"
            ids = booklet_ids(book["lesson_ids_json"])
            if (
                knowledge_id not in ids
                or not db.execute(
                    "SELECT 1 FROM coach_knowledge WHERE user_id=? AND knowledge_id=? AND status='saved'",
                    (user_id, knowledge_id),
                ).fetchone()
            ):
                raise ValueError("只能记住本手册中本人已保存教案的位置。")
            old = db.execute(
                "SELECT knowledge_id,revision FROM coach_booklet_positions WHERE user_id=? AND booklet_id=?",
                (user_id, identity),
            ).fetchone()
            if old and old["knowledge_id"] == knowledge_id:
                return "unchanged"
            if (old["revision"] if old else 0) != position_revision:
                return "conflict"
            db.execute(
                "INSERT INTO coach_booklet_positions VALUES(?,?,?,?,?) ON CONFLICT(user_id,booklet_id) DO UPDATE SET knowledge_id=excluded.knowledge_id,revision=excluded.revision,updated_at=excluded.updated_at",
                (user_id, identity, knowledge_id, position_revision + 1, now),
            )
        return "saved"

    def change_booklet(
        self,
        user_id,
        identity,
        revision,
        operation,
        *,
        knowledge_id=None,
        title=None,
        now=None,
    ):
        if (
            type(revision) is not int
            or not 1 <= revision <= 1000000000
            or operation not in {"title", "add", "up", "down", "remove"}
        ):
            raise ValueError("手册操作无法读取。")
        if operation == "title":
            title = booklet_title(title)
        elif (
            not isinstance(knowledge_id, str)
            or re.fullmatch(r"[a-f0-9]{32}", knowledge_id) is None
        ):
            raise ValueError("教案编号无法读取。")
        now = int(time()) if now is None else now
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute(
                "SELECT * FROM coach_booklets WHERE user_id=? AND booklet_id=?",
                (user_id, identity),
            ).fetchone()
            if old is None:
                return "missing"
            if old["revision"] != revision:
                return "conflict"
            ids = booklet_ids(old["lesson_ids_json"])
            if operation == "title":
                if title == old["title"]:
                    return "unchanged"
            else:
                title = old["title"]
                if operation == "add":
                    if not db.execute(
                        "SELECT 1 FROM coach_knowledge WHERE user_id=? AND knowledge_id=? AND status='saved'",
                        (user_id, knowledge_id),
                    ).fetchone():
                        raise ValueError("只能收录本人已经确认保存的教案。")
                    if knowledge_id in ids:
                        return "unchanged"
                    if len(ids) >= MAX_CHAPTERS:
                        raise ValueError(
                            "一本手册最多 100 章，可另建手册或移出暂不需要的章节。"
                        )
                    ids.append(knowledge_id)
                elif knowledge_id not in ids:
                    return "unchanged"
                elif operation == "remove":
                    ids.remove(knowledge_id)
                else:
                    index = ids.index(knowledge_id)
                    other = index + (-1 if operation == "up" else 1)
                    if not 0 <= other < len(ids):
                        return "unchanged"
                    ids[index], ids[other] = ids[other], ids[index]
            db.execute(
                "UPDATE coach_booklets SET title=?,lesson_ids_json=?,revision=revision+1,updated_at=? WHERE user_id=? AND booklet_id=?",
                (title, json.dumps(ids), now, user_id, identity),
            )
        return "saved"

    def list_memories(self, user_id):
        with closing(self._connect()) as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT memory_id,content,revision,created_at,updated_at FROM coach_memories WHERE user_id=? ORDER BY created_at,memory_id",
                    (user_id,),
                )
            ]

    def memory(self, user_id, memory_id):
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT memory_id,content,revision,created_at,updated_at FROM coach_memories WHERE user_id=? AND memory_id=?",
                (user_id, memory_id),
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def _insert_memory(db, user_id, content, now):
        if db.execute(
            "SELECT 1 FROM coach_memories WHERE user_id=? AND content=?",
            (user_id, content),
        ).fetchone():
            return "existing"
        if (
            db.execute(
                "SELECT COUNT(*) FROM coach_memories WHERE user_id=?", (user_id,)
            ).fetchone()[0]
            >= MAX_MEMORIES
        ):
            return "full"
        db.execute(
            "INSERT INTO coach_memories VALUES(?,?,?,1,?,?)",
            (uuid4().hex, user_id, content, now, now),
        )
        return "created"

    def add_memory(self, user_id, content, *, now=None):
        content = validate_memory(content)
        now = int(time()) if now is None else now
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            return self._insert_memory(db, user_id, content, now)

    def update_memory(self, user_id, memory_id, content, revision, *, now=None):
        content = validate_memory(content)
        now = int(time()) if now is None else now
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT revision FROM coach_memories WHERE user_id=? AND memory_id=?",
                (user_id, memory_id),
            ).fetchone()
            if row is None:
                return "missing"
            if row[0] != revision:
                return "conflict"
            if db.execute(
                "SELECT 1 FROM coach_memories WHERE user_id=? AND memory_id<>? AND content=?",
                (user_id, memory_id, content),
            ).fetchone():
                return "existing"
            db.execute(
                "UPDATE coach_memories SET content=?,revision=revision+1,updated_at=? WHERE user_id=? AND memory_id=?",
                (content, now, user_id, memory_id),
            )
            return "updated"

    def delete_memory(self, user_id, memory_id, revision):
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT revision FROM coach_memories WHERE user_id=? AND memory_id=?",
                (user_id, memory_id),
            ).fetchone()
            if row is None:
                return "missing"
            if row[0] != revision:
                return "conflict"
            db.execute(
                "DELETE FROM coach_memories WHERE user_id=? AND memory_id=?",
                (user_id, memory_id),
            )
            return "deleted"

    def finish_memory_request(self, user_id, nonce, content, *, now):
        content = validate_memory(content)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            active = db.execute(
                "SELECT 1 FROM coach_turns WHERE user_id=? AND nonce=? AND status='pending' AND created_at>?",
                (user_id, nonce, now - PENDING_LIFETIME),
            ).fetchone()
            if active is None:
                return False
            result = self._insert_memory(db, user_id, content, now)
            if result == "full":
                answer = "这次还没有保存：学习记忆已达到 20 条。请到左侧‘我的学习记忆’整理已有内容，再重新发送。"
            elif result == "existing":
                answer = "这条学习记忆已经保存，无需重复添加。你可以在左侧‘我的学习记忆’查看、修改或删除。"
            else:
                answer = (
                    "已记住："
                    + content
                    + "\n\n以后的交流会参考这条学习记忆。你可以在左侧‘我的学习记忆’查看、修改或删除。"
                )
            db.execute(
                "UPDATE coach_turns SET assistant_content=?,status='complete',completed_at=? WHERE user_id=? AND nonce=?",
                (answer, now, user_id, nonce),
            )
            return True

    @staticmethod
    def _store_topic(db, user_id, learning, now, material_id=None):
        key = topic_key(learning["topic"])
        row = db.execute(
            "SELECT * FROM coach_topics WHERE user_id=? AND topic_key=?", (user_id, key)
        ).fetchone()
        current = db.execute(
            "SELECT topic_id FROM coach_active_topic WHERE user_id=?", (user_id,)
        ).fetchone()
        if row is None:
            identity = uuid4().hex
            title = learning["topic"]
            db.execute(
                "INSERT INTO coach_topics VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    identity,
                    user_id,
                    key,
                    title,
                    learning["progress"],
                    learning["next_step"],
                    material_id,
                    now,
                    now,
                ),
            )
        else:
            identity, title = row["topic_id"], row["title"]
            db.execute(
                "UPDATE coach_topics SET progress=?,next_step=?,material_id=?,updated_at=? WHERE user_id=? AND topic_id=?",
                (
                    learning["progress"],
                    learning["next_step"],
                    row["material_id"] if material_id is None else material_id,
                    now,
                    user_id,
                    identity,
                ),
            )
        if current is not None and current[0] != identity:
            db.execute("DELETE FROM coach_review WHERE user_id=?", (user_id,))
        db.execute(
            "DELETE FROM coach_topic_parts WHERE user_id=? AND topic_id=? AND material_id<>COALESCE((SELECT material_id FROM coach_topics WHERE user_id=? AND topic_id=?),'')",
            (user_id, identity, user_id, identity),
        )
        db.execute(
            "INSERT INTO coach_active_topic VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET topic_id=excluded.topic_id",
            (user_id, identity),
        )
        db.execute(
            "INSERT INTO coach_learning VALUES(?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET topic=excluded.topic,progress=excluded.progress,next_step=excluded.next_step,updated_at=excluded.updated_at",
            (user_id, title, learning["progress"], learning["next_step"], now),
        )
        return identity

    @staticmethod
    def _activate_topic(db, user_id, identity):
        row = db.execute(
            "SELECT * FROM coach_topics WHERE user_id=? AND topic_id=?",
            (user_id, identity),
        ).fetchone()
        if row is None:
            raise ValueError("找不到这个学习主题。")
        current = db.execute(
            "SELECT topic_id FROM coach_active_topic WHERE user_id=?", (user_id,)
        ).fetchone()
        db.execute(
            "INSERT INTO coach_active_topic VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET topic_id=excluded.topic_id",
            (user_id, identity),
        )
        db.execute(
            "INSERT INTO coach_learning VALUES(?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET topic=excluded.topic,progress=excluded.progress,next_step=excluded.next_step,updated_at=excluded.updated_at",
            (
                user_id,
                row["title"],
                row["progress"],
                row["next_step"],
                row["updated_at"],
            ),
        )
        if current is None or current[0] != identity:
            db.execute("DELETE FROM coach_review WHERE user_id=?", (user_id,))
        return dict(row)

    def _require_idle(self, db, user_id, now):
        self._expire(db, user_id, now)
        if db.execute(
            "SELECT 1 FROM coach_turns WHERE user_id=? AND status='pending'", (user_id,)
        ).fetchone():
            raise TopicBusy("教练还在回复，请等本轮完成后再切换主题或资料。")

    def active_topic(self, user_id):
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT topic.* FROM coach_topics AS topic JOIN coach_active_topic AS active ON active.topic_id=topic.topic_id AND active.user_id=topic.user_id WHERE topic.user_id=?",
                (user_id,),
            ).fetchone()
        return dict(row) if row else None

    def topic(self, user_id, identity):
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM coach_topics WHERE user_id=? AND topic_id=?",
                (user_id, identity),
            ).fetchone()
        return dict(row) if row else None

    def list_topics(self, user_id, *, query="", offset=0, limit=11):
        needle = topic_key(query)
        with closing(self._connect()) as db:
            db.create_function("study_text", 1, topic_key, deterministic=True)
            return [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM coach_topics WHERE user_id=? AND "
                    "(instr(topic_key,?)>0 OR instr(study_text(progress),?)>0 "
                    "OR instr(study_text(next_step),?)>0) "
                    "ORDER BY updated_at DESC,topic_id LIMIT ? OFFSET ?",
                    (user_id, needle, needle, needle, limit, offset),
                )
            ]

    def create_topic(self, user_id, title, material_id="", *, now=None):
        title = validate_topic_title(title)
        now = int(time()) if now is None else now
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            self._require_idle(db, user_id, now)
            existing = db.execute(
                "SELECT topic_id FROM coach_topics WHERE user_id=? AND topic_key=?",
                (user_id, topic_key(title)),
            ).fetchone()
            if existing:
                self._activate_topic(db, user_id, existing[0])
                return "existing"
            self._store_topic(
                db,
                user_id,
                {
                    "topic": title,
                    "progress": "尚未开始讨论。",
                    "next_step": "从你最想理解的一个问题开始。",
                },
                now,
                material_id,
            )
            db.execute("DELETE FROM coach_review WHERE user_id=?", (user_id,))
            return "created"

    def edit_topic(
        self,
        user_id,
        identity,
        title,
        progress,
        next_step,
        *,
        expected_version,
        now=None,
    ):
        if (
            not isinstance(expected_version, str)
            or re.fullmatch(r"[a-f0-9]{64}", expected_version) is None
        ):
            raise ValueError("学习记录版本无法核对，请重新打开编辑页。")
        now = int(time()) if now is None else now
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM coach_topics WHERE user_id=? AND topic_id=?",
                (user_id, identity),
            ).fetchone()
            if row is None:
                return "missing"
            if topic_edit_version(row) != expected_version:
                return "conflict"
            title, progress, next_step = validate_topic_record(
                title, progress, next_step
            )
            if (row["title"], row["progress"], row["next_step"]) == (
                title,
                progress,
                next_step,
            ):
                return "unchanged"
            self._require_idle(db, user_id, now)
            if db.execute(
                "SELECT 1 FROM coach_topics WHERE user_id=? AND topic_key=? AND topic_id<>?",
                (user_id, topic_key(title), identity),
            ).fetchone():
                return "duplicate"
            db.execute(
                "UPDATE coach_topics SET title=?,topic_key=?,progress=?,next_step=?,updated_at=? WHERE user_id=? AND topic_id=?",
                (title, topic_key(title), progress, next_step, now, user_id, identity),
            )
            active = db.execute(
                "SELECT topic_id FROM coach_active_topic WHERE user_id=?", (user_id,)
            ).fetchone()
            if active and active[0] == identity:
                db.execute(
                    "INSERT INTO coach_learning VALUES(?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET topic=excluded.topic,progress=excluded.progress,next_step=excluded.next_step,updated_at=excluded.updated_at",
                    (user_id, title, progress, next_step, now),
                )
        return "updated"

    def activate_topic(self, user_id, identity, *, now=None):
        now = int(time()) if now is None else now
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            self._require_idle(db, user_id, now)
            return self._activate_topic(db, user_id, identity)

    def bind_topic_material(self, user_id, material_id, *, default_selector):
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            now = int(time())
            self._require_idle(db, user_id, now)
            active = db.execute(
                "SELECT topic_id FROM coach_active_topic WHERE user_id=?", (user_id,)
            ).fetchone()
            if active:
                db.execute(
                    "UPDATE coach_topics SET material_id=?,updated_at=? WHERE user_id=? AND topic_id=?",
                    (material_id, now, user_id, active[0]),
                )
                db.execute(
                    "DELETE FROM coach_topic_parts WHERE user_id=? AND topic_id=?",
                    (user_id, active[0]),
                )
            else:
                default_selector()
            db.execute("DELETE FROM coach_review WHERE user_id=?", (user_id,))

    def topic_part(self, user_id, *, topic_id=None):
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT part.* FROM coach_topic_parts AS part JOIN coach_topics AS topic ON topic.topic_id=part.topic_id AND topic.user_id=part.user_id AND topic.material_id=part.material_id WHERE part.user_id=? AND part.topic_id=COALESCE(?,(SELECT topic_id FROM coach_active_topic WHERE user_id=?))",
                (user_id, topic_id, user_id),
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def _set_part(db, user_id, topic_id, material_id, chunk_id, now):
        if chunk_id:
            db.execute(
                "INSERT INTO coach_topic_parts VALUES(?,?,?,?,?) ON CONFLICT(user_id,topic_id) DO UPDATE SET material_id=excluded.material_id,chunk_id=excluded.chunk_id,updated_at=excluded.updated_at",
                (user_id, topic_id, material_id, chunk_id, now),
            )
        else:
            db.execute(
                "DELETE FROM coach_topic_parts WHERE user_id=? AND topic_id=?",
                (user_id, topic_id),
            )

    def select_material_part(self, user_id, material_id, title, chunk_id, *, now=None):
        # Ownership of material and chunk is verified by the caller. All study
        # state changes below share one transaction and the existing idle guard.
        now = int(time()) if now is None else now
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            self._require_idle(db, user_id, now)
            row = db.execute(
                "SELECT topic.topic_id FROM coach_topics AS topic LEFT JOIN coach_active_topic AS active ON active.user_id=topic.user_id AND active.topic_id=topic.topic_id WHERE topic.user_id=? AND topic.material_id=? ORDER BY (active.topic_id IS NOT NULL) DESC,topic.updated_at DESC,topic.topic_id LIMIT 1",
                (user_id, material_id),
            ).fetchone()
            if row:
                identity = row[0]
                self._activate_topic(db, user_id, identity)
            else:
                base = "研读《" + title[:100] + "》"
                name, counter = base, 1
                while db.execute(
                    "SELECT 1 FROM coach_topics WHERE user_id=? AND topic_key=?",
                    (user_id, topic_key(name)),
                ).fetchone():
                    counter += 1
                    name = base + " · " + str(counter)
                identity = self._store_topic(
                    db,
                    user_id,
                    {
                        "topic": name,
                        "progress": "尚未开始讨论。",
                        "next_step": "从所选段落的核心知识点开始，结合一个例子理解。",
                    },
                    now,
                    material_id,
                )
            self._set_part(db, user_id, identity, material_id, chunk_id, now)
            db.execute(
                "UPDATE coach_topics SET updated_at=? WHERE user_id=? AND topic_id=?",
                (now, user_id, identity),
            )
            db.execute(
                "UPDATE coach_learning SET updated_at=? WHERE user_id=?", (now, user_id)
            )
            db.execute("DELETE FROM coach_review WHERE user_id=?", (user_id,))
            return identity

    def book_units(self, user_id, material_id):
        with closing(self._connect()) as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM coach_book_units WHERE user_id=? AND material_id=? ORDER BY start_pos,unit_id",
                    (user_id, material_id),
                )
            ]

    def book_coverage(self, user_id, material_id):
        with closing(self._connect()) as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM coach_book_coverage WHERE user_id=? AND material_id=? ORDER BY explained_at,chunk_id",
                    (user_id, material_id),
                )
            ]

    def book_position(self, user_id, material_id):
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT part.* FROM coach_topic_parts part JOIN coach_topics topic ON topic.user_id=part.user_id AND topic.topic_id=part.topic_id AND topic.material_id=part.material_id LEFT JOIN coach_active_topic active ON active.user_id=topic.user_id AND active.topic_id=topic.topic_id WHERE part.user_id=? AND part.material_id=? ORDER BY (active.topic_id IS NOT NULL) DESC,topic.updated_at DESC,topic.topic_id LIMIT 1",
                (user_id, material_id),
            ).fetchone()
        return dict(row) if row else None

    def save_book_unit(
        self, user_id, material_id, unit_id, title, start, end, revision, *, now=None
    ):
        # The route validates ownership, material bounds and readable content.
        title = validate_topic_title(title)
        if (
            len(title) > 80
            or type(start) is not int
            or type(end) is not int
            or not 1 <= start <= end
            or type(revision) is not int
            or revision < 0
        ):
            raise ValueError("学习单元标题最多 80 字，请检查起止位置。")
        now = int(time()) if now is None else now
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            self._require_idle(db, user_id, now)
            old = db.execute(
                "SELECT * FROM coach_book_units WHERE unit_id=? AND user_id=? AND material_id=?",
                (unit_id, user_id, material_id),
            ).fetchone()
            if old is None and revision:
                return "missing"
            if old and old["revision"] != revision:
                return "conflict"
            if db.execute(
                "SELECT 1 FROM coach_book_units WHERE user_id=? AND material_id=? AND unit_id<>? AND start_pos<=? AND end_pos>=?",
                (user_id, material_id, unit_id, end, start),
            ).fetchone():
                raise ValueError("学习单元范围不能重叠，请先核对已有目录。")
            if old:
                if (old["title"], old["start_pos"], old["end_pos"]) == (
                    title,
                    start,
                    end,
                ):
                    return "unchanged"
                db.execute(
                    "UPDATE coach_book_units SET title=?,start_pos=?,end_pos=?,revision=revision+1,updated_at=? WHERE unit_id=?",
                    (title, start, end, now, unit_id),
                )
            else:
                if (
                    db.execute(
                        "SELECT COUNT(*) FROM coach_book_units WHERE user_id=? AND material_id=?",
                        (user_id, material_id),
                    ).fetchone()[0]
                    >= 60
                ):
                    raise ValueError("每份资料最多 60 个学习单元，可修改现有单元。")
                # A foreign unit id must never be overwritten.
                if db.execute(
                    "SELECT 1 FROM coach_book_units WHERE unit_id=?", (unit_id,)
                ).fetchone():
                    return "missing"
                db.execute(
                    "INSERT INTO coach_book_units VALUES(?,?,?,?,?,?,1,?)",
                    (unit_id, user_id, material_id, title, start, end, now),
                )
        return "saved"

    def topic_turns(self, user_id, identity):
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT turn.* FROM coach_turns AS turn JOIN coach_turn_topics AS tag ON tag.turn_id=turn.turn_id AND tag.user_id=turn.user_id WHERE turn.user_id=? AND tag.topic_id=? ORDER BY turn.turn_id DESC LIMIT 40",
                (user_id, identity),
            ).fetchall()
        turns = [dict(row) for row in reversed(rows)]
        for turn in turns:
            turn["citations"] = json.loads(turn.pop("citations_json"))
        return turns

    def _connect(self):
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _expire(connection, user_id, now):
        # Never automatically resend an interrupted provider request.
        connection.execute(
            "UPDATE coach_turns SET status='failed', completed_at=? "
            "WHERE user_id=? AND status='pending' AND created_at<=?",
            (now, user_id, now - PENDING_LIFETIME),
        )

    @staticmethod
    def _history_page(connection, user_id, before=None):
        rows = connection.execute(
            "SELECT turn_id, user_content, assistant_content, status, created_at, citations_json "
            "FROM coach_turns WHERE user_id=? AND turn_id<? ORDER BY turn_id DESC LIMIT ?",
            (
                user_id,
                before if before is not None else 9223372036854775807,
                HISTORY_PAGE_SIZE + 1,
            ),
        ).fetchall()
        turns = [dict(row) for row in reversed(rows[:HISTORY_PAGE_SIZE])]
        for turn in turns:
            turn["citations"] = json.loads(turn.pop("citations_json"))
        return {
            "turns": turns,
            "before": turns[0]["turn_id"] if len(rows) > HISTORY_PAGE_SIZE else None,
        }

    def history_page(self, user_id, *, before):
        if type(before) is not int or not 1 <= before <= 9223372036854775807:
            raise ValueError("invalid history cursor")
        with closing(self._connect()) as connection:
            return self._history_page(connection, user_id, before)

    def dialogue_status(self, user_id, nonce, *, now=None):
        """Read only the owned request's status; never expire, resend or bill it."""
        if (
            not isinstance(nonce, str)
            or re.fullmatch(r"[A-Za-z0-9_-]{43}", nonce) is None
        ):
            raise ValueError("invalid request")
        now = int(time()) if now is None else now
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT status,created_at FROM coach_turns WHERE user_id=? AND nonce=?",
                (user_id, nonce),
            ).fetchone()
        status = row["status"] if row else "missing"
        if row and status == "pending" and row["created_at"] <= now - PENDING_LIFETIME:
            status = "expired"
        return {"status": status}

    def conversation_records(
        self, user_id, *, query="", topic_id="", page=1, start_day="", end_day=""
    ):
        """Read owned stored messages without expiring requests or changing learning state."""
        query = search_query(query)
        scope, scope_values = _review_scope(topic_id)
        lower, upper = conversation_date_window(start_day, end_day)
        date_scope, date_values = "", []
        if lower is not None:
            date_scope += " AND turn.created_at>=?"
            date_values.append(lower)
        if upper is not None:
            date_scope += " AND turn.created_at<?"
            date_values.append(upper)
        if type(page) is not int or not 1 <= page <= 10000:
            raise ValueError("请输入有效的对话记录页码。")
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT "
                + _REVIEW_FIELDS
                + _REVIEW_FROM
                + "WHERE turn.user_id=?"
                + scope
                + date_scope
                + " AND (instr(lower(turn.user_content),lower(?))>0 "
                "OR instr(lower(COALESCE(turn.assistant_content,'')),lower(?))>0) "
                "ORDER BY turn.turn_id DESC LIMIT 21 OFFSET ?",
                (user_id, *scope_values, *date_values, query, query, (page - 1) * 20),
            ).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            excerpts = []
            for key, label in (("user_content", "你"), ("assistant_content", "知行")):
                text = item.pop(key) or ""
                if not text:
                    continue
                excerpt = (
                    match_contexts(text, query, limit=1)["contexts"]
                    if query
                    else [
                        {"text": text[:160], "before": False, "after": len(text) > 160}
                    ]
                )
                if excerpt:
                    excerpts.append({"speaker": label, **excerpt[0]})
            results.append({**item, "excerpts": excerpts})
        return results

    def conversation_record(self, user_id, turn_id):
        if type(turn_id) is not int or not 1 <= turn_id <= 9223372036854775807:
            raise ValueError("请输入有效的对话记录编号。")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN")
            row = db.execute(
                "SELECT "
                + _REVIEW_FIELDS
                + ",turn.citations_json"
                + _REVIEW_FROM
                + "WHERE turn.user_id=? AND turn.turn_id=?",
                (user_id, turn_id),
            ).fetchone()
            if row is None:
                return None
            item = dict(row)
            scope, values = _review_scope(item["topic_id"] or "unfiled")
            neighbors = {}
            for key, comparison, ordering in (
                ("previous", "<", "DESC"),
                ("next", ">", "ASC"),
            ):
                neighbor = db.execute(
                    "SELECT turn.turn_id"
                    + _REVIEW_FROM
                    + "WHERE turn.user_id=?"
                    + scope
                    + " AND turn.turn_id"
                    + comparison
                    + "? ORDER BY turn.turn_id "
                    + ordering
                    + " LIMIT 1",
                    (user_id, *values, turn_id),
                ).fetchone()
                neighbors[key] = neighbor[0] if neighbor else None
            lessons = [
                dict(lesson)
                for lesson in db.execute(
                    "SELECT knowledge_id,title,status FROM coach_knowledge "
                    "WHERE user_id=? AND turn_id=? AND status IN ('pending','saved')",
                    (user_id, turn_id),
                )
            ]
        item["citations"] = json.loads(item.pop("citations_json"))
        return {**item, "neighbors": neighbors, "lessons": lessons}

    def view(self, user_id, *, now=None):
        now = int(time()) if now is None else now
        with closing(self._connect()) as connection, connection:
            self._expire(connection, user_id, now)
            page = self._history_page(connection, user_id)
            learning = connection.execute(
                "SELECT topic, progress, next_step, updated_at FROM coach_learning WHERE user_id=?",
                (user_id,),
            ).fetchone()
        return {**page, "learning": dict(learning) if learning else None}

    def claim(
        self,
        user_id,
        nonce,
        text,
        *,
        now,
        study_id=None,
        part_id=None,
        part_material_id=None,
        detached=False,
        unit_guard=None,
        ai_kind=None,
        review_guard=None,
        end_review=False,
    ):
        if ai_kind not in {None, "dialogue", "unit_lesson"}:
            raise ValueError("invalid AI request kind")
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            self._expire(connection, user_id, now)
            existing = connection.execute(
                "SELECT status FROM coach_turns WHERE user_id=? AND nonce=?",
                (user_id, nonce),
            ).fetchone()
            if existing:
                return "duplicate"
            if (
                review_guard is not None
                and self._review_state(connection, user_id) != review_guard
            ):
                return "review_changed"
            if connection.execute(
                "SELECT 1 FROM coach_turns WHERE user_id=? AND status='pending'",
                (user_id,),
            ).fetchone():
                return "busy"
            if unit_guard is not None:
                unit = connection.execute(
                    "SELECT revision FROM coach_book_units WHERE user_id=? AND material_id=? AND unit_id=?",
                    (user_id, unit_guard["material_id"], unit_guard["unit_id"]),
                ).fetchone()
                covered = sorted(
                    row[0]
                    for row in connection.execute(
                        "SELECT chunk_id FROM coach_book_coverage WHERE user_id=? AND material_id=?",
                        (user_id, unit_guard["material_id"]),
                    )
                )
                if (
                    unit is None
                    or unit[0] != unit_guard["revision"]
                    or covered != unit_guard["coverage_ids"]
                ):
                    raise ValueError("单元或讲解记录已变化，请重新核对整理范围。")
            usage = budget(connection, user_id, now) if ai_kind else None
            if usage and usage["reason"]:
                return "daily_limit"
            if end_review:
                connection.execute(
                    "DELETE FROM coach_review WHERE user_id=?", (user_id,)
                )
            if study_id is not None:
                self._activate_topic(connection, user_id, study_id)
            if part_id is not None:
                target = connection.execute(
                    "SELECT topic.topic_id,topic.material_id FROM coach_topics AS topic JOIN coach_active_topic AS active ON active.topic_id=topic.topic_id AND active.user_id=topic.user_id WHERE topic.user_id=?",
                    (user_id,),
                ).fetchone()
                if target is None or target["material_id"] != part_material_id:
                    raise ValueError("study material changed")
                before = connection.execute(
                    "SELECT chunk_id FROM coach_topic_parts WHERE user_id=? AND topic_id=?",
                    (user_id, target["topic_id"]),
                ).fetchone()
                if (before[0] if before else "") != part_id:
                    connection.execute(
                        "DELETE FROM coach_review WHERE user_id=?", (user_id,)
                    )
                self._set_part(
                    connection,
                    user_id,
                    target["topic_id"],
                    part_material_id,
                    part_id,
                    now,
                )
            connection.execute(
                "INSERT INTO coach_turns(user_id,nonce,user_content,status,created_at) "
                "VALUES(?,?,?,'pending',?)",
                (user_id, nonce, text, now),
            )
            if not detached:
                connection.execute(
                    "INSERT INTO coach_turn_topics SELECT turn.turn_id,turn.user_id,active.topic_id FROM coach_turns AS turn JOIN coach_active_topic AS active ON active.user_id=turn.user_id WHERE turn.user_id=? AND turn.nonce=?",
                    (user_id, nonce),
                )
            if ai_kind:
                connection.execute(
                    "INSERT INTO coach_ai_usage(user_id,nonce,day,kind,started_at) VALUES(?,?,?,?,?)",
                    (user_id, nonce, usage["day"], ai_kind, now),
                )
        return "claimed"

    def growth_review(self, user_id, *, period="7", now=None):
        """Read an owned, consistent activity summary; these records are not scores."""
        if period not in {"7", "30", "all"}:
            raise ValueError("请选择最近7天、30天或全部时间。")
        now = int(time()) if now is None else now
        if type(now) is not int or now < 0:
            raise ValueError("回顾时间无法读取。")
        zone = timezone(timedelta(hours=8))
        today = datetime.fromtimestamp(now, zone).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        start = today - timedelta(days=int(period) - 1) if period != "all" else None
        since = int(start.timestamp()) if start else 0
        scope = " WHERE turn.user_id=? AND turn.status='complete' AND turn.completed_at>=? AND turn.completed_at<=?"
        with closing(self._connect()) as db:
            db.execute("BEGIN")
            totals = db.execute(
                "SELECT COUNT(*) AS completed_turns,COUNT(DISTINCT topic.topic_id) AS active_topics,COALESCE(SUM(CASE WHEN topic.topic_id IS NULL THEN 1 ELSE 0 END),0) AS unfiled_turns"
                + _REVIEW_FROM
                + scope,
                (user_id, since, now),
            ).fetchone()
            saved = db.execute(
                "SELECT COUNT(*) FROM coach_knowledge WHERE user_id=? AND status='saved' AND saved_at>=? AND saved_at<=?",
                (user_id, since, now),
            ).fetchone()[0]
            turns = db.execute(
                "SELECT turn.turn_id,substr(turn.user_content,1,180) AS question,length(turn.user_content)>180 AS shortened,turn.completed_at,topic.topic_id,topic.title AS topic_title"
                + _REVIEW_FROM
                + scope
                + " ORDER BY turn.completed_at DESC,turn.turn_id DESC LIMIT 5",
                (user_id, since, now),
            ).fetchall()
            lessons = db.execute(
                "SELECT knowledge_id,title,topic,saved_at FROM coach_knowledge WHERE user_id=? AND status='saved' AND saved_at>=? AND saved_at<=? ORDER BY saved_at DESC,knowledge_id LIMIT 5",
                (user_id, since, now),
            ).fetchall()
            topics = db.execute(
                "SELECT topic.topic_id,topic.title,COUNT(*) AS completed_turns,MAX(turn.completed_at) AS last_completed_at"
                + _REVIEW_FROM
                + scope
                + " AND topic.topic_id IS NOT NULL GROUP BY topic.topic_id,topic.title ORDER BY last_completed_at DESC,topic.topic_id LIMIT 5",
                (user_id, since, now),
            ).fetchall()
        return {
            "period": period,
            "start_day": start.strftime("%Y-%m-%d") if start else None,
            "end_day": today.strftime("%Y-%m-%d"),
            "as_of": now,
            **dict(totals),
            "saved_lessons": saved,
            "recent_turns": [dict(row) for row in turns],
            "recent_lessons": [dict(row) for row in lessons],
            "recent_topics": [dict(row) for row in topics],
        }

    def ai_usage(self, user_id, *, now=None):
        now = int(time()) if now is None else now
        with closing(self._connect()) as db, db:
            db.execute("BEGIN")
            snapshot = budget(db, user_id, now)
            rows = [
                dict(row)
                for row in db.execute(
                    "SELECT day,kind,COUNT(*) AS count FROM coach_ai_usage WHERE user_id=? AND day>=date(?,'-6 days') AND day<=? GROUP BY day,kind ORDER BY day DESC,kind",
                    (user_id, snapshot["day"], snapshot["day"]),
                )
            ]
        return {**snapshot, "recent": rows}

    def finish(
        self,
        user_id,
        nonce,
        answer,
        learning,
        *,
        now,
        citations=None,
        draft=None,
        material_id=None,
        part_id=None,
        explained_part=False,
        unit_summary=None,
    ):
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            changed = connection.execute(
                "UPDATE coach_turns SET status='complete', assistant_content=?, completed_at=?, citations_json=? "
                "WHERE user_id=? AND nonce=? AND status='pending' AND created_at>?",
                (
                    answer,
                    now,
                    json.dumps(citations or [], ensure_ascii=False),
                    user_id,
                    nonce,
                    now - PENDING_LIFETIME,
                ),
            ).rowcount
            if changed and learning is not None:
                identity = self._store_topic(
                    connection, user_id, learning, now, material_id
                )
                if part_id:
                    self._set_part(
                        connection, user_id, identity, material_id, part_id, now
                    )
                connection.execute(
                    "INSERT INTO coach_turn_topics SELECT turn_id,user_id,? FROM coach_turns WHERE user_id=? AND nonce=? ON CONFLICT(turn_id) DO UPDATE SET topic_id=excluded.topic_id",
                    (identity, user_id, nonce),
                )
            if changed and explained_part and material_id and part_id:
                connection.execute(
                    "INSERT INTO coach_book_coverage SELECT user_id,?,?,turn_id,? FROM coach_turns WHERE user_id=? AND nonce=? ON CONFLICT(user_id,material_id,chunk_id) DO NOTHING",
                    (material_id, part_id, now, user_id, nonce),
                )
            if changed and draft is not None:
                turn_id = connection.execute(
                    "SELECT turn_id FROM coach_turns WHERE user_id=? AND nonce=?",
                    (user_id, nonce),
                ).fetchone()[0]
                knowledge_id = uuid4().hex
                connection.execute(
                    "INSERT INTO coach_knowledge VALUES(?,?,?,?,?,?,?,'pending',?,NULL)",
                    (
                        knowledge_id,
                        user_id,
                        turn_id,
                        draft["title"],
                        draft["topic"],
                        draft["content"],
                        json.dumps(citations or [], ensure_ascii=False),
                        now,
                    ),
                )
                if unit_summary is not None:
                    connection.execute(
                        "INSERT INTO coach_knowledge_units VALUES(?,?,?,?,?)",
                        (
                            knowledge_id,
                            user_id,
                            unit_summary["material_id"],
                            unit_summary["unit_id"],
                            json.dumps(unit_summary, ensure_ascii=False),
                        ),
                    )
        return bool(changed)

    def unit_knowledge(self, user_id, material_id, unit_id, *, offset=0, limit=21):
        with closing(self._connect()) as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT k.knowledge_id,k.title,k.status,k.created_at,link.scope_json FROM coach_knowledge k JOIN coach_knowledge_units link ON link.knowledge_id=k.knowledge_id AND link.user_id=k.user_id WHERE k.user_id=? AND link.material_id=? AND link.unit_id=? AND k.status<>'dismissed' ORDER BY k.created_at DESC,k.knowledge_id LIMIT ? OFFSET ?",
                    (user_id, material_id, unit_id, limit, offset),
                )
            ]

    def unit_lesson_result(self, user_id, nonce):
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT k.knowledge_id FROM coach_knowledge k JOIN coach_turns t ON t.turn_id=k.turn_id AND t.user_id=k.user_id JOIN coach_knowledge_units link ON link.knowledge_id=k.knowledge_id AND link.user_id=k.user_id WHERE k.user_id=? AND t.nonce=? AND k.status<>'dismissed'",
                (user_id, nonce),
            ).fetchone()
        return row[0] if row else None

    def knowledge(
        self, user_id, knowledge_id, *, saved_only=False, include_dismissed=False
    ):
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT lesson.*, COALESCE((SELECT generation FROM coach_draft_restores WHERE user_id=lesson.user_id AND knowledge_id=lesson.knowledge_id),0) AS draft_generation, COALESCE((SELECT MAX(revision) FROM coach_knowledge_versions WHERE user_id=lesson.user_id AND knowledge_id=lesson.knowledge_id),1) AS revision, COALESCE((SELECT created_at FROM coach_knowledge_versions WHERE user_id=lesson.user_id AND knowledge_id=lesson.knowledge_id ORDER BY revision DESC LIMIT 1),lesson.saved_at) AS revised_at FROM coach_knowledge AS lesson WHERE user_id=? AND knowledge_id=?"
                + ("" if include_dismissed else " AND status<>'dismissed'"),
                (user_id, knowledge_id),
            ).fetchone()
        if not row or (saved_only and row["status"] != "saved"):
            return None
        result = dict(row)
        result["citations"] = json.loads(result.pop("citations_json"))
        with closing(self._connect()) as db:
            link = db.execute(
                "SELECT scope_json FROM coach_knowledge_units WHERE user_id=? AND knowledge_id=?",
                (user_id, knowledge_id),
            ).fetchone()
        if link:
            result["unit_summary"] = json.loads(link[0])
        return result

    def list_knowledge(
        self,
        user_id,
        *,
        status="saved",
        query="",
        offset=0,
        limit=21,
        favorites_only=False,
        topic="",
    ):
        query = search_query(query)
        topic = lesson_topic(topic)
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT knowledge_id,title,topic,status,created_at"
                + (",content" if query else "")
                + " FROM coach_knowledge WHERE user_id=? AND status=? AND (instr(lower(title),lower(?))>0 OR instr(lower(topic),lower(?))>0 OR instr(lower(content),lower(?))>0)"
                + (" AND topic=?" if topic else "")
                + (
                    " AND status='saved' AND EXISTS(SELECT 1 FROM coach_lesson_favorites AS favorite WHERE favorite.user_id=coach_knowledge.user_id AND favorite.knowledge_id=coach_knowledge.knowledge_id AND favorite.selected=1)"
                    if favorites_only
                    else ""
                )
                + " ORDER BY created_at DESC, knowledge_id LIMIT ? OFFSET ?",
                (
                    user_id,
                    status,
                    query,
                    query,
                    query,
                    *([topic] if topic else []),
                    limit,
                    offset,
                ),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            if query:
                item["search_match"] = lesson_match(
                    item["title"], item["topic"], item.pop("content"), query
                )
            result.append(item)
        return result

    def knowledge_topics(
        self, user_id, *, status="saved", favorites_only=False, topic=""
    ):
        """Owned directory counts and bounded topic choices; no content or writes."""
        topic = lesson_topic(topic)
        scope = " FROM coach_knowledge WHERE user_id=? AND status=?"
        if favorites_only:
            scope += " AND status='saved' AND EXISTS(SELECT 1 FROM coach_lesson_favorites f WHERE f.user_id=coach_knowledge.user_id AND f.knowledge_id=coach_knowledge.knowledge_id AND f.selected=1)"
        with closing(self._connect()) as db, db:
            db.execute("BEGIN")
            counts = db.execute(
                "SELECT COUNT(*) AS total,COALESCE(SUM(CASE WHEN topic=? THEN 1 ELSE 0 END),0) AS selected"
                + scope,
                (topic, user_id, status),
            ).fetchone()
            rows = db.execute(
                "SELECT topic,COUNT(*) AS count"
                + scope
                + " GROUP BY topic ORDER BY MAX(created_at) DESC,topic LIMIT 201",
                (user_id, status),
            ).fetchall()
        choices = [dict(row) for row in rows[:200] if row["topic"]]
        if topic and all(row["topic"] != topic for row in choices):
            choices.append({"topic": topic, "count": counts["selected"]})
        return {
            "topics": choices,
            "total": counts["total"],
            "selected_count": counts["selected"] if topic else counts["total"],
            "truncated": len(rows) > 200,
        }

    def lesson_favorite(self, user_id, knowledge_id):
        """Read a saved lesson's shortcut state without changing content or position."""
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT COALESCE(favorite.selected,0) AS selected,COALESCE(favorite.revision,0) AS revision FROM coach_knowledge AS lesson LEFT JOIN coach_lesson_favorites AS favorite ON favorite.user_id=lesson.user_id AND favorite.knowledge_id=lesson.knowledge_id WHERE lesson.user_id=? AND lesson.knowledge_id=? AND lesson.status='saved'",
                (user_id, knowledge_id),
            ).fetchone()
        return (
            {"selected": bool(row["selected"]), "revision": row["revision"]}
            if row
            else None
        )

    def set_lesson_favorite(self, user_id, knowledge_id, selected, revision):
        """Set an explicit desired state; old forms never toggle a newer choice."""
        if (
            type(selected) is not bool
            or type(revision) is not int
            or not 0 <= revision <= 1000000000
        ):
            raise ValueError("收藏状态或版本无法核对。")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            lesson = db.execute(
                "SELECT 1 FROM coach_knowledge WHERE user_id=? AND knowledge_id=? AND status='saved'",
                (user_id, knowledge_id),
            ).fetchone()
            if lesson is None:
                return "missing"
            row = db.execute(
                "SELECT selected,revision FROM coach_lesson_favorites WHERE user_id=? AND knowledge_id=?",
                (user_id, knowledge_id),
            ).fetchone()
            current_revision, current_selected = (
                (row["revision"], bool(row["selected"])) if row else (0, False)
            )
            if current_revision != revision:
                return "conflict"
            if current_selected == selected:
                return "unchanged"
            db.execute(
                "INSERT INTO coach_lesson_favorites(user_id,knowledge_id,selected,revision) VALUES(?,?,?,?) ON CONFLICT(user_id,knowledge_id) DO UPDATE SET selected=excluded.selected,revision=excluded.revision",
                (user_id, knowledge_id, int(selected), revision + 1),
            )
        return "updated"

    def change_draft(
        self,
        user_id,
        knowledge_id,
        operation,
        expected_version,
        *,
        title=None,
        content=None,
    ):
        """Stage, confirm or dismiss an owned pending draft in one transaction."""
        if (
            operation not in {"stage", "save", "dismiss"}
            or not isinstance(expected_version, str)
            or re.fullmatch(r"[a-f0-9]{64}", expected_version) is None
        ):
            raise ValueError("草稿操作或版本无法核对。")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT lesson.*, COALESCE((SELECT generation FROM coach_draft_restores WHERE user_id=lesson.user_id AND knowledge_id=lesson.knowledge_id),0) AS draft_generation FROM coach_knowledge AS lesson WHERE user_id=? AND knowledge_id=?",
                (user_id, knowledge_id),
            ).fetchone()
            if row is None or row["status"] == "dismissed":
                return "missing"
            if row["status"] != "pending":
                return "saved"
            if draft_version(row) != expected_version:
                return "conflict"
            if operation == "dismiss":
                db.execute(
                    "UPDATE coach_knowledge SET status='dismissed' WHERE user_id=? AND knowledge_id=? AND status='pending'",
                    (user_id, knowledge_id),
                )
                return "dismissed"
            title, content = draft_text(title, content)
            if operation == "stage":
                if (title, content) == (row["title"], row["content"]):
                    return "unchanged"
                db.execute(
                    "UPDATE coach_knowledge SET title=?,content=? WHERE user_id=? AND knowledge_id=? AND status='pending'",
                    (title, content, user_id, knowledge_id),
                )
                return "staged"
            db.execute(
                "UPDATE coach_knowledge SET title=?,content=?,status='saved',saved_at=? WHERE user_id=? AND knowledge_id=? AND status='pending'",
                (title, content, int(time()), user_id, knowledge_id),
            )
        return "saved_now"

    def restore_draft(self, user_id, knowledge_id, expected_version):
        """Recover only an owned removed draft; invalidate all pre-recovery forms."""
        if (
            not isinstance(expected_version, str)
            or re.fullmatch(r"[a-f0-9]{64}", expected_version) is None
        ):
            raise ValueError("草稿版本无法核对。")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT lesson.*, COALESCE((SELECT generation FROM coach_draft_restores WHERE user_id=lesson.user_id AND knowledge_id=lesson.knowledge_id),0) AS draft_generation FROM coach_knowledge AS lesson WHERE user_id=? AND knowledge_id=?",
                (user_id, knowledge_id),
            ).fetchone()
            if row is None:
                return "missing"
            if row["status"] != "dismissed":
                return "processed"
            if draft_version(row) != expected_version:
                return "conflict"
            db.execute(
                "UPDATE coach_knowledge SET status='pending',saved_at=NULL WHERE user_id=? AND knowledge_id=? AND status='dismissed'",
                (user_id, knowledge_id),
            )
            db.execute(
                "INSERT INTO coach_draft_restores(user_id,knowledge_id,generation) VALUES(?,?,1) ON CONFLICT(user_id,knowledge_id) DO UPDATE SET generation=generation+1",
                (user_id, knowledge_id),
            )
        return "restored"

    def confirm_knowledge(
        self, user_id, knowledge_id, *, save=True, title=None, content=None
    ):
        if title is not None and (
            not isinstance(title, str) or not 1 <= len(title.strip()) <= 120
        ):
            raise ValueError("invalid title")
        if content is not None and (
            not isinstance(content, str) or not 1 <= len(content.strip()) <= 12000
        ):
            raise ValueError("invalid lesson")
        with closing(self._connect()) as db, db:
            db.execute(
                "UPDATE coach_knowledge SET status=?,saved_at=?,title=COALESCE(?,title),content=COALESCE(?,content) WHERE user_id=? AND knowledge_id=? AND status='pending'",
                (
                    "saved" if save else "dismissed",
                    int(time()) if save else None,
                    title.strip() if title else None,
                    content.strip() if content else None,
                    user_id,
                    knowledge_id,
                ),
            )
        return self.knowledge(user_id, knowledge_id)

    def knowledge_versions(self, user_id, knowledge_id, *, offset=0, limit=21):
        with closing(self._connect()) as db:
            db.execute("BEGIN")
            item = db.execute(
                "SELECT title,saved_at FROM coach_knowledge WHERE user_id=? AND knowledge_id=? AND status='saved'",
                (user_id, knowledge_id),
            ).fetchone()
            if item is None:
                return []
            rows = db.execute(
                "SELECT revision,title,created_at,restored_from FROM coach_knowledge_versions WHERE user_id=? AND knowledge_id=? ORDER BY revision DESC LIMIT ? OFFSET ?",
                (user_id, knowledge_id, limit, offset),
            ).fetchall()
            if not rows and offset == 0:
                return [
                    {
                        "revision": 1,
                        "title": item["title"],
                        "created_at": item["saved_at"],
                        "restored_from": None,
                    }
                ]
            return [dict(row) for row in rows]

    def knowledge_version(self, user_id, knowledge_id, revision):
        with closing(self._connect()) as db:
            db.execute("BEGIN")
            item = db.execute(
                "SELECT title,content,saved_at FROM coach_knowledge WHERE user_id=? AND knowledge_id=? AND status='saved'",
                (user_id, knowledge_id),
            ).fetchone()
            if item is None:
                return None
            row = db.execute(
                "SELECT revision,title,content,created_at,restored_from FROM coach_knowledge_versions WHERE user_id=? AND knowledge_id=? AND revision=?",
                (user_id, knowledge_id, revision),
            ).fetchone()
            if row:
                return dict(row)
            if (
                revision == 1
                and not db.execute(
                    "SELECT 1 FROM coach_knowledge_versions WHERE user_id=? AND knowledge_id=? LIMIT 1",
                    (user_id, knowledge_id),
                ).fetchone()
            ):
                return {
                    "revision": 1,
                    "title": item["title"],
                    "content": item["content"],
                    "created_at": item["saved_at"],
                    "restored_from": None,
                }
            return None

    def revise_knowledge(
        self,
        user_id,
        knowledge_id,
        revision,
        *,
        title=None,
        content=None,
        restore=None,
        now=None,
    ):
        if type(revision) is not int or not 1 <= revision <= 1000000000:
            raise ValueError("invalid revision")
        if restore is not None:
            if (
                type(restore) is not int
                or not 1 <= restore <= 1000000000
                or title is not None
                or content is not None
            ):
                raise ValueError("invalid restore")
        elif (
            not isinstance(title, str)
            or not 1 <= len(title.strip()) <= 120
            or not isinstance(content, str)
            or not 1 <= len(content.strip()) <= 12000
            or any(c in title for c in "\r\n\x00")
            or "\x00" in content
            or any(0xD800 <= ord(c) <= 0xDFFF for c in title + content)
        ):
            raise ValueError("invalid lesson")
        now = int(time()) if now is None else now
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            item = db.execute(
                "SELECT * FROM coach_knowledge WHERE user_id=? AND knowledge_id=? AND status='saved'",
                (user_id, knowledge_id),
            ).fetchone()
            if item is None:
                return "missing"
            current = (
                db.execute(
                    "SELECT MAX(revision) FROM coach_knowledge_versions WHERE user_id=? AND knowledge_id=?",
                    (user_id, knowledge_id),
                ).fetchone()[0]
                or 1
            )
            if current != revision:
                return "conflict"
            if restore is not None:
                source = db.execute(
                    "SELECT title,content FROM coach_knowledge_versions WHERE user_id=? AND knowledge_id=? AND revision=?",
                    (user_id, knowledge_id, restore),
                ).fetchone()
                if source is None:
                    if restore != 1 or current != 1:
                        return "missing"
                    source = item
                title, content = source["title"], source["content"]
            else:
                title, content = title.strip(), content.strip()
            if title == item["title"] and content == item["content"]:
                return "unchanged"
            if db.execute(
                "SELECT 1 FROM coach_review WHERE user_id=? AND knowledge_id=?",
                (user_id, knowledge_id),
            ).fetchone():
                self._require_idle(db, user_id, now)
            if current == 1:
                db.execute(
                    "INSERT OR IGNORE INTO coach_knowledge_versions VALUES(?,?,1,?,?,?,NULL)",
                    (
                        user_id,
                        knowledge_id,
                        item["title"],
                        item["content"],
                        item["saved_at"],
                    ),
                )
            db.execute(
                "INSERT INTO coach_knowledge_versions VALUES(?,?,?,?,?,?,?)",
                (user_id, knowledge_id, current + 1, title, content, now, restore),
            )
            db.execute(
                "UPDATE coach_knowledge SET title=?,content=? WHERE user_id=? AND knowledge_id=? AND status='saved'",
                (title, content, user_id, knowledge_id),
            )
            return "updated"

    def select_review(self, user_id, knowledge_id=None, *, material_id=None):
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            now = int(time())
            self._require_idle(db, user_id, now)
            if knowledge_id is None:
                db.execute("DELETE FROM coach_review WHERE user_id=?", (user_id,))
            else:
                lesson = db.execute(
                    "SELECT title,topic FROM coach_knowledge WHERE user_id=? AND knowledge_id=? AND status='saved'",
                    (user_id, knowledge_id),
                ).fetchone()
                if lesson is None:
                    raise ValueError("saved lesson unavailable")
                target = db.execute(
                    "SELECT topic_id FROM coach_topics WHERE user_id=? AND topic_key=?",
                    (user_id, topic_key(lesson["topic"])),
                ).fetchone()
                if target:
                    self._activate_topic(db, user_id, target[0])
                else:
                    self._store_topic(
                        db,
                        user_id,
                        {
                            "topic": lesson["topic"],
                            "progress": "已打开教案《"
                            + lesson["title"]
                            + "》，准备重温。",
                            "next_step": "从教案的核心知识点开始，结合具体例子回顾。",
                        },
                        now,
                        material_id,
                    )
                db.execute(
                    "INSERT INTO coach_review_versions(user_id,revision) VALUES(?,1) ON CONFLICT(user_id) DO UPDATE SET revision=revision+1",
                    (user_id,),
                )
                db.execute(
                    "INSERT INTO coach_review VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET knowledge_id=excluded.knowledge_id",
                    (user_id, knowledge_id),
                )

    @staticmethod
    def _review_state(db, user_id):
        row = db.execute(
            "SELECT (SELECT knowledge_id FROM coach_review WHERE user_id=?) AS knowledge_id,COALESCE((SELECT revision FROM coach_review_versions WHERE user_id=?),0) AS revision",
            (user_id, user_id),
        ).fetchone()
        return {"knowledge_id": row["knowledge_id"] or "", "revision": row["revision"]}

    def review_state(self, user_id):
        with closing(self._connect()) as db:
            return self._review_state(db, user_id)

    def end_review(self, user_id, knowledge_id, revision):
        if (
            not isinstance(knowledge_id, str)
            or re.fullmatch(r"[a-f0-9]{32}", knowledge_id) is None
            or type(revision) is not int
            or not 0 <= revision <= 1000000000
        ):
            raise ValueError("invalid review state")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if self._review_state(db, user_id) != {
                "knowledge_id": knowledge_id,
                "revision": revision,
            }:
                return "conflict"
            self._require_idle(db, user_id, int(time()))
            db.execute("DELETE FROM coach_review WHERE user_id=?", (user_id,))
        return "ended"

    def review(self, user_id):
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT knowledge_id FROM coach_review WHERE user_id=?", (user_id,)
            ).fetchone()
        return self.knowledge(user_id, row[0], saved_only=True) if row else None

    def fail(self, user_id, nonce, *, now):
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "UPDATE coach_turns SET status='failed', completed_at=? "
                "WHERE user_id=? AND nonce=? AND status='pending'",
                (now, user_id, nonce),
            )
