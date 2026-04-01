---
name: upstage-form-parser
description: Extract structured fields from scanned forms and semi-structured documents using Upstage OCR/Parse plus schema-constrained extraction. Use when asked to parse application forms, receipts, certificates, contracts, or survey sheets into reliable JSON with required-field checks.
---

# Upstage Form Parser

## Core workflow

1. Receive form-like input (`.pdf`, image PDF, scan).
2. Run OCR/parse, then extract fields into a provided JSON schema.
3. Mark missing or uncertain required fields explicitly.
4. Save parsed JSON + validation report.

## Output contract

Always return:

- `*.parsed.json` (schema-aligned)
- `*.review.md` (missing fields, ambiguity, normalization notes)

## Execution command

```bash
python3 scripts/run_form_parser.py <input.pdf> \
  --schema references/schema-template.json \
  --out-dir <output_dir> \
  --ocr-url "$UPSTAGE_OCR_URL" \
  --api-key "$UPSTAGE_API_KEY"
```

## Resource map

- Script: `scripts/run_form_parser.py`
- Example schema: `references/schema-template.json`
