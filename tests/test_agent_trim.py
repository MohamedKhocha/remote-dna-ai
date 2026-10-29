"""Trimming a long session: the class's test, with a scripted model.

A long session is made on purpose; the old tool answers must be gone before
the model sees the state (it is asked, in effect, "what did the first send
return?" and cannot find it), while the confirmed buttons, kept in state,
survive.
"""
import unittest

try:
    from langchain.messages import AIMessage, HumanMessage, ToolMessage
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

    from agent.remote_agent import build_agent
except ImportError:  # pragma: no cover
    GenericFakeChatModel = None


def call(name, args, i):
    return AIMessage("", tool_calls=[{"name": name, "args": args, "id": f"call_{i}"}])


if GenericFakeChatModel is not None:
    class RecordingModel(GenericFakeChatModel):
        """Plays a script and remembers every message list it was shown."""
        seen: list = []

        def bind_tools(self, tools, **kwargs):
            return self

        def _generate(self, messages, *args, **kwargs):
            RecordingModel.seen.append(list(messages))
            return super()._generate(messages, *args, **kwargs)


@unittest.skipIf(GenericFakeChatModel is None, "agent packages not installed")
class TrimTest(unittest.TestCase):
    def test_old_round_trips_go_before_the_model_sees_them_and_state_survives(self):
        buttons = ["volUp", "volDown", "mute", "ok", "back", "chUp", "chDown", "menu"]
        script, i = [call("choose_address", {"protocol": "samsung32", "address": 14}, 0), AIMessage("Ready.")], 1
        for b in buttons * 3:  # 24 turns, each one confirm round trip and a reply
            script += [call("confirm_button", {"button": b, "command": i}, i), AIMessage(f"{b} noted.")]
            i += 1
        RecordingModel.seen = []
        agent = build_agent(model=RecordingModel(messages=iter(script)))
        cfg = {"configurable": {"thread_id": "long"}}
        agent.invoke({"messages": [HumanMessage("start")]}, cfg)
        for n in range(24):
            out = agent.invoke({"messages": [HumanMessage(f"yes {n}")]}, cfg)

        last_view = RecordingModel.seen[-1]
        first_answers = [m for m in last_view if isinstance(m, ToolMessage) and m.tool_call_id in ("call_0", "call_1")]
        self.assertEqual(first_answers, [], "the first round trips were trimmed before the model saw them")
        self.assertLess(len(last_view), 60, "the model is not resent the whole session")
        self.assertEqual(len(out["confirmed"]), len(buttons), "what matters lives in state and survives")
        self.assertEqual(out["protocol"], "samsung32")
        ids = {c["id"] for m in last_view if isinstance(m, AIMessage) for c in m.tool_calls}
        answers = {m.tool_call_id for m in last_view if isinstance(m, ToolMessage)}
        self.assertEqual(ids, answers, "no call without its answer, no answer without its call")


if __name__ == "__main__":
    unittest.main()
