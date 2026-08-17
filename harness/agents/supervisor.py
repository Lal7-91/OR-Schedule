from __future__ import annotations

import json
import re
from collections.abc import Callable

from langchain_core.language_models.chat_models import BaseChatModel

from harness.agents.tool_loop import run_agent_turn
from harness.config import Settings
from harness.prompt_loader import load_prompt
from harness.state import HarnessState


def _parse_verdict(text: str) -> tuple[str, str]:
    try:
        data = json.loads(text)
        return data.get("verdict", "revise"), data.get("feedback", "")
    except (json.JSONDecodeError, TypeError):
        match = re.search(r'"verdict"\s*:\s*"(accept|revise)"', text or "")
        return (match.group(1) if match else "revise"), (text or "")


def make_supervisor_node(llm: BaseChatModel, settings: Settings) -> Callable[[HarnessState], dict]:
    system_prompt = load_prompt("supervisor")

    def supervisor_node(state: HarnessState) -> dict:
        iteration = state.get("iteration", 0) + 1
        user_content = (
            f"Schedule: {json.dumps(state['schedule_snapshot'])}\n"
            f"Hard-constraint violations (authoritative): {json.dumps(state['violations'])}\n"
            f"Constraint Checker critique: {state.get('constraint_critique')}\n"
            f"Priority Optimizer notes: {state.get('optimizer_notes')}\n"
            f"Iteration {iteration} of max {settings.max_iterations}."
        )

        raw = run_agent_turn(llm, [], system_prompt, user_content)
        verdict, feedback = _parse_verdict(raw)

        # Deterministic override: violations can never be waived by the LLM.
        if state["violations"]:
            verdict = "revise"
            if not feedback:
                feedback = "Deterministic validation still reports violations; fix them first."

        if verdict == "accept":
            result_verdict = "accepted"
        elif iteration >= settings.max_iterations:
            result_verdict = "max_iterations_reached"
        else:
            result_verdict = "pending"

        return {
            "iteration": iteration,
            "verdict": result_verdict,
            "supervisor_feedback": feedback,
        }

    return supervisor_node
