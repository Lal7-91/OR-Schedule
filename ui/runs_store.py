"""Reads run logs written by harness/runner.py off disk for the UI."""
from __future__ import annotations

import json
from pathlib import Path

RUNS_DIR = Path("runs")

AGENT_ORDER = ["scheduler", "constraint_checker", "priority_optimizer", "supervisor"]


def list_runs() -> list[dict]:
    if not RUNS_DIR.exists():
        return []
    runs = []
    for run_dir in RUNS_DIR.iterdir():
        meta_path = run_dir / "meta.json"
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text())
        except json.JSONDecodeError:
            continue
        meta["run_dir"] = str(run_dir)
        runs.append(meta)
    return sorted(runs, key=lambda m: m.get("started_at", 0), reverse=True)


def load_meta(run_id: str) -> dict | None:
    meta_path = RUNS_DIR / run_id / "meta.json"
    if not meta_path.exists():
        return None
    try:
        return json.loads(meta_path.read_text())
    except json.JSONDecodeError:
        return None


def load_events(run_id: str) -> list[dict]:
    events_path = RUNS_DIR / run_id / "events.jsonl"
    if not events_path.exists():
        return []
    events = []
    for line in events_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # a line may be mid-write while a run is live; skip it this refresh
    return events


def latest_state(events: list[dict]) -> dict | None:
    for event in reversed(events):
        if "state" in event:
            return event["state"]
    return None


def completed_nodes(events: list[dict]) -> list[str]:
    return [e["node"] for e in events if e.get("event") == "node_finished"]
