from __future__ import annotations

import argparse
import dataclasses

from rich.console import Console
from rich.table import Table

from harness.config import load_settings
from harness.domain.fixtures import load_toy_problem
from harness.domain.store import ScheduleStore
from harness.graph import build_graph
from harness.llm import build_llm
from harness.state import HarnessState, make_initial_state

console = Console()


def print_report(state: HarnessState) -> None:
    table = Table(title="Final schedule")
    table.add_column("Surgery")
    table.add_column("Room")
    table.add_column("Surgeon")
    table.add_column("Start")
    table.add_column("End")

    for surgery_id, a in sorted(state["schedule_snapshot"].items()):
        table.add_row(surgery_id, a["room_id"], a["surgeon_id"], a["start"], a["end"])

    console.print(table)

    verdict_style = {
        "accepted": "bold green",
        "max_iterations_reached": "bold red",
        "pending": "bold yellow",
    }.get(state["verdict"], "bold")
    console.print(f"\nVerdict: [{verdict_style}]{state['verdict']}[/] after {state['iteration']} iteration(s)")

    if state["violations"]:
        console.print("\n[bold red]Remaining violations:[/]")
        for v in state["violations"]:
            console.print(f"  - ({v['type']}) {v['message']}")

    if state.get("supervisor_feedback"):
        console.print(f"\nLatest supervisor feedback: {state['supervisor_feedback']}")


def run(problem_path: str, max_iterations: int | None = None, verbose: bool = False) -> HarnessState:
    settings = load_settings()
    if max_iterations is not None:
        settings = dataclasses.replace(settings, max_iterations=max_iterations)

    if verbose:
        console.print(f"[dim]Settings: {settings}[/]")

    problem = load_toy_problem(problem_path)
    store = ScheduleStore(problem)
    llm = build_llm(settings)
    app = build_graph(store, llm, settings)

    final_state = app.invoke(make_initial_state(problem.model_dump()))
    print_report(final_state)
    return final_state


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the OR-scheduling agent harness.")
    parser.add_argument("--problem", default="data/toy_problem.yaml", help="Path to a problem YAML fixture.")
    parser.add_argument("--max-iterations", type=int, default=None, help="Override MAX_SUPERVISOR_ITERATIONS.")
    parser.add_argument("--verbose", action="store_true", help="Print extra diagnostic info.")
    args = parser.parse_args()
    run(args.problem, max_iterations=args.max_iterations, verbose=args.verbose)


if __name__ == "__main__":
    main()
