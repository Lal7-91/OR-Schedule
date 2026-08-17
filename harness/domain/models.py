from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator

TIME_FMT = "%H:%M"
DATE_FMT = "%Y-%m-%d"


def to_minutes(hhmm: str) -> int:
    t = datetime.strptime(hhmm, TIME_FMT)  # noqa: DTZ007 -- plain wall-clock, no timezone involved
    return t.hour * 60 + t.minute


def _validate_hhmm(value: str) -> str:
    datetime.strptime(value, TIME_FMT)  # noqa: DTZ007 -- plain wall-clock, no timezone involved
    return value


def _validate_date(value: str) -> str:
    datetime.strptime(value, DATE_FMT)  # noqa: DTZ007 -- plain calendar date, no timezone involved
    return value


def _validate_dates(values: list[str]) -> list[str]:
    for value in values:
        _validate_date(value)
    return values


class Room(BaseModel):
    id: str
    operating_start: str
    operating_end: str

    _v_start = field_validator("operating_start")(_validate_hhmm)
    _v_end = field_validator("operating_end")(_validate_hhmm)


class AvailabilityWindow(BaseModel):
    """A single date+time range a surgeon is available. If a Surgeon has no
    windows at all, they're treated as available every horizon date during
    room hours (unrestricted) -- windows are an opt-in restriction."""

    date: str
    start: str
    end: str

    _v_date = field_validator("date")(_validate_date)
    _v_start = field_validator("start")(_validate_hhmm)
    _v_end = field_validator("end")(_validate_hhmm)

    @property
    def start_minutes(self) -> int:
        return to_minutes(self.start)

    @property
    def end_minutes(self) -> int:
        return to_minutes(self.end)


class Surgeon(BaseModel):
    id: str
    availability: list[AvailabilityWindow] = []

    def is_available(self, date: str, start_minutes: int, end_minutes: int) -> bool:
        if not self.availability:
            return True  # unrestricted
        return any(
            w.date == date and w.start_minutes <= start_minutes and end_minutes <= w.end_minutes
            for w in self.availability
        )


class Surgery(BaseModel):
    id: str
    duration_minutes: int
    required_surgeon_id: str
    priority: Literal["urgent", "routine"] = "routine"


class Assignment(BaseModel):
    surgery_id: str
    room_id: str
    surgeon_id: str
    date: str
    start: str
    end: str

    _v_date = field_validator("date")(_validate_date)
    _v_start = field_validator("start")(_validate_hhmm)
    _v_end = field_validator("end")(_validate_hhmm)

    @property
    def start_minutes(self) -> int:
        return to_minutes(self.start)

    @property
    def end_minutes(self) -> int:
        return to_minutes(self.end)


class ProblemInstance(BaseModel):
    horizon: list[str]
    rooms: list[Room]
    surgeons: list[Surgeon]
    surgeries: list[Surgery]

    _v_horizon = field_validator("horizon")(_validate_dates)

    def room(self, room_id: str) -> Room | None:
        return next((r for r in self.rooms if r.id == room_id), None)

    def surgeon(self, surgeon_id: str) -> Surgeon | None:
        return next((s for s in self.surgeons if s.id == surgeon_id), None)

    def surgery(self, surgery_id: str) -> Surgery | None:
        return next((s for s in self.surgeries if s.id == surgery_id), None)


class Schedule:
    """Mutable holder of assignments for a single problem run. Not a pydantic
    model itself since it is mutated in place by tool calls (add/remove)."""

    def __init__(self, assignments: dict[str, Assignment] | None = None) -> None:
        self._assignments: dict[str, Assignment] = dict(assignments or {})

    def add(self, assignment: Assignment) -> None:
        self._assignments[assignment.surgery_id] = assignment

    def remove(self, surgery_id: str) -> bool:
        return self._assignments.pop(surgery_id, None) is not None

    def get(self, surgery_id: str) -> Assignment | None:
        return self._assignments.get(surgery_id)

    def all(self) -> list[Assignment]:
        return list(self._assignments.values())

    def scheduled_surgery_ids(self) -> set[str]:
        return set(self._assignments.keys())

    def to_dict(self) -> dict[str, dict]:
        return {a.surgery_id: a.model_dump() for a in self._assignments.values()}
