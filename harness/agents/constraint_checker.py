from __future__ import annotations

import json
from collections.abc import Callable

from langchain_core.language_models.chat_models import BaseChatModel

from harness.agents.tool_loop import run_agent_turn
from harness.domain.store import ScheduleStore
from harness.domain.tools import make_constraint_tools
from harness.prompt_loader import load_prompt
from harness.state import HarnessState


def make_constraint_checker_node(
    llm: BaseChatModel, store: ScheduleStore
) -> Callable[[HarnessState], dict]:
    tools = make_constraint_tools(store)
    system_prompt = load_prompt("constraint_checker")

    def constraint_checker_node(state: HarnessState) -> dict:
        user_content = (
            f"Current schedule: {json.dumps(store.current_schedule())}\n"
            "Call validate_schedule and summarize the result for the Scheduler."
        )
        critique = run_agent_turn(llm, tools, system_prompt, user_content)

        # Authoritative: read straight from the deterministic checker, never
        # from the agent's prose, no matter what it said.
        violations = store.validate()
        return {"violations": violations, "constraint_critique": critique}

    return constraint_checker_node
