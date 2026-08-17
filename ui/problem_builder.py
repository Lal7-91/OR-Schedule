"""Interactive builder for a harness problem file: horizon dates, rooms,
surgeons (with optional availability windows), and surgeries. Lets you
assemble a problem without hand-editing YAML, then save it and run it from
the Live run tab.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import streamlit as st
import yaml
from pydantic import ValidationError

# See the matching comment in app.py -- this module can be imported before
# app.py's own sys.path fix runs, so it needs its own guard too.
_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from harness.domain.fixtures import load_toy_problem
from harness.domain.models import ProblemInstance

DEFAULT_SOURCE = "data/toy_problem.yaml"


def _hhmm_to_time(value) -> dt.time | None:
    """Coerce a stored 'HH:MM' string (or an already-a-time value) into a
    datetime.time for TimeColumn widgets, which pick from a clock rather
    than requiring the user to type text."""
    if isinstance(value, dt.time):
        return value
    if not value:
        return None
    try:
        return dt.datetime.strptime(value, "%H:%M").time()  # noqa: DTZ007 -- wall-clock only
    except ValueError:
        return None


def _time_to_hhmm(value) -> str:
    """Inverse of _hhmm_to_time -- what actually gets stored/saved."""
    if isinstance(value, dt.time):
        return value.strftime("%H:%M")
    return value or ""


def _with_time_widgets(rows: list[dict], fields: list[str]) -> list[dict]:
    return [{**row, **{f: _hhmm_to_time(row.get(f)) for f in fields}} for row in rows]


def _from_time_widgets(rows: list[dict], fields: list[str]) -> list[dict]:
    return [{**row, **{f: _time_to_hhmm(row.get(f)) for f in fields}} for row in rows]

# Session-state keys, namespaced so this tab doesn't collide with the rest of the app.
_KEYS = ["pb_horizon", "pb_rooms", "pb_surgeons", "pb_availability", "pb_surgeries", "pb_loaded_from"]


def _problem_to_editor_state(problem: ProblemInstance) -> dict:
    availability_rows = [
        {"surgeon_id": s.id, "date": w.date, "start": w.start, "end": w.end}
        for s in problem.surgeons
        for w in s.availability
    ]
    return {
        "pb_horizon": list(problem.horizon),
        "pb_rooms": [r.model_dump() for r in problem.rooms],
        "pb_surgeons": [{"id": s.id} for s in problem.surgeons],
        "pb_availability": availability_rows,
        "pb_surgeries": [s.model_dump() for s in problem.surgeries],
    }


def _ensure_state() -> None:
    if "pb_horizon" in st.session_state:
        return
    try:
        problem = load_toy_problem(DEFAULT_SOURCE)
    except (OSError, yaml.YAMLError, ValidationError):
        problem = None
    if problem is not None:
        st.session_state.update(_problem_to_editor_state(problem))
    else:
        today = dt.date.today().isoformat()  # noqa: DTZ011 -- plain calendar date, no timezone involved
        st.session_state.update(
            {
                "pb_horizon": [today],
                "pb_rooms": [{"id": "OR1", "operating_start": "08:00", "operating_end": "16:00"}],
                "pb_surgeons": [{"id": "SURG-A"}],
                "pb_availability": [],
                "pb_surgeries": [],
            }
        )
    st.session_state["pb_loaded_from"] = DEFAULT_SOURCE


def _load_file(path: str) -> None:
    problem = load_toy_problem(path)  # raises on missing/invalid file -- caller handles
    st.session_state.update(_problem_to_editor_state(problem))
    st.session_state["pb_loaded_from"] = path


def _assemble_problem() -> ProblemInstance:
    surgeon_ids = [s["id"] for s in st.session_state["pb_surgeons"] if s.get("id")]
    availability_by_surgeon: dict[str, list[dict]] = {sid: [] for sid in surgeon_ids}
    for row in st.session_state["pb_availability"]:
        sid = row.get("surgeon_id")
        if sid in availability_by_surgeon and row.get("date") and row.get("start") and row.get("end"):
            availability_by_surgeon[sid].append(
                {"date": row["date"], "start": row["start"], "end": row["end"]}
            )

    data = {
        "horizon": st.session_state["pb_horizon"],
        "rooms": [r for r in st.session_state["pb_rooms"] if r.get("id")],
        "surgeons": [
            {"id": sid, "availability": availability_by_surgeon.get(sid, [])} for sid in surgeon_ids
        ],
        "surgeries": [s for s in st.session_state["pb_surgeries"] if s.get("id")],
    }
    return ProblemInstance.model_validate(data)


def render() -> None:
    st.header("Problem builder")
    _ensure_state()

    st.caption(f"Currently editing a copy loaded from `{st.session_state['pb_loaded_from']}`.")

    with st.expander("Load a different problem file", expanded=False):
        col1, col2 = st.columns([3, 1])
        load_path = col1.text_input("Path", value=DEFAULT_SOURCE, key="pb_load_path")
        if col2.button("Load", key="pb_load_btn"):
            try:
                _load_file(load_path)
                st.success(f"Loaded {load_path}")
                st.rerun()
            except Exception as exc:  # noqa: BLE001 -- show any load failure to the user
                st.error(f"Couldn't load {load_path}: {exc}")

    st.subheader("Scheduling horizon")
    default_date = (
        dt.date.fromisoformat(st.session_state["pb_horizon"][0])
        if st.session_state["pb_horizon"]
        else dt.date.today()  # noqa: DTZ011 -- plain calendar date, no timezone involved
    )
    horizon_start = st.date_input("First date", value=default_date)
    horizon_days = st.number_input(
        "Number of days", min_value=1, max_value=30, value=max(len(st.session_state["pb_horizon"]), 1)
    )
    st.session_state["pb_horizon"] = [
        (horizon_start + dt.timedelta(days=i)).isoformat() for i in range(int(horizon_days))
    ]
    st.caption("Dates: " + ", ".join(st.session_state["pb_horizon"]))

    st.subheader("Rooms")
    edited_rooms = st.data_editor(
        _with_time_widgets(st.session_state["pb_rooms"], ["operating_start", "operating_end"]),
        num_rows="dynamic",
        width="stretch",
        key="pb_rooms_editor",
        column_config={
            "id": st.column_config.TextColumn("Room ID", required=True),
            "operating_start": st.column_config.TimeColumn("Opens", required=True, step=900),
            "operating_end": st.column_config.TimeColumn("Closes", required=True, step=900),
        },
    )
    st.session_state["pb_rooms"] = _from_time_widgets(edited_rooms, ["operating_start", "operating_end"])

    st.subheader("Surgeons")
    st.session_state["pb_surgeons"] = st.data_editor(
        st.session_state["pb_surgeons"],
        num_rows="dynamic",
        width="stretch",
        key="pb_surgeons_editor",
        column_config={"id": st.column_config.TextColumn("Surgeon ID", required=True)},
    )

    surgeon_ids = [s["id"] for s in st.session_state["pb_surgeons"] if s.get("id")]

    st.subheader("Surgeon availability")
    st.caption(
        "Optional. A surgeon with no rows here is available any horizon date within room "
        "hours. Add rows to *restrict* a surgeon to specific date+time windows."
    )
    edited_availability = st.data_editor(
        _with_time_widgets(st.session_state["pb_availability"], ["start", "end"]),
        num_rows="dynamic",
        width="stretch",
        key="pb_availability_editor",
        column_config={
            "surgeon_id": st.column_config.SelectboxColumn("Surgeon", options=surgeon_ids, required=True),
            "date": st.column_config.SelectboxColumn(
                "Date", options=st.session_state["pb_horizon"], required=True
            ),
            "start": st.column_config.TimeColumn("From", required=True, step=900),
            "end": st.column_config.TimeColumn("Until", required=True, step=900),
        },
    )
    st.session_state["pb_availability"] = _from_time_widgets(edited_availability, ["start", "end"])

    st.subheader("Surgeries")
    st.session_state["pb_surgeries"] = st.data_editor(
        st.session_state["pb_surgeries"],
        num_rows="dynamic",
        width="stretch",
        key="pb_surgeries_editor",
        column_config={
            "id": st.column_config.TextColumn("Surgery ID", required=True),
            "duration_minutes": st.column_config.NumberColumn("Duration (min)", min_value=1, required=True),
            "required_surgeon_id": st.column_config.SelectboxColumn(
                "Required surgeon", options=surgeon_ids, required=True
            ),
            "priority": st.column_config.SelectboxColumn(
                "Priority", options=["urgent", "routine"], required=True
            ),
        },
    )

    st.subheader("Save")
    col1, col2 = st.columns([3, 1])
    save_path = col1.text_input("Save as", value="data/custom_problem.yaml", key="pb_save_path")
    if col2.button("Save problem", type="primary", key="pb_save_btn"):
        try:
            problem = _assemble_problem()
        except ValidationError as exc:
            st.error(f"Problem isn't valid yet:\n\n{exc}")
        else:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            Path(save_path).write_text(yaml.safe_dump(problem.model_dump(), sort_keys=False))
            st.success(f"Saved to {save_path} — pick it as the problem file in the Live run tab to use it.")
