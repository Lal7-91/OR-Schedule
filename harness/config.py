from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    ollama_base_url: str
    ollama_model: str
    ollama_api_key: str
    max_iterations: int
    dry_run: bool
    request_timeout_seconds: float = 90.0
    max_response_tokens: int = 512


def load_settings() -> Settings:
    return Settings(
        ollama_base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        ollama_model=os.environ.get("OLLAMA_MODEL", "qwen2.5:7b-instruct"),
        ollama_api_key=os.environ.get("OLLAMA_API_KEY", "ollama"),
        max_iterations=int(os.environ.get("MAX_SUPERVISOR_ITERATIONS", "5")),
        dry_run=_env_bool("HARNESS_DRY_RUN", default=False),
        request_timeout_seconds=float(os.environ.get("OLLAMA_REQUEST_TIMEOUT_SECONDS", "90")),
        max_response_tokens=int(os.environ.get("OLLAMA_MAX_RESPONSE_TOKENS", "512")),
    )
