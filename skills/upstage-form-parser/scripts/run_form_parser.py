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
        if len(s) >= 10:
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
    seen = set()
    out = []
    for c in chunks:
        if c not in seen:
            out.append(c)
            seen.add(c)
    return "\n".join(out)


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


def call_schema_extract(text: str, schema: Dict[str, Any], api_key: str, chat_url: str, model: str, timeout: int) -> Dict[str, Any]:
    payload = {
        "model": model,
        "temperature": 0.0,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "form_fields", "schema": schema},
        },
        "messages": [
            {
                "role": "system",
                "content": "Extract fields from OCR text into the schema. If unknown, return empty string. Do not hallucinate.",
            },
            {
                "role": "user",
                "content": "OCR text:\n" + text[:28000],
            },
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


def missing_required(parsed: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
    req = schema.get("required", [])
    missing = []
    for k in req:
        v = parsed.get(k)
        if v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, list) and len(v) == 0):
            missing.append(k)
    return missing


def review_markdown(parsed: Dict[str, Any], missing: List[str]) -> str:
    lines = ["# Form Parse Review", ""]
    if missing:
        lines.append("## Missing required fields")
        for k in missing:
            lines.append(f"- {k}")
    else:
        lines.append("## Missing required fields")
        lines.append("- none")
    lines += ["", "## Notes", "- Review low-confidence OCR zones manually before final use."]
    lines += ["", "## Parsed Preview", "```json", json.dumps(parsed, ensure_ascii=False, indent=2), "```", ""]
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(description="Parse scanned forms into schema JSON using Upstage OCR + Solar")
    p.add_argument("input", type=Path)
    p.add_argument("--schema", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, default=Path("."))
    p.add_argument("--api-key", default=os.getenv("UPSTAGE_API_KEY"))
    p.add_argument("--ocr-url", default=os.getenv("UPSTAGE_OCR_URL"), help="Upstage OCR endpoint URL")
    p.add_argument("--chat-url", default="https://api.upstage.ai/v1/chat/completions")
    p.add_argument("--model", default="solar-pro2")
    p.add_argument("--timeout", type=int, default=120)
    args = p.parse_args()

    if not args.api_key:
        raise SystemExit("UPSTAGE_API_KEY is required")
    if not args.ocr_url:
        raise SystemExit("--ocr-url (or UPSTAGE_OCR_URL) is required")
    if not args.input.exists():
        raise SystemExit(f"Input file not found: {args.input}")
    if not args.schema.exists():
        raise SystemExit(f"Schema file not found: {args.schema}")

    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    args.out_dir.mkdir(parents=True, exist_ok=True)

    ocr = call_ocr(args.input, args.api_key, args.ocr_url, args.timeout)
    text = extract_text(ocr)
    if len(text.strip()) < 30:
        raise SystemExit("OCR output is too short. Check OCR endpoint or input quality.")

    parsed = call_schema_extract(text, schema, args.api_key, args.chat_url, args.model, args.timeout)
    miss = missing_required(parsed, schema)

    stem = args.input.stem
    parsed_path = args.out_dir / f"{stem}.parsed.json"
    review_path = args.out_dir / f"{stem}.review.md"

    parsed_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
    review_path.write_text(review_markdown(parsed, miss), encoding="utf-8")

    print(json.dumps({"ok": True, "parsed": str(parsed_path), "review": str(review_path), "missing_required": miss}, ensure_ascii=False))


if __name__ == "__main__":
    main()
