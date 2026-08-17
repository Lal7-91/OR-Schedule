"""Streamlit dashboard for the OR-scheduling agent harness.

Run with: streamlit run ui/app.py
Two views: start and watch a run live, or browse past runs.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import streamlit as st
from components import check_ollama_reachable, render_run_state
from runs_store import completed_nodes, latest_state, list_runs, load_events, load_meta

# Explicit path insertion rather than relying on the editable install: under
# Streamlit's threaded script execution, the `harness` package's editable-
# install import hook doesn't reliably resolve in the script's own thread.
_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from harness.config import load_settings
from harness.runner import new_run_id

st.set_page_config(page_title="OR-Schedule Harness", page_icon="🏥", layout="wide")


def start_run(problem_path: str, max_iterations: int, dry_run: bool) -> str:
    run_id = new_run_id()
    cmd = [
        sys.executable,
        "-m",
        "harness.runner",
        "--problem",
        problem_path,
        "--run-id",
        run_id,
        "--max-iterations",
        str(max_iterations),
    ]
    if dry_run:
        cmd.append("--dry-run")
    subprocess.Popen(cmd, cwd=Path(__file__).resolve().parent.parent)
    return run_id


def sidebar_connection_status() -> None:
    settings = load_settings()
    st.sidebar.subheader("LLM connection")
    st.sidebar.write(f"`{settings.ollama_base_url}`")
    st.sidebar.write(f"Model: `{settings.ollama_model}`")
    if check_ollama_reachable(settings.ollama_base_url):
        st.sidebar.success("Reachable")
    else:
        st.sidebar.error("Not reachable")


def live_run_view() -> None:
    st.header("Live run")

    with st.form("start_run_form"):
        col1, col2, col3 = st.columns([2, 1, 1])
        problem_path = col1.text_input("Problem file", value="data/toy_problem.yaml")
        max_iterations = col2.number_input("Max iterations", min_value=1, max_value=20, value=5)
        dry_run = col3.checkbox("Dry run (no LLM)", value=False)
        submitted = st.form_submit_button("Start run", type="primary")

    if submitted:
        run_id = start_run(problem_path, int(max_iterations), dry_run)
        st.session_state["live_run_id"] = run_id

    run_id = st.session_state.get("live_run_id")
    if not run_id:
        st.info("Start a run above to watch the agents work.")
        return

    render_live_run(run_id)


@st.fragment(run_every=2)
def render_live_run(run_id: str) -> None:
    meta = load_meta(run_id)
    events = load_events(run_id)

    if meta is None:
        st.warning("Waiting for the run to start…")
        return

    st.caption(f"Run `{run_id}` — status: **{meta['status']}**")

    if meta["status"] == "error":
        st.error("The run failed.")
        error_events = [e for e in events if e.get("event") == "run_error"]
        if error_events:
            st.code(error_events[-1].get("traceback", error_events[-1].get("error", "")))
        return

    state = latest_state(events)
    if state is None:
        st.info("Waiting for the first agent to finish…")
        return

    render_run_state(state, completed_nodes(events), meta["max_iterations"])

    if meta["status"] == "finished":
        st.balloons()


def past_runs_view() -> None:
    st.header("Past runs")
    runs = list_runs()
    if not runs:
        st.info("No runs yet — start one from the Live run tab.")
        return

    options = {
        f"{r['run_id']} — {r.get('final_verdict') or r['status']} "
        f"({r.get('final_iteration', 0)} iter, {r['model']})": r["run_id"]
        for r in runs
    }
    choice = st.selectbox("Select a run", list(options.keys()))
    run_id = options[choice]

    meta = load_meta(run_id)
    events = load_events(run_id)
    state = latest_state(events)

    if meta:
        st.caption(
            f"Problem: `{meta['problem_path']}` · Model: `{meta['model']}` · "
            f"Started: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(meta['started_at']))}"
        )

    if state is None:
        st.info("This run has no recorded state yet.")
        return

    render_run_state(state, completed_nodes(events), meta["max_iterations"] if meta else 5)


st.title("🏥 OR-Schedule Agent Harness")
st.caption("A 4-agent supervisor/worker LangGraph harness solving a toy OR-scheduling problem.")

sidebar_connection_status()

tab_live, tab_past = st.tabs(["Live run", "Past runs"])
with tab_live:
    live_run_view()
with tab_past:
    past_runs_view()
