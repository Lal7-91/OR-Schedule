from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_openai import ChatOpenAI

from harness.config import Settings


class ScriptedChatModel(GenericFakeChatModel):
    """GenericFakeChatModel, but bind_tools() is a no-op returning self.

    The base class has no notion of tools -- it just plays back a fixed
    message script regardless of what's asked of it -- so calling
    bind_tools() on it would otherwise raise NotImplementedError. Since
    scripted responses already encode any tool calls we want the fake to
    "make" (as AIMessage(tool_calls=[...])), binding tools is a no-op here.
    """

    def bind_tools(self, tools: Any, **kwargs: Any) -> ScriptedChatModel:
        return self


def build_llm(settings: Settings) -> BaseChatModel:
    """Build the chat model the harness's agents talk to.

    Normally this points at a self-hosted Ollama server via its OpenAI-
    compatible /v1 endpoint (see README for setup). When HARNESS_DRY_RUN is
    set, a trivial scripted model is returned instead so the harness's
    control flow (the revise-loop, the iteration cap, the graph wiring)
    can be smoke-tested with no network and no real model at all.

    For a more meaningful dry run that actually exercises the revise-loop
    with scripted tool calls, see tests/test_graph_stub.py, which builds
    its own GenericFakeChatModel with a purpose-scripted conversation
    instead of relying on this default.
    """
    if settings.dry_run:
        return build_trivial_dry_run_llm()

    return ChatOpenAI(
        base_url=settings.ollama_base_url,
        api_key=settings.ollama_api_key,
        model=settings.ollama_model,
        temperature=0,
        timeout=settings.request_timeout_seconds,
        max_tokens=settings.max_response_tokens,
        max_retries=0,  # a stuck/slow local model shouldn't be retried 2-3x on top of its own timeout
    )


def build_trivial_dry_run_llm() -> BaseChatModel:
    """A model that never calls a tool and always accepts immediately.

    Useful only to confirm the graph runs start-to-finish without crashing
    when no LLM is configured -- it will *not* schedule any surgeries,
    since it never emits a tool call.
    """
    return ScriptedChatModel(
        messages=iter(
            [
                '{"note": "dry-run: no tool calls issued"}',
                '{"note": "dry-run: no tool calls issued"}',
                '{"note": "dry-run: no tool calls issued"}',
                '{"verdict": "accept", "feedback": "dry-run: nothing to verify"}',
            ]
            * 10
        )
    )
