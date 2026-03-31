#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PATTERN='재영|jaeyeong|Jaeyeong|AVRTG|avrtg|@gmail\.com|@dgist\.ac\.kr|[0-9]{1,3}(\.[0-9]{1,3}){3}'

echo "[privacy-check] scanning tracked text files..."
if git grep -nE "$PATTERN" -- . ':!*.skill' ':!*.png' ':!*.jpg' ':!*.jpeg' ':!*.gif' ':!*.pdf'; then
  echo
  echo "[FAIL] potential sensitive markers found"
  exit 1
fi

echo "[PASS] no default sensitive markers found"
