#!/usr/bin/env bash
set -euo pipefail

DECK="output/aiayn-brief-2026-03-31/slidesgrab-html-workflow/slides"
ROOT_OUT="output/aiayn-brief-2026-03-31/slidesgrab-html-workflow"

cmd="${1:-help}"

case "$cmd" in
  edit)
    slides-grab edit --slides-dir "$DECK"
    ;;
  validate)
    slides-grab validate --slides-dir "$DECK" --format concise
    ;;
  pdf)
    slides-grab pdf --slides-dir "$DECK" --output "$ROOT_OUT/aiayn_slides.pdf"
    ;;
  pdf-print)
    slides-grab pdf --slides-dir "$DECK" --mode print --output "$ROOT_OUT/aiayn_slides_print.pdf"
    ;;
  pptx)
    slides-grab convert --slides-dir "$DECK" --output "$ROOT_OUT/aiayn_slides.pptx" --resolution 2160p
    ;;
  all)
    slides-grab validate --slides-dir "$DECK" --format concise
    slides-grab pdf --slides-dir "$DECK" --output "$ROOT_OUT/aiayn_slides.pdf"
    slides-grab convert --slides-dir "$DECK" --output "$ROOT_OUT/aiayn_slides.pptx" --resolution 2160p
    ;;
  *)
    cat <<'EOF'
Usage: run.sh [edit|validate|pdf|pdf-print|pptx|all]
EOF
    ;;
esac
