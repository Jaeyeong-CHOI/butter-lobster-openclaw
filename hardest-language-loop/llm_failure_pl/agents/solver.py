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
            allowed_solver_overrides = {
                "provider",
                "model",
                "temperature",
                "thinking",
                "max_output_tokens",
                "response_format",
                "base_url",
                "api_key_env",
                "timeout_seconds",
                "extra_body",
            }
            settings.update({k: v for k, v in solver_model.items() if k in allowed_solver_overrides and v is not None})
        return AgentPrompt(
            system=SOLVER_SYSTEM,
            user=solver_user_prompt(language_spec, task, solver_model),
            settings=settings,
        )
