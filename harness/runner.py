"""Streams a harness run into SQLite (harness/db.py), so a separate UI
process can show live progress (and later replay past runs) without being
in the same Python process as the run itself.
"""
from __future__ import annotations

import argparse
import time
import traceback
from pathlib import Path

from harness import db
from harness.config import Settings, load_settings
from harness.domain.fixtures import load_toy_problem
from harness.domain.store import ScheduleStore
from harness.graph import build_graph
from harness.llm import build_llm
from harness.state import make_initial_state


def new_run_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def run_and_log(
    run_id: str,
    problem_path: str,
    settings: Settings | None = None,
    db_path: Path | str = db.DB_PATH,
) -> None:
    settings = settings or load_settings()
    conn = db.connect(db_path)

    problem = load_toy_problem(problem_path)
    db.create_run(
        conn,
        run_id=run_id,
        problem_path=problem_path,
        problem=problem.model_dump(),
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
        max_iterations=settings.max_iterations,
        dry_run=settings.dry_run,
    )
    db.append_event(conn, run_id, "run_started")

    try:
        store = ScheduleStore(problem)
        llm = build_llm(settings)
        app = build_graph(store, llm, settings)

        state = make_initial_state(problem.model_dump())
        for chunk in app.stream(state, stream_mode="updates"):
            for node_name, update in chunk.items():
                state = {**state, **update}
                db.append_event(conn, run_id, "node_finished", node=node_name, state=state)

        db.finish_run(conn, run_id, "finished", state.get("verdict"), state.get("iteration", 0))
        db.append_event(conn, run_id, "run_finished", state=state)
    except Exception as exc:  # noqa: BLE001 -- surfaced to the UI, not swallowed
        db.finish_run(conn, run_id, "error", None, 0)
        db.append_event(conn, run_id, "run_error", error=str(exc), traceback=traceback.format_exc())
    finally:
        conn.close()


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
