---
name: latex-report-format
description: Apply a reusable LaTeX house format (colors, typography, section styling, table styling) and produce matching PDF and presentation outputs. Use when asked to draft/edit styled reports, compile .tex to final PDF, or build polished PPT/Beamer slides that preserve the same design language.
---

# LaTeX Report Format

## Quick start workflow

1. Read `references/format-rules.md` and lock style constraints.
2. If user provides an existing LaTeX house template, preserve:
   - palette (`\definecolor`),
   - fonts (`fontspec`, `kotex`),
   - section/table/box styles (`titlesec`, `tcolorbox`, table heads).
3. Build report from `assets/templates/report_template.tex` (or user template).
4. Build slides from:
   - `assets/templates/slides_beamer.tex` (LaTeX path), or
   - `assets/templates/slides_outline.md` + `scripts/build_styled_pptx.py` (PPTX path).
5. Compile with `scripts/compile_latex.sh <path/to/main.tex>`.
6. Return artifact paths + style checklist.

## Non-negotiable style constraints

- Preserve design tokens (color/font/hierarchy) unless user explicitly overrides.
- Do not downgrade to plain default PPT/LaTeX style.
- Prioritize readability: spacing, contrast, clear visual hierarchy.

## PPT quality checklist (required)

- 16:9 canvas with consistent margins
- Strong title hierarchy (Title / Subtitle / Body)
- 1 core message per slide
- Body text size readable at distance (>= 20pt)
- Consistent accent color and card style
- Avoid dense full-text paragraphs

## Personalization fields (required if user asks)

Support these optional metadata fields in both report and slides:

- `author_display_name` (e.g., 작성자 이름)
- `course_name` (e.g., 수업명/세미나명)
- `affiliation` (소속)
- `date_label` (발표/제출 날짜 라벨)

When provided, render them in:

- Report: cover page + header/footer identity line
- Slides: title slide subtitle/footer area

If not provided, keep neutral placeholders.

## Output contract

### Report/PDF

Return:
- edited file list
- compile command + engine
- output PDF path
- style checklist (palette/font/section/table)
- personalization checklist (name/course/affiliation/date)

### Slides/PPT

Return:
- source file path (`.tex` or `.py/.md`)
- output slide path (`.pptx` or `.pdf`)
- slide-by-slide outline
- style checklist (hierarchy/readability/consistency)
- personalization checklist (name/course/affiliation/date)

## Resource map

- Rules: `references/format-rules.md`
- Report→slide mapping: `references/ppt-mapping.md`
- Compile helper: `scripts/compile_latex.sh`
- PPT generator helper: `scripts/build_styled_pptx.py`
- Templates: `assets/templates/*`
