"""SQLite-backed storage for harness run history.

Replaces the earlier runs/<run_id>/{meta.json,events.jsonl} file scheme.
One writer (harness/runner.py, run as its own subprocess) and one reader
(the Streamlit UI, polling) talk to the same SQLite file concurrently --
WAL mode is enabled so reads don't block on the writer.

Problem definitions are NOT stored here; they stay as YAML files
(data/*.yaml) -- small, human-readable, and worth keeping hand-editable
and diffable in git, unlike run history which is disposable local output.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

DB_PATH = Path("runs") / "harness.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    problem_path TEXT NOT NULL,
    problem_json TEXT NOT NULL,
    model TEXT NOT NULL,
    base_url TEXT NOT NULL,
    max_iterations INTEGER NOT NULL,
    dry_run INTEGER NOT NULL,
    status TEXT NOT NULL,
    started_at REAL NOT NULL,
    finished_at REAL,
    final_verdict TEXT,
    final_iteration INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS run_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    event TEXT NOT NULL,
    node TEXT,
    state_json TEXT,
    error TEXT,
    traceback TEXT,
    ts REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_run_events_run_id ON run_events(run_id, id);
"""


def connect(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_SCHEMA)
    return conn


def create_run(
    conn: sqlite3.Connection,
    run_id: str,
    problem_path: str,
    problem: dict,
    model: str,
    base_url: str,
    max_iterations: int,
    dry_run: bool,
) -> None:
    conn.execute(
        """INSERT INTO runs
           (run_id, problem_path, problem_json, model, base_url, max_iterations,
            dry_run, status, started_at, final_iteration)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'running', ?, 0)""",
        (
            run_id,
            problem_path,
            json.dumps(problem),
            model,
            base_url,
            max_iterations,
            int(dry_run),
            time.time(),
        ),
    )
    conn.commit()


def append_event(
    conn: sqlite3.Connection,
    run_id: str,
    event: str,
    node: str | None = None,
    state: dict | None = None,
    error: str | None = None,
    traceback: str | None = None,
) -> None:
    conn.execute(
        """INSERT INTO run_events (run_id, event, node, state_json, error, traceback, ts)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            run_id,
            event,
            node,
            json.dumps(state) if state is not None else None,
            error,
            traceback,
            time.time(),
        ),
    )
    conn.commit()


def finish_run(
    conn: sqlite3.Connection,
    run_id: str,
    status: str,
    final_verdict: str | None,
    final_iteration: int,
) -> None:
    conn.execute(
        """UPDATE runs SET status = ?, finished_at = ?, final_verdict = ?, final_iteration = ?
           WHERE run_id = ?""",
        (status, time.time(), final_verdict, final_iteration, run_id),
    )
    conn.commit()


def _row_to_meta(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "run_id": row["run_id"],
        "problem_path": row["problem_path"],
        "problem": json.loads(row["problem_json"]),
        "model": row["model"],
        "base_url": row["base_url"],
        "max_iterations": row["max_iterations"],
        "dry_run": bool(row["dry_run"]),
        "status": row["status"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "final_verdict": row["final_verdict"],
        "final_iteration": row["final_iteration"],
    }


def list_runs(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM runs ORDER BY started_at DESC").fetchall()
    return [_row_to_meta(r) for r in rows]


def get_run(conn: sqlite3.Connection, run_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    return _row_to_meta(row) if row else None


def get_events(conn: sqlite3.Connection, run_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM run_events WHERE run_id = ? ORDER BY id ASC", (run_id,)
    ).fetchall()
    events = []
    for r in rows:
        event: dict[str, Any] = {"event": r["event"], "ts": r["ts"]}
        if r["node"] is not None:
            event["node"] = r["node"]
        if r["state_json"] is not None:
            event["state"] = json.loads(r["state_json"])
        if r["error"] is not None:
            event["error"] = r["error"]
        if r["traceback"] is not None:
            event["traceback"] = r["traceback"]
        events.append(event)
    return events
