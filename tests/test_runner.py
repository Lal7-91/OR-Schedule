"""Runner writes well-formed run history to SQLite for the UI to consume --
verified with the trivial dry-run model (no network/LLM needed), writing
into a temp DB file so the repo's real runs/harness.db is never touched.
"""
from __future__ import annotations

from harness import db
from harness.config import Settings
from harness.runner import run_and_log


def test_run_and_log_writes_run_and_events(tmp_path):
    settings = Settings(
        ollama_base_url="unused",
        ollama_model="unused",
        ollama_api_key="unused",
        max_iterations=2,
        dry_run=True,
    )
    db_path = tmp_path / "test.db"

    run_and_log("test-run", "data/toy_problem.yaml", settings=settings, db_path=db_path)

    conn = db.connect(db_path)
    meta = db.get_run(conn, "test-run")
    assert meta["status"] == "finished"
    assert meta["final_verdict"] in {"accepted", "max_iterations_reached"}
    assert meta["finished_at"] is not None

    events = db.get_events(conn, "test-run")
    conn.close()

    assert events[0]["event"] == "run_started"
    assert events[-1]["event"] == "run_finished"

    node_events = [e for e in events if e["event"] == "node_finished"]
    assert {e["node"] for e in node_events} == {
        "scheduler",
        "constraint_checker",
        "priority_optimizer",
        "supervisor",
    }
    # Every node_finished event carries a full state snapshot the UI can render.
    assert all("state" in e for e in node_events)
