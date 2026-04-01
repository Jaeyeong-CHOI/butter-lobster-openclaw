---
name: ppt-design-builder
description: Build presentation decks with editable PPT components (text/shapes/tables) and polished visual design. Use when asked to create or improve PPT design, convert report structure into slides, apply metadata anchors, or compose decks from selected slides-grab templates.
---

# PPT Design Builder

## Preferred mode (default)

Use fully editable PPT components (not raster images) whenever possible.

Primary script:

- `scripts/build_editable_reportstyle_pptx.py`

## Available build modes

### Mode A — Editable report-style PPT (recommended)

Use when user wants report-like style + in-PPT editability.

- script: `scripts/build_editable_reportstyle_pptx.py`

### Mode B — Template-composed slides-grab deck (HTML-first)

Use when user wants to pick and combine built-in template blocks.

- script: `scripts/build_slidesgrab_template_deck.py`
- catalog: `references/slides-grab-template-catalog.md`
- note: PPT export from slides-grab is experimental/raster-prone; source-of-truth is HTML.

### Mode C — Report-clone (image-based)

Use only when user explicitly asks for visual parity over editability.

- script: `scripts/build_report_clone_pptx.py`

## Metadata anchors (if requested)

Place consistently across slides:

- top-right: `date_label`
- bottom-left: `author_display_name`
- bottom-right: `presentation_title`

## PPT quality checklist

- cover and body layouts visually distinct
- <= 4 bullets per slide where possible
- strong hierarchy (title/subtitle/body)
- consistent palette and spacing
- avoid clipped text and overflow

## Output checklist

Return:

- source path(s)
- output PPTX path
- template/mode used
- metadata checklist (date/author/title)
- editability status (editable objects vs image-based)

## Resource map

- Slide mapping: `references/ppt-mapping.md`
- Style constraints: `references/format-rules.md`
- Template catalog: `references/slides-grab-template-catalog.md`
- Editable report-style: `scripts/build_editable_reportstyle_pptx.py`
- Styled PPT helper: `scripts/build_styled_pptx.py`
- slides-grab composer: `scripts/build_slidesgrab_template_deck.py`
- Image clone helper: `scripts/build_report_clone_pptx.py`
- Optional templates: `assets/templates/slides_beamer.tex`, `assets/templates/slides_outline.md`
