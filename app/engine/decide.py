"""Deterministic interview routing.

The LLM only emits signals (an `Evaluation`). This module decides what to do with them,
using plain Python so every rule is unit-testable without a model.

Conventions:
- `state.turns` already includes the turn that was just answered and evaluated.
- `state.plan.topics` is already in interview order (the planner sorts by priority).
"""

from __future__ import annotations

from app.config import DEFAULT_ROUTING, RoutingRules
from app.evaluation.scoring import overall_score
from app.schemas import Action, Decision, Difficulty, InterviewState, SessionStatus

_LEVELS = (Difficulty.EASY, Difficulty.MEDIUM, Difficulty.HARD)


def _shift(difficulty: Difficulty, step: int) -> Difficulty:
    """Move one level up (+1) or down (-1), clamped to easy..hard."""
    index = _LEVELS.index(difficulty) + step
    return _LEVELS[max(0, min(index, len(_LEVELS) - 1))]


def _adjusted_difficulty(current: Difficulty, overall: float, rules: RoutingRules) -> Difficulty:
    if overall >= rules.strong_threshold:
        return _shift(current, +1)
    if overall <= rules.weak_threshold:
        return _shift(current, -1)
    return current


def _same_topic(a: str, b: str) -> bool:
    return a.strip().lower() == b.strip().lower()


def decide(state: InterviewState, rules: RoutingRules = DEFAULT_ROUTING) -> Decision:
    if not state.turns:
        raise ValueError("decide() needs at least one answered turn")
    evaluation = state.turns[-1].evaluation
    if evaluation is None:
        raise ValueError("decide() needs the latest turn to be evaluated")

    overall = overall_score(evaluation)
    difficulty = _adjusted_difficulty(state.current_difficulty, overall, rules)

    topics = state.plan.topics
    topic = topics[state.current_topic_idx]
    asked_on_topic = sum(1 for t in state.turns if _same_topic(t.question.topic, topic.name))
    topic_has_room = asked_on_topic < topic.max_questions

    # 1. Question budget used up.
    if len(state.turns) >= state.plan.turn_budget:
        return Decision(action=Action.END, difficulty=difficulty, reason="question budget used up")

    # 2. The answer left gaps worth probing, and the topic still has room.
    if (
        evaluation.needs_followup
        and state.followups_on_current_topic < rules.max_followups_per_topic
        and topic_has_room
    ):
        return Decision(
            action=Action.FOLLOW_UP,
            difficulty=difficulty,
            reason=f"answer left gaps (overall {overall}); following up on '{topic.name}'",
        )

    # 3. Strong answer and room left: ask something harder on the same topic.
    if overall >= rules.strong_threshold and topic_has_room:
        return Decision(
            action=Action.DEEPEN,
            difficulty=difficulty,
            reason=f"strong answer (overall {overall}); going deeper on '{topic.name}'",
        )

    # 4. Move on, or finish if this was the last topic.
    next_index = state.current_topic_idx + 1
    if next_index >= len(topics):
        return Decision(action=Action.END, difficulty=difficulty, reason="all topics covered")

    next_topic = topics[next_index]
    return Decision(
        action=Action.NEXT_TOPIC,
        difficulty=next_topic.start_difficulty,
        reason=f"done with '{topic.name}'; moving to '{next_topic.name}'",
    )


def apply_decision(state: InterviewState, decision: Decision) -> InterviewState:
    """Return a new state with the decision applied. Never mutates the input."""
    updates: dict = {"current_difficulty": decision.difficulty}

    if decision.action is Action.FOLLOW_UP:
        updates["followups_on_current_topic"] = state.followups_on_current_topic + 1
    elif decision.action is Action.NEXT_TOPIC:
        updates["current_topic_idx"] = state.current_topic_idx + 1
        updates["followups_on_current_topic"] = 0
    elif decision.action is Action.END:
        updates["status"] = SessionStatus.COMPLETED

    return state.model_copy(update=updates)