"""Tier B: exercise the harness's control flow (loop-back edge, iteration
counter, max-iteration guard) end-to-end with NO real LLM and NO network,
by scripting a fake model's exact conversation turn-by-turn. Proves the
graph wiring itself works before an Ollama server exists to test against.
"""
from __future__ import annotations

from langchain_core.messages import AIMessage

from harness.config import Settings
from harness.domain.models import ProblemInstance, Room, Surgeon, Surgery
from harness.domain.store import ScheduleStore
from harness.graph import build_graph
from harness.llm import ScriptedChatModel
from harness.state import make_initial_state


def tool_call_message(name: str, args: dict, call_id: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


DATE = "2026-08-18"


def build_test_problem() -> ProblemInstance:
    return ProblemInstance(
        horizon=[DATE],
        rooms=[
            Room(id="OR1", operating_start="08:00", operating_end="16:00"),
            Room(id="OR2", operating_start="08:00", operating_end="16:00"),
        ],
        surgeons=[Surgeon(id="SURG-A"), Surgeon(id="SURG-B")],
        surgeries=[
            Surgery(id="S1", duration_minutes=60, required_surgeon_id="SURG-A", priority="urgent"),
            Surgery(id="S2", duration_minutes=60, required_surgeon_id="SURG-B", priority="routine"),
        ],
    )


def build_scripted_script() -> list:
    return [
        # --- iteration 1: scheduler double-books OR1 ---
        tool_call_message(
            "assign_surgery",
            {"surgery_id": "S1", "room_id": "OR1", "date": DATE, "start_time": "08:00"},
            "c1",
        ),
        tool_call_message(
            "assign_surgery",
            {"surgery_id": "S2", "room_id": "OR1", "date": DATE, "start_time": "08:30"},
            "c2",
        ),
        "Scheduled S1 and S2.",  # scheduler's final answer, no more tool calls
        tool_call_message("validate_schedule", {}, "c3"),
        "S1 and S2 conflict in OR1 -- move one of them.",  # constraint checker's final answer
        "Priorities look fine; S1 is urgent and already scheduled early.",  # priority optimizer
        '{"verdict": "revise", "feedback": "Fix the room conflict between S1 and S2 in OR1."}',  # supervisor
        # --- iteration 2: scheduler fixes it ---
        tool_call_message("unassign_surgery", {"surgery_id": "S2"}, "c4"),
        tool_call_message(
            "assign_surgery",
            {"surgery_id": "S2", "room_id": "OR2", "date": DATE, "start_time": "08:00"},
            "c5",
        ),
        "Moved S2 to OR2 to resolve the conflict.",  # scheduler's final answer
        tool_call_message("validate_schedule", {}, "c6"),
        "No violations now.",  # constraint checker's final answer
        "Schedule looks reasonable now.",  # priority optimizer
        '{"verdict": "accept", "feedback": ""}',  # supervisor accepts
    ]


def test_revise_loop_then_accept():
    problem = build_test_problem()
    store = ScheduleStore(problem)
    llm = ScriptedChatModel(messages=iter(build_scripted_script()))
    settings = Settings(
        ollama_base_url="unused",
        ollama_model="unused",
        ollama_api_key="unused",
        max_iterations=5,
        dry_run=False,
    )

    app = build_graph(store, llm, settings)
    final_state = app.invoke(make_initial_state(problem.model_dump()))

    assert final_state["verdict"] == "accepted"
    assert final_state["iteration"] == 2
    assert final_state["violations"] == []
    assert final_state["schedule_snapshot"]["S1"]["room_id"] == "OR1"
    assert final_state["schedule_snapshot"]["S2"]["room_id"] == "OR2"


def test_max_iterations_guard_stops_infinite_revise():
    problem = build_test_problem()
    store = ScheduleStore(problem)
    # Scheduler never calls a tool, constraint checker finds nothing to
    # validate (empty schedule = no violations), but the supervisor always
    # asks for a revision anyway -- this must terminate at the iteration cap.
    script = (
        [
            "no-op",  # scheduler
            "no-op",  # constraint checker (no validate_schedule call)
            "no-op",  # priority optimizer
            '{"verdict": "revise", "feedback": "try again"}',  # supervisor
        ]
        * 3
    )
    llm = ScriptedChatModel(messages=iter(script))
    settings = Settings(
        ollama_base_url="unused",
        ollama_model="unused",
        ollama_api_key="unused",
        max_iterations=3,
        dry_run=False,
    )

    app = build_graph(store, llm, settings)
    final_state = app.invoke(make_initial_state(problem.model_dump()))

    assert final_state["verdict"] == "max_iterations_reached"
    assert final_state["iteration"] == 3
