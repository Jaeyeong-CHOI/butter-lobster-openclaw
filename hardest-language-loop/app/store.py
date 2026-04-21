from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
import shutil
from typing import Any, Iterator

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "loop.db"
SECRETS_PATH = BASE_DIR / "data" / "secrets.json"
CANDIDATE_ROOT = BASE_DIR / "data" / "candidates"

DEFAULT_SETTINGS = {
    "agent2_model": "gpt-5.4",
}


def _read_secrets() -> dict[str, Any]:
    if not SECRETS_PATH.exists():
        return {}
    try:
        return json.loads(SECRETS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_secrets(data: dict[str, Any]) -> None:
    SECRETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SECRETS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        SECRETS_PATH.chmod(0o600)
    except Exception:
        pass


def set_openai_api_key(api_key: str) -> None:
    secrets = _read_secrets()
    secrets["openai_api_key"] = api_key
    _write_secrets(secrets)


def clear_openai_api_key() -> None:
    secrets = _read_secrets()
    secrets.pop("openai_api_key", None)
    _write_secrets(secrets)


def get_openai_api_key() -> str | None:
    value = _read_secrets().get("openai_api_key")
    return value if isinstance(value, str) and value else None


def get_openai_api_key_status() -> dict[str, Any]:
    key = get_openai_api_key()
    if not key:
        return {"configured": False, "masked": None}
    if len(key) <= 10:
        masked = "*" * len(key)
    else:
        masked = f"{key[:7]}...{key[-4:]}"
    return {"configured": True, "masked": masked}


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

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL
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
        for key, value in DEFAULT_SETTINGS.items():
            conn.execute(
                "INSERT INTO settings(key, value_json) VALUES (?, ?) ON CONFLICT(key) DO NOTHING",
                (key, json.dumps(value, ensure_ascii=False)),
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


def get_settings() -> dict[str, Any]:
    with get_conn() as conn:
        rows = conn.execute("SELECT key, value_json FROM settings").fetchall()
        out = dict(DEFAULT_SETTINGS)
        for row in rows:
            out[row["key"]] = json.loads(row["value_json"])
        return out


def set_setting(key: str, value: Any) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO settings(key, value_json) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json",
            (key, json.dumps(value, ensure_ascii=False)),
        )


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


def _benchmark_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    model_rows = conn.execute(
        """
        SELECT model_name, COUNT(*) AS n, AVG(success) AS pass_rate
        FROM evaluations GROUP BY model_name ORDER BY pass_rate ASC, model_name ASC
        """
    ).fetchall()
    task_rows = conn.execute(
        """
        SELECT task_name, COUNT(*) AS n, AVG(success) AS pass_rate
        FROM evaluations GROUP BY task_name ORDER BY pass_rate ASC, task_name ASC
        """
    ).fetchall()
    level_rows = conn.execute(
        """
        SELECT level, COUNT(*) AS n, AVG(failure_rate) AS avg_failure, SUM(CASE WHEN archived = 1 THEN 1 ELSE 0 END) AS archived_n
        FROM candidates GROUP BY level ORDER BY avg_failure DESC
        """
    ).fetchall()
    return {
        "models": [row_to_dict(r) for r in model_rows],
        "tasks": [row_to_dict(r) for r in task_rows],
        "levels": [row_to_dict(r) for r in level_rows],
    }


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
            "settings": get_settings(),
            "stats": {
                "total_candidates": total_candidates,
                "archived_candidates": archived,
                "total_evaluations": total_evaluations,
            },
            "hardest": row_to_dict(hardest),
            "benchmark": _benchmark_summary(conn),
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
    if CANDIDATE_ROOT.exists():
        shutil.rmtree(CANDIDATE_ROOT)
    CANDIDATE_ROOT.mkdir(parents=True, exist_ok=True)
