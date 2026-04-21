#!/usr/bin/env python3
from __future__ import annotations

import json
import time
import sys
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8787"


def get_json(path: str):
    with urllib.request.urlopen(BASE + path, timeout=120) as resp:
        return json.loads(resp.read().decode())


def post_json(path: str, payload: dict | None = None):
    data = None if payload is None else json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    cfg = post_json(
        "/api/config",
        {
            "solver_bench": {
                "enabled_models": ["gpt-4.1-mini"],
                "repeat_count": 1,
                "parallelism": 1,
                "thinking": "medium",
                "temperature": 0.2,
            }
        },
    )
    assert cfg["ok"] is True
    post_json("/api/loop/reset")
    step = post_json("/api/loop/step")
    assert step["ok"] is True
    items = []
    deadline = time.time() + 180
    while time.time() < deadline:
        overview = get_json("/api/overview")
        items = get_json("/api/candidates?limit=5")["items"]
        if items and overview["stats"].get("total_evaluations", 0) > 0:
            break
        time.sleep(2)
    else:
        raise AssertionError("timed out waiting for candidate/evaluation generation")
    assert "benchmark" in overview and "strategy_tree" in overview
    assert items, "expected at least one candidate"
    detail = get_json(f"/api/candidates/{items[0]['id']}")
    assert detail["artifacts"]["files"]["interpreter.ml"]
    assert detail["artifacts"]["files"]["validator_result.json"]
    backup = post_json("/api/backup", {"reason": "smoke-test"})
    print(json.dumps({
        "ok": True,
        "candidate": detail["name"],
        "evaluation_count": len(detail.get("evaluations", [])),
        "backup": backup.get("backup"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
