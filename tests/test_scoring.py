import pytest

from app.evaluation.scoring import overall_score, session_score, topic_scores
from tests.factories import make_eval, make_turn


@pytest.mark.parametrize("score", [1, 3, 5])
def test_uniform_scores_give_same_overall(score):
    assert overall_score(make_eval(score)) == float(score)


def test_weights_are_applied():
    # correctness has weight 0.35: 0.35 * 5 + 0.65 * 1 = 2.4
    assert overall_score(make_eval(1, correctness=5)) == pytest.approx(2.4)


def test_topic_scores_average_per_topic():
    turns = [
        make_turn("Python", score=5),
        make_turn("Python", score=3),
        make_turn("SQL", score=2),
    ]
    assert topic_scores(turns) == {"Python": 4.0, "SQL": 2.0}


def test_unevaluated_turns_are_skipped():
    turns = [make_turn("Python", score=4), make_turn("Python", evaluated=False)]
    assert topic_scores(turns) == {"Python": 4.0}
    assert session_score(turns) == 4.0


def test_session_score_is_none_without_evaluations():
    assert session_score([]) is None
    assert session_score([make_turn(evaluated=False)]) is None