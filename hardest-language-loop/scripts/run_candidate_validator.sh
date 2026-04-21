#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${1:-}"

if [[ -z "$TARGET" ]]; then
  echo "Usage: $(basename "$0") <candidate-id|candidate-name>" >&2
  exit 1
fi

python3 - "$ROOT" "$TARGET" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
target = sys.argv[2]
sys.path.insert(0, str(root))

from app import store  # noqa: E402
from app.artifacts import materialize_candidate_bundle, load_candidate_bundle  # noqa: E402

store.init_db()

candidate = store.get_candidate(target)
if candidate is None:
    items = store.list_candidates(limit=1000)
    for item in items:
        if item.get('name') == target:
            candidate = store.get_candidate(item['id']) or item
            break

if candidate is None:
    raise SystemExit(f"[error] candidate not found: {target}")

parent_name = None
if candidate.get('parent_id'):
    parent = store.get_candidate(candidate['parent_id'])
    parent_name = parent.get('name') if parent else None

materialize_candidate_bundle(
    candidate,
    parent_name=parent_name,
    evaluations=candidate.get('evaluations', []),
    analysis={
        'status': candidate.get('status'),
        'archived': candidate.get('archived'),
        'failure_rate': candidate.get('failure_rate'),
        'metadata': candidate.get('metadata', {}),
    },
)

bundle = load_candidate_bundle(candidate)
validator = json.loads(bundle['files']['validator_result.json'])
print(json.dumps(validator, ensure_ascii=False, indent=2))
PY
