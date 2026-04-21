#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CAND_ROOT="$ROOT/data/candidates"
TARGET="${1:-}"

if ! command -v ocaml >/dev/null 2>&1; then
  echo "[error] ocaml runtime not found. Install with: brew install ocaml" >&2
  exit 1
fi

if [[ -z "$TARGET" ]]; then
  echo "Usage: $(basename "$0") <candidate-id|candidate-name|interpreter-path>" >&2
  exit 1
fi

resolve_interpreter() {
  local target="$1"

  if [[ -f "$target" ]]; then
    printf '%s\n' "$target"
    return 0
  fi

  if [[ -f "$CAND_ROOT/$target/interpreter.ml" ]]; then
    printf '%s\n' "$CAND_ROOT/$target/interpreter.ml"
    return 0
  fi

  python3 - "$ROOT" "$target" <<'PY'
import sqlite3, sys
from pathlib import Path
root = Path(sys.argv[1])
target = sys.argv[2]
db = root / 'data' / 'loop.db'
if not db.exists():
    raise SystemExit(1)
conn = sqlite3.connect(db)
try:
    cur = conn.execute("SELECT id FROM candidates WHERE name = ? ORDER BY created_at DESC LIMIT 1", (target,))
    row = cur.fetchone()
    if row:
        print(root / 'data' / 'candidates' / row[0] / 'interpreter.ml')
finally:
    conn.close()
PY
}

INTERPRETER_PATH="$(resolve_interpreter "$TARGET")"

if [[ -z "$INTERPRETER_PATH" || ! -f "$INTERPRETER_PATH" ]]; then
  echo "[error] could not resolve interpreter for target: $TARGET" >&2
  exit 1
fi

echo "[info] ocaml version: $(ocaml -version 2>/dev/null | head -n 1)"
echo "[info] running: $INTERPRETER_PATH"
ocaml "$INTERPRETER_PATH"
