# Remote DNA AI

The learning part of [REMOTE DNA](https://play.google.com/store/apps/details?id=com.beinteck.remotedna),
an Android app that turns a phone into the remote for a TV or air conditioner.

## The problem

When a remote is lost or broken, a TV that works becomes unusable. Remote apps
carry lists of codes for global brands, but many sets sold in Algeria and North
Africa carry local brand names that no list knows. The same holds in Latin America:
Semp, Noblex, Kalley, Caixun and Multilaser have no code set in this
catalogue, and Philco, BGH and AOC have one each.

REMOTE DNA already handles such a TV: it finds the address the TV listens on,
then learns the buttons one at a time by asking the user what the TV did. That
works, and it is slow, because one address is often shared by dozens of
different remotes that give the same command numbers to different buttons.

## What this repository does

It asks one question: **once a few buttons are confirmed, how much of the rest
of the remote can be predicted?** Every button predicted correctly is a question
the user is not asked.

Status, 18 October 2026: the model is evaluated, merged into the app, and
ships in REMOTE DNA since 1.0.8. On a real Iris 43G7200 TV, "Teach my TV" with
the model on found the TV and learned its buttons. Version 1.0.9 added the
model-number search (photograph the label, or type the number); 1.0.10, built
on 18 October, replaces the thirty-question deep search with one tap.

Update, 29 October: an **agent** (`agent/`) puts these pieces in a
conversation. The user describes the TV or types the model number; a language
model finds where the TV listens, sends one code at a time only after the user
says yes, records what the TV really did, and uses the DNA model for the rest.
It runs in a terminal, as an MCP server for other agents, and live on the demo
page. See [`agent/README.md`](agent/README.md).

Update, 30 October: the agent now applies every class of LangChain's agent
course, each with a test and a measured result: a label photo, runtime context
(country, language, whether the phone has an emitter), a sub-agent that
identifies the TV, limits the model cannot talk past, trimmed long sessions
(32% fewer messages resent), approve / reject / edit before every send, a
stronger model only when a session is stuck, redaction of personal data before
anything reaches the model, and attacks run against it (one found a real hole:
a hidden tool was still callable, now refused where tools run). The same week,
STRIDE and OWASP were run on the app's live server (private repository): four
issues found, fixed and deployed. The agent's own threats are in
[`THREAT_MODEL.md`](THREAT_MODEL.md). 70 tests pass here.

## Results so far

The test is a TV whose brand is in no list: every remote of the target's brand
is removed from the catalogue, the first buttons the app would learn are
revealed, and the rest are guessed. The model's three settings were chosen on
one half of the brands. The numbers below are from the other half, which
nothing was tuned on.

Every remote (635 of them):

| Confirmed buttons | most_common | exact_match | mixture |
|---|---|---|---|
| 1 | 37.8% | 42.7% | 44.6% |
| 2 | 38.0% | 42.4% | 46.5% |
| 3 | 38.2% | 41.5% | 47.1% |
| 5 | 38.5% | 42.2% | 51.3% |

Remotes whose address another brand also uses (416):

| Confirmed buttons | most_common | exact_match | mixture |
|---|---|---|---|
| 1 | 53.8% | 60.8% | 60.3% |
| 2 | 53.8% | 60.1% | 62.3% |
| 3 | 53.8% | 58.5% | 61.9% |
| 5 | 53.7% | 58.9% | 65.6% |

Remotes alone on their address (219):

| Confirmed buttons | most_common | exact_match | mixture |
|---|---|---|---|
| 1 | 0.0% | 0.0% | 7.6% |
| 2 | 0.0% | 0.0% | 8.5% |
| 3 | 0.0% | 0.0% | 11.2% |
| 5 | 0.0% | 0.0% | 15.1% |

Each cell is the share of the remaining buttons guessed with the right command.

- `most_common` is what the app does today: the most frequent command for each
  button on that address, whatever is already known.
- `exact_match` votes only among remotes on that address that agree with every
  confirmed button.
- `mixture` is the model. Every catalogue remote that resembles the one being
  rebuilt votes with a weight: full weight on the same address, a small one on
  another address if it shares a confirmed button, and less for each confirmed
  button it gets wrong.

What this says, plainly:

- The model is the only one that gets better as buttons are confirmed: from
  44.6% after one button to 51.3% after five, where the app's current method
  stays near 38%.
- After a single button it is barely ahead of exact matching, and slightly
  behind it on shared addresses. One button is not enough to rebuild a remote.
- A third of the remotes sit alone on their address. Today's method can say
  nothing about them. Looking at layouts on other addresses recovers a little,
  7.6% to 15.1%, and that is the weakest part of the model and the one that
  matters most for an unknown TV.

## Questions asked until the remote works

The share of buttons guessed right is a means. What a user feels is how many
times the app asks "what did the TV do?". `dna/simulate.py` replays a "Teach my
TV" session on every remote of the held-out half: one command per question,
until volume up, volume down, mute, OK and back are all found.

| Remotes | Sessions | Today: mean | Today: median | Model: mean | Model: median |
|---|---|---|---|---|---|
| Every remote | 597 | 58.3 | 36 | 50.7 | 29 |
| Address shared with another brand | 390 | 48.9 | 26 | 37.2 | 8 |
| Alone on its address | 207 | 76.0 | 49 | 76.0 | 49 |

Sessions still unfinished after 300 questions: today 21, model 15.

- "Today" is the app's current order, fixed before the first question.
- "Model" re-ranks the untried commands after every answer, and learns from
  "nothing happened" as well: a remote that uses that command for any button
  cannot be this TV's.
- Where another brand shares the address, the typical session drops from 26
  questions to 8, and the total number of questions by about a quarter.
- That is an average, not a promise for every TV. Session by session, the
  model asked fewer questions in 114 cases, the same number in 168 and more in
  108. It wins big when it recognises the remote and loses a few questions
  when it chases the wrong one.
- Where the TV is alone on its address, the app keeps today's order. On the
  tuning half, letting the model steer there lost more sessions than it won
  (53 against 21) and saved nothing overall. Treating NEC remotes that share
  the low byte of the address as neighbours did not help either (28 won, 29
  lost on the tuning half). Neither did ordering the sweep by how often the
  protocol's remotes use each command: it won on the tuning half and lost on
  the held-out half (median 49 questions up to 84). Both attempts are in
  `MODEL_CARD.md`. This is the open problem.

## Skipping the search: the model number

The fastest session asks no question at all. Most TVs carry their model
number on a label at the back, and Flipper-IRDB names each of its dumps after
the TV or remote it came from. `data/models.json` keeps those names: 253 dumps
from 64 brands, plus TVs tested by hand: an IRIS 43G7200, whose infrared
remote the app carries, and an IRIS 43E6A, an Android TV that the app pairs
with over Wi-Fi. In the app, ML Kit reads the label from a photo on the phone
(the photo is deleted once read), and `dna/models.py`'s search, mirrored in the
app, turns the text into a remote that one press of power confirms, or into
the Android TV pairing.

The labels of those two TVs shaped the rules. The 43G7200 prints its model with
no "Model" word, next to "100-240V~50/60Hz", which also mixes letters and
digits; so electrical ratings and serial-number lines are skipped. Both labels
are in the tests.

`python -m dna.models` checks the search alone: for every indexed model, is
the right remote returned for a clean label, for one with a region suffix the
index lacks, and for one with a character misread as its look-alike (0 and O,
1 and I, 5 and S, 8 and B, 2 and Z), and for the same model in a screen size
the index lacks (the leading digits of 43G7200 are its size; one remote drives
every size)?

| Label | Models | Right remote first | In the top 3 |
|---|---|---|---|
| clean | 254 | 99.6% | 99.6% |
| suffix | 254 | 96.9% | 96.9% |
| misread | 254 | 96.1% | 96.1% |
| other size | 51 | 100.0% | 100.0% |

What this does not say: how often a real TV is in the index. For the global
brands sold in Algeria (Samsung, LG, Hisense, TCL) it sometimes is; for local
brands it almost never is yet: Brandt has two dumps, and Condor, Iris, Stream
and Skyworth none. Each TV a user teaches and chooses to share can add its
model, which is how that gap closes. How well ML Kit reads real labels on the
phone is measured on the device, not here.

## A TV no remote knows: one tap instead of thirty questions

Before any button is learned, the app must find the address the TV listens
on. When no catalogue address reaches it, as with a real Stream TV, the app
tries the 720 addresses no catalogue remote uses, with number keys.

Up to 1.0.9 that took batches of 24 addresses and one "did anything happen?"
per batch: up to 37 answers, nearly all of them "no". A yes/no answer carries
at most one bit. Since 1.0.10 the phone sends every address back to back
without stopping, and the user taps "I saw it!" once, when the channel number
changes. The moment of the tap points to the few sends on air in the 3
seconds before it, about six bits in a single gesture; a replay, a halving
and a confirmation settle them. The sweep goes over every address with one
number key, then again with a second, chosen by greedy set cover, so most
TVs are found in the first pass.

`python -m dna.sweep` replays it for a TV on every one of the 720 addresses,
using the app's own frame timings:

| Search | Answers: mean | Answers: max | Time: mean | Missed |
|---|---|---|---|---|
| Batches of 24 (up to 1.0.9) | 22.2 | 37 | 158 s | 0 |
| Sweep, TV knows the first key, tap 0.7 s late | 7.4 | 9 | 66 s | 0 |
| Sweep, TV knows the first key, tap 1.8 s late | 8.0 | 9 | 69 s | 0 |
| Sweep, TV knows only the second key, tap 1.8 s late | 8.0 | 9 | 138 s | 0 |

Answers include the tap. Times assume 2.5 s to look and answer each question.

- A stray tap costs two answers, then the sweep carries on.
- A tap more than 3 s late misses the TV: the one failure case.
- The two keys reach 69% of the catalogue's NEC remotes and 94% to 100% of
  the other protocols'; a TV that knows neither does not react.
- These are simulated hands. The first real test is the Stream TV.

## Live demo

`demo/index.html` (live at https://mohamedkhocha.github.io/remote-dna/demo/)
has four parts, each running the same code as the Python, in JavaScript:

1. **Learning the buttons:** pick any remote, and the page plays the TV while
   today's order and the model race side by side, with the reason for each
   of the model's choices (`demo/dna.js`).
2. **Deep search:** the page hides a TV on one of the 720 unknown addresses,
   sends them in real time, and the visitor taps "I saw it!" when the drawn
   TV's channel number changes; the replay, halving and confirmation follow,
   next to what the old batch search would have asked (`demo/sweep.js`).
3. **Find by model:** type a model number or paste a label's text
   (`demo/models.js`). Reading a photo needs ML Kit, which runs only in the
   app.
4. **The agent:** replay a real recorded session, or talk to it live with your
   own free Gemini key (kept in the tab, sent only to Google's API). Every
   code waits for your click (`demo/agent.js`, `demo/agent-ui.js`).

`tests/test_parity.py` checks that all four give exactly the same answers
as the Python: every remote's session, more than a thousand model searches,
160 deep searches with three different hands, and 600 of the agent's
predictions.

To run it locally, serve the repository root and open the demo:

```
python -m http.server 8000
# then open http://localhost:8000/demo/
```

## Run it

Python 3.11 or later. No dependencies.

```
python -m unittest        # tests
python -m dna.evaluate    # the tables above (the held-out half)
python -m dna.evaluate --fold all
python -m dna.simulate    # questions per session (the held-out half)
python -m dna.models      # model-number search under simulated misreads
python -m dna.sweep       # deep search: the sweep against the batches it replaced
```

The agent needs a few packages and a free Gemini key (`agent/README.md`):

```
pip install -r agent/requirements.txt
echo GOOGLE_API_KEY=your-key > .env
python -m agent.chat         # the agent in a terminal, with a virtual TV
python -m agent.mcp_server   # its read-only tools for any MCP client
python -m agent.team         # the same agent as a team (identifier + main agent)
python -m agent.attack       # talk to it as an attacker; every send is refused
```

## Layout

| Path | What it is |
|---|---|
| `data/catalogue.json` | Known remotes: protocol, address, button to command |
| `data/models.json` | Model numbers (TVs and remotes) and the remote each points to |
| `dna/models.py` | Model-number search, and its check under simulated misreads |
| `experiments/` | Ideas measured and not kept, with their numbers |
| `dna/catalogue.py` | Loads the catalogue and folds exact duplicates |
| `dna/predict.py` | The baseline, exact matching, and the model (`mixture`) |
| `dna/simulate.py` | Replays a teach session and counts the questions |
| `dna/sweep.py` | The deep search: the sweep and the tap, against the old batches |
| `dna/export.py` | Writes the settings and parity fixture the phone app uses |
| `export/` | Those two files |
| `demo/` | The browser demo: the model, the deep search, the model-number search and the agent in JavaScript |
| `agent/` | The agent: LangChain tools over the model, human approval of every send, an MCP server |
| `dna/evaluate.py` | Evaluation with the target's brand removed, on a fixed half of the brands |
| `tests/` | Unit tests, including one that the held-out brand cannot leak |

## In the app

Since version 1.0.8, the app runs the model on the phone, in its "Teach my TV" feature: after every
answer, the codes the model believes in move to the front of what is left to
try. `python -m dna.export` writes the settings the app bundles and 40
recorded sessions its tests replay step by step, so the phone and this
repository cannot drift apart. Since 1.0.9 the app also searches by model
number, reading the label with ML Kit on the phone; since 1.0.10 its deep
search is the sweep above. See `MODEL_CARD.md` for what it does and does
not do, and `THREAT_MODEL.md` for how it is kept safe.

## What existed before, and what is built here

- **Before the Thirduni project month:** the REMOTE DNA app (published on Google
  Play on 4 October 2026), its infrared engine, and the catalogue in `data/`.
  The app's source code is private and is not part of this repository.
- **Built during the project month:** everything else in this repository, and
  in the app the code that runs the model, the model-number search with its
  on-phone label reading (1.0.9), and the deep-search sweep (1.0.10).
- **Built in the last week (29 October):** the agent in `agent/` and the
  demo page's fourth part, while following LangChain Academy's agent course
  in the programme's third week.

## Who built what

Mohamed Khocha, alone, with Claude Code (Anthropic's coding agent) as the
assistant that wrote most of the code under his direction.

- **Mohamed Khocha:** the product and the problem; the decision to measure
  questions per session rather than accuracy alone; the request for a deep
  search that saves both time and questions; the choice to read labels on the
  phone, offline; testing on real TVs (an Iris 43G7200 on a Skyworth chassis,
  an Iris 43E6A Android TV and a Stream TV) and photographing their labels; the
  go/no-go on every result; the app; the idea of turning the course's agent
  lessons into an agent for this product.
- **Claude Code:** the evaluation method, the model, the simulation, the
  model-number search, the sweep and its simulation, the JavaScript and
  TypeScript ports with their parity tests, the demo page, the agent and
  the documentation, each reviewed and run before it was committed.

## What happens next

Help the third of TVs that sit alone on their address, starting with code
layouts shared across addresses. Measure the model against real users'
mistakes, not only perfect answers. Feed it remotes confirmed in the app,
with the safeguards in `THREAT_MODEL.md`. Bring the same approach to air
conditioners.

## Rights

See `NOTICE` for the source code and `DATA.md` for the catalogue.
