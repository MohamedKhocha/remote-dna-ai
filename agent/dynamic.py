"""The agent changes with who is asking (the dynamic-agents class).

One wrap-style middleware, around every model call:

1. The prompt follows the user's language, read from the runtime context.
2. A phone without an infrared emitter never sees send_code, and if the model
   calls it anyway (it can: it knows the name from the prompt; the attack in
   agent/attack.py did exactly that), the call is refused where tools run.
   Hiding a tool from the model is not a lock; refusing it at execution is.
3. The model escalates when the session gets hard. Flash-Lite answers by
   default; once two addresses have been ruled out (a TV the catalogue knows
   badly), a stronger model takes over. Short, easy sessions stay cheap.
"""
from __future__ import annotations

from langchain.agents.middleware import AgentMiddleware
from langchain.messages import SystemMessage, ToolMessage

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

    @staticmethod
    def _no_emitter(runtime) -> bool:
        ctx = runtime.context if runtime is not None else None
        return ctx is not None and getattr(ctx, "phone_has_ir", True) is False

    def _refuse(self, request):
        if request.tool_call["name"] == "send_code" and self._no_emitter(request.runtime):
            return ToolMessage("Refused: this phone has no infrared emitter, so no code can be sent.",
                               tool_call_id=request.tool_call["id"], name="send_code", status="error")
        return None

    def wrap_tool_call(self, request, handler):
        return self._refuse(request) or handler(request)

    async def awrap_tool_call(self, request, handler):
        return self._refuse(request) or await handler(request)

    def wrap_model_call(self, request, handler):
        return handler(self._adapt(request))

    async def awrap_model_call(self, request, handler):
        return await handler(self._adapt(request))
