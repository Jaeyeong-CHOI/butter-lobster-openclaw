from __future__ import annotations

from typing import Any

from ..prompts import SOLVER_SYSTEM, solver_user_prompt
from ..settings import AgentSettings
from .base import AgentPrompt, BaseAgent


class SolverAgent(BaseAgent):
    """Agent B: generates JSON-AST programs for a candidate language."""

    def prompt(
        self,
        language_spec: dict[str, Any],
        task: dict[str, Any],
        solver_model: dict[str, Any] | None = None,
    ) -> AgentPrompt:
        settings = dict(self.settings.to_dict())
        if solver_model:
            settings.update({k: v for k, v in solver_model.items() if k in settings})
        return AgentPrompt(
            system=SOLVER_SYSTEM,
            user=solver_user_prompt(language_spec, task, solver_model),
            settings=settings,
        )
