from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
ENV_EXAMPLE_PATH = PROJECT_ROOT / ".env.example"


@dataclass(frozen=True, slots=True)
class ProviderSecret:
    provider: str
    env_var: str
    configured: bool
    masked: str | None
    source: str | None
    from_project_env_file: bool
    from_runtime_env: bool


def load_dotenv(path: str | Path = ENV_PATH, *, override: bool = False) -> dict[str, str]:
    """Load simple KEY=VALUE pairs from .env without third-party deps.

    This intentionally supports only the dotenv subset we need for local API
    keys: blank lines, comments, optional `export`, and quoted values.
    """
    path = Path(path)
    loaded: dict[str, str] = {}
    if not path.exists():
        return loaded

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue
        if override or key not in os.environ:
            os.environ[key] = value
        loaded[key] = value
    return loaded


def mask_secret(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


PROVIDER_ENV_VARS = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GOOGLE_API_KEY",
    "vllm": "VLLM_API_KEY",
}


def get_secret(env_var: str, *, load_env: bool = True) -> str | None:
    if load_env:
        load_dotenv()
    value = os.environ.get(env_var)
    return value if value else None


def get_provider_api_key(provider: str, *, load_env: bool = True) -> str | None:
    provider_key = provider.lower().strip()
    env_var = PROVIDER_ENV_VARS.get(provider_key)
    if not env_var:
        raise KeyError(f"Unknown provider: {provider}")
    return get_secret(env_var, load_env=load_env)


def provider_status(*, load_env: bool = True) -> list[ProviderSecret]:
    loaded = load_dotenv() if load_env else {}
    runtime_before_or_after = os.environ
    if load_env:
        load_dotenv()

    def _source(env_var: str) -> tuple[str | None, bool, bool]:
        from_project_env_file = bool(loaded.get(env_var))
        from_runtime_env = bool(runtime_before_or_after.get(env_var))
        source = "project .env" if from_project_env_file else ("runtime environment" if from_runtime_env else None)
        return source, from_project_env_file, from_runtime_env

    return [
        ProviderSecret(
            provider=provider,
            env_var=env_var,
            configured=bool(os.environ.get(env_var)),
            masked=mask_secret(os.environ.get(env_var)),
            source=_source(env_var)[0],
            from_project_env_file=_source(env_var)[1],
            from_runtime_env=_source(env_var)[2],
        )
        for provider, env_var in PROVIDER_ENV_VARS.items()
    ]


def provider_status_dict(*, load_env: bool = True) -> list[dict[str, Any]]:
    return [
        {
            "provider": item.provider,
            "env_var": item.env_var,
            "configured": item.configured,
            "masked": item.masked,
            "source": item.source,
            "from_project_env_file": item.from_project_env_file,
            "from_runtime_env": item.from_runtime_env,
        }
        for item in provider_status(load_env=load_env)
    ]
