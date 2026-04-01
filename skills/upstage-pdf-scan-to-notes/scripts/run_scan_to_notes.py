#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List

import requests


def collect_text(node: Any, bucket: List[str]) -> None:
    if isinstance(node, str):
        s = node.strip()
        if len(s) >= 20:
            bucket.append(s)
    elif isinstance(node, dict):
        for v in node.values():
            collect_text(v, bucket)
    elif isinstance(node, list):
        for v in node:
            collect_text(v, bucket)


def extract_text(payload: Any) -> str:
    chunks: List[str] = []
    collect_text(payload, chunks)
    # dedupe while preserving order
    seen = set()
    dedup = []
    for c in chunks:
        if c not in seen:
            dedup.append(c)
            seen.add(c)
    return "\n\n".join(dedup)


def call_ocr(file_path: Path, api_key: str, ocr_url: str, timeout: int) -> Dict[str, Any]:
    with file_path.open("rb") as f:
        resp = requests.post(
            ocr_url,
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (file_path.name, f, "application/pdf")},
            timeout=timeout,
        )
    resp.raise_for_status()
    return resp.json()


def call_solar_summary(text: str, api_key: str, chat_url: str, model: str, lang: str, timeout: int) -> Dict[str, Any]:
    schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "one_line": {"type": "string"},
            "summary": {"type": "string"},
            "key_points": {"type": "array", "items": {"type": "string"}},
            "terms": {"type": "array", "items": {"type": "string"}},
            "action_items": {"type": "array", "items": {"type": "string"}},
            "confidence_notes": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "title",
            "one_line",
            "summary",
            "key_points",
            "terms",
            "action_items",
            "confidence_notes",
        ],
        "additionalProperties": False,
    }

    sys_prompt = (
        "You are a document analyst. Return strict JSON only. "
        f"Write primary narrative in {lang}. "
        "Do not invent unreadable content; put uncertainty into confidence_notes."
    )
    user_prompt = (
        "Create clean structured notes from OCR text. Preserve numbers and entities.\n\n"
        + text[:24000]
    )

    payload = {
        "model": model,
        "temperature": 0.2,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "scan_notes", "schema": schema},
        },
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    resp = requests.post(
        chat_url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
    return json.loads(content)


def to_markdown(notes: Dict[str, Any]) -> str:
    lines = [
        f"# {notes.get('title','Untitled')}",
        "",
        f"**One-line:** {notes.get('one_line','-')}",
        "",
        "## Summary",
        notes.get("summary", "-"),
        "",
        "## Key Points",
    ]
    for x in notes.get("key_points", []):
        lines.append(f"- {x}")

    lines += ["", "## Terms"]
    for x in notes.get("terms", []):
        lines.append(f"- {x}")

    lines += ["", "## Action Items"]
    for x in notes.get("action_items", []):
        lines.append(f"- {x}")

    lines += ["", "## Confidence Notes"]
    for x in notes.get("confidence_notes", []):
        lines.append(f"- {x}")

    return "\n".join(lines) + "\n"


def main() -> None:
    p = argparse.ArgumentParser(description="OCR scanned PDF with Upstage and generate structured notes")
    p.add_argument("input", type=Path)
    p.add_argument("--out-dir", type=Path, default=Path("."))
    p.add_argument("--api-key", default=os.getenv("UPSTAGE_API_KEY"))
    p.add_argument("--ocr-url", default=os.getenv("UPSTAGE_OCR_URL"), help="Upstage OCR endpoint URL")
    p.add_argument("--chat-url", default="https://api.upstage.ai/v1/chat/completions")
    p.add_argument("--model", default="solar-pro2")
    p.add_argument("--lang", default="ko")
    p.add_argument("--timeout", type=int, default=120)
    args = p.parse_args()

    if not args.api_key:
        raise SystemExit("UPSTAGE_API_KEY is required")
    if not args.ocr_url:
        raise SystemExit("--ocr-url (or UPSTAGE_OCR_URL) is required")
    if not args.input.exists():
        raise SystemExit(f"Input file not found: {args.input}")

    args.out_dir.mkdir(parents=True, exist_ok=True)

    ocr = call_ocr(args.input, args.api_key, args.ocr_url, args.timeout)
    text = extract_text(ocr)
    if len(text.strip()) < 50:
        raise SystemExit("OCR output is too short. Check OCR endpoint or input quality.")

    notes = call_solar_summary(text, args.api_key, args.chat_url, args.model, args.lang, args.timeout)

    stem = args.input.stem
    json_path = args.out_dir / f"{stem}.notes.json"
    md_path = args.out_dir / f"{stem}.notes.md"

    json_path.write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(to_markdown(notes), encoding="utf-8")

    print(json.dumps({"ok": True, "json": str(json_path), "markdown": str(md_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
