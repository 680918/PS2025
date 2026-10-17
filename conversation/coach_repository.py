"""Account-owned dialogue and learning anchors, independent of legacy journeys."""

import sqlite3
import json
from uuid import uuid4
from contextlib import closing
from pathlib import Path
from coach.learning_memory import MAX_MEMORIES, validate_memory
from time import time
from coach.learning_topics import topic_key, validate_topic_title, TopicBusy


PENDING_LIFETIME = 180
HISTORY_PAGE_SIZE = 40


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
                CREATE TABLE IF NOT EXISTS coach_review (user_id TEXT PRIMARY KEY, knowledge_id TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS coach_topics (
                    topic_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, topic_key TEXT NOT NULL,
                    title TEXT NOT NULL, progress TEXT NOT NULL, next_step TEXT NOT NULL,
                    material_id TEXT, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL,
                    UNIQUE(user_id,topic_key)
                );
                CREATE TABLE IF NOT EXISTS coach_active_topic (user_id TEXT PRIMARY KEY, topic_id TEXT NOT NULL);
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
        with closing(self._connect()) as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM coach_topics WHERE user_id=? AND instr(topic_key,?)>0 ORDER BY updated_at DESC,topic_id LIMIT ? OFFSET ?",
                    (user_id, topic_key(query), limit, offset),
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
            else:
                default_selector()
            db.execute("DELETE FROM coach_review WHERE user_id=?", (user_id,))

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

    def claim(self, user_id, nonce, text, *, now, study_id=None):
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            self._expire(connection, user_id, now)
            existing = connection.execute(
                "SELECT status FROM coach_turns WHERE user_id=? AND nonce=?",
                (user_id, nonce),
            ).fetchone()
            if existing:
                return "duplicate"
            if connection.execute(
                "SELECT 1 FROM coach_turns WHERE user_id=? AND status='pending'",
                (user_id,),
            ).fetchone():
                return "busy"
            if study_id is not None:
                self._activate_topic(connection, user_id, study_id)
            connection.execute(
                "INSERT INTO coach_turns(user_id,nonce,user_content,status,created_at) "
                "VALUES(?,?,?,'pending',?)",
                (user_id, nonce, text, now),
            )
            connection.execute(
                "INSERT INTO coach_turn_topics SELECT turn.turn_id,turn.user_id,active.topic_id FROM coach_turns AS turn JOIN coach_active_topic AS active ON active.user_id=turn.user_id WHERE turn.user_id=? AND turn.nonce=?",
                (user_id, nonce),
            )
        return "claimed"

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
                connection.execute(
                    "INSERT INTO coach_turn_topics SELECT turn_id,user_id,? FROM coach_turns WHERE user_id=? AND nonce=? ON CONFLICT(turn_id) DO UPDATE SET topic_id=excluded.topic_id",
                    (identity, user_id, nonce),
                )
            if changed and draft is not None:
                turn_id = connection.execute(
                    "SELECT turn_id FROM coach_turns WHERE user_id=? AND nonce=?",
                    (user_id, nonce),
                ).fetchone()[0]
                connection.execute(
                    "INSERT INTO coach_knowledge VALUES(?,?,?,?,?,?,?,'pending',?,NULL)",
                    (
                        uuid4().hex,
                        user_id,
                        turn_id,
                        draft["title"],
                        draft["topic"],
                        draft["content"],
                        json.dumps(citations or [], ensure_ascii=False),
                        now,
                    ),
                )
        return bool(changed)

    def knowledge(self, user_id, knowledge_id, *, saved_only=False):
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM coach_knowledge WHERE user_id=? AND knowledge_id=? AND status<> 'dismissed'",
                (user_id, knowledge_id),
            ).fetchone()
        if not row or (saved_only and row["status"] != "saved"):
            return None
        result = dict(row)
        result["citations"] = json.loads(result.pop("citations_json"))
        return result

    def list_knowledge(self, user_id, *, status="saved", query="", offset=0, limit=21):
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT knowledge_id,title,topic,status,created_at FROM coach_knowledge WHERE user_id=? AND status=? AND (instr(lower(title),lower(?))>0 OR instr(lower(topic),lower(?))>0) ORDER BY created_at DESC, knowledge_id LIMIT ? OFFSET ?",
                (user_id, status, query, query, limit, offset),
            ).fetchall()
        return [dict(row) for row in rows]

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

    def select_review(self, user_id, knowledge_id=None, *, material_id=None):
        lesson = (
            self.knowledge(user_id, knowledge_id, saved_only=True)
            if knowledge_id
            else None
        )
        if knowledge_id is not None and lesson is None:
            raise ValueError("saved lesson unavailable")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            now = int(time())
            self._require_idle(db, user_id, now)
            if knowledge_id is None:
                db.execute("DELETE FROM coach_review WHERE user_id=?", (user_id,))
            else:
                self._store_topic(
                    db,
                    user_id,
                    {
                        "topic": lesson["topic"],
                        "progress": "已打开教案《" + lesson["title"] + "》，准备重温。",
                        "next_step": "从教案的核心知识点开始，结合具体例子回顾。",
                    },
                    now,
                    material_id,
                )
                db.execute(
                    "INSERT INTO coach_review VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET knowledge_id=excluded.knowledge_id",
                    (user_id, knowledge_id),
                )

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
