# Report → PPT mapping

Use this mapping to convert a LaTeX report structure into presentation slides.

## Recommended 10-slide baseline

1. Title + authors + affiliation
2. Problem statement and motivation
3. Dataset/task setup
4. Method overview (pipeline)
5. Experimental setup
6. Main results (core metrics only)
7. Ablation/robustness highlights
8. Feedback and direction updates
9. Current direction / next steps
10. Conclusion + discussion points

## Compression/expansion rules

- For short decks (5-7 slides): merge 3+4, 5+6, and 8+9.
- For long decks (12+ slides): split results into per-dataset/per-metric slides.

## Visual policy

- Keep one message per slide.
- Prefer large tables over dense paragraphs only when readability is preserved.
- Mark unresolved figures with TODO placeholders instead of inventing numbers.
