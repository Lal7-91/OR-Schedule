"""Runner writes well-formed run logs for the UI to consume -- verified with
the trivial dry-run model (no network/LLM needed), writing into a temp dir
so the repo's real runs/ directory is never touched by tests.
"""
from __future__ import annotations

import json

from harness.config import Settings
from harness.runner import run_and_log


def test_run_and_log_writes_meta_and_events(tmp_path):
    settings = Settings(
        ollama_base_url="unused",
        ollama_model="unused",
        ollama_api_key="unused",
        max_iterations=2,
        dry_run=True,
    )

    run_and_log("test-run", "data/toy_problem.yaml", settings=settings, runs_dir=tmp_path)

    run_dir = tmp_path / "test-run"
    meta = json.loads((run_dir / "meta.json").read_text())
    assert meta["status"] == "finished"
    assert meta["final_verdict"] in {"accepted", "max_iterations_reached"}
    assert meta["finished_at"] is not None

    lines = (run_dir / "events.jsonl").read_text().strip().splitlines()
    events = [json.loads(line) for line in lines]

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
