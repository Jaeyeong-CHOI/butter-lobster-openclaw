# Agent Prompt Archive

Role-based prompt archive for reusable agents across research, engineering, and productivity workflows.

## Purpose
- Centralize reusable prompts for different agent roles.
- Keep prompts modular, auditable, and easy to evolve.
- Reuse shared principles while customizing role-specific behavior.

## Structure
- `prompts/shared/`: Global rules used across all agents
- `prompts/research/`: Research planning, execution, review, writing
- `prompts/engineering/`: Coding, debugging, refactoring, code review
- `prompts/productivity/`: Summarization, prioritization, planning
- `prompts/meta/`: Multi-agent orchestration
- `templates/`: Prompt authoring templates

## Recommended Usage
1. Load `prompts/shared/00_shared_principles.md` as a base system/developer prompt.
2. Load one role prompt (e.g., `prompts/research/research_planner_executor.md`) as task prompt.
3. Keep outputs in a consistent contract:
   - Objective
   - What was done
   - Evidence/artifacts
   - Risks/limits
   - Next actions

## Notes
- Do not fabricate citations, results, or metrics.
- Use human approval before external/public actions.
- Version prompt changes with clear commit messages.
