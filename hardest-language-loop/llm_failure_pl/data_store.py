from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .settings import RunSettings, default_settings
from .strategy_tree import StrategyTree


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_write_json(path: Path, data: dict[str, Any] | list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


@dataclass(slots=True)
class RunPaths:
    run_id: str
    root: Path
    manifest: Path
    strategy_tree: Path
    events: Path
    artifacts: Path


class FileStore:
    """Append-friendly file store for reproducible experiments.

    Layout:
        data/runs/<run_id>/
          manifest.json
          strategy_tree.json
          events.jsonl
          artifacts/
    """

    def __init__(self, data_root: str | Path = "data/runs") -> None:
        self.data_root = Path(data_root)

    def start_run(self, settings: RunSettings | None = None, run_id: str | None = None) -> RunPaths:
        settings = settings or default_settings()
        run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:6]
        root = self.data_root / run_id
        paths = RunPaths(
            run_id=run_id,
            root=root,
            manifest=root / "manifest.json",
            strategy_tree=root / "strategy_tree.json",
            events=root / "events.jsonl",
            artifacts=root / "artifacts",
        )
        paths.artifacts.mkdir(parents=True, exist_ok=False)
        atomic_write_json(
            paths.manifest,
            {
                "run_id": run_id,
                "created_at": now_iso(),
                "settings": settings.to_dict(),
                "schema_version": 1,
            },
        )
        paths.events.write_text("", encoding="utf-8")
        return paths

    def save_tree(self, paths: RunPaths, tree: StrategyTree) -> None:
        atomic_write_json(paths.strategy_tree, tree.to_dict())

    def load_tree(self, paths: RunPaths) -> StrategyTree:
        return StrategyTree.from_dict(json.loads(paths.strategy_tree.read_text(encoding="utf-8")))

    def append_event(self, paths: RunPaths, kind: str, payload: dict[str, Any]) -> None:
        paths.events.parent.mkdir(parents=True, exist_ok=True)
        with paths.events.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"created_at": now_iso(), "kind": kind, "payload": payload}, ensure_ascii=False) + "\n")

    def save_json_artifact(self, paths: RunPaths, relative_path: str, data: dict[str, Any] | list[Any]) -> Path:
        path = paths.artifacts / relative_path
        atomic_write_json(path, data)
        return path

    def save_text_artifact(self, paths: RunPaths, relative_path: str, text: str) -> Path:
        path = paths.artifacts / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path
