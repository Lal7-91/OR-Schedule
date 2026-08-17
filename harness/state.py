from __future__ import annotations

from typing import Literal, TypedDict


class HarnessState(TypedDict):
    problem: dict
    schedule_snapshot: dict
    violations: list[dict]
    constraint_critique: str | None
    optimizer_notes: str | None
    supervisor_feedback: str | None
    iteration: int
    verdict: Literal["pending", "accepted", "max_iterations_reached"]


def make_initial_state(problem: dict) -> HarnessState:
    return HarnessState(
        problem=problem,
        schedule_snapshot={},
        violations=[],
        constraint_critique=None,
        optimizer_notes=None,
        supervisor_feedback=None,
        iteration=0,
        verdict="pending",
    )
