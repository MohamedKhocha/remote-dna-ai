"""Keep a long teach session short (the managing-long-conversations class).

A session is send, "did it react?", confirm, dozens of times. The messages
pile up, and every model call resends all of them. But what the agent must
remember is not in those messages: the address, the confirmed buttons and the
ruled-out addresses live in the state. So old tool round trips can go.

TrimToolHistory is a before-agent hook: at the start of each run it removes
old tool round trips, a call and its answers together, never one without the
other. The user's words, the agent's replies and the state all stay.
"""
from __future__ import annotations

from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain.messages import AIMessage, RemoveMessage, ToolMessage


class TrimToolHistory(AgentMiddleware):
    def __init__(self, keep_recent: int = 12, start_after: int = 40):
        super().__init__()
        self.keep_recent = keep_recent  # messages at the end that are never touched
        self.start_after = start_after  # nothing is trimmed in a short conversation

    def before_agent(self, state, runtime) -> dict[str, Any] | None:
        messages = state["messages"]
        if len(messages) <= self.start_after:
            return None
        cut = len(messages) - self.keep_recent
        old, recent = messages[:cut], messages[cut:]
        answered_late = {m.tool_call_id for m in recent if isinstance(m, ToolMessage)}
        # A round trip goes only if the call carried no text and none of its answers is recent.
        gone_calls: set[str] = set()
        drop: list[str] = []
        for m in old:
            if isinstance(m, AIMessage) and m.tool_calls and not (m.text or "").strip():
                ids = {c["id"] for c in m.tool_calls}
                if not ids & answered_late:
                    gone_calls |= ids
                    drop.append(m.id)
        drop += [m.id for m in old if isinstance(m, ToolMessage) and m.tool_call_id in gone_calls]
        return {"messages": [RemoveMessage(id=i) for i in drop]} if drop else None
