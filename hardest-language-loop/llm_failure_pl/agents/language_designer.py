from __future__ import annotations

from typing import Any

from ..prompts import LANGUAGE_DESIGNER_SYSTEM, language_designer_user_prompt
from ..settings import AgentSettings
from ..strategy_tree import StrategyTree
from .base import AgentPrompt, BaseAgent


class LanguageDesignerAgent(BaseAgent):
    """Agent A: proposes languages and edits the strategy tree."""

    def __init__(self, settings: AgentSettings) -> None:
        super().__init__(settings)

    @staticmethod
    def new_strategy_tree() -> StrategyTree:
        return StrategyTree.new(
            title="Open exploration of Python-near semantic interference",
            hypothesis=(
                "LLMs may fail when a language looks Python-like but one semantic rule quietly diverges "
                "from the Python prior."
            ),
            tags=["clean-slate", "python-near", "semantic-interference"],
        )

    def prompt(self, tree: StrategyTree, recent_results: list[dict[str, Any]] | None = None) -> AgentPrompt:
        return AgentPrompt(
            system=LANGUAGE_DESIGNER_SYSTEM,
            user=language_designer_user_prompt(tree, recent_results),
            settings=self.settings.to_dict(),
        )

    def apply_tree_ops(self, tree: StrategyTree, ops: list[dict[str, Any]]) -> list[str]:
        changed = tree.apply_ops(ops)
        return [node.id for node in changed]
