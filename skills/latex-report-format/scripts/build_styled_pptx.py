#!/usr/bin/env python3
"""Minimal styled PPTX generator helper.

Usage:
  python build_styled_pptx.py --title "My Deck" --out ./deck.pptx

This script provides a clean default style system (16:9, title hierarchy,
card-based body area). Extend per project.
"""

import argparse
from pptx import Presentation
from pptx.util import Pt
from pptx.dml.color import RGBColor


def add_title_slide(prs, title, subtitle):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = RGBColor(246, 248, 254)

    bar = s.shapes.add_shape(1, 0, 0, prs.slide_width, int(0.36 * 914400))
    bar.fill.solid(); bar.fill.fore_color.rgb = RGBColor(26, 60, 140)
    bar.line.fill.background()

    t = s.shapes.add_textbox(int(0.8 * 914400), int(1.2 * 914400), int(11.6 * 914400), int(1.5 * 914400)).text_frame
    t.clear(); p = t.paragraphs[0]
    p.text = title; p.font.size = Pt(44); p.font.bold = True; p.font.color.rgb = RGBColor(14, 32, 80)

    sub = s.shapes.add_textbox(int(0.85 * 914400), int(2.4 * 914400), int(10.5 * 914400), int(0.8 * 914400)).text_frame
    sub.clear(); q = sub.paragraphs[0]
    q.text = subtitle; q.font.size = Pt(24); q.font.color.rgb = RGBColor(72, 86, 120)


def add_bullet_slide(prs, title, bullets):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = RGBColor(250, 251, 255)

    t = s.shapes.add_textbox(int(0.7 * 914400), int(0.45 * 914400), int(12 * 914400), int(0.9 * 914400)).text_frame
    t.clear(); p = t.paragraphs[0]
    p.text = title; p.font.size = Pt(36); p.font.bold = True; p.font.color.rgb = RGBColor(14, 32, 80)

    card = s.shapes.add_shape(1, int(0.7 * 914400), int(1.5 * 914400), int(12 * 914400), int(5.4 * 914400))
    card.fill.solid(); card.fill.fore_color.rgb = RGBColor(255, 255, 255)
    card.line.color.rgb = RGBColor(220, 228, 246)

    tf = card.text_frame; tf.clear()
    for i, b in enumerate(bullets):
        bp = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        bp.text = b; bp.level = 0; bp.font.size = Pt(24); bp.font.color.rgb = RGBColor(40, 42, 52)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--title', required=True)
    ap.add_argument('--subtitle', default='Styled presentation')
    ap.add_argument('--author-display-name', default='[author_display_name]')
    ap.add_argument('--course-name', default='[course_name]')
    ap.add_argument('--affiliation', default='[affiliation]')
    ap.add_argument('--date-label', default='[date_label]')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    prs = Presentation()
    prs.slide_width = int(13.333 * 914400)
    prs.slide_height = int(7.5 * 914400)

    add_title_slide(prs, args.title, f"{args.subtitle} · {args.course_name}")
    add_bullet_slide(prs, 'Overview', [
        f"Author: {args.author_display_name}",
        f"Affiliation: {args.affiliation}",
        f"Date: {args.date_label}",
    ])
    add_bullet_slide(prs, 'Next Steps', ['Action 1', 'Action 2'])

    prs.save(args.out)
    print(args.out)


if __name__ == '__main__':
    main()
