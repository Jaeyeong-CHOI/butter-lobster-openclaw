# HTML-first editing workflow (slides-grab)

이 deck은 HTML을 원본으로 계속 수정하는 용도다.

## Deck
- `output/aiayn-brief-2026-03-31/slidesgrab-html-workflow-v2/slides/`

## Edit
```bash
slides-grab edit --slides-dir output/aiayn-brief-2026-03-31/slidesgrab-html-workflow-v2/slides
```

## Export PDF
```bash
slides-grab pdf --slides-dir output/aiayn-brief-2026-03-31/slidesgrab-html-workflow-v2/slides --output output/aiayn-brief-2026-03-31/slidesgrab-html-workflow-v2/aiayn_slides.pdf
```

## Export PPTX (raster)
```bash
slides-grab convert --slides-dir output/aiayn-brief-2026-03-31/slidesgrab-html-workflow-v2/slides --output output/aiayn-brief-2026-03-31/slidesgrab-html-workflow-v2/aiayn_slides.pptx --resolution 2160p
```

> `convert`는 실험적/래스터 성격이라 PPT 내부 편집은 제한적.
> 디자인 수정은 HTML 쪽에서 계속하는 게 정석.
