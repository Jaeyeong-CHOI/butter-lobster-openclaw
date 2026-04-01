#!/usr/bin/env python3
"""Build a slides-grab deck from selected built-in templates.

Features:
- choose any subset/order of slides-grab templates
- inject common metadata placeholders
- optional validate + convert to PPTX in one run

Example:
  python build_slidesgrab_template_deck.py \
    --deck-dir ./tmp/deck1 \
    --templates cover,section-divider,content,statistics,closing \
    --author-display-name "Jaeyeong CHOI" \
    --presentation-title "Attention Is All You Need Presentation" \
    --date-label 2026-04-01 \
    --convert-out ./tmp/deck1.pptx
"""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

BUILTIN_TEMPLATES = {
    "cover",
    "contents",
    "section-divider",
    "content",
    "split-layout",
    "quote",
    "statistics",
    "chart",
    "diagram",
    "diagram-tldraw",
    "timeline",
    "team",
    "closing",
}


def find_templates_dir() -> Path:
    env = os.environ.get("SLIDES_GRAB_TEMPLATES_DIR")
    candidates = []
    if env:
        candidates.append(Path(env))
    candidates.append(Path("/opt/homebrew/lib/node_modules/slides-grab/templates"))

    try:
        npm_root = subprocess.check_output(["npm", "root", "-g"], text=True).strip()
        candidates.append(Path(npm_root) / "slides-grab" / "templates")
    except Exception:
        pass

    for c in candidates:
        if c.exists() and c.is_dir() and (c / "cover.html").exists():
            return c
    raise FileNotFoundError("Could not locate slides-grab templates directory")


def overlay_meta_html(author: str, date_label: str, presentation_title: str) -> str:
    # lightweight inline footer (non-positioned) to avoid validator overflow on strict templates
    return f"""
<div style=\"margin-top:8pt;font-size:8pt;color:#8b93a6;display:flex;justify-content:space-between;\">
  <span>{author}</span><span>{date_label}</span><span>{presentation_title}</span>
</div>
""".strip()


def apply_basic_replacements(html: str, title: str, author: str, date_label: str, presentation_title: str) -> str:
    replacements = {
        "Business Deck": title,
        "Title Here": title,
        "Main Topic": title,
        "Luna Martinez": author,
        "March 2025": date_label,
        "www.yourwebsite.com": presentation_title,
        "hello@company.com": f"{author} · {presentation_title}",
    }
    for old, new in replacements.items():
        html = html.replace(old, new)
    return html


def ensure_diagram_asset(slides_dir: Path):
    assets = slides_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    svg = assets / "diagram.svg"
    if svg.exists():
        return
    svg.write_text(
        """
<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900">
  <rect width="100%" height="100%" fill="#f8f9fc"/>
  <rect x="120" y="160" width="380" height="170" rx="20" fill="#eef2ff" stroke="#c7d2fe" stroke-width="4"/>
  <text x="310" y="255" text-anchor="middle" font-family="Arial" font-size="42" fill="#1e3a8a">Input</text>
  <rect x="620" y="160" width="380" height="170" rx="20" fill="#ecfeff" stroke="#a5f3fc" stroke-width="4"/>
  <text x="810" y="255" text-anchor="middle" font-family="Arial" font-size="42" fill="#0f766e">Process</text>
  <rect x="1120" y="160" width="360" height="170" rx="20" fill="#fff7ed" stroke="#fdba74" stroke-width="4"/>
  <text x="1300" y="255" text-anchor="middle" font-family="Arial" font-size="42" fill="#9a3412">Output</text>
  <line x1="500" y1="245" x2="620" y2="245" stroke="#64748b" stroke-width="8"/>
  <line x1="1000" y1="245" x2="1120" y2="245" stroke="#64748b" stroke-width="8"/>
</svg>
""".strip(),
        encoding="utf-8",
    )


def run(cmd: list[str]):
    subprocess.check_call(cmd)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deck-dir", required=True, help="Deck root (contains slides/)")
    ap.add_argument("--templates", required=True, help="Comma-separated templates in order")
    ap.add_argument("--title", default="Attention Is All You Need")
    ap.add_argument("--author-display-name", default="Jaeyeong CHOI")
    ap.add_argument("--presentation-title", default="Attention Is All You Need Presentation")
    ap.add_argument("--date-label", default="2026-04-01")
    ap.add_argument("--inject-meta", action="store_true", help="Inject author/date/title footer into each slide HTML")
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--convert-out", help="If set, run slides-grab convert and write PPTX here")
    ap.add_argument("--resolution", default="2160p")
    args = ap.parse_args()

    template_names = [x.strip() for x in args.templates.split(",") if x.strip()]
    invalid = [t for t in template_names if t not in BUILTIN_TEMPLATES]
    if invalid:
        raise SystemExit(f"Invalid template names: {invalid}")

    templates_dir = find_templates_dir()
    deck_dir = Path(args.deck_dir)
    slides_dir = deck_dir / "slides"
    slides_dir.mkdir(parents=True, exist_ok=True)

    for i, tname in enumerate(template_names, start=1):
        html = (templates_dir / f"{tname}.html").read_text(encoding="utf-8")
        html = apply_basic_replacements(
            html,
            title=args.title,
            author=args.author_display_name,
            date_label=args.date_label,
            presentation_title=args.presentation_title,
        )
        if args.inject_meta:
            meta = overlay_meta_html(args.author_display_name, args.date_label, args.presentation_title)
            if "</body>" in html:
                html = html.replace("</body>", meta + "\n</body>")
        (slides_dir / f"slide-{i:02d}.html").write_text(html, encoding="utf-8")

    if "diagram-tldraw" in template_names:
        ensure_diagram_asset(slides_dir)

    if args.validate:
        run(["slides-grab", "validate", "--slides-dir", str(slides_dir), "--format", "concise"])

    if args.convert_out:
        run([
            "slides-grab",
            "convert",
            "--slides-dir",
            str(slides_dir),
            "--output",
            args.convert_out,
            "--resolution",
            args.resolution,
        ])

    print(f"deck ready: {deck_dir}")


if __name__ == "__main__":
    main()
