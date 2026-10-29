"""The dynamic middleware, with scripted models: no network, no key."""
import unittest

try:
    from langchain.messages import AIMessage, HumanMessage
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

    from agent.remote_agent import RemoteContext, build_agent
except ImportError:  # pragma: no cover
    GenericFakeChatModel = None


def call(name, args, i):
    return AIMessage("", tool_calls=[{"name": name, "args": args, "id": f"call_{i}"}])


if GenericFakeChatModel is not None:
    class Seeing(GenericFakeChatModel):
        """Remembers the tools and the system prompt of every call it answers."""
        log: list = []
        tag: str = "small"

        def bind_tools(self, tools, **kwargs):
            Seeing.log.append((self.tag, [getattr(t, "name", None) or t.get("name") for t in tools]))
            return self

        def _generate(self, messages, *args, **kwargs):
            Seeing.log.append((self.tag, messages[0].text if messages else ""))
            return super()._generate(messages, *args, **kwargs)


@unittest.skipIf(GenericFakeChatModel is None, "agent packages not installed")
class DynamicTest(unittest.TestCase):
    def setUp(self):
        Seeing.log = []

    def run_once(self, ctx, script, strong=None, thread="d"):
        agent = build_agent(model=Seeing(messages=iter(script)), strong_model=strong)
        return agent.invoke({"messages": [HumanMessage("hi")]}, {"configurable": {"thread_id": thread}}, context=ctx)

    def test_the_prompt_follows_the_users_language(self):
        self.run_once(RemoteContext(language="fr"), [AIMessage("Bonjour.")])
        prompts = [x for _, x in Seeing.log if isinstance(x, str)]
        self.assertTrue(any("The user's language is French" in p for p in prompts))

    def test_a_phone_without_an_emitter_never_sees_send_code(self):
        self.run_once(RemoteContext(phone_has_ir=False), [AIMessage("No emitter.")])
        tool_lists = [x for _, x in Seeing.log if isinstance(x, list)]
        self.assertTrue(tool_lists)
        self.assertTrue(all("send_code" not in t for t in tool_lists))
        self.assertTrue(all("find_model" in t for t in tool_lists))

    def test_a_stuck_session_moves_to_the_stronger_model(self):
        strong = Seeing(messages=iter([AIMessage("Strong model here.")]), tag="strong")
        script = [
            call("choose_address", {"protocol": "nec", "address": 1}, 1), call("rule_out_address", {}, 2),
            call("choose_address", {"protocol": "nec", "address": 2}, 3), call("rule_out_address", {}, 4),
        ]
        out = self.run_once(RemoteContext(), script, strong=strong)
        self.assertEqual(len(out["ruled_out"]), 2)
        self.assertEqual(out["messages"][-1].text, "Strong model here.")
        answered = [tag for tag, x in Seeing.log if isinstance(x, str)]
        self.assertEqual(answered.count("small"), 4)
        self.assertEqual(answered[-1], "strong")


if __name__ == "__main__":
    unittest.main()
