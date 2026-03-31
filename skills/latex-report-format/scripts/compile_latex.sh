#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <path/to/main.tex>"
  exit 1
fi

TEX_FILE="$1"
if [[ ! -f "$TEX_FILE" ]]; then
  echo "[ERR] tex file not found: $TEX_FILE"
  exit 1
fi

WORKDIR="$(cd "$(dirname "$TEX_FILE")" && pwd)"
BASENAME="$(basename "$TEX_FILE")"

cd "$WORKDIR"

echo "[INFO] compiling: $WORKDIR/$BASENAME"
if command -v latexmk >/dev/null 2>&1; then
  latexmk -pdf -interaction=nonstopmode -halt-on-error "$BASENAME"
else
  echo "[WARN] latexmk not found; fallback to pdflatex x2"
  pdflatex -interaction=nonstopmode -halt-on-error "$BASENAME"
  pdflatex -interaction=nonstopmode -halt-on-error "$BASENAME"
fi

echo "[OK] output: ${TEX_FILE%.tex}.pdf"
