"""Application settings, loaded once from environment variables / .env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()

# Weights for the Python-computed overall technical score. Must sum to 1.0.
SCORE_WEIGHTS: dict[str, float] = {
    "correctness": 0.35,
    "depth": 0.25,
    "completeness": 0.15,
    "relevance": 0.15,
    "clarity": 0.10,
}


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    llm_provider: str
    llm_model: str
    groq_api_key: str | None
    # Temperature 0 keeps the grader as consistent as possible between runs.
    llm_temperature: float
    # Extra attempts after the first one when the output fails schema validation.
    llm_max_retries: int
    llm_timeout_s: float


@lru_cache
def get_settings() -> Settings:
    return Settings(
        llm_provider=os.getenv("LLM_PROVIDER", "groq").strip().lower(),
        llm_model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile").strip(),
        groq_api_key=os.getenv("GROQ_API_KEY") or None,
        llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0")),
        llm_max_retries=int(os.getenv("LLM_MAX_RETRIES", "2")),
        llm_timeout_s=float(os.getenv("LLM_TIMEOUT_S", "30")),
    )