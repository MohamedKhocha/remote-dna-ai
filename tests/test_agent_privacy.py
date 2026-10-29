"""Personal data typed by mistake never reaches the model (PIIMiddleware)."""
import unittest

try:
    from langchain.messages import AIMessage, HumanMessage
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

    from agent.remote_agent import build_agent
except ImportError:  # pragma: no cover
    GenericFakeChatModel = None

if GenericFakeChatModel is not None:
    class Seeing(GenericFakeChatModel):
        seen: list = []

        def bind_tools(self, tools, **kwargs):
            return self

        def _generate(self, messages, *args, **kwargs):
            Seeing.seen.append(" ".join(m.text for m in messages))
            return super()._generate(messages, *args, **kwargs)


@unittest.skipIf(GenericFakeChatModel is None, "agent packages not installed")
class PrivacyTest(unittest.TestCase):
    def test_email_phone_and_card_are_redacted_but_the_model_number_is_kept(self):
        Seeing.seen = []
        agent = build_agent(model=Seeing(messages=iter([AIMessage("Thanks.")])), strong_model=None)
        text = ("My TV is an Iris, MODEL: 43G7200. Call me on 0661 23 45 67 or +213 661234567, "
                "mail me at amine.k@example.com, my card is 4111 1111 1111 1111.")
        agent.invoke({"messages": [HumanMessage(text)]}, {"configurable": {"thread_id": "pii"}})
        sent = Seeing.seen[-1]
        for secret in ("0661 23 45 67", "661234567", "amine.k@example.com", "4111 1111 1111 1111"):
            self.assertNotIn(secret, sent)
        self.assertIn("REDACTED", sent)
        self.assertIn("43G7200", sent, "model numbers must survive: they are what the agent needs")


if __name__ == "__main__":
    unittest.main()
