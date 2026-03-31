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

ENGINE="pdflatex"
if grep -q "\\usepackage{fontspec}" "$BASENAME"; then
  ENGINE="xelatex"
fi

echo "[INFO] compiling: $WORKDIR/$BASENAME"
echo "[INFO] engine: $ENGINE"

if command -v latexmk >/dev/null 2>&1; then
  if [[ "$ENGINE" == "xelatex" ]]; then
    latexmk -xelatex -interaction=nonstopmode -halt-on-error "$BASENAME"
  else
    latexmk -pdf -interaction=nonstopmode -halt-on-error "$BASENAME"
  fi
else
  if [[ "$ENGINE" == "xelatex" ]]; then
    xelatex -interaction=nonstopmode -halt-on-error "$BASENAME"
    xelatex -interaction=nonstopmode -halt-on-error "$BASENAME"
  else
    pdflatex -interaction=nonstopmode -halt-on-error "$BASENAME"
    pdflatex -interaction=nonstopmode -halt-on-error "$BASENAME"
  fi
fi

echo "[OK] output: ${TEX_FILE%.tex}.pdf"
