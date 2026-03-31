---
name: latex-report-format
description: Apply a reusable LaTeX house format and reuse it for PDF and PPT deliverables. Use when asked to draft or edit technical reports in a consistent style, compile .tex into final PDFs, or convert the same report structure into slide decks (Beamer/PPT outline). Trigger on requests like "포맷으로 작성", "LaTeX 템플릿 불러와", "보고서 PDF 만들어", or "이 보고서로 발표자료/PPT 만들어".
---

# LaTeX Report Format

## Quick start workflow

1. Read `references/template-links.md` to find canonical template sources.
2. Read `references/format-rules.md` and lock those constraints before writing.
3. If no local base file exists, copy `assets/templates/report_template.tex` as the working draft.
4. Draft or edit sections while preserving the format constraints.
5. Compile with `scripts/compile_latex.sh <path/to/main.tex>`.
6. If slide output is requested, map sections with `references/ppt-mapping.md` and start from:
   - `assets/templates/slides_beamer.tex` (LaTeX Beamer), or
   - `assets/templates/slides_outline.md` (PPT outline source).

## Non-negotiable style constraints

Apply all constraints from `references/format-rules.md`.
If a user asks to override any constraint, follow the user instruction and clearly note which rule changed.

## Output contract

### For report/PDF tasks

Return:

- Edited file list
- Compile command used
- Output PDF path
- Constraint checklist status (pass/fail per rule)

### For PPT/slide tasks

Return:

- Slide source file path (`.tex` or `.md`)
- Slide-by-slide outline
- Open placeholders requiring user input (e.g., figures not selected yet)

## Resource map

- Rules: `references/format-rules.md`
- Canonical links: `references/template-links.md`
- Section→slide mapping: `references/ppt-mapping.md`
- Compile helper: `scripts/compile_latex.sh`
- Templates: `assets/templates/*`
