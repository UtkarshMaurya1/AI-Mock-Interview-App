"""Manual check: build an interview plan from a real resume (and optional job description).

Usage:
    python scripts/try_planner.py data/resume.pdf
    python scripts/try_planner.py data/resume.pdf --jd data/jd.txt --level senior
"""

import argparse

from app.config import ConfigError
from app.engine.ingestion import IngestionError, build_source
from app.engine.planner import create_plan
from app.llm.base import LLMError
from app.llm.factory import get_llm_client
from app.schemas import Level


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an interview plan from your documents.")
    parser.add_argument("resume", help="path to your resume (.pdf, .docx, .txt, .md)")
    parser.add_argument("--jd", help="path to a job description file")
    parser.add_argument("--level", choices=[level.value for level in Level])
    args = parser.parse_args()

    try:
        source = build_source(resume_path=args.resume, jd_path=args.jd)
        level = Level(args.level) if args.level else None
        plan = create_plan(get_llm_client(), source, level=level)
    except (ConfigError, IngestionError, LLMError) as exc:
        raise SystemExit(f"Error: {exc}") from exc

    print(f"Role: {plan.role} | Level: {plan.level} | Budget: {plan.turn_budget}\n")
    for topic in plan.topics:
        print(f"[{topic.priority}] {topic.name}")
        print(f"    source: {topic.source} | start: {topic.start_difficulty}")
        print(f"    max questions: {topic.max_questions}")
        print(f"    evidence: {topic.evidence}\n")


if __name__ == "__main__":
    main()