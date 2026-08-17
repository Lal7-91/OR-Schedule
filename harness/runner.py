"""Streams a harness run to a JSONL event log on disk, so a separate UI
process can show live progress (and later replay past runs) without being
in the same Python process as the run itself.

Each run gets its own directory under `runs/<run_id>/`:
  meta.json     -- static info about the run (problem, settings, status)
  events.jsonl  -- one JSON object per line, appended as the graph executes
"""
from __future__ import annotations

import argparse
import json
import time
import traceback
from pathlib import Path
from typing import Any

from harness.config import Settings, load_settings
from harness.domain.fixtures import load_toy_problem
from harness.domain.store import ScheduleStore
from harness.graph import build_graph
from harness.llm import build_llm
from harness.state import make_initial_state

RUNS_DIR = Path("runs")


def _now() -> float:
    return time.time()


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2))


def new_run_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def run_and_log(
    run_id: str,
    problem_path: str,
    settings: Settings | None = None,
    runs_dir: Path | None = None,
) -> None:
    settings = settings or load_settings()
    run_dir = (runs_dir or RUNS_DIR) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    events_path = run_dir / "events.jsonl"
    meta_path = run_dir / "meta.json"

    problem = load_toy_problem(problem_path)
    meta: dict[str, Any] = {
        "run_id": run_id,
        "problem_path": problem_path,
        "problem": problem.model_dump(),
        "model": settings.ollama_model,
        "base_url": settings.ollama_base_url,
        "max_iterations": settings.max_iterations,
        "dry_run": settings.dry_run,
        "status": "running",
        "started_at": _now(),
        "finished_at": None,
        "final_verdict": None,
        "final_iteration": 0,
    }
    _write_json(meta_path, meta)

    def emit(event: dict) -> None:
        with events_path.open("a") as f:
            f.write(json.dumps({**event, "ts": _now()}) + "\n")

    emit({"event": "run_started"})

    try:
        store = ScheduleStore(problem)
        llm = build_llm(settings)
        app = build_graph(store, llm, settings)

        state = make_initial_state(problem.model_dump())
        for chunk in app.stream(state, stream_mode="updates"):
            for node_name, update in chunk.items():
                state = {**state, **update}
                emit({"event": "node_finished", "node": node_name, "state": state})

        meta["status"] = "finished"
        meta["final_verdict"] = state.get("verdict")
        meta["final_iteration"] = state.get("iteration", 0)
        emit({"event": "run_finished", "state": state})
    except Exception as exc:  # noqa: BLE001 -- surfaced to the UI, not swallowed
        meta["status"] = "error"
        emit({"event": "run_error", "error": str(exc), "traceback": traceback.format_exc()})
    finally:
        meta["finished_at"] = _now()
        _write_json(meta_path, meta)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the harness and log events for the UI.")
    parser.add_argument("--problem", default="data/toy_problem.yaml")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    settings = load_settings()
    if args.max_iterations is not None:
        import dataclasses

        settings = dataclasses.replace(settings, max_iterations=args.max_iterations)
    if args.dry_run:
        import dataclasses

        settings = dataclasses.replace(settings, dry_run=True)

    run_id = args.run_id or new_run_id()
    run_and_log(run_id, args.problem, settings)


if __name__ == "__main__":
    main()
