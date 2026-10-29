# Threat model

What could go wrong with the Remote DNA model and the way the app uses it,
worked through with STRIDE. Scope: this repository, the exported model file,
and the code in the app that runs it.

## Assets

- **The user's TV and their trust in the app.** A wrong code can switch the TV
  off or change its input in the middle of a session.
- **The user's privacy.** Which TV they own and which codes it answers to.
- **The integrity of the model.** Its settings and the catalogue it reasons
  from.
- **This repository**, published for evaluation.

## STRIDE

| Threat | What it would look like here | What stops it |
|---|---|---|
| **Spoofing** | A fake model file passed off as ours | The app does not download models. The file is bundled at build time, so replacing it means shipping a new app through Google Play. A future remote update would have to be signed and checked on the phone, with the bundled copy as fallback |
| **Tampering** | Someone changes the catalogue or the settings so the model favours harmful codes | `catalogue_sha256` in the exported file, and the app's test checks its catalogue has the same hash. The parity tests fail if the phone's numbers drift from the Python's. Changes go through commits and CI |
| **Repudiation** | Not knowing which model a given app version runs | The exported file names the commit it came from and the catalogue hash |
| **Information disclosure** | Codes or device details leaving the phone | The model runs on the phone with no network call. The training data contains no user data. Secret scanning and push protection are on for this repository, which holds no keys at all |
| **Denial of service** | The model making a session hang or crash the app | Work per answer is bounded by the catalogue size. Any exception leaves the usual order in place. Sessions give up after 300 questions in the simulation; in the app the user can stop at any time |
| **Elevation of privilege** | The model doing more than suggest an order | It only reorders codes the app was going to try anyway. Power and source codes, as known for that address, are never moved forward. Nothing is saved unless the user confirmed it |

## The agent (`agent/`, demo part 4)

A language model now chooses which tool to call, so the threats change:

| Threat | What it would look like here | What stops it |
|---|---|---|
| **Prompt injection** | Text on a label, or typed into the chat, tells the agent to send codes on its own or to ignore the user | The model can only *ask* to send: `HumanInTheLoopMiddleware` pauses before every `send_code`, and the page sends nothing without a click. A refusal sends nothing (`tests/test_agent_flow.py`). The system prompt treats label text as data |
| **A confident wrong answer** | The agent says a button works when it does not | A button is recorded only by `confirm_button`, which the prompt allows only after the user says the TV reacted; the summary lists confirmed buttons only |
| **Information disclosure** | The Gemini key leaking | Python reads it from `.env`, which git ignores. The demo page keeps the visitor's key in memory, never stores it, and sends it only to Google's API. The repository holds no key; secret scanning is on |
| **Denial of service** | A slow or busy model service | Timeout, three retries and a rate limiter on the model; at most 12 model calls per turn on the page |
| **Elevation of privilege** | Another agent using the MCP server to act on a TV | The MCP server is read-only: lookups and predictions, no send |

What the agent sends to Google: the conversation, the model number typed, and
the tool results (addresses and command numbers). Nothing else about the user.

## Data poisoning, later

Today the model learns from the published catalogue only. If confirmed remotes
from users are added later, a few false contributions could steer it. The plan
for that day: train offline, use only remotes confirmed by a minimum number of
different contributors (the app's backend already applies such a threshold to
its community catalogue), and keep the bundled model as the reviewed baseline.

## What is not covered

The app's other features, its backend and its payment flow are outside this
repository and have their own review.
