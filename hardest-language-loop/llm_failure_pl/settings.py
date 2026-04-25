from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class AgentSettings:
    """Runtime knobs for one generative agent.

    These settings intentionally stay lightweight. Provider integration can be
    added later without changing the agent/data layout.
    """

    name: str
    role: str
    model: str = "gpt-5.5"
    provider: str = "openai-codex"
    temperature: float = 0.7
    thinking: str = "medium"
    max_output_tokens: int = 4096
    response_format: str = "json_object"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SolverModelSettings:
    """One model included in the solver benchmark pool."""

    provider: str
    model: str
    temperature: float = 0.0
    thinking: str = "medium"
    max_output_tokens: int = 4096
    response_format: str = "json_object"
    repeats: int = 1
    base_url: str | None = None
    api_key_env: str | None = None
    timeout_seconds: int = 120
    extra_body: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def default_solver_models() -> list[SolverModelSettings]:
    return [
        SolverModelSettings(provider="openai", model="gpt-5.4", temperature=0.0, thinking="medium", repeats=10),
        SolverModelSettings(provider="openai", model="gpt-4o", temperature=0.0, thinking="medium", repeats=10),
        SolverModelSettings(
            provider="vllm",
            model="gemma-4-31b-it",
            temperature=0.0,
            thinking="off",
            repeats=10,
            base_url="http://100.78.221.93:8000/v1",
            api_key_env="VLLM_API_KEY",
            timeout_seconds=120,
        ),
        SolverModelSettings(
            provider="vllm",
            model="qwen3.6-27b",
            temperature=0.0,
            thinking="off",
            repeats=10,
            base_url="http://100.78.221.93:8001/v1",
            api_key_env="VLLM_API_KEY",
            timeout_seconds=120,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        ),
    ]


@dataclass(slots=True)
class RunSettings:
    """Default settings for the clean-slate Python agent loop."""

    dry_run: bool = True
    seed: int = 20260424
    data_root: str = "data/runs"
    max_parallel_solver_requests: int = 8
    solver_models: list[SolverModelSettings] = field(default_factory=default_solver_models)
    language_designer: AgentSettings = field(
        default_factory=lambda: AgentSettings(
            name="language_designer",
            role="Generate candidate languages and maintain the strategy tree",
            provider="openai",
            model="gpt-5.4",
            temperature=0.8,
            thinking="extra_high",
            max_output_tokens=12000,
        )
    )
    solver: AgentSettings = field(
        default_factory=lambda: AgentSettings(
            name="solver",
            role="Solve tasks in a candidate language using JSON AST programs",
            provider="openai",
            model="gpt-5.4",
            temperature=0.0,
            thinking="medium",
        )
    )
    curator: AgentSettings = field(
        default_factory=lambda: AgentSettings(
            name="curator",
            role="Read experiment results and recommend strategy-tree edits",
            temperature=0.3,
            thinking="high",
        )
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "seed": self.seed,
            "data_root": self.data_root,
            "max_parallel_solver_requests": self.max_parallel_solver_requests,
            "solver_models": [model.to_dict() for model in self.solver_models],
            "language_designer": self.language_designer.to_dict(),
            "solver": self.solver.to_dict(),
            "curator": self.curator.to_dict(),
        }


def default_settings() -> RunSettings:
    return RunSettings()
