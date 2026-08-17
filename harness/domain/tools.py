"""LangChain tool wrappers around a ScheduleStore.

Built via factory functions so each tool closes over one specific
ScheduleStore instance for a single harness run, instead of touching
module-level globals (which would break if multiple runs ever happened
in the same process).
"""
from __future__ import annotations

from langchain_core.tools import StructuredTool

from harness.domain.store import ScheduleStore


def make_scheduler_tools(store: ScheduleStore) -> list[StructuredTool]:
    """Tools for the Scheduler agent: read + write access to the schedule."""

    def get_current_schedule() -> dict:
        """Return all current assignments as {surgery_id: {room_id, start, end, surgeon_id}}."""
        return store.current_schedule()

    def get_unscheduled_surgeries() -> list[str]:
        """Return the IDs of surgeries that have not yet been assigned a room/time."""
        return store.unscheduled_surgery_ids()

    def assign_surgery(surgery_id: str, room_id: str, start_time: str) -> dict:
        """Assign surgery_id to room_id starting at start_time ('HH:MM', 24h clock).

        The end time is derived automatically from the surgery's known duration.
        Returns {"ok": bool, "reason": str | None}.
        """
        return store.assign(surgery_id, room_id, start_time)

    def unassign_surgery(surgery_id: str) -> dict:
        """Remove an existing assignment for surgery_id, if any.

        Returns {"ok": bool, "reason": str | None}.
        """
        return store.unassign(surgery_id)

    return [
        StructuredTool.from_function(get_current_schedule),
        StructuredTool.from_function(get_unscheduled_surgeries),
        StructuredTool.from_function(assign_surgery),
        StructuredTool.from_function(unassign_surgery),
    ]


def make_readonly_schedule_tools(store: ScheduleStore) -> list[StructuredTool]:
    """Read-only tools for agents that should see but not mutate the schedule
    (Priority Optimizer)."""

    def get_current_schedule() -> dict:
        """Return all current assignments as {surgery_id: {room_id, start, end, surgeon_id}}."""
        return store.current_schedule()

    def get_unscheduled_surgeries() -> list[str]:
        """Return the IDs of surgeries that have not yet been assigned a room/time."""
        return store.unscheduled_surgery_ids()

    return [
        StructuredTool.from_function(get_current_schedule),
        StructuredTool.from_function(get_unscheduled_surgeries),
    ]


def make_constraint_tools(store: ScheduleStore) -> list[StructuredTool]:
    """Tools for the Constraint Checker agent: deterministic validation only."""

    def validate_schedule() -> dict:
        """Run deterministic hard-constraint checks on the full current schedule.

        Returns {"valid": bool, "violations": [{"type", "surgery_id", "message"}, ...]}.
        This check is authoritative — its result cannot be overridden by agent judgment.
        """
        violations = store.validate()
        return {"valid": len(violations) == 0, "violations": violations}

    return [StructuredTool.from_function(validate_schedule)]
