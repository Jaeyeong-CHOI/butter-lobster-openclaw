from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "loop.db"


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            PRAGMA journal_mode=WAL;

            CREATE TABLE IF NOT EXISTS loop_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                status TEXT NOT NULL DEFAULT 'idle',
                iteration INTEGER NOT NULL DEFAULT 0,
                started_at TEXT,
                updated_at TEXT,
                note TEXT
            );

            CREATE TABLE IF NOT EXISTS candidates (
                id TEXT PRIMARY KEY,
                parent_id TEXT,
                level TEXT NOT NULL,
                name TEXT NOT NULL,
                mutation_summary TEXT NOT NULL,
                interpreter_hint TEXT NOT NULL,
                similarity_score REAL NOT NULL,
                conflict_score REAL NOT NULL,
                solvable_score REAL NOT NULL,
                novelty_score REAL NOT NULL,
                failure_rate REAL NOT NULL DEFAULT 0,
                archived INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'generated',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS evaluations (
                id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL,
                model_name TEXT NOT NULL,
                task_name TEXT NOT NULL,
                prompt_mode TEXT NOT NULL,
                success INTEGER NOT NULL,
                score REAL NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(candidate_id) REFERENCES candidates(id)
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            INSERT INTO loop_state(id, status, iteration, updated_at, note)
            VALUES (1, 'idle', 0, datetime('now'), 'Loop not started yet')
            ON CONFLICT(id) DO NOTHING
            """
        )
        conn.commit()


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def set_loop_state(*, status: str, iteration: int | None = None, note: str | None = None) -> None:
    with get_conn() as conn:
        if iteration is None:
            conn.execute(
                "UPDATE loop_state SET status = ?, updated_at = datetime('now'), note = ? WHERE id = 1",
                (status, note),
            )
        else:
            conn.execute(
                "UPDATE loop_state SET status = ?, iteration = ?, updated_at = datetime('now'), note = ? WHERE id = 1",
                (status, iteration, note),
            )


def get_loop_state() -> dict[str, Any]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM loop_state WHERE id = 1").fetchone()
        return row_to_dict(row) or {"status": "idle", "iteration": 0}


def insert_candidate(candidate: dict[str, Any]) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO candidates(
                id, parent_id, level, name, mutation_summary, interpreter_hint,
                similarity_score, conflict_score, solvable_score, novelty_score,
                failure_rate, archived, status, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate["id"],
                candidate.get("parent_id"),
                candidate["level"],
                candidate["name"],
                candidate["mutation_summary"],
                candidate["interpreter_hint"],
                candidate["similarity_score"],
                candidate["conflict_score"],
                candidate["solvable_score"],
                candidate["novelty_score"],
                candidate.get("failure_rate", 0.0),
                1 if candidate.get("archived") else 0,
                candidate.get("status", "generated"),
                json.dumps(candidate.get("metadata", {}), ensure_ascii=False),
                candidate["created_at"],
            ),
        )


def update_candidate_outcome(candidate_id: str, *, failure_rate: float, archived: bool, status: str, metadata: dict[str, Any]) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE candidates
            SET failure_rate = ?, archived = ?, status = ?, metadata_json = ?
            WHERE id = ?
            """,
            (failure_rate, 1 if archived else 0, status, json.dumps(metadata, ensure_ascii=False), candidate_id),
        )


def insert_evaluation(evaluation: dict[str, Any]) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO evaluations(
                id, candidate_id, model_name, task_name, prompt_mode, success, score, notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evaluation["id"],
                evaluation["candidate_id"],
                evaluation["model_name"],
                evaluation["task_name"],
                evaluation["prompt_mode"],
                1 if evaluation["success"] else 0,
                evaluation["score"],
                evaluation.get("notes", ""),
                evaluation["created_at"],
            ),
        )


def insert_event(kind: str, payload: dict[str, Any], created_at: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO events(kind, payload_json, created_at) VALUES (?, ?, ?)",
            (kind, json.dumps(payload, ensure_ascii=False), created_at),
        )


def list_events(after_id: int = 0, limit: int = 100) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM events WHERE id > ? ORDER BY id ASC LIMIT ?",
            (after_id, limit),
        ).fetchall()
        return [{**row_to_dict(r), "payload": json.loads(r["payload_json"])} for r in rows]


def get_overview() -> dict[str, Any]:
    with get_conn() as conn:
        state = row_to_dict(conn.execute("SELECT * FROM loop_state WHERE id = 1").fetchone()) or {}
        total_candidates = conn.execute("SELECT COUNT(*) AS c FROM candidates").fetchone()["c"]
        archived = conn.execute("SELECT COUNT(*) AS c FROM candidates WHERE archived = 1").fetchone()["c"]
        total_evaluations = conn.execute("SELECT COUNT(*) AS c FROM evaluations").fetchone()["c"]
        hardest = conn.execute(
            """
            SELECT id, name, level, failure_rate, similarity_score, conflict_score, solvable_score
            FROM candidates ORDER BY failure_rate DESC, conflict_score DESC LIMIT 1
            """
        ).fetchone()
        return {
            "state": state,
            "stats": {
                "total_candidates": total_candidates,
                "archived_candidates": archived,
                "total_evaluations": total_evaluations,
            },
            "hardest": row_to_dict(hardest),
        }


def list_candidates(limit: int = 50) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM candidates ORDER BY created_at DESC, failure_rate DESC LIMIT ?",
            (limit,),
        ).fetchall()
        out = []
        for r in rows:
            item = row_to_dict(r) or {}
            item["metadata"] = json.loads(item.pop("metadata_json", "{}"))
            out.append(item)
        return out


def get_candidate(candidate_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        candidate = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
        if candidate is None:
            return None
        item = row_to_dict(candidate) or {}
        item["metadata"] = json.loads(item.pop("metadata_json", "{}"))
        eval_rows = conn.execute(
            "SELECT * FROM evaluations WHERE candidate_id = ? ORDER BY created_at ASC",
            (candidate_id,),
        ).fetchall()
        item["evaluations"] = [row_to_dict(r) for r in eval_rows]
        return item


def reset_all() -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM evaluations")
        conn.execute("DELETE FROM candidates")
        conn.execute("DELETE FROM events")
        conn.execute(
            "UPDATE loop_state SET status = 'idle', iteration = 0, updated_at = datetime('now'), note = 'Loop reset' WHERE id = 1"
        )
