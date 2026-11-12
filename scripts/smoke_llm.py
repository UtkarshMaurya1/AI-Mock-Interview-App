# Run from the project root:  python -m scripts.smoke_llm

import time

from app.llm.factory import get_llm_client
from app.schemas import Evaluation

SYSTEM = (
    "You are a strict technical interviewer grading a candidate's answer. "
    "Score each dimension from 1 to 5 (1 = incorrect or missing, 3 = partially correct, "
    "5 = complete and precise). Keep each justification to one sentence. "
    "Set needs_followup to true if the answer left important gaps."
)

PROMPT = """\
Question: Explain how Python's asyncio event loop handles many concurrent connections \
on a single thread.

A good answer should cover:
- coroutines yield control at await points
- the event loop schedules ready tasks
- non-blocking I/O with a selector (epoll/kqueue)
- blocking calls stall the whole loop

Candidate's answer:
Asyncio uses an event loop that runs coroutines. When a coroutine awaits something like \
network I/O, it gives control back to the loop so another coroutine can run. It is single \
threaded, so there are no race conditions between threads.
"""


def main() -> None:
    llm = get_llm_client()

    start = time.perf_counter()
    evaluation = llm.generate_structured(system=SYSTEM, prompt=PROMPT, schema=Evaluation)
    elapsed = time.perf_counter() - start

    print(f"OK: validated Evaluation in {elapsed:.2f}s\n")
    for name, score in evaluation.scores().items():
        print(f"  {name:<13} {score}/5  {getattr(evaluation, name).justification}")
    print(f"\n  needs_followup: {evaluation.needs_followup}")
    print(f"  gaps: {evaluation.gaps}")


if __name__ == "__main__":
    main()