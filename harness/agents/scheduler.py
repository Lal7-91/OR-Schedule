from __future__ import annotations

import json
from collections.abc import Callable

from langchain_core.language_models.chat_models import BaseChatModel

from harness.agents.tool_loop import run_agent_turn
from harness.domain.store import ScheduleStore
from harness.domain.tools import make_scheduler_tools
from harness.prompt_loader import load_prompt
from harness.state import HarnessState


def make_scheduler_node(llm: BaseChatModel, store: ScheduleStore) -> Callable[[HarnessState], dict]:
    tools = make_scheduler_tools(store)
    system_prompt = load_prompt("scheduler")

    def scheduler_node(state: HarnessState) -> dict:
        user_content = (
            "Toy OR-scheduling problem (rooms/surgeons/surgeries):\n"
            f"{json.dumps(state['problem'], indent=2)}\n\n"
            f"Current schedule: {json.dumps(store.current_schedule())}\n"
            f"Unscheduled surgeries: {store.unscheduled_surgery_ids()}\n"
        )
        feedback = state.get("supervisor_feedback")
        if feedback:
            user_content += f"\nFeedback from the previous review round -- address this:\n{feedback}\n"

        run_agent_turn(llm, tools, system_prompt, user_content)
        return {"schedule_snapshot": store.current_schedule()}

    return scheduler_node
