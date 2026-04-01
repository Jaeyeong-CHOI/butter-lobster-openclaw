# PptxGenJS Editable PPTX Starter

A minimal starter project to generate **fully editable** PPTX files (text/shapes/tables) using PptxGenJS.

## Why this

- `slides-grab convert` currently exports raster-style PPTX (limited in-slide editing).
- This starter focuses on editable PowerPoint components directly.

## References

- PptxGenJS: https://github.com/gitbrent/PptxGenJS
- python-pptx: https://github.com/scanny/python-pptx
- docxtemplater: https://github.com/open-xml-templating/docxtemplater

## Usage

```bash
cd pptxgenjs-editable-template
npm install
npm run build:all
```

Generated outputs:

- `output/attention_is_all_you_need_dgist-report.pptx`
- `output/attention_is_all_you_need_minimal-light.pptx`
- `output/attention_is_all_you_need_academic-dark.pptx`

Single-theme build examples:

```bash
npm run build:dgist
npm run build:minimal
npm run build:dark
```

## Theme system

Theme tokens live in `src/themes.js`.

Current themes:

- `dgist-report`
- `minimal-light`
- `academic-dark`

To add a new theme, duplicate one entry in `THEMES` and change colors/font.

## Customize

Edit `src/build.js`:

- metadata (author/date/title)
- per-slide layout/content
- text density and spacing

The output remains editable in PowerPoint/Google Slides.
