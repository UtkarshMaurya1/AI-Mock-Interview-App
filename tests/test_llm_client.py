import pytest
from pydantic import BaseModel

from app.llm.base import BaseLLMClient, StructuredOutputError


class Pong(BaseModel):
    reply: str
    count: int


class FakeLLM(BaseLLMClient):
    """Returns queued responses and records every request it receives."""

    def __init__(self, responses: list[str], *, max_retries: int = 2) -> None:
        super().__init__(max_retries=max_retries)
        self._responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    def _complete(self, *, system: str, prompt: str) -> str:
        self.calls.append((system, prompt))
        return self._responses.pop(0)


GOOD = '{"reply": "pong", "count": 1}'


def test_valid_output_returned_on_first_attempt():
    llm = FakeLLM([GOOD])
    result = llm.generate_structured(system="s", prompt="p", schema=Pong)
    assert result == Pong(reply="pong", count=1)
    assert len(llm.calls) == 1


def test_markdown_fences_are_stripped():
    llm = FakeLLM([f"```json\n{GOOD}\n```"])
    result = llm.generate_structured(system="s", prompt="p", schema=Pong)
    assert result.reply == "pong"


def test_schema_is_included_in_system_prompt():
    llm = FakeLLM([GOOD])
    llm.generate_structured(system="be nice", prompt="p", schema=Pong)
    system_sent, _ = llm.calls[0]
    assert "be nice" in system_sent
    assert '"reply"' in system_sent and '"count"' in system_sent


def test_retries_after_invalid_json_then_succeeds():
    llm = FakeLLM(["not json at all", GOOD])
    result = llm.generate_structured(system="s", prompt="p", schema=Pong)
    assert result.count == 1
    assert len(llm.calls) == 2


def test_retry_prompt_contains_error_feedback():
    llm = FakeLLM(['{"reply": "pong"}', GOOD])  # missing "count"
    llm.generate_structured(system="s", prompt="original question", schema=Pong)
    _, retry_prompt = llm.calls[1]
    assert "original question" in retry_prompt
    assert "previous reply was invalid" in retry_prompt
    assert "count" in retry_prompt


def test_raises_after_exhausting_retries():
    llm = FakeLLM(["bad", "bad", "bad"], max_retries=2)
    with pytest.raises(StructuredOutputError):
        llm.generate_structured(system="s", prompt="p", schema=Pong)
    assert len(llm.calls) == 3  # first attempt + 2 retries


def test_zero_retries_means_single_attempt():
    llm = FakeLLM(["bad"], max_retries=0)
    with pytest.raises(StructuredOutputError):
        llm.generate_structured(system="s", prompt="p", schema=Pong)
    assert len(llm.calls) == 1