---
name: latex-report-writer
description: Write and style technical reports in LaTeX and export polished PDF outputs. Use when asked to draft/edit a report in report-style format, preserve color/font/section/table design tokens from an existing LaTeX template, or compile .tex to final PDF.
---

# LaTeX Report Writer

## Core workflow

1. Read `references/format-rules.md` first.
2. If the user has a prior template, preserve its style tokens (colors/fonts/section/table styles).
3. If no template is provided, start from `assets/templates/report_template.tex`.
4. Fill content while preserving visual hierarchy and readability.
5. Compile using `scripts/compile_latex.sh <path/to/main.tex>`.

## Metadata fields (when requested)

Support these fields in report cover/header identity:

- `author_display_name`
- `course_name`
- `affiliation`
- `date_label`

Use placeholders if missing; do not invent personal details.

## Output checklist

Return:

- edited file list
- compile command and engine used
- output PDF path
- style checklist (palette/font/section/table preserved)
- metadata checklist (name/course/affiliation/date)

## Resource map

- Rules: `references/format-rules.md`
- Template links: `references/template-links.md`
- Compile script: `scripts/compile_latex.sh`
- Base template: `assets/templates/report_template.tex`
