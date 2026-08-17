"""Deterministic, LLM-free hard-constraint checks for a Schedule.

This module is intentionally pure Python with no framework/LLM dependency —
it is the single source of truth for whether a schedule is valid. Agents
call into it via a tool wrapper (see tools.py) but never get to override
its verdict.
"""
from __future__ import annotations

from itertools import combinations
from typing import TypedDict

from harness.domain.models import Assignment, ProblemInstance, Schedule, to_minutes


class Violation(TypedDict):
    type: str
    surgery_id: str
    message: str


def _overlaps(a: Assignment, b: Assignment) -> bool:
    return (
        a.date == b.date
        and a.start_minutes < b.end_minutes
        and b.start_minutes < a.end_minutes
    )


def _check_double_booked_rooms(assignments: list[Assignment]) -> list[Violation]:
    violations: list[Violation] = []
    for a, b in combinations(assignments, 2):
        if a.room_id == b.room_id and _overlaps(a, b):
            violations.append(
                Violation(
                    type="double_booked_room",
                    surgery_id=a.surgery_id,
                    message=(
                        f"Surgery {a.surgery_id} ({a.date} {a.start}-{a.end}) overlaps surgery "
                        f"{b.surgery_id} ({b.date} {b.start}-{b.end}) in room {a.room_id}."
                    ),
                )
            )
            violations.append(
                Violation(
                    type="double_booked_room",
                    surgery_id=b.surgery_id,
                    message=(
                        f"Surgery {b.surgery_id} ({b.date} {b.start}-{b.end}) overlaps surgery "
                        f"{a.surgery_id} ({a.date} {a.start}-{a.end}) in room {b.room_id}."
                    ),
                )
            )
    return violations


def _check_double_booked_surgeons(assignments: list[Assignment]) -> list[Violation]:
    violations: list[Violation] = []
    for a, b in combinations(assignments, 2):
        if a.surgeon_id == b.surgeon_id and _overlaps(a, b):
            violations.append(
                Violation(
                    type="double_booked_surgeon",
                    surgery_id=a.surgery_id,
                    message=(
                        f"Surgeon {a.surgeon_id} is double-booked: surgery {a.surgery_id} "
                        f"({a.date} {a.start}-{a.end}) overlaps surgery {b.surgery_id} "
                        f"({b.date} {b.start}-{b.end})."
                    ),
                )
            )
            violations.append(
                Violation(
                    type="double_booked_surgeon",
                    surgery_id=b.surgery_id,
                    message=(
                        f"Surgeon {b.surgeon_id} is double-booked: surgery {b.surgery_id} "
                        f"({b.date} {b.start}-{b.end}) overlaps surgery {a.surgery_id} "
                        f"({a.date} {a.start}-{a.end})."
                    ),
                )
            )
    return violations


def _check_operating_hours(
    assignments: list[Assignment], problem: ProblemInstance
) -> list[Violation]:
    violations: list[Violation] = []
    for a in assignments:
        room = problem.room(a.room_id)
        if room is None:
            violations.append(
                Violation(
                    type="unknown_room",
                    surgery_id=a.surgery_id,
                    message=f"Surgery {a.surgery_id} is assigned to unknown room {a.room_id}.",
                )
            )
            continue
        room_start = to_minutes(room.operating_start)
        room_end = to_minutes(room.operating_end)
        if a.start_minutes < room_start or a.end_minutes > room_end:
            violations.append(
                Violation(
                    type="outside_operating_hours",
                    surgery_id=a.surgery_id,
                    message=(
                        f"Surgery {a.surgery_id} ({a.start}-{a.end}) falls outside room "
                        f"{room.id}'s operating hours ({room.operating_start}-{room.operating_end})."
                    ),
                )
            )
    return violations


def _check_within_horizon(
    assignments: list[Assignment], problem: ProblemInstance
) -> list[Violation]:
    violations: list[Violation] = []
    for a in assignments:
        if a.date not in problem.horizon:
            violations.append(
                Violation(
                    type="date_outside_horizon",
                    surgery_id=a.surgery_id,
                    message=(
                        f"Surgery {a.surgery_id} is scheduled on {a.date}, which is outside "
                        f"the scheduling horizon: {problem.horizon}."
                    ),
                )
            )
    return violations


def _check_surgeon_availability(
    assignments: list[Assignment], problem: ProblemInstance
) -> list[Violation]:
    violations: list[Violation] = []
    for a in assignments:
        surgeon = problem.surgeon(a.surgeon_id)
        if surgeon is None:
            violations.append(
                Violation(
                    type="unknown_surgeon",
                    surgery_id=a.surgery_id,
                    message=f"Surgery {a.surgery_id} is assigned to unknown surgeon {a.surgeon_id}.",
                )
            )
            continue
        if not surgeon.is_available(a.date, a.start_minutes, a.end_minutes):
            violations.append(
                Violation(
                    type="surgeon_unavailable",
                    surgery_id=a.surgery_id,
                    message=(
                        f"Surgeon {a.surgeon_id} is not available on {a.date} "
                        f"{a.start}-{a.end} for surgery {a.surgery_id}."
                    ),
                )
            )
    return violations


def _check_all_surgeries_scheduled(
    schedule: Schedule, problem: ProblemInstance
) -> list[Violation]:
    scheduled = schedule.scheduled_surgery_ids()
    return [
        Violation(
            type="unscheduled_surgery",
            surgery_id=s.id,
            message=f"Surgery {s.id} has not been assigned a room/date/time yet.",
        )
        for s in problem.surgeries
        if s.id not in scheduled
    ]


def validate_schedule(problem: ProblemInstance, schedule: Schedule) -> list[Violation]:
    assignments = schedule.all()
    violations: list[Violation] = []
    violations += _check_double_booked_rooms(assignments)
    violations += _check_double_booked_surgeons(assignments)
    violations += _check_operating_hours(assignments, problem)
    violations += _check_within_horizon(assignments, problem)
    violations += _check_surgeon_availability(assignments, problem)
    violations += _check_all_surgeries_scheduled(schedule, problem)
    return violations
