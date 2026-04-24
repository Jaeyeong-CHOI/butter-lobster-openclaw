from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..settings import AgentSettings


@dataclass(slots=True)
class AgentPrompt:
    system: str
    user: str
    settings: dict[str, Any]


class BaseAgent:
    def __init__(self, settings: AgentSettings) -> None:
        self.settings = settings

    def prompt(self, *args: Any, **kwargs: Any) -> AgentPrompt:  # pragma: no cover - interface
        raise NotImplementedError

    def render(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        prompt = self.prompt(*args, **kwargs)
        return {
            "agent": self.settings.name,
            "system": prompt.system,
            "user": prompt.user,
            "settings": prompt.settings,
        }
