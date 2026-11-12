"""Test doubles shared across test files."""

from __future__ import annotations

from app.llm.base import BaseLLMClient


class FakeLLM(BaseLLMClient):
    """Returns queued responses and records every request it receives."""

    def __init__(self, responses: list[str], *, max_retries: int = 2) -> None:
        super().__init__(max_retries=max_retries)
        self._responses = list(responses)
        self.calls: list[tuple[str, str]] = []  # (system, prompt) per request

    def _complete(self, *, system: str, prompt: str) -> str:
        self.calls.append((system, prompt))
        return self._responses.pop(0)