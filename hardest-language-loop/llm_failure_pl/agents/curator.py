from __future__ import annotations

from typing import Any

from ..prompts import CURATOR_SYSTEM, curator_user_prompt
from ..settings import AgentSettings
from ..strategy_tree import StrategyTree
from .base import AgentPrompt, BaseAgent


class CuratorAgent(BaseAgent):
    """Agent C: converts experiment results into strategy-tree edits."""

    def prompt(self, tree: StrategyTree, evaluation_results: list[dict[str, Any]]) -> AgentPrompt:
        return AgentPrompt(
            system=CURATOR_SYSTEM,
            user=curator_user_prompt(tree, evaluation_results),
            settings=self.settings.to_dict(),
        )
