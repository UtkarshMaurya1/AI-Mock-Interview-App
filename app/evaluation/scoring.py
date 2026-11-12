"""Deterministic scoring. The LLM gives per-dimension scores; Python combines them."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from app.config import SCORE_WEIGHTS
from app.schemas import DIMENSIONS, Evaluation, Turn


def overall_score(evaluation: Evaluation, weights: dict[str, float] = SCORE_WEIGHTS) -> float:
    """Weighted average of the rubric dimensions, on the same 1-5 scale."""
    scores = evaluation.scores()
    total = sum(weights[dim] * scores[dim] for dim in DIMENSIONS)
    return round(total, 2)


def topic_scores(turns: Sequence[Turn]) -> dict[str, float]:
    """Mean overall score per topic. Turns without an evaluation are skipped."""
    by_topic: dict[str, list[float]] = defaultdict(list)
    for turn in turns:
        if turn.evaluation is not None:
            by_topic[turn.question.topic].append(overall_score(turn.evaluation))
    return {topic: round(sum(vals) / len(vals), 2) for topic, vals in by_topic.items()}


def session_score(turns: Sequence[Turn]) -> float | None:
    """Mean overall score across all evaluated turns, or None if nothing was evaluated."""
    values = [overall_score(t.evaluation) for t in turns if t.evaluation is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 2)