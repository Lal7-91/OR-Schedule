from __future__ import annotations

from harness.domain.constraints import Violation, validate_schedule
from harness.domain.models import Assignment, ProblemInstance, Schedule


class ScheduleStore:
    """Mutable per-run container pairing a static ProblemInstance with the
    Schedule being built. Created fresh for each harness run; tools close
    over a single instance of this rather than touching module globals."""

    def __init__(self, problem: ProblemInstance) -> None:
        self.problem = problem
        self.schedule = Schedule()

    def current_schedule(self) -> dict[str, dict]:
        return self.schedule.to_dict()

    def unscheduled_surgery_ids(self) -> list[str]:
        scheduled = self.schedule.scheduled_surgery_ids()
        return [s.id for s in self.problem.surgeries if s.id not in scheduled]

    def assign(self, surgery_id: str, room_id: str, start_time: str) -> dict:
        surgery = self.problem.surgery(surgery_id)
        if surgery is None:
            return {"ok": False, "reason": f"Unknown surgery_id: {surgery_id}"}

        room = self.problem.room(room_id)
        if room is None:
            return {"ok": False, "reason": f"Unknown room_id: {room_id}"}

        try:
            from harness.domain.models import to_minutes

            end_minutes = to_minutes(start_time) + surgery.duration_minutes
            end_time = f"{end_minutes // 60:02d}:{end_minutes % 60:02d}"
        except ValueError:
            return {"ok": False, "reason": f"Invalid start_time format: {start_time!r} (expected 'HH:MM')"}

        assignment = Assignment(
            surgery_id=surgery.id,
            room_id=room.id,
            surgeon_id=surgery.required_surgeon_id,
            start=start_time,
            end=end_time,
        )
        self.schedule.add(assignment)
        return {"ok": True, "reason": None}

    def unassign(self, surgery_id: str) -> dict:
        removed = self.schedule.remove(surgery_id)
        return {"ok": removed, "reason": None if removed else f"{surgery_id} was not scheduled"}

    def validate(self) -> list[Violation]:
        return validate_schedule(self.problem, self.schedule)
