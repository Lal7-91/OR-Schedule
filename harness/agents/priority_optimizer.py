from __future__ import annotations

import json
from collections.abc import Callable

from langchain_core.language_models.chat_models import BaseChatModel

from harness.agents.tool_loop import run_agent_turn
from harness.domain.store import ScheduleStore
from harness.domain.tools import make_readonly_schedule_tools
from harness.prompt_loader import load_prompt
from harness.state import HarnessState


def make_priority_optimizer_node(
    llm: BaseChatModel, store: ScheduleStore
) -> Callable[[HarnessState], dict]:
    tools = make_readonly_schedule_tools(store)
    system_prompt = load_prompt("priority_optimizer")

    def priority_optimizer_node(state: HarnessState) -> dict:
        priorities = {s["id"]: s["priority"] for s in state["problem"]["surgeries"]}
        user_content = (
            f"Current schedule: {json.dumps(store.current_schedule())}\n"
            f"Unscheduled surgeries: {store.unscheduled_surgery_ids()}\n"
            f"Surgery priorities: {json.dumps(priorities)}\n"
        )
        notes = run_agent_turn(llm, tools, system_prompt, user_content)
        return {"optimizer_notes": notes}

    return priority_optimizer_node
