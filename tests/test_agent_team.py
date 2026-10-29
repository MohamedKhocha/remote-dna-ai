"""The multi-agent split, with scripted models: no network, no key.

The main agent reaches the identifier only through identify_tv, sees only its
final answer (the multi-agent class's warning), and still cannot send a code
without the user's yes.
"""
import unittest

try:
    from langchain.messages import AIMessage, HumanMessage
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
    from langgraph.types import Command

    from agent.team import build_team
except ImportError:  # pragma: no cover
    GenericFakeChatModel = None


def call(name, args, i):
    return AIMessage("", tool_calls=[{"name": name, "args": args, "id": f"call_{i}"}])


if GenericFakeChatModel is not None:
    class ScriptedModel(GenericFakeChatModel):
        def bind_tools(self, tools, **kwargs):
            return self


@unittest.skipIf(GenericFakeChatModel is None, "agent packages not installed")
class TeamTest(unittest.TestCase):
    def test_the_identifier_works_behind_one_tool_and_sending_still_waits(self):
        identifier = ScriptedModel(messages=iter([
            call("find_model", {"label_text": "MODEL: 43G7200"}, 1),
            AIMessage("IRIS 43G7200: samsung32 address 14."),
        ]))
        main = ScriptedModel(messages=iter([
            call("identify_tv", {"description": "Iris TV, label MODEL: 43G7200"}, 2),
            call("choose_address", {"protocol": "samsung32", "address": 14}, 3),
            call("send_code", {"button": "volUp"}, 4),
            AIMessage("Did the volume go up?"),
        ]))
        sent = []
        team = build_team(model=main, identifier_model=identifier,
                          sender=lambda p, a, c: sent.append((p, a, c)) or "sent")
        cfg = {"configurable": {"thread_id": "team"}}
        out = team.invoke({"messages": [HumanMessage("My Iris TV, label MODEL: 43G7200")]}, cfg)

        answer = next(m for m in out["messages"] if getattr(m, "name", None) == "identify_tv")
        self.assertEqual(answer.text, "IRIS 43G7200: samsung32 address 14.")
        names = {getattr(m, "name", None) for m in out["messages"]}
        self.assertNotIn("find_model", names, "the identifier's own tool calls stay inside it")
        self.assertIn("__interrupt__", out)
        self.assertEqual(sent, [])

        team.invoke(Command(resume={"decisions": [{"type": "approve"}]}), cfg)
        self.assertEqual(sent, [("samsung32", 14, 20)])

    def test_the_main_agent_no_longer_carries_the_lookup_tools(self):
        team = build_team(model=ScriptedModel(messages=iter([AIMessage("hi")])),
                          identifier_model=ScriptedModel(messages=iter([AIMessage("-")])))
        tools = set(team.nodes["tools"].bound.tools_by_name)
        self.assertIn("identify_tv", tools)
        self.assertFalse({"find_model", "brand_addresses"} & tools)


if __name__ == "__main__":
    unittest.main()
