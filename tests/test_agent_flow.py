"""The agent's loop with a scripted model: no network, no key.

Checks the parts a demo cannot prove: nothing reaches the TV without the
user's yes, a refusal sends nothing, and confirmed buttons live in the state.
Skipped when the agent's packages (agent/requirements.txt) are not installed,
so the standard-library CI still runs everything else.
"""
import unittest

try:
    from langchain.messages import AIMessage, HumanMessage
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
    from langgraph.types import Command

    from agent.remote_agent import build_agent, photo_message
except ImportError:  # pragma: no cover
    GenericFakeChatModel = None


def call(name, args, i):
    return AIMessage("", tool_calls=[{"name": name, "args": args, "id": f"call_{i}"}])


if GenericFakeChatModel is not None:
    class ScriptedModel(GenericFakeChatModel):
        def bind_tools(self, tools, **kwargs):
            return self


@unittest.skipIf(GenericFakeChatModel is None, "agent packages not installed")
class AgentFlowTest(unittest.TestCase):
    def run_session(self, decision):
        sent = []
        script = iter([
            call("find_model", {"label_text": "43G7200"}, 1),
            call("choose_address", {"protocol": "samsung32", "address": 14}, 2),
            call("send_code", {"button": "volUp"}, 3),
            AIMessage("Did the volume go up?"),
            call("confirm_button", {"button": "volUp", "command": 20}, 4),
            AIMessage("Volume up works."),
        ])
        agent = build_agent(model=ScriptedModel(messages=script),
                            sender=lambda p, a, c: sent.append((p, a, c)) or "sent")
        cfg = {"configurable": {"thread_id": "t"}}
        out = agent.invoke({"messages": [HumanMessage("Iris TV, label 43G7200")]}, cfg)
        self.assertIn("__interrupt__", out)
        self.assertEqual(sent, [], "nothing may be sent before the user answers")
        out = agent.invoke(Command(resume={"decisions": [decision]}), cfg)
        return agent, cfg, out, sent

    def test_approved_send_reaches_the_tv_and_the_confirmation_is_remembered(self):
        agent, cfg, out, sent = self.run_session({"type": "approve"})
        self.assertEqual(sent, [("samsung32", 14, 20)])
        out = agent.invoke({"messages": [HumanMessage("yes")]}, cfg)
        self.assertEqual(out["confirmed"], {"volUp": 20})
        self.assertEqual(out["messages"][-1].text, "Volume up works.")

    def test_a_refused_send_never_reaches_the_tv(self):
        _, _, _, sent = self.run_session({"type": "reject", "message": "no"})
        self.assertEqual(sent, [])


    def test_a_label_photo_travels_as_base64_with_its_type(self):
        import base64
        from pathlib import Path

        path = Path(__file__).resolve().parent.parent / "agent" / "labels" / "label-iris.png"
        msg = photo_message(str(path))
        text, image = msg.content
        self.assertEqual(text["type"], "text")
        self.assertEqual((image["type"], image["mime_type"]), ("image", "image/png"))
        self.assertEqual(base64.b64decode(image["base64"]), path.read_bytes())


if __name__ == "__main__":
    unittest.main()
