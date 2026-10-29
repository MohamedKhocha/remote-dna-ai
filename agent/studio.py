"""The agent for LangGraph Studio: a chat window that shows every step.

    langgraph dev        # from the repository root; needs langgraph-cli[inmem]

Studio keeps the conversation itself, so the agent is built without its own
checkpointer. The TV is the same virtual IRIS 43G7200 as in agent.chat; its
reaction is written into the send_code result so you can see it in Studio.
Every send still stops for your approval in Studio's interrupt panel.
"""
from __future__ import annotations

from agent.remote_agent import build_agent
from agent.tools import VirtualTV

_tv = VirtualTV.from_model("43G7200")


def _sender(protocol: str, address: int, command: int) -> str:
    seen = _tv.receive(protocol, address, command)
    return f"sent; the virtual TV shows: {seen}" if seen else "sent; the virtual TV shows nothing"


graph = build_agent(sender=_sender, memory=False)
