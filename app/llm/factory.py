"""Builds the configured LLM client. The only place that knows which providers exist."""

from __future__ import annotations

from app.config import ConfigError, Settings, get_settings
from app.llm.base import BaseLLMClient


def get_llm_client(settings: Settings | None = None) -> BaseLLMClient:
    settings = settings or get_settings()

    if settings.llm_provider == "groq":
        if not settings.groq_api_key:
            raise ConfigError("GROQ_API_KEY is not set. Add it to your .env file.")
        # Imported here so code and tests that never use Groq don't need the SDK installed.
        from app.llm.groq_client import GroqClient

        return GroqClient(
            api_key=settings.groq_api_key,
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            timeout_s=settings.llm_timeout_s,
            max_retries=settings.llm_max_retries,
        )

    raise ConfigError(f"Unknown LLM_PROVIDER: {settings.llm_provider!r}")