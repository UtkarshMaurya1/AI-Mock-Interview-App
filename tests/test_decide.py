import pytest

from app.config import RoutingRules
from app.engine.decide import apply_decision, decide
from app.schemas import Action, Decision, Difficulty, SessionStatus
from tests.factories import make_state, make_topic, make_turn


def test_requires_an_answered_turn():
    with pytest.raises(ValueError):
        decide(make_state())


def test_requires_latest_turn_to_be_evaluated():
    with pytest.raises(ValueError):
        decide(make_state(turns=[make_turn(evaluated=False)]))


def test_budget_exhausted_ends_interview():
    state = make_state(turns=[make_turn(score=3)] * 2, turn_budget=2)
    assert decide(state).action is Action.END


def test_budget_beats_followup():
    state = make_state(turns=[make_turn(needs_followup=True)] * 2, turn_budget=2)
    assert decide(state).action is Action.END


def test_followup_when_gaps_and_room():
    state = make_state(turns=[make_turn(score=3, needs_followup=True)])
    decision = decide(state)
    assert decision.action is Action.FOLLOW_UP
    assert decision.difficulty is Difficulty.MEDIUM


def test_followup_cap_moves_on():
    state = make_state(turns=[make_turn(score=3, needs_followup=True)], followups=2)
    decision = decide(state)
    assert decision.action is Action.NEXT_TOPIC


def test_followup_skipped_when_topic_is_full():
    topics = [make_topic("Python", max_questions=1), make_topic("SQL")]
    state = make_state(topics=topics, turns=[make_turn("Python", score=3, needs_followup=True)])
    assert decide(state).action is Action.NEXT_TOPIC


def test_strong_answer_deepens_and_raises_difficulty():
    state = make_state(turns=[make_turn(score=5)])
    decision = decide(state)
    assert decision.action is Action.DEEPEN
    assert decision.difficulty is Difficulty.HARD


def test_difficulty_is_capped_at_hard():
    state = make_state(turns=[make_turn(score=5)], difficulty=Difficulty.HARD)
    assert decide(state).difficulty is Difficulty.HARD


def test_strong_answer_on_full_topic_moves_on():
    topics = [make_topic("Python", max_questions=1), make_topic("SQL")]
    state = make_state(topics=topics, turns=[make_turn("Python", score=5)])
    assert decide(state).action is Action.NEXT_TOPIC


def test_weak_answer_lowers_difficulty_on_followup():
    state = make_state(turns=[make_turn(score=1, needs_followup=True)])
    decision = decide(state)
    assert decision.action is Action.FOLLOW_UP
    assert decision.difficulty is Difficulty.EASY


def test_weak_answer_without_followup_moves_on():
    state = make_state(turns=[make_turn(score=1)])
    assert decide(state).action is Action.NEXT_TOPIC


def test_difficulty_is_floored_at_easy():
    state = make_state(
        turns=[make_turn(score=1, needs_followup=True)], difficulty=Difficulty.EASY
    )
    assert decide(state).difficulty is Difficulty.EASY


def test_next_topic_resets_to_that_topics_start_difficulty():
    topics = [make_topic("Python"), make_topic("SQL", start_difficulty=Difficulty.HARD)]
    state = make_state(topics=topics, turns=[make_turn("Python", score=3)])
    decision = decide(state)
    assert decision.action is Action.NEXT_TOPIC
    assert decision.difficulty is Difficulty.HARD


def test_last_topic_done_ends_interview():
    state = make_state(turns=[make_turn("SQL", score=3)], topic_idx=1)
    assert decide(state).action is Action.END


def test_custom_rules_change_behavior():
    state = make_state(turns=[make_turn(score=3)])
    rules = RoutingRules(strong_threshold=3.0)
    assert decide(state, rules).action is Action.DEEPEN


def test_apply_followup_increments_counter():
    state = make_state(turns=[make_turn()])
    new = apply_decision(
        state, Decision(action=Action.FOLLOW_UP, difficulty=Difficulty.EASY, reason="x")
    )
    assert new.followups_on_current_topic == 1
    assert new.current_difficulty is Difficulty.EASY
    assert new.current_topic_idx == 0


def test_apply_next_topic_advances_and_resets_followups():
    state = make_state(turns=[make_turn()], followups=2)
    new = apply_decision(
        state, Decision(action=Action.NEXT_TOPIC, difficulty=Difficulty.HARD, reason="x")
    )
    assert new.current_topic_idx == 1
    assert new.followups_on_current_topic == 0
    assert new.current_difficulty is Difficulty.HARD


def test_apply_end_completes_session():
    state = make_state(turns=[make_turn()])
    new = apply_decision(
        state, Decision(action=Action.END, difficulty=Difficulty.MEDIUM, reason="x")
    )
    assert new.status is SessionStatus.COMPLETED


def test_apply_decision_does_not_mutate_input():
    state = make_state(turns=[make_turn()])
    apply_decision(
        state, Decision(action=Action.NEXT_TOPIC, difficulty=Difficulty.HARD, reason="x")
    )
    assert state.current_topic_idx == 0
    assert state.status is SessionStatus.PLANNED