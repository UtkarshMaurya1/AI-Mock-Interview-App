import pytest
from pydantic import ValidationError

from app.schemas import (
    Difficulty,
    DimensionScore,
    Evaluation,
    InterviewPlan,
    InterviewState,
    Level,
    SessionStatus,
    Topic,
    TopicSource,
    VoiceMetrics,
)


def _dim(score: int = 3) -> DimensionScore:
    return DimensionScore(score=score, justification="ok")


def _topic(name: str = "Python async") -> Topic:
    return Topic(name=name, source=TopicSource.BOTH, evidence="Built async scrapers", priority=4)


def _plan(*topics: Topic) -> InterviewPlan:
    return InterviewPlan(
        role="Python Engineer",
        level=Level.MID,
        topics=list(topics) or [_topic()],
        turn_budget=8,
    )


def _evaluation() -> Evaluation:
    return Evaluation(
        correctness=_dim(4),
        depth=_dim(3),
        relevance=_dim(5),
        completeness=_dim(2),
        clarity=_dim(4),
        needs_followup=True,
        gaps=["no mention of backpressure"],
        claim_to_probe=None,
        ideal_answer_sketch="Explain event loop, tasks, and backpressure.",
    )


@pytest.mark.parametrize("bad", [0, 6, -1])
def test_score_out_of_range_rejected(bad):
    with pytest.raises(ValidationError):
        DimensionScore(score=bad, justification="x")


def test_evaluation_roundtrip_and_scores():
    ev = _evaluation()
    restored = Evaluation.model_validate_json(ev.model_dump_json())
    assert restored == ev
    assert restored.scores() == {
        "correctness": 4,
        "depth": 3,
        "relevance": 5,
        "completeness": 2,
        "clarity": 4,
    }


def test_evaluation_missing_dimension_rejected():
    data = _evaluation().model_dump()
    del data["clarity"]
    with pytest.raises(ValidationError):
        Evaluation.model_validate(data)


def test_duplicate_topic_names_rejected():
    with pytest.raises(ValidationError):
        _plan(_topic("Docker"), _topic("docker"))


def test_plan_requires_topics():
    with pytest.raises(ValidationError):
        InterviewPlan(role="x", level=Level.JUNIOR, topics=[], turn_budget=5)


def test_state_defaults():
    state = InterviewState(plan=_plan())
    assert state.status == SessionStatus.PLANNED
    assert state.current_difficulty == Difficulty.MEDIUM
    assert state.turns == []
    assert len(state.session_id) == 32


def test_voice_metrics_rejects_negative():
    with pytest.raises(ValidationError):
        VoiceMetrics(
            duration_s=-1,
            words_per_minute=120,
            filler_count=0,
            filler_rate=0,
            long_pause_count=0,
            longest_pause_s=0,
        )