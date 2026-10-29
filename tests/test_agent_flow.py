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

    from agent.remote_agent import RemoteContext, build_agent, photo_message
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


    def test_context_reaches_the_agent_only_through_its_tool(self):
        script = iter([call("user_context", {}, 1), AIMessage("Je vous réponds en français.")])
        agent = build_agent(model=ScriptedModel(messages=script))
        out = agent.invoke({"messages": [HumanMessage("salut")]}, {"configurable": {"thread_id": "c"}},
                           context=RemoteContext(country="FR", language="fr", phone_has_ir=False))
        tool_msg = next(m for m in out["messages"] if getattr(m, "name", None) == "user_context")
        self.assertIn('"language": "fr"', tool_msg.text.replace("'", '"'))
        self.assertIn('"phone_has_ir": false', tool_msg.text.replace("'", '"').replace("False", "false"))

    def test_a_ruled_out_address_is_not_tested_again(self):
        script = iter([
            call("choose_address", {"protocol": "nec", "address": 4}, 1),
            call("rule_out_address", {}, 2),
            call("choose_address", {"protocol": "nec", "address": 4}, 3),
            AIMessage("That address was already tried."),
        ])
        agent = build_agent(model=ScriptedModel(messages=script))
        out = agent.invoke({"messages": [HumanMessage("nothing happened")]}, {"configurable": {"thread_id": "r"}})
        self.assertEqual(out["ruled_out"], ["nec 4"])
        self.assertIn("already ruled out", out["messages"][-2].text)


    def test_a_protocol_written_by_another_agent_is_normalised(self):
        script = iter([call("choose_address", {"protocol": "Samsung32", "address": 14}, 1), AIMessage("ok")])
        agent = build_agent(model=ScriptedModel(messages=script))
        out = agent.invoke({"messages": [HumanMessage("go")]}, {"configurable": {"thread_id": "n"}})
        self.assertEqual(out["protocol"], "samsung32")


    def test_the_send_limit_stops_a_session_that_keeps_sending(self):
        sent = []
        script = iter([
            call("choose_address", {"protocol": "samsung32", "address": 14}, 1),
            call("send_code", {"button": "volUp"}, 2),
            call("send_code", {"button": "mute"}, 3),
            AIMessage("Stopped."),
        ])
        agent = build_agent(model=ScriptedModel(messages=script), send_limit=1,
                            sender=lambda p, a, c: sent.append(c) or "sent")
        cfg = {"configurable": {"thread_id": "limit"}}
        out = agent.invoke({"messages": [HumanMessage("go")]}, cfg)
        while "__interrupt__" in out:
            n = len(out["__interrupt__"][0].value["action_requests"])
            out = agent.invoke(Command(resume={"decisions": [{"type": "approve"}] * n}), cfg)
        self.assertEqual(sent, [20], "only the first send gets through")

    def test_a_turn_cannot_call_the_model_forever(self):
        loop = iter([call("user_context", {}, i) for i in range(50)])
        agent = build_agent(model=ScriptedModel(messages=loop), turn_limit=3)
        out = agent.invoke({"messages": [HumanMessage("hi")]}, {"configurable": {"thread_id": "turn"}})
        calls = sum(1 for m in out["messages"] if getattr(m, "tool_calls", None))
        self.assertLessEqual(calls, 3)


    def test_an_edited_send_uses_the_users_button_without_asking_again(self):
        sent = []
        script = iter([
            call("choose_address", {"protocol": "samsung32", "address": 14}, 1),
            call("send_code", {"button": "volUp"}, 2),
            AIMessage("Did the TV mute?"),
        ])
        agent = build_agent(model=ScriptedModel(messages=script), sender=lambda p, a, c: sent.append(c) or "sent")
        cfg = {"configurable": {"thread_id": "edit"}}
        out = agent.invoke({"messages": [HumanMessage("go")]}, cfg)
        self.assertIn("__interrupt__", out)
        out = agent.invoke(Command(resume={"decisions": [
            {"type": "edit", "edited_action": {"name": "send_code", "args": {"button": "mute"}}}]}), cfg)
        self.assertEqual(sent, [13], "mute's code, not volume up's")
        self.assertNotIn("__interrupt__", out)


if __name__ == "__main__":
    unittest.main()
