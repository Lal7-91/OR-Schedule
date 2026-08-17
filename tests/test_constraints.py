import pytest

from harness.domain.constraints import validate_schedule
from harness.domain.models import (
    Assignment,
    AvailabilityWindow,
    ProblemInstance,
    Room,
    Schedule,
    Surgeon,
    Surgery,
)

DATE = "2026-08-18"
OTHER_DATE = "2026-08-19"


@pytest.fixture
def problem() -> ProblemInstance:
    return ProblemInstance(
        horizon=[DATE, OTHER_DATE],
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


def _a(surgery_id, room_id, surgeon_id, start, end, date=DATE) -> Assignment:
    return Assignment(
        surgery_id=surgery_id, room_id=room_id, surgeon_id=surgeon_id,
        date=date, start=start, end=end,
    )


def test_valid_schedule_has_no_violations(problem):
    schedule = Schedule()
    schedule.add(_a("S1", "OR1", "SURG-A", "08:00", "09:00"))
    schedule.add(_a("S2", "OR2", "SURG-B", "08:00", "09:00"))
    schedule.add(_a("S3", "OR1", "SURG-A", "09:00", "10:30"))

    assert validate_schedule(problem, schedule) == []


def test_unscheduled_surgery_detected(problem):
    schedule = Schedule()
    schedule.add(_a("S1", "OR1", "SURG-A", "08:00", "09:00"))
    # S2 and S3 are never assigned.

    violations = validate_schedule(problem, schedule)
    unscheduled = {v["surgery_id"] for v in violations if v["type"] == "unscheduled_surgery"}
    assert unscheduled == {"S2", "S3"}


def test_double_booked_room_detected(problem):
    schedule = Schedule()
    schedule.add(_a("S1", "OR1", "SURG-A", "08:00", "09:00"))
    schedule.add(_a("S3", "OR1", "SURG-A", "08:30", "10:00"))

    violations = validate_schedule(problem, schedule)
    types = {v["type"] for v in violations}
    assert "double_booked_room" in types
    surgery_ids_flagged = {v["surgery_id"] for v in violations if v["type"] == "double_booked_room"}
    assert surgery_ids_flagged == {"S1", "S3"}


def test_double_booked_surgeon_detected(problem):
    schedule = Schedule()
    schedule.add(_a("S1", "OR1", "SURG-A", "08:00", "09:00"))
    schedule.add(_a("S3", "OR2", "SURG-A", "08:30", "10:00"))

    violations = validate_schedule(problem, schedule)
    types = {v["type"] for v in violations}
    assert "double_booked_surgeon" in types


def test_same_room_and_surgeon_different_dates_is_fine(problem):
    schedule = Schedule()
    schedule.add(_a("S1", "OR1", "SURG-A", "08:00", "09:00", date=DATE))
    schedule.add(_a("S3", "OR1", "SURG-A", "08:30", "10:00", date=OTHER_DATE))
    schedule.add(_a("S2", "OR2", "SURG-B", "08:00", "09:00", date=DATE))

    # Same room/time-of-day and same surgeon, but different dates — not a real conflict.
    assert validate_schedule(problem, schedule) == []


def test_outside_operating_hours_detected(problem):
    schedule = Schedule()
    # OR3 closes at 12:00; a 90-minute surgery starting at 11:00 runs until 12:30.
    schedule.add(_a("S3", "OR3", "SURG-A", "11:00", "12:30"))

    violations = validate_schedule(problem, schedule)
    types = {v["type"] for v in violations}
    assert "outside_operating_hours" in types


def test_date_outside_horizon_detected(problem):
    schedule = Schedule()
    schedule.add(_a("S1", "OR1", "SURG-A", "08:00", "09:00", date="2026-09-01"))

    violations = validate_schedule(problem, schedule)
    types = {v["type"] for v in violations}
    assert "date_outside_horizon" in types


def test_surgeon_unavailable_detected():
    problem = ProblemInstance(
        horizon=[DATE],
        rooms=[Room(id="OR1", operating_start="08:00", operating_end="16:00")],
        surgeons=[
            Surgeon(
                id="SURG-B",
                availability=[AvailabilityWindow(date=DATE, start="13:00", end="16:00")],
            )
        ],
        surgeries=[Surgery(id="S1", duration_minutes=60, required_surgeon_id="SURG-B")],
    )
    schedule = Schedule()
    schedule.add(_a("S1", "OR1", "SURG-B", "08:00", "09:00"))  # outside the 13:00-16:00 window

    violations = validate_schedule(problem, schedule)
    types = {v["type"] for v in violations}
    assert "surgeon_unavailable" in types


def test_non_overlapping_same_room_is_fine(problem):
    schedule = Schedule()
    schedule.add(_a("S1", "OR1", "SURG-A", "08:00", "09:00"))
    schedule.add(_a("S3", "OR1", "SURG-A", "09:00", "10:30"))
    schedule.add(_a("S2", "OR2", "SURG-B", "08:00", "09:00"))

    # Same room and same surgeon, but back-to-back (not overlapping) — should be valid.
    assert validate_schedule(problem, schedule) == []
