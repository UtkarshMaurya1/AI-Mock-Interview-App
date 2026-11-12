"""Planner: turns the candidate's resume/JD into an InterviewPlan.

The LLM drafts the role, level and topics. Python then enforces everything that should be
deterministic: topic order, de-duplication, topic count and the question budget.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.engine.ingestion import InterviewSource
from app.llm.base import BaseLLMClient
from app.prompts import render_prompt, wrap_untrusted
from app.schemas import InterviewPlan, Level, Topic


@dataclass(frozen=True)
class PlanningRules:
    turn_budget: int = 10  # total questions in a session, follow-ups included
    max_topics: int = 5


DEFAULT_PLANNING = PlanningRules()


class PlanDraft(BaseModel):
    """What the LLM is asked for. It never chooses the budget; Python does."""

    role: str = Field(min_length=1)
    level: Level
    topics: list[Topic] = Field(min_length=1)


def build_plan(
    draft: PlanDraft,
    *,
    level: Level | None = None,
    rules: PlanningRules = DEFAULT_PLANNING,
) -> InterviewPlan:
    """Turn the LLM's draft into the final plan (pure Python, no LLM)."""
    # Highest priority first. sorted() is stable, so ties keep the LLM's own order.
    ranked = sorted(draft.topics, key=lambda topic: -topic.priority)

    seen: set[str] = set()
    unique: list[Topic] = []
    for topic in ranked:
        key = topic.name.strip().lower()
        if key not in seen:
            seen.add(key)
            unique.append(topic)

    return InterviewPlan(
        role=draft.role,
        level=level or draft.level,
        topics=unique[: rules.max_topics],
        turn_budget=rules.turn_budget,
    )


def _user_prompt(source: InterviewSource) -> str:
    parts = []
    if source.resume_text:
        parts.append(wrap_untrusted("resume", source.resume_text))
    if source.jd_text:
        parts.append(wrap_untrusted("job_description", source.jd_text))
    parts.append("Create the interview plan.")
    return "\n\n".join(parts)


def create_plan(
    llm: BaseLLMClient,
    source: InterviewSource,
    *,
    level: Level | None = None,
    rules: PlanningRules = DEFAULT_PLANNING,
) -> InterviewPlan:
    """Ask the LLM for a draft plan from the candidate's documents, then finalize it."""
    if level is not None:
        level_instruction = f"The candidate is interviewing at {level.value} level. Use that."
    else:
        level_instruction = "Infer it from the candidate's experience and the role's seniority."

    system = render_prompt(
        "plan",
        max_topics=str(rules.max_topics),
        level_instruction=level_instruction,
    )
    draft = llm.generate_structured(
        system=system,
        prompt=_user_prompt(source),
        schema=PlanDraft,
    )
    return build_plan(draft, level=level, rules=rules)