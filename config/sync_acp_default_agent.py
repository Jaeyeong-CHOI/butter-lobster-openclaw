#!/usr/bin/env python3
"""Sync OpenClaw ACP default agent from the configured default model.

Rule:
- openai-codex/* -> acp.defaultAgent = "codex"
- anthropic/claude* -> acp.defaultAgent = "claude"
- otherwise keep existing defaultAgent (or fallback to "codex")

Also ensures:
- acp.allowedAgents contains ["codex", "claude"]
- channels.discord.threadBindings.spawnAcpSessions = true
"""

from __future__ import annotations

import json
from pathlib import Path

CFG = Path.home() / '.openclaw' / 'openclaw.json'


def resolve_target(model: str | None, current: str | None) -> str:
    m = (model or '').strip().lower()
    if m.startswith('openai-codex/'):
        return 'codex'
    if m.startswith('anthropic/') and 'claude' in m:
        return 'claude'
    return (current or 'codex').strip() or 'codex'


def main() -> int:
    data = json.loads(CFG.read_text())

    primary = (
        data.get('agents', {})
        .get('defaults', {})
        .get('model', {})
        .get('primary')
    )

    acp = data.setdefault('acp', {})
    old_default = acp.get('defaultAgent')
    new_default = resolve_target(primary, old_default)
    acp['defaultAgent'] = new_default

    allowed = acp.get('allowedAgents')
    if not isinstance(allowed, list):
        allowed = []

    for agent in ('codex', 'claude'):
        if agent not in allowed:
            allowed.append(agent)

    # keep order stable and unique
    seen = set()
    normalized = []
    for x in allowed:
        if isinstance(x, str) and x not in seen:
            seen.add(x)
            normalized.append(x)
    acp['allowedAgents'] = normalized

    channels = data.setdefault('channels', {})
    discord = channels.setdefault('discord', {})
    thread_bindings = discord.setdefault('threadBindings', {})
    if thread_bindings.get('enabled') is None:
        thread_bindings['enabled'] = True
    thread_bindings['spawnAcpSessions'] = True

    CFG.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

    print('primary_model:', primary)
    print('acp.defaultAgent:', old_default, '->', new_default)
    print('acp.allowedAgents:', normalized)
    print('discord.threadBindings:', thread_bindings)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
