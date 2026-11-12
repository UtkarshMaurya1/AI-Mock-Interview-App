import pytest

from app.config import SCORE_WEIGHTS, ConfigError, Settings
from app.llm.factory import get_llm_client
from app.schemas import DIMENSIONS


def _settings(**overrides) -> Settings:
    base = {
        "llm_provider": "groq",
        "llm_model": "some-model",
        "groq_api_key": "test-key",
        "llm_temperature": 0.0,
        "llm_max_retries": 2,
        "llm_timeout_s": 30.0,
    }
    base.update(overrides)
    return Settings(**base)


def test_score_weights_sum_to_one():
    assert sum(SCORE_WEIGHTS.values()) == pytest.approx(1.0)


def test_score_weights_cover_exactly_the_rubric_dimensions():
    assert set(SCORE_WEIGHTS) == set(DIMENSIONS)


def test_factory_rejects_unknown_provider():
    with pytest.raises(ConfigError):
        get_llm_client(_settings(llm_provider="nope"))


def test_factory_requires_api_key():
    with pytest.raises(ConfigError):
        get_llm_client(_settings(groq_api_key=None))