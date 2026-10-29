# Remote DNA agent

A conversation that rebuilds a lost TV remote. The user describes the TV, or
types the model number from its label; the agent finds where the TV listens,
sends one code at a time **only after the user says yes**, records what the
TV really did, and uses the DNA model to guess the remaining buttons.

Built in the last week of the Thirduni programme (October 2026), following
LangChain Academy's agent course, with Claude Code. The DNA model in `dna/`
existed before; this folder is new.

| Course class | Where it is |
|---|---|
| Foundational models | `create_agent` with Gemini; timeout, retries and a rate limiter on the model |
| Tools | `find_model`, `brand_addresses`, `predict_buttons` over the catalogue (`tools.py`) |
| Short-term memory, state | `RemoteState` keeps the address and the confirmed buttons; a checkpointer keeps the conversation |
| MCP | `mcp_server.py` offers the read-only tools to any MCP client |
| Human in the loop | `HumanInTheLoopMiddleware` pauses before every `send_code` |

## Run it

```
pip install -r agent/requirements.txt     # Python 3.12 or 3.13
echo GOOGLE_API_KEY=your-key > .env       # free key: aistudio.google.com/apikey
python -m agent.chat                      # talk to it; the TV is a virtual IRIS 43G7200
python -m agent.mcp_server                # or plug the tools into Claude, Cursor or Codex
```

The default model is `gemini-3.1-flash-lite` (free tier). Any LangChain model
works: `REMOTE_DNA_MODEL=anthropic:claude-...` or `openai:...` in `.env`.

## What it is not

- The virtual TV answers with a catalogue remote on the TV's address, so the
  demo shows the conversation, not the model's accuracy. Accuracy is measured
  on held-out brands by `python -m dna.evaluate` (see the main README).
- In the app the phone's infrared emitter sends the code; here `send_code`
  calls whatever sender it is given.

## Safety

- Nothing is sent without the user's approval; a refusal sends nothing
  (`tests/test_agent_flow.py`).
- Label text is treated as data, not instructions (system prompt).
- The key lives in `.env`, which git ignores. The MCP server cannot send codes.
