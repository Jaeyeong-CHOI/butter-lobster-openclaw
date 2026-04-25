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
        tree = StrategyTree.new(
            title="Open exploration of LLM-resistant programming-language semantics",
            hypothesis=(
                "Search broadly over executable toy-language semantics instead of assuming a Python-near answer. "
                "Use the strategy tree to compare semantic families, preserve diversity, and expand branches that "
                "produce reproducible solver failures."
            ),
            tags=["clean-slate", "open-search", "semantic-interference", "quality-diversity"],
        )
        root = tree.get(tree.root_id)
        root.artifacts["search_dimensions"] = {
            "surface_distance": ["python-near", "python-far", "abstract-json-ast"],
            "semantic_families": [
                "truthiness",
                "control-flow",
                "comparison",
                "arithmetic",
                "literal",
                "binding",
                "evaluation-order",
            ],
            "selection_policy": "expand both high-failure and underexplored families; do not lock onto Python-near a priori",
        }
        return tree

    def prompt(self, tree: StrategyTree, recent_results: list[dict[str, Any]] | None = None) -> AgentPrompt:
        return AgentPrompt(
            system=LANGUAGE_DESIGNER_SYSTEM,
            user=language_designer_user_prompt(tree, recent_results),
            settings=self.settings.to_dict(),
        )

    def apply_tree_ops(self, tree: StrategyTree, ops: list[dict[str, Any]]) -> list[str]:
        changed = tree.apply_ops(ops)
        return [node.id for node in changed]
