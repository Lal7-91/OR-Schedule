"""Reads run history (written by harness/runner.py into SQLite) for the UI.

Same function signatures as the earlier file-based version on purpose --
app.py and components.py don't need to know the storage backend changed.
"""
from __future__ import annotations

import sys
from pathlib import Path

# See the matching comment in app.py -- this module can be imported before
# app.py's own sys.path fix runs, so it needs its own guard too.
_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from harness import db

AGENT_ORDER = ["scheduler", "constraint_checker", "priority_optimizer", "supervisor"]


def list_runs() -> list[dict]:
    conn = db.connect()
    try:
        return db.list_runs(conn)
    finally:
        conn.close()


def load_meta(run_id: str) -> dict | None:
    conn = db.connect()
    try:
        return db.get_run(conn, run_id)
    finally:
        conn.close()


def load_events(run_id: str) -> list[dict]:
    conn = db.connect()
    try:
        return db.get_events(conn, run_id)
    finally:
        conn.close()


def latest_state(events: list[dict]) -> dict | None:
    for event in reversed(events):
        if "state" in event:
            return event["state"]
    return None


def completed_nodes(events: list[dict]) -> list[str]:
    return [e["node"] for e in events if e.get("event") == "node_finished"]
