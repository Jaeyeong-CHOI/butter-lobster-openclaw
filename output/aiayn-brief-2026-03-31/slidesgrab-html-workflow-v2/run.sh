#!/usr/bin/env bash
set -euo pipefail
DECK="output/aiayn-brief-2026-03-31/slidesgrab-html-workflow-v2/slides"
OUT="output/aiayn-brief-2026-03-31/slidesgrab-html-workflow-v2"

case "${1:-help}" in
  edit) slides-grab edit --slides-dir "$DECK" ;;
  pdf) slides-grab pdf --slides-dir "$DECK" --output "$OUT/aiayn_slides.pdf" ;;
  pptx) slides-grab convert --slides-dir "$DECK" --output "$OUT/aiayn_slides.pptx" --resolution 2160p ;;
  help|*) echo "Usage: run.sh [edit|pdf|pptx]" ;;
esac
