#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REASON="${1:-manual}"

python3 - "$ROOT" "$REASON" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
reason = sys.argv[2]
sys.path.insert(0, str(root))

from app import store  # noqa: E402

store.init_db()
backup = store.create_backup_snapshot(reason=reason)
if backup is None:
    print(json.dumps({"ok": True, "backup": None, "message": "No experiment data to back up."}, ensure_ascii=False, indent=2))
else:
    print(json.dumps({"ok": True, "backup": backup}, ensure_ascii=False, indent=2))
PY
