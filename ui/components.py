"""Reusable Streamlit rendering pieces shared by the live-run and past-runs
views, kept separate from page logic so both views render state identically.
"""
from __future__ import annotations

import streamlit as st
from runs_store import AGENT_ORDER

AGENT_LABELS = {
    "scheduler": "Scheduler",
    "constraint_checker": "Constraint Checker",
    "priority_optimizer": "Priority Optimizer",
    "supervisor": "Supervisor",
}

VERDICT_STYLE = {
    "accepted": ("green", "Accepted"),
    "max_iterations_reached": ("red", "Max iterations reached"),
    "pending": ("orange", "In progress"),
}


def render_pipeline(done_nodes: list[str], current_iteration: int) -> None:
    st.caption(f"Iteration {current_iteration}")
    cols = st.columns(len(AGENT_ORDER))
    # The node most recently completed in this pass through the pipeline.
    last_done = done_nodes[-1] if done_nodes else None
    for col, node in zip(cols, AGENT_ORDER, strict=True):
        label = AGENT_LABELS[node]
        if node == last_done:
            col.markdown(f"**:blue[{label}]** ✅")
        elif node in done_nodes:
            col.markdown(f"{label} ✅")
        else:
            col.markdown(f":gray[{label}]")


def render_verdict(verdict: str | None, iteration: int, max_iterations: int) -> None:
    color, label = VERDICT_STYLE.get(verdict, ("gray", verdict or "not started"))
    st.markdown(f"### Verdict: :{color}[{label}]")
    st.progress(min(iteration / max(max_iterations, 1), 1.0), text=f"{iteration} / {max_iterations} iterations")


def render_schedule(schedule_snapshot: dict) -> None:
    if not schedule_snapshot:
        st.info("No surgeries scheduled yet.")
        return
    rows = sorted(schedule_snapshot.values(), key=lambda a: (a["room_id"], a["start"]))
    st.dataframe(
        [
            {
                "Surgery": a["surgery_id"],
                "Room": a["room_id"],
                "Surgeon": a["surgeon_id"],
                "Start": a["start"],
                "End": a["end"],
            }
            for a in rows
        ],
        hide_index=True,
        width="stretch",
    )


def render_violations(violations: list[dict]) -> None:
    if not violations:
        st.success("No constraint violations.")
        return
    st.error(f"{len(violations)} constraint violation(s):")
    for v in violations:
        st.markdown(f"- **{v['type']}** ({v['surgery_id']}): {v['message']}")


def render_agent_notes(state: dict) -> None:
    with st.expander("Constraint Checker critique", expanded=False):
        st.write(state.get("constraint_critique") or "_(none yet)_")
    with st.expander("Priority Optimizer notes", expanded=False):
        st.write(state.get("optimizer_notes") or "_(none yet)_")
    with st.expander("Supervisor feedback", expanded=False):
        st.write(state.get("supervisor_feedback") or "_(none yet)_")


def render_run_state(state: dict, done_nodes: list[str], max_iterations: int) -> None:
    render_pipeline(done_nodes, state.get("iteration", 0))
    render_verdict(state.get("verdict"), state.get("iteration", 0), max_iterations)

    col1, col2 = st.columns([3, 2])
    with col1:
        st.subheader("Schedule")
        render_schedule(state.get("schedule_snapshot", {}))
    with col2:
        st.subheader("Constraint check")
        render_violations(state.get("violations", []))

    st.subheader("Agent notes")
    render_agent_notes(state)


def check_ollama_reachable(base_url: str, timeout: float = 2.0) -> bool:
    import httpx

    try:
        resp = httpx.get(f"{base_url}/models", timeout=timeout)
        return resp.status_code == 200
    except httpx.HTTPError:
        return False
