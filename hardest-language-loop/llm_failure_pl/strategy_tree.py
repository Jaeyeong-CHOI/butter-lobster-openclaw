from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def short_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:10]}"


def _empty_metrics() -> dict[str, Any]:
    return {
        "trials": 0,
        "successes": 0,
        "failures": 0,
        "failure_rate": None,
        "best_failure_case_id": None,
        "model_stats": {},
        "problem_stats": {},
        "score": 0.0,
        "last_result_at": None,
    }


@dataclass(slots=True)
class StrategyNode:
    id: str
    title: str
    hypothesis: str
    parent_id: str | None = None
    status: str = "active"
    tags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    children: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=_empty_metrics)
    artifacts: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StrategyNode":
        node = cls(
            id=data["id"],
            title=data["title"],
            hypothesis=data["hypothesis"],
            parent_id=data.get("parent_id"),
            status=data.get("status", "active"),
            tags=list(data.get("tags", [])),
            notes=list(data.get("notes", [])),
            children=list(data.get("children", [])),
            metrics={**_empty_metrics(), **dict(data.get("metrics", {}))},
            artifacts=dict(data.get("artifacts", {})),
            created_at=data.get("created_at", now_iso()),
            updated_at=data.get("updated_at", now_iso()),
        )
        return node


@dataclass(slots=True)
class StrategyTree:
    root_id: str
    nodes: dict[str, StrategyNode] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def new(cls, title: str, hypothesis: str, tags: list[str] | None = None) -> "StrategyTree":
        root = StrategyNode(
            id=short_id("root"),
            title=title,
            hypothesis=hypothesis,
            tags=tags or ["root"],
        )
        tree = cls(root_id=root.id, nodes={root.id: root})
        tree.log_event("tree_created", {"root_id": root.id, "title": title})
        return tree

    def log_event(self, kind: str, payload: dict[str, Any]) -> None:
        self.history.append({"created_at": now_iso(), "kind": kind, "payload": payload})

    def get(self, node_id: str) -> StrategyNode:
        try:
            return self.nodes[node_id]
        except KeyError as exc:
            raise KeyError(f"Unknown strategy node: {node_id}") from exc

    def add_child(
        self,
        parent_id: str,
        title: str,
        hypothesis: str,
        tags: list[str] | None = None,
        note: str | None = None,
        artifacts: dict[str, Any] | None = None,
    ) -> StrategyNode:
        parent = self.get(parent_id)
        child = StrategyNode(
            id=short_id("node"),
            parent_id=parent_id,
            title=title,
            hypothesis=hypothesis,
            tags=tags or [],
            artifacts=artifacts or {},
        )
        if note:
            child.notes.append(note)
        self.nodes[child.id] = child
        parent.children.append(child.id)
        parent.updated_at = now_iso()
        self.log_event("add_child", {"parent_id": parent_id, "node_id": child.id, "title": title})
        return child

    def attach_artifact(self, node_id: str, key: str, value: Any, note: str | None = None) -> StrategyNode:
        node = self.get(node_id)
        node.artifacts[key] = value
        if note:
            node.notes.append(note)
        node.updated_at = now_iso()
        self.log_event("attach_artifact", {"node_id": node_id, "key": key})
        return node

    def mutate_node(
        self,
        node_id: str,
        *,
        title: str | None = None,
        hypothesis: str | None = None,
        status: str | None = None,
        add_tags: list[str] | None = None,
        remove_tags: list[str] | None = None,
        note: str | None = None,
    ) -> StrategyNode:
        node = self.get(node_id)
        if title is not None:
            node.title = title
        if hypothesis is not None:
            node.hypothesis = hypothesis
        if status is not None:
            node.status = status
        if add_tags:
            for tag in add_tags:
                if tag not in node.tags:
                    node.tags.append(tag)
        if remove_tags:
            remove = set(remove_tags)
            node.tags = [tag for tag in node.tags if tag not in remove]
        if note:
            node.notes.append(note)
        node.updated_at = now_iso()
        self.log_event("mutate_node", {"node_id": node_id, "status": node.status, "note": note})
        return node

    @staticmethod
    def _bump_breakdown(metrics: dict[str, Any], bucket: str, key: str | None, success: bool) -> None:
        if not key:
            return
        stats = metrics.setdefault(bucket, {})
        item = stats.setdefault(key, {"trials": 0, "successes": 0, "failures": 0, "failure_rate": None})
        item["trials"] += 1
        item["successes"] += int(success)
        item["failures"] += int(not success)
        item["failure_rate"] = item["failures"] / item["trials"] if item["trials"] else None

    @staticmethod
    def _score(metrics: dict[str, Any]) -> float:
        trials = int(metrics.get("trials") or 0)
        if trials <= 0:
            return 0.0
        failure_rate = float(metrics.get("failure_rate") or 0.0)
        confidence = 1.0 - math.exp(-trials / 8.0)
        return round(failure_rate * confidence, 4)

    def record_result(self, node_id: str, result: dict[str, Any]) -> StrategyNode:
        node = self.get(node_id)
        counted = bool(result.get("counted", True))
        success = bool(result.get("success"))
        if counted:
            metrics = node.metrics
            metrics["trials"] = int(metrics.get("trials") or 0) + 1
            metrics["successes"] = int(metrics.get("successes") or 0) + int(success)
            metrics["failures"] = int(metrics.get("failures") or 0) + int(not success)
            metrics["failure_rate"] = metrics["failures"] / metrics["trials"] if metrics["trials"] else None
            metrics["last_result_at"] = now_iso()
            self._bump_breakdown(metrics, "model_stats", result.get("model"), success)
            self._bump_breakdown(metrics, "problem_stats", result.get("problem_id"), success)
            metrics["score"] = self._score(metrics)
            if not success and result.get("case_id"):
                metrics["best_failure_case_id"] = result["case_id"]
        node.notes.append(
            f"result: success={success} counted={counted} model={result.get('model', 'n/a')} "
            f"problem={result.get('problem_id', 'n/a')} case={result.get('case_id', 'n/a')} "
            f"note={result.get('note', '')}".strip()
        )
        node.updated_at = now_iso()
        self.log_event("record_result", {"node_id": node_id, "result": result})
        return node

    def apply_ops(self, ops: list[dict[str, Any]]) -> list[StrategyNode]:
        """Apply model-proposed tree operations.

        Supported ops are intentionally small and auditable:
        - add_child: parent_id, title, hypothesis, tags?, note?, artifacts?
        - mutate_node: node_id, title?, hypothesis?, status?, add_tags?, remove_tags?, note?
        - attach_artifact: node_id, key, value, note?
        - record_result: node_id, result
        """
        changed: list[StrategyNode] = []
        for op in ops:
            kind = op.get("op")
            if kind == "add_child":
                changed.append(
                    self.add_child(
                        parent_id=op["parent_id"],
                        title=op["title"],
                        hypothesis=op["hypothesis"],
                        tags=op.get("tags"),
                        note=op.get("note"),
                        artifacts=op.get("artifacts"),
                    )
                )
            elif kind == "mutate_node":
                changed.append(
                    self.mutate_node(
                        op["node_id"],
                        title=op.get("title"),
                        hypothesis=op.get("hypothesis"),
                        status=op.get("status"),
                        add_tags=op.get("add_tags"),
                        remove_tags=op.get("remove_tags"),
                        note=op.get("note"),
                    )
                )
            elif kind == "attach_artifact":
                changed.append(self.attach_artifact(op["node_id"], op["key"], op.get("value"), op.get("note")))
            elif kind == "record_result":
                changed.append(self.record_result(op["node_id"], op["result"]))
            else:
                raise ValueError(f"Unsupported tree op: {kind}")
        return changed

    def ranked_nodes(self, *, active_only: bool = False) -> list[StrategyNode]:
        nodes = [node for node in self.nodes.values() if not active_only or node.status == "active"]

        def key(node: StrategyNode) -> tuple[float, float, int]:
            score = float(node.metrics.get("score") or 0.0)
            failure_rate = node.metrics.get("failure_rate")
            return (
                score,
                float(failure_rate) if failure_rate is not None else -1.0,
                int(node.metrics.get("trials") or 0),
            )

        return sorted(nodes, key=key, reverse=True)

    def best_node_for_expansion(self) -> StrategyNode:
        active = [node for node in self.ranked_nodes(active_only=True) if node.id != self.root_id]
        return active[0] if active else self.get(self.root_id)

    def compact(self) -> dict[str, Any]:
        return {
            "root_id": self.root_id,
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "history_tail": self.history[-20:],
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_id": self.root_id,
            "nodes": {node_id: node.to_dict() for node_id, node in self.nodes.items()},
            "history": self.history,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StrategyTree":
        return cls(
            root_id=data["root_id"],
            nodes={node_id: StrategyNode.from_dict(node) for node_id, node in data["nodes"].items()},
            history=list(data.get("history", [])),
        )
