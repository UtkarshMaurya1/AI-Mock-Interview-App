"""Small builders so tests can create valid objects in one line."""

from __future__ import annotations

from app.schemas import (
    DIMENSIONS,
    Difficulty,
    DimensionScore,
    Evaluation,
    GeneratedQuestion,
    InterviewPlan,
    InterviewState,
    Level,
    Topic,
    TopicSource,
    Turn,
)


def make_eval(score: int = 3, *, needs_followup: bool = False, **per_dimension: int) -> Evaluation:
    """Every dimension gets `score`; override single dimensions with keyword arguments."""
    unknown = set(per_dimension) - set(DIMENSIONS)
    if unknown:
        raise ValueError(f"unknown dimensions: {unknown}")
    dims = {
        name: DimensionScore(score=per_dimension.get(name, score), justification="test")
        for name in DIMENSIONS
    }
    return Evaluation(
        **dims,
        needs_followup=needs_followup,
        ideal_answer_sketch="test sketch",
    )


def make_question(
    topic: str = "Python",
    difficulty: Difficulty = Difficulty.MEDIUM,
    is_followup: bool = False,
) -> GeneratedQuestion:
    return GeneratedQuestion(
        text=f"Question about {topic}",
        topic=topic,
        difficulty=difficulty,
        is_followup=is_followup,
        probes=["something"],
        based_on="resume",
    )


def make_turn(
    topic: str = "Python",
    score: int = 3,
    *,
    needs_followup: bool = False,
    evaluated: bool = True,
) -> Turn:
    return Turn(
        question=make_question(topic),
        answer_text="an answer",
        evaluation=make_eval(score, needs_followup=needs_followup) if evaluated else None,
    )


def make_topic(
    name: str = "Python",
    *,
    max_questions: int = 3,
    start_difficulty: Difficulty = Difficulty.MEDIUM,
) -> Topic:
    return Topic(
        name=name,
        source=TopicSource.BOTH,
        evidence="evidence",
        priority=3,
        start_difficulty=start_difficulty,
        max_questions=max_questions,
    )


def make_state(
    *,
    topics: list[Topic] | None = None,
    turns: list[Turn] | None = None,
    topic_idx: int = 0,
    difficulty: Difficulty = Difficulty.MEDIUM,
    followups: int = 0,
    turn_budget: int = 8,
) -> InterviewState:
    plan = InterviewPlan(
        role="Python Engineer",
        level=Level.MID,
        topics=topics or [make_topic("Python"), make_topic("SQL")],
        turn_budget=turn_budget,
    )
    return InterviewState(
        plan=plan,
        turns=turns or [],
        current_topic_idx=topic_idx,
        current_difficulty=difficulty,
        followups_on_current_topic=followups,
    )