import pytest

from harness.domain.models import (
    Assignment,
    AvailabilityWindow,
    Room,
    Schedule,
    Surgeon,
    Surgery,
    to_minutes,
)


def test_to_minutes():
    assert to_minutes("00:00") == 0
    assert to_minutes("08:30") == 8 * 60 + 30
    assert to_minutes("23:59") == 23 * 60 + 59


def test_room_rejects_bad_time_format():
    with pytest.raises(ValueError):
        Room(id="OR1", operating_start="8am", operating_end="16:00")


def test_surgery_defaults_priority_routine():
    s = Surgery(id="S1", duration_minutes=30, required_surgeon_id="SURG-A")
    assert s.priority == "routine"


def test_assignment_rejects_bad_date_format():
    with pytest.raises(ValueError):
        Assignment(
            surgery_id="S1", room_id="OR1", surgeon_id="SURG-A",
            date="18-08-2026", start="08:00", end="09:00",
        )


def test_assignment_minutes_properties():
    a = Assignment(
        surgery_id="S1", room_id="OR1", surgeon_id="SURG-A",
        date="2026-08-18", start="08:00", end="09:00",
    )
    assert a.start_minutes == 480
    assert a.end_minutes == 540


def test_surgeon_with_no_availability_is_unrestricted():
    s = Surgeon(id="SURG-A")
    assert s.is_available("2026-08-18", to_minutes("08:00"), to_minutes("09:00")) is True


def test_surgeon_availability_window_enforced():
    s = Surgeon(
        id="SURG-B",
        availability=[AvailabilityWindow(date="2026-08-18", start="13:00", end="16:00")],
    )
    assert s.is_available("2026-08-18", to_minutes("13:00"), to_minutes("14:00")) is True
    assert s.is_available("2026-08-18", to_minutes("08:00"), to_minutes("09:00")) is False
    assert s.is_available("2026-08-19", to_minutes("13:00"), to_minutes("14:00")) is False


def test_schedule_add_remove_and_to_dict():
    schedule = Schedule()
    a = Assignment(
        surgery_id="S1", room_id="OR1", surgeon_id="SURG-A",
        date="2026-08-18", start="08:00", end="09:00",
    )
    schedule.add(a)

    assert schedule.get("S1") == a
    assert schedule.scheduled_surgery_ids() == {"S1"}
    assert schedule.to_dict() == {"S1": a.model_dump()}

    assert schedule.remove("S1") is True
    assert schedule.remove("S1") is False
    assert schedule.scheduled_surgery_ids() == set()
