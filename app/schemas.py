"""Core data contracts for the mock interview engine.

Design rules:
- LLM components return structured objects (Question, Evaluation, Plan).
- Routing decisions are made by deterministic Python, never by these models.
- Technical evaluation and voice delivery are separate objects and are never blended.
- The overall score is NOT stored here; Python computes it from the dimensions.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

class Difficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class Level(StrEnum):
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"


class TopicSource(StrEnum):
    RESUME = "resume"
    JD = "jd"
    BOTH = "both"


class SessionStatus(StrEnum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABORTED = "aborted"


# 1 = incorrect/missing, 3 = partially correct, 5 = complete and precise.
Score = Annotated[int, Field(ge=1, le=5)]

DIMENSIONS = ("correctness", "depth", "relevance", "completeness", "clarity")


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Plan (output of the `plan` node)
# ---------------------------------------------------------------------------


class Topic(BaseModel):
    name: str = Field(min_length=1)
    source: TopicSource
    # The resume line or JD requirement that justifies this topic.
    # This is what keeps questions grounded and follow-ups specific.
    evidence: str = Field(min_length=1)
    priority: int = Field(ge=1, le=5, description="5 = most important")
    start_difficulty: Difficulty = Difficulty.MEDIUM
    max_questions: int = Field(default=3, ge=1, le=6)


class InterviewPlan(BaseModel):
    role: str = Field(min_length=1)
    level: Level
    topics: list[Topic] = Field(min_length=1)
    turn_budget: int = Field(ge=1, description="Maximum number of questions in the session")

    @model_validator(mode="after")
    def _topic_names_unique(self) -> InterviewPlan:
        names = [t.name.strip().lower() for t in self.topics]
        if len(names) != len(set(names)):
            raise ValueError("topic names must be unique")
        return self


# ---------------------------------------------------------------------------
# Question (output of the `ask` node)
# ---------------------------------------------------------------------------


class GeneratedQuestion(BaseModel):
    text: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    difficulty: Difficulty
    is_followup: bool = False
    # What a good answer must demonstrate; the evaluator uses this as its checklist.
    probes: list[str] = Field(min_length=1)
    # Resume claim, JD line, or previous answer this question is based on.
    based_on: str = Field(min_length=1)


# ---------------------------------------------------------------------------
# Evaluation (output of the `evaluate` node) - technical content only
# ---------------------------------------------------------------------------


class DimensionScore(BaseModel):
    score: Score
    justification: str = Field(min_length=1, max_length=400)


class Evaluation(BaseModel):
    correctness: DimensionScore
    depth: DimensionScore
    relevance: DimensionScore
    completeness: DimensionScore
    clarity: DimensionScore

    # Signals consumed by the deterministic `decide` step.
    needs_followup: bool
    gaps: list[str] = Field(default_factory=list)
    claim_to_probe: str | None = None

    ideal_answer_sketch: str = Field(min_length=1)

    def scores(self) -> dict[str, int]:
        """Raw dimension scores, for the Python-side weighted overall."""
        return {name: getattr(self, name).score for name in DIMENSIONS}


# ---------------------------------------------------------------------------
# Voice delivery (computed in code from STT word timestamps, never by an LLM)
# ---------------------------------------------------------------------------


class VoiceMetrics(BaseModel):
    duration_s: float = Field(ge=0)
    words_per_minute: float = Field(ge=0)
    filler_count: int = Field(ge=0)
    filler_rate: float = Field(ge=0, description="Fillers per 100 words")
    long_pause_count: int = Field(ge=0)
    longest_pause_s: float = Field(ge=0)
    # STT models often drop fillers from transcripts, so counts may undercount.
    fillers_approximate: bool = True


# ---------------------------------------------------------------------------
# Turn and session state
# ---------------------------------------------------------------------------


class Turn(BaseModel):
    question: GeneratedQuestion
    answer_text: str | None = None
    # Evaluation runs in the background, so it may arrive after the answer.
    evaluation: Evaluation | None = None
    voice_metrics: VoiceMetrics | None = None
    asked_at: datetime = Field(default_factory=_utcnow)
    answered_at: datetime | None = None


class InterviewState(BaseModel):
    """LangGraph state. Pure data: all routing logic lives in the `decide` function."""

    session_id: str = Field(default_factory=lambda: uuid4().hex)
    plan: InterviewPlan
    turns: list[Turn] = Field(default_factory=list)
    current_topic_idx: int = Field(default=0, ge=0)
    current_difficulty: Difficulty = Difficulty.MEDIUM
    # Question texts already asked, used to prevent repeats.
    asked_questions: list[str] = Field(default_factory=list)
    followups_on_current_topic: int = Field(default=0, ge=0)
    status: SessionStatus = SessionStatus.PLANNED