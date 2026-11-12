from __future__ import annotations

import groq

from app.llm.base import BaseLLMClient, LLMError


class GroqClient(BaseLLMClient):
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        temperature: float = 0.0,
        timeout_s: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        super().__init__(max_retries=max_retries)
        self._client = groq.Groq(api_key=api_key, timeout=timeout_s)
        self._model = model
        self._temperature = temperature

    def _complete(self, *, system: str, prompt: str) -> str:
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                temperature=self._temperature,
                # JSON mode: guarantees syntactically valid JSON, not schema compliance.
                # Schema compliance is enforced by BaseLLMClient's validate-and-retry loop.
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            )
        except groq.GroqError as exc:
            raise LLMError(f"Groq request failed: {exc}") from exc

        content = response.choices[0].message.content
        if not content:
            raise LLMError("Groq returned an empty response")
        return content