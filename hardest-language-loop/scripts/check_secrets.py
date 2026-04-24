#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from llm_failure_pl.secrets import ENV_PATH, provider_status_dict


def main() -> int:
    print(json.dumps({"env_path": str(ENV_PATH), "providers": provider_status_dict()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
