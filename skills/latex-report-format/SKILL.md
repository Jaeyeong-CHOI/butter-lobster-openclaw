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
   - `assets/templates/slides_outline.md` + `scripts/build_styled_pptx.py` (PPTX path), or
   - `scripts/build_report_clone_pptx.py` when user wants report style copied 1:1 as slide images, or
   - `scripts/build_editable_reportstyle_pptx.py` when user wants report-like style with fully editable PPT objects, or
   - `scripts/build_slidesgrab_template_deck.py` when user wants to compose PPT from selected `slides-grab` templates.
5. Compile with `scripts/compile_latex.sh <path/to/main.tex>`.
6. Return artifact paths + style checklist.

## Non-negotiable style constraints

- Preserve design tokens (color/font/hierarchy) unless user explicitly overrides.
- For PPT, replicate report template look-and-feel as closely as practical (palette, header/footer rhythm, boxed grouping).
- Do not downgrade to plain default PPT/LaTeX style.
- Prioritize readability: spacing, contrast, clear visual hierarchy.

## PPT quality checklist (required)

- 16:9 canvas with consistent margins
- Strong title hierarchy (Title / Subtitle / Body)
- **Cover slide and body slides must use different layouts** (cover: hero-focused, body: content-focused)
- 1 core message per slide
- Body text size readable at distance (>= 20pt)
- Consistent accent color and card style
- Avoid dense full-text paragraphs
- Prefer <=4 bullets per slide
- Preserve report template design language as much as practical (palette, section markers, box style, header/footer rhythm)
- Metadata placement fixed when requested:
  - **Top-right**: `date_label`
  - **Bottom-left**: `author_display_name`
  - **Bottom-right**: `presentation_title`

## Personalization fields (required if user asks)

Support these optional metadata fields in both report and slides:

- `author_display_name` (e.g., 작성자 이름)
- `presentation_title` (발표 제목)
- `course_name` (e.g., 수업명/세미나명)
- `affiliation` (소속)
- `date_label` (발표/제출 날짜 라벨)

When provided, render them in:

- Report: cover page + header/footer identity line
- Slides: metadata anchors (top-right date, bottom-left author, bottom-right presentation title)

If not provided, keep neutral placeholders.

## slides-grab template mode

When user asks to pick from multiple templates (e.g., "13개 중 필요한 것만 골라"), use:

```bash
python scripts/build_slidesgrab_template_deck.py \
  --deck-dir <deck_dir> \
  --templates cover,section-divider,content,statistics,closing \
  --title "<title>" \
  --author-display-name "<author>" \
  --presentation-title "<presentation_title>" \
  --date-label "<yyyy-mm-dd>" \
  --convert-out <output.pptx>
```

Template list/reference: `references/slides-grab-template-catalog.md`

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
- slides-grab template catalog: `references/slides-grab-template-catalog.md`
- Compile helper: `scripts/compile_latex.sh`
- PPT generator helper: `scripts/build_styled_pptx.py`
- Report-clone PPT helper (image-based): `scripts/build_report_clone_pptx.py`
- Report-style editable PPT helper: `scripts/build_editable_reportstyle_pptx.py`
- slides-grab deck builder: `scripts/build_slidesgrab_template_deck.py`
- Templates: `assets/templates/*`
