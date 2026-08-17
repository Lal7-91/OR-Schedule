"""Shared bounded tool-calling loop used by every agent node.

This is the actual "harness" mechanic: send the model a system+user
message, execute whatever tool calls it requests, feed the results back
as ToolMessages, and repeat until it stops calling tools (or a round cap
is hit). Kept as one small, inspectable helper rather than hidden inside
a framework's AgentExecutor, since seeing this loop explicitly is the
point of the exercise.
"""
from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool

MAX_TOOL_ROUNDS = 6


def run_agent_turn(
    llm: BaseChatModel,
    tools: list[StructuredTool],
    system_prompt: str,
    user_content: str,
) -> str:
    tools_by_name = {t.name: t for t in tools}
    model = llm.bind_tools(tools) if tools else llm
    messages: list[BaseMessage] = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content),
    ]

    for _ in range(MAX_TOOL_ROUNDS):
        response = model.invoke(messages)
        messages.append(response)

        tool_calls = getattr(response, "tool_calls", None)
        if not tool_calls:
            return response.content

        for call in tool_calls:
            tool = tools_by_name.get(call["name"])
            result = tool.invoke(call["args"]) if tool else {"error": f"Unknown tool: {call['name']}"}
            messages.append(ToolMessage(content=str(result), tool_call_id=call["id"]))

    return "(tool-call round limit reached without a final answer)"
