from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, StateGraph

from harness.agents.constraint_checker import make_constraint_checker_node
from harness.agents.priority_optimizer import make_priority_optimizer_node
from harness.agents.scheduler import make_scheduler_node
from harness.agents.supervisor import make_supervisor_node
from harness.config import Settings
from harness.domain.store import ScheduleStore
from harness.state import HarnessState


def route_after_supervisor(state: HarnessState) -> str:
    if state["verdict"] in ("accepted", "max_iterations_reached"):
        return END
    return "scheduler"


def build_graph(store: ScheduleStore, llm: BaseChatModel, settings: Settings):
    """Wire the 4-agent supervisor/worker graph:

        scheduler -> constraint_checker -> priority_optimizer -> supervisor
                                                                       |
                                          (revise) <--------------------
                                          (accepted / max_iterations) -> END

    `llm` is injected rather than built internally so tests can swap in a
    scripted fake model without touching this module at all.
    """
    graph = StateGraph(HarnessState)
    graph.add_node("scheduler", make_scheduler_node(llm, store))
    graph.add_node("constraint_checker", make_constraint_checker_node(llm, store))
    graph.add_node("priority_optimizer", make_priority_optimizer_node(llm, store))
    graph.add_node("supervisor", make_supervisor_node(llm, settings))

    graph.set_entry_point("scheduler")
    graph.add_edge("scheduler", "constraint_checker")
    graph.add_edge("constraint_checker", "priority_optimizer")
    graph.add_edge("priority_optimizer", "supervisor")
    graph.add_conditional_edges("supervisor", route_after_supervisor)

    return graph.compile()
