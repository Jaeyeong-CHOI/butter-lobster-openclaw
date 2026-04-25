from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
        loop_result/vN/
          manifest.json
          strategy_tree.json
          events.jsonl
          artifacts/
    """

    VERSION_RE = re.compile(r"^v(\d+)$")

    def __init__(self, data_root: str | Path = "loop_result") -> None:
        self.data_root = Path(data_root)

    def _paths_for(self, run_id: str) -> RunPaths:
        root = self.data_root / run_id
        return RunPaths(
            run_id=run_id,
            root=root,
            manifest=root / "manifest.json",
            strategy_tree=root / "strategy_tree.json",
            events=root / "events.jsonl",
            artifacts=root / "artifacts",
        )

    def _version_numbers(self) -> list[int]:
        if not self.data_root.exists():
            return []
        versions: list[int] = []
        for path in self.data_root.iterdir():
            if not path.is_dir():
                continue
            match = self.VERSION_RE.match(path.name)
            if match:
                versions.append(int(match.group(1)))
        return sorted(versions)

    def next_version_id(self) -> str:
        versions = self._version_numbers()
        return f"v{versions[-1] + 1}" if versions else "v0"

    def latest_version_id(self) -> str | None:
        versions = self._version_numbers()
        return f"v{versions[-1]}" if versions else None

    def start_run(self, settings: RunSettings | None = None, run_id: str | None = None, *, resume: bool = False) -> RunPaths:
        settings = settings or default_settings()
        run_id = run_id or self.next_version_id()
        paths = self._paths_for(run_id)
        if resume:
            if not paths.root.exists():
                raise FileNotFoundError(f"Cannot resume missing run folder: {paths.root}")
            paths.artifacts.mkdir(parents=True, exist_ok=True)
            if not paths.events.exists():
                paths.events.write_text("", encoding="utf-8")
            manifest = {}
            if paths.manifest.exists():
                manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))
            manifest.setdefault("run_id", run_id)
            manifest.setdefault("created_at", now_iso())
            manifest.setdefault("schema_version", 1)
            manifest.setdefault("resume_events", [])
            manifest["latest_settings"] = settings.to_dict()
            manifest["resume_events"].append({"resumed_at": now_iso(), "settings": settings.to_dict()})
            atomic_write_json(paths.manifest, manifest)
            self.append_event(paths, "run_resumed", {"run_id": run_id})
            return paths

        paths.artifacts.mkdir(parents=True, exist_ok=False)
        atomic_write_json(
            paths.manifest,
            {
                "run_id": run_id,
                "created_at": now_iso(),
                "settings": settings.to_dict(),
                "schema_version": 1,
                "versioned_result_root": str(self.data_root),
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
