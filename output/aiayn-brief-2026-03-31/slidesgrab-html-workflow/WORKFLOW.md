# slides-grab HTML-first workflow (editable)

이 워크플로우는 **PPT 내부 수정**이 아니라, `slide-*.html`을 원본으로 수정하는 방식이다.

## Deck 위치

- `output/aiayn-brief-2026-03-31/slidesgrab-html-workflow/slides/`

## 1) 인터랙티브 편집기 실행

```bash
slides-grab edit --slides-dir output/aiayn-brief-2026-03-31/slidesgrab-html-workflow/slides
```

## 2) 품질 검증

```bash
slides-grab validate --slides-dir output/aiayn-brief-2026-03-31/slidesgrab-html-workflow/slides --format concise
```

## 3) PDF 내보내기 (권장)

```bash
slides-grab pdf --slides-dir output/aiayn-brief-2026-03-31/slidesgrab-html-workflow/slides --output output/aiayn-brief-2026-03-31/slidesgrab-html-workflow/aiayn_slides.pdf
```

텍스트 선택 가능한 PDF가 필요하면:

```bash
slides-grab pdf --slides-dir output/aiayn-brief-2026-03-31/slidesgrab-html-workflow/slides --mode print --output output/aiayn-brief-2026-03-31/slidesgrab-html-workflow/aiayn_slides_print.pdf
```

## 4) PPTX 내보내기 (참고용)

```bash
slides-grab convert --slides-dir output/aiayn-brief-2026-03-31/slidesgrab-html-workflow/slides --output output/aiayn-brief-2026-03-31/slidesgrab-html-workflow/aiayn_slides.pptx --resolution 2160p
```

> 주의: `convert` 결과는 도구 특성상 래스터 성격이 강해서 PPT 내부 컴포넌트 수정이 제한적일 수 있음.
> 편집은 HTML에서 계속하는 것을 기본으로 권장.
