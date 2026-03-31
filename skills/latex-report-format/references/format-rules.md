# Report format rules (canonical)

Apply these rules by default when drafting or editing technical reports.

## 1) Terminology and naming

- Use one canonical project/paper name throughout the document.
- Keep naming consistent across title, section headers, tables, and captions.

## 2) Visual identity preservation (important)

When a prior LaTeX house template exists, preserve these elements:

- **Palette:** `\definecolor` set and semantic usage (title/navy/accent/background)
- **Typography:** `fontspec + kotex` setup and heading/body contrast
- **Hierarchy:** section/subsection styles from `titlesec`
- **Structure:** consistent table header styling and key boxes (`tcolorbox`/similar)
- **Header/Footer:** page identity (`fancyhdr`), page number styling

If user asks to change style, apply requested override and note it explicitly.

## 3) Engine rule

- If the template uses `fontspec`, compile with **XeLaTeX**.
- Otherwise use PDFLaTeX by default.

## 4) Content policy

- Keep only core metrics requested for the report.
- Remove legacy/obsolete sections unless explicitly requested.
- Insert page break before "Current direction" section when requested.

## 5) Table quality policy

- Prioritize alignment, spacing, and line-break readability.
- Avoid cramped cells; split long text into multiline cells when needed.

## 6) Slide conversion policy

- Keep color palette and typography tone aligned with report style.
- Use one core message per slide.
- Prefer readable visuals over dense text blocks.

## 7) Identity metadata placement

If user provides identity/class metadata, place consistently:

- `author_display_name`: report cover "작성" line, slide title/subtitle, footer credit
- `course_name`: report cover and slide subtitle (or header ribbon)
- `affiliation`: report cover info table and first/last slide footer
- `date_label`: report cover date + slide footer date

Do not invent personal details. Use placeholders when absent.

## 8) Change handling

- User instruction has highest priority.
- When conflicting rules appear, follow user instruction and record override.
