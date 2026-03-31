# butter-lobster-openclaw

![Butter Lobster OpenClaw mascot](assets/butter-lobster-openclaw-v6.png)

A reusable **public OpenClaw starter kit** with practical prompts, workflow rules, and a sample skill.

> Korean version: [README.ko.md](README.ko.md)

---

## Why this repo

- Start a new OpenClaw setup quickly
- Reuse prompt/rules markdown files safely
- Adapt the workspace for personal or team use

---

## Quick start

```bash
git clone <your-repo-url>
cd butter-lobster-openclaw
mkdir -p ~/.openclaw
cp starter/openclaw.sample.json ~/.openclaw/openclaw.json
```

Then fill your tokens/channel settings in `~/.openclaw/openclaw.json`.

Start gateway:

```bash
openclaw gateway start
openclaw gateway status
```

---

## What’s included

- Core prompt/rules markdown
  - `AGENTS.md`, `SOUL.md`, `HEARTBEAT.md`, `docs/*`
- Reusable prompt templates
  - `agent-prompts/*`
- Example skill (report + slides format)
  - `skills/latex-report-format/*`
  - packaged file: `skills/dist/latex-report-format.skill`
- ACP default-agent sync utility
  - `config/sync_acp_default_agent.py`
- Starter config
  - `starter/openclaw.sample.json`

---

## Customization points

- Assistant tone/identity: `SOUL.md`
- Execution rules: `AGENTS.md`
- Recurring checks: `HEARTBEAT.md`
- Formatting skill: `skills/latex-report-format/`
- Model-based ACP routing sync: `config/sync_acp_default_agent.py`

---

## Open-source basics

- License: [MIT](LICENSE)
- Contributing guide: [CONTRIBUTING.md](CONTRIBUTING.md)
- Code of Conduct: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- Security policy: [SECURITY.md](SECURITY.md)

---

## Notes

- Never commit real secrets/tokens.
- Keep a separate private workspace for personal memories and sensitive files.
