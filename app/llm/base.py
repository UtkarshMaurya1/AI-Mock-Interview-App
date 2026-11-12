"""Provider-independent LLM interface with schema validation and retry.

Providers only implement `_complete` (prompt in, raw text out). The validate-and-retry
loop lives here once, so every provider behaves identically and the loop is testable
with a fake provider.
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


class LLMError(Exception):
    """Any failure talking to an LLM provider."""


class StructuredOutputError(LLMError):
    """The model never produced output that validates against the requested schema."""


def _strip_fences(text: str) -> str:
    """Remove a surrounding ```json ... ``` fence if the model added one."""
    text = text.strip()
    match = _FENCE_RE.match(text)
    return match.group(1) if match else text


class BaseLLMClient(ABC):
    def __init__(self, *, max_retries: int = 2) -> None:
        self.max_retries = max_retries

    @abstractmethod
    def _complete(self, *, system: str, prompt: str) -> str:
        """Send one request to the provider and return the raw text of the reply."""

    def generate_structured(self, *, system: str, prompt: str, schema: type[T]) -> T:
        """Ask the model for JSON matching `schema`; retry with error feedback if invalid."""
        schema_json = json.dumps(schema.model_json_schema())
        full_system = (
            f"{system}\n\n"
            "Respond with a single JSON object that matches this JSON Schema. "
            "No prose and no markdown fences.\n"
            f"{schema_json}"
        )

        current_prompt = prompt
        last_error: ValidationError | None = None

        for _attempt in range(self.max_retries + 1):
            raw = self._complete(system=full_system, prompt=current_prompt)
            try:
                return schema.model_validate_json(_strip_fences(raw))
            except ValidationError as exc:
                last_error = exc
                current_prompt = (
                    f"{prompt}\n\n"
                    "Your previous reply was invalid:\n"
                    f"{exc}\n\n"
                    "Return corrected JSON only."
                )

        raise StructuredOutputError(
            f"No valid {schema.__name__} after {self.max_retries + 1} attempts: {last_error}"
        )