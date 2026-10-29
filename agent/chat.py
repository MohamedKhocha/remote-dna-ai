"""Talk to the Remote DNA agent in a terminal, with a virtual TV.

    python -m agent.chat                  # the TV is an IRIS 43G7200
    python -m agent.chat --tv 43G7200

The key comes from a .env file next to this repository's README
(GOOGLE_API_KEY=...). It is never printed and never committed.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import uuid

from dotenv import load_dotenv
from langchain.messages import HumanMessage
from langgraph.types import Command

from .remote_agent import build_agent
from .tools import VirtualTV

NAMES = {"volUp": "volume up", "volDown": "volume down", "chUp": "channel up", "chDown": "channel down",
         "ok": "OK", "back": "back", "mute": "mute", "menu": "menu", "power": "power"}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    ap = argparse.ArgumentParser()
    ap.add_argument("--tv", default="43G7200", help="model number of the virtual TV")
    tv = VirtualTV.from_model(ap.parse_args().tv)

    def sender(protocol: str, address: int, command: int) -> str:
        seen = tv.receive(protocol, address, command)
        print(f"   [TV] {'reacts: ' + NAMES.get(seen, seen) if seen else 'nothing happens'}")
        return "sent"

    agent = build_agent(sender=sender)
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    print("Remote DNA agent. Describe your TV; empty line to quit.\n")
    payload = None
    while True:
        if payload is None:
            text = input("you> ").strip()
            if not text:
                return
            payload = {"messages": [HumanMessage(text)]}
        result = agent.invoke(payload, config)
        payload = None
        if "__interrupt__" in result:
            decisions = []
            for req in result["__interrupt__"][0].value["action_requests"]:
                ok = input(f"   send {req['args'].get('button')}? [y/n] ").strip().lower().startswith("y")
                decisions.append({"type": "approve"} if ok else
                                 {"type": "reject", "message": "The user did not send it."})
            payload = Command(resume={"decisions": decisions})
            continue
        print(f"agent> {result['messages'][-1].text}\n")


if __name__ == "__main__":
    main()
