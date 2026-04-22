from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import shutil
from typing import Any, Iterator

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "loop.db"
SECRETS_PATH = BASE_DIR / "data" / "secrets.json"
CANDIDATE_ROOT = BASE_DIR / "data" / "candidates"
BACKUP_ROOT = BASE_DIR / "data" / "backups"

DEFAULT_SETTINGS = {
    "agent_a_model": "gpt-5.4",
    "agent_a_temperature": 0.7,
    "agent_a_thinking": "high",
    "solver_models": [
        "gpt-5.4",
        "gpt-5.4-mini",
        "gpt-5.4-nano",
        "gpt-4.1",
        "gpt-4.1-mini",
        "gpt-4o",
        "gpt-4o-mini",
        "o4-mini",
    ],
    "solver_temperature": 0.2,
    "solver_thinking": "medium",
    "solver_repeat_count": 5,
    "solver_parallelism": 10,
    "solver_request_timeout_seconds": 75,
    "solver_max_retries": 3,
    "solver_retry_backoff_base_seconds": 1.5,
    "provider_default": "openai",
}


def _mask_api_key(key: str) -> str:
    if len(key) <= 10:
        return "*" * len(key)
    return f"{key[:7]}...{key[-4:]}"


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
    return {"configured": True, "masked": _mask_api_key(key)}


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
        eval_columns = {row["name"] for row in conn.execute("PRAGMA table_info(evaluations)").fetchall()}
        if "metadata_json" not in eval_columns:
            conn.execute("ALTER TABLE evaluations ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}'")
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


def create_backup_snapshot(reason: str = "manual") -> dict[str, Any] | None:
    overview = get_overview()
    candidate_count = int(overview["stats"].get("total_candidates", 0))
    evaluation_count = int(overview["stats"].get("total_evaluations", 0))
    with get_conn() as conn:
        event_count = int(conn.execute("SELECT COUNT(*) FROM events").fetchone()[0])
    has_candidate_files = CANDIDATE_ROOT.exists() and any(CANDIDATE_ROOT.iterdir())
    has_db = DB_PATH.exists() and DB_PATH.stat().st_size > 0
    if not any([candidate_count, evaluation_count, event_count, has_candidate_files, has_db]):
        return None

    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    safe_reason = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in reason).strip("-") or "manual"
    backup_dir = BACKUP_ROOT / f"{timestamp}-{safe_reason}"
    backup_dir.mkdir(parents=True, exist_ok=False)

    if DB_PATH.exists():
        shutil.copy2(DB_PATH, backup_dir / "loop.db")
    if CANDIDATE_ROOT.exists() and any(CANDIDATE_ROOT.iterdir()):
        shutil.copytree(CANDIDATE_ROOT, backup_dir / "candidates")

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "stats": overview["stats"],
        "hardest": overview.get("hardest"),
        "settings": overview.get("settings"),
        "providers": overview.get("providers"),
        "includes": {
            "loop_db": (backup_dir / "loop.db").exists(),
            "candidates_dir": (backup_dir / "candidates").exists(),
            "secrets": False,
        },
        "event_count": event_count,
    }
    (backup_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "path": str(backup_dir),
        "stats": overview["stats"],
        "event_count": event_count,
        "manifest": manifest,
    }


def get_loop_state() -> dict[str, Any]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM loop_state WHERE id = 1").fetchone()
        return row_to_dict(row) or {"status": "idle", "iteration": 0}


def get_settings() -> dict[str, Any]:
    with get_conn() as conn:
        rows = conn.execute("SELECT key, value_json FROM settings").fetchall()
        out = dict(DEFAULT_SETTINGS)
        for row in rows:
            if row["key"] in DEFAULT_SETTINGS:
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
                id, candidate_id, model_name, task_name, prompt_mode, success, score, notes, created_at, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                json.dumps(evaluation.get("metadata", {}), ensure_ascii=False),
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
        SELECT model_name, COUNT(*) AS n, SUM(success) AS success_count, AVG(success) AS pass_rate
        FROM evaluations GROUP BY model_name ORDER BY pass_rate ASC, model_name ASC
        """
    ).fetchall()
    task_rows = conn.execute(
        """
        SELECT task_name, COUNT(*) AS n, SUM(success) AS success_count, AVG(success) AS pass_rate
        FROM evaluations GROUP BY task_name ORDER BY pass_rate ASC, task_name ASC
        """
    ).fetchall()
    family_rows = conn.execute(
        """
        SELECT COALESCE(json_extract(metadata_json, '$.strategy_family'), level) AS strategy_family,
               COUNT(*) AS n,
               AVG(failure_rate) AS avg_failure,
               SUM(CASE WHEN archived = 1 THEN 1 ELSE 0 END) AS archived_n
        FROM candidates
        GROUP BY COALESCE(json_extract(metadata_json, '$.strategy_family'), level)
        ORDER BY avg_failure DESC
        """
    ).fetchall()
    return {
        "models": [row_to_dict(r) for r in model_rows],
        "tasks": [row_to_dict(r) for r in task_rows],
        "families": [row_to_dict(r) for r in family_rows],
    }


def _strategy_tree_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute("SELECT id, name, metadata_json, archived, failure_rate FROM candidates ORDER BY created_at ASC").fetchall()
    nodes: dict[str, Any] = {
        "root": {
            "label": "Hardest-language search root",
            "kind": "root",
            "status": "active",
            "count": 0,
            "archived_count": 0,
            "avg_failure": 0.0,
        }
    }
    edges: list[list[str]] = []
    family_order: list[str] = []
    leaf_order: dict[str, list[str]] = {}
    family_stats: dict[str, dict[str, Any]] = {}
    leaf_stats: dict[str, dict[str, Any]] = {}

    for row in rows:
        meta = json.loads(row["metadata_json"] or "{}")
        family = meta.get("strategy_family") or "unclassified"
        leaf = meta.get("strategy_leaf") or f"{family}_leaf"
        family_label = family.replace("_", " ").title()
        leaf_label = leaf.replace("_", " ").title()
        if family not in family_stats:
            family_order.append(family)
            family_stats[family] = {"count": 0, "archived_count": 0, "failure_sum": 0.0}
            nodes[family] = {"label": family_label, "kind": "family", "status": "explored"}
            edges.append(["root", family])
            leaf_order[family] = []
        if leaf not in leaf_stats:
            leaf_order[family].append(leaf)
            leaf_stats[leaf] = {"count": 0, "archived_count": 0, "failure_sum": 0.0, "family": family}
            nodes[leaf] = {"label": leaf_label, "kind": "strategy", "status": "candidate"}
            edges.append([family, leaf])

        family_stats[family]["count"] += 1
        family_stats[family]["archived_count"] += int(row["archived"])
        family_stats[family]["failure_sum"] += float(row["failure_rate"])
        leaf_stats[leaf]["count"] += 1
        leaf_stats[leaf]["archived_count"] += int(row["archived"])
        leaf_stats[leaf]["failure_sum"] += float(row["failure_rate"])

    total = len(rows)
    archived_total = sum(int(row["archived"]) for row in rows)
    nodes["root"].update(
        {
            "count": total,
            "archived_count": archived_total,
            "avg_failure": round(sum(float(row["failure_rate"]) for row in rows) / total, 3) if total else 0.0,
        }
    )

    for family in family_order:
        stats = family_stats[family]
        nodes[family].update(
            {
                "count": stats["count"],
                "archived_count": stats["archived_count"],
                "avg_failure": round(stats["failure_sum"] / stats["count"], 3) if stats["count"] else 0.0,
            }
        )
    for family, leaves in leaf_order.items():
        for leaf in leaves:
            stats = leaf_stats[leaf]
            nodes[leaf].update(
                {
                    "count": stats["count"],
                    "archived_count": stats["archived_count"],
                    "avg_failure": round(stats["failure_sum"] / stats["count"], 3) if stats["count"] else 0.0,
                }
            )

    return {"nodes": nodes, "edges": edges}


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
            "providers": {"openai": get_openai_api_key_status()},
            "stats": {
                "total_candidates": total_candidates,
                "archived_candidates": archived,
                "total_evaluations": total_evaluations,
            },
            "hardest": row_to_dict(hardest),
            "benchmark": _benchmark_summary(conn),
            "strategy_tree": _strategy_tree_summary(conn),
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
        evaluations = []
        for row in eval_rows:
            data = row_to_dict(row) or {}
            data["metadata"] = json.loads(data.pop("metadata_json", "{}"))
            evaluations.append(data)
        item["evaluations"] = evaluations
        return item


def reset_all() -> dict[str, Any] | None:
    backup = create_backup_snapshot("reset")
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
    return backup
