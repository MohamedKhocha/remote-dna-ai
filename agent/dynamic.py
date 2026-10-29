"""The agent changes with who is asking (the dynamic-agents class).

One wrap-style middleware, around every model call:

1. The prompt follows the user's language, read from the runtime context.
2. A phone without an infrared emitter never sees send_code: the tool is not
   there, so the model cannot even ask to use it.
3. The model escalates when the session gets hard. Flash-Lite answers by
   default; once two addresses have been ruled out (a TV the catalogue knows
   badly), a stronger model takes over. Short, easy sessions stay cheap.
"""
from __future__ import annotations

from langchain.agents.middleware import AgentMiddleware
from langchain.messages import SystemMessage

LANGUAGES = {"ar": "Arabic", "fr": "French", "en": "English", "es": "Spanish"}
ESCALATE_AFTER = 2  # ruled-out addresses before the stronger model takes over


class DynamicAgent(AgentMiddleware):
    def __init__(self, strong_model=None, escalate_after: int = ESCALATE_AFTER):
        super().__init__()
        self.strong_model = strong_model  # None: never escalate
        self.escalate_after = escalate_after

    def _adapt(self, request):
        ctx = request.runtime.context if request.runtime is not None else None
        changes = {}

        language = LANGUAGES.get(getattr(ctx, "language", None) or "", None)
        if language:
            base = request.system_message.text if request.system_message is not None else ""
            changes["system_message"] = SystemMessage(
                base + f"\n\nThe user's language is {language}: answer in it unless they write in another one.")

        if ctx is not None and getattr(ctx, "phone_has_ir", True) is False:
            changes["tools"] = [t for t in request.tools if getattr(t, "name", None) != "send_code"]

        ruled_out = request.state.get("ruled_out") or []
        if self.strong_model is not None and len(ruled_out) >= self.escalate_after:
            changes["model"] = self.strong_model

        return request.override(**changes) if changes else request

    def wrap_model_call(self, request, handler):
        return handler(self._adapt(request))

    async def awrap_model_call(self, request, handler):
        return await handler(self._adapt(request))
