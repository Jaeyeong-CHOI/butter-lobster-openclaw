---
name: upstage-pdf-scan-to-notes
description: Convert scanned PDFs or image-heavy documents into clean research notes using Upstage document digitization + Solar summarization. Use when asked to OCR scan PDFs, extract readable text from noisy pages, and produce structured notes (summary, key points, terms, action items) in Korean or English.
---

# Upstage PDF Scan to Notes

## Core workflow

1. Confirm input document path and output language (`ko` default).
2. Run `scripts/run_scan_to_notes.py` to OCR the document and generate structured notes JSON + Markdown.
3. If OCR quality is weak, rerun with a smaller page range or preprocessed file.
4. Return both machine-readable JSON and human-readable notes.

## Output contract

Always return:

- `*.notes.json`
- `*.notes.md`
- short quality note (missing pages, low-confidence sections, unreadable blocks)

## Execution command

```bash
python3 scripts/run_scan_to_notes.py <input.pdf> \
  --out-dir <output_dir> \
  --ocr-url "$UPSTAGE_OCR_URL" \
  --api-key "$UPSTAGE_API_KEY" \
  --lang ko
```

## Resource map

- Script: `scripts/run_scan_to_notes.py`
- Prompt template: `references/notes-prompt.md`
