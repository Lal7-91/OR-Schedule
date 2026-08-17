import pytest

from harness.domain.constraints import validate_schedule
from harness.domain.models import Assignment, ProblemInstance, Room, Schedule, Surgeon, Surgery


@pytest.fixture
def problem() -> ProblemInstance:
    return ProblemInstance(
        rooms=[
            Room(id="OR1", operating_start="08:00", operating_end="16:00"),
            Room(id="OR2", operating_start="08:00", operating_end="16:00"),
            Room(id="OR3", operating_start="08:00", operating_end="12:00"),
        ],
        surgeons=[Surgeon(id="SURG-A"), Surgeon(id="SURG-B")],
        surgeries=[
            Surgery(id="S1", duration_minutes=60, required_surgeon_id="SURG-A", priority="urgent"),
            Surgery(id="S2", duration_minutes=60, required_surgeon_id="SURG-B", priority="routine"),
            Surgery(id="S3", duration_minutes=90, required_surgeon_id="SURG-A", priority="routine"),
        ],
    )


def test_valid_schedule_has_no_violations(problem):
    schedule = Schedule()
    schedule.add(Assignment(surgery_id="S1", room_id="OR1", surgeon_id="SURG-A", start="08:00", end="09:00"))
    schedule.add(Assignment(surgery_id="S2", room_id="OR2", surgeon_id="SURG-B", start="08:00", end="09:00"))
    schedule.add(Assignment(surgery_id="S3", room_id="OR1", surgeon_id="SURG-A", start="09:00", end="10:30"))

    assert validate_schedule(problem, schedule) == []


def test_unscheduled_surgery_detected(problem):
    schedule = Schedule()
    schedule.add(Assignment(surgery_id="S1", room_id="OR1", surgeon_id="SURG-A", start="08:00", end="09:00"))
    # S2 and S3 are never assigned.

    violations = validate_schedule(problem, schedule)
    unscheduled = {v["surgery_id"] for v in violations if v["type"] == "unscheduled_surgery"}
    assert unscheduled == {"S2", "S3"}


def test_double_booked_room_detected(problem):
    schedule = Schedule()
    schedule.add(Assignment(surgery_id="S1", room_id="OR1", surgeon_id="SURG-A", start="08:00", end="09:00"))
    schedule.add(Assignment(surgery_id="S3", room_id="OR1", surgeon_id="SURG-A", start="08:30", end="10:00"))

    violations = validate_schedule(problem, schedule)
    types = {v["type"] for v in violations}
    assert "double_booked_room" in types
    surgery_ids_flagged = {v["surgery_id"] for v in violations if v["type"] == "double_booked_room"}
    assert surgery_ids_flagged == {"S1", "S3"}


def test_double_booked_surgeon_detected(problem):
    schedule = Schedule()
    schedule.add(Assignment(surgery_id="S1", room_id="OR1", surgeon_id="SURG-A", start="08:00", end="09:00"))
    schedule.add(Assignment(surgery_id="S3", room_id="OR2", surgeon_id="SURG-A", start="08:30", end="10:00"))

    violations = validate_schedule(problem, schedule)
    types = {v["type"] for v in violations}
    assert "double_booked_surgeon" in types


def test_outside_operating_hours_detected(problem):
    schedule = Schedule()
    # OR3 closes at 12:00; a 90-minute surgery starting at 11:00 runs until 12:30.
    schedule.add(Assignment(surgery_id="S3", room_id="OR3", surgeon_id="SURG-A", start="11:00", end="12:30"))

    violations = validate_schedule(problem, schedule)
    types = {v["type"] for v in violations}
    assert "outside_operating_hours" in types


def test_non_overlapping_same_room_is_fine(problem):
    schedule = Schedule()
    schedule.add(Assignment(surgery_id="S1", room_id="OR1", surgeon_id="SURG-A", start="08:00", end="09:00"))
    schedule.add(Assignment(surgery_id="S3", room_id="OR1", surgeon_id="SURG-A", start="09:00", end="10:30"))
    schedule.add(Assignment(surgery_id="S2", room_id="OR2", surgeon_id="SURG-B", start="08:00", end="09:00"))

    # Same room and same surgeon, but back-to-back (not overlapping) — should be valid.
    assert validate_schedule(problem, schedule) == []
