# Model card: Remote DNA

## What it does

While the REMOTE DNA app teaches itself an unknown TV, it sends one infrared
code at a time and the user says what the TV did. This model chooses which
code to send next, so that the buttons the user needs are found with fewer
questions.

## How it works

It is a weighted nearest-neighbour vote, not a neural network.

1. Every catalogue remote speaking the TV's protocol is a candidate.
2. A candidate on the TV's own address starts at weight 1. One on another
   address starts at 0.05 and only counts once it has agreed with an answer.
3. After each answer, a candidate keeps 95% of its weight if it agrees, keeps
   5% if it contradicts it, and keeps half if it does not have that button.
   "Nothing happened" is an answer too: a candidate that uses that code for
   any button keeps 5%.
4. Each untried code is scored by the summed weight of the candidates that use
   it for a button still missing. The highest score is sent next.

Every choice can be traced back to the remotes that voted for it, and the demo
shows them.

## Data

`data/catalogue.json`: 1,280 code sets for 465 brands, 1,258 after folding
exact duplicates, built from Flipper-IRDB (CC0) and irdb (see `DATA.md`). It
contains no data from users of the app.

## How the settings were chosen and tested

The brands are split in two halves by a hash of the brand name (fold 0 and
fold 1). The three settings were chosen by looking at fold 0 only. Every number
reported in the README comes from fold 1, which nothing was tuned on.

For each test remote, every remote of its brand is removed from the catalogue
first, so the test is a TV whose brand no list knows.

## Results (fold 1)

| Measure | Today's order | Model |
|---|---|---|
| Buttons guessed right after 1 / 5 confirmed | 37.8% / 38.5% | 44.6% / 51.3% |
| Questions until the essentials are found, median, address shared with another brand (390 TVs) | 26 | 8 |
| Same, total over those 390 TVs | 100% | about 76% |
| Same, address used by no other brand (207 TVs) | 49 | 49 (model off) |

Session by session on shared addresses, the model asked fewer questions in
114 cases, the same in 168 and more in 108.

## Limitations

- **TVs alone on their address get no help.** A third of the catalogue. On the
  tuning half, letting the model steer there lost 53 sessions and won 21, so it
  is switched off for them. One idea was tried and failed: most of these are
  NEC remotes, and NEC receivers that read only the low byte of the address
  could be served by remotes sharing that byte. On the tuning half (63 such
  TVs) the model then won 28 sessions and lost 29, with no change in the
  median, so it was not kept and the held-out half was not used for it.
  A second idea also failed: instead of sweeping commands 0, 1, 2…, try
  first the commands the protocol's remotes use most, at any address, and
  those mostly used for power last (`experiments/lone_prior.py`). On the
  tuning half it looked good (median 52 questions down to 32; 68 sessions
  won, 29 lost), so it was measured once on the held-out half, where it was
  worse (median 49 up to 84; 88 won, 112 lost). It was not kept.
- **It can lose a session.** When the answers point to the wrong remote, it
  chases it for a few questions before the evidence turns.
- **Asking the most informative question did not help.** Adding information
  gain to the choice (the expected drop in entropy over the remotes still in
  play, weighted against the chance of a hit; `experiments/info_gain.py`)
  asked more questions in total on the tuning half at every weight tried
  (16,713 questions with today's rule; 16,904 to 17,169 with information
  gain), and lost more sessions than it won. The held-out half was not used.
  The likely reason: the goal is to find a few buttons, not to name the
  remote, and today's rule already aims at the buttons directly.
- **The simulation assumes perfect answers.** Real users miss a reaction or
  name the wrong button. The app replays and confirms each answer, but the
  model has not been measured against human mistakes yet.
- **The catalogue has errors and gaps.** Brand names in it are unreliable: one
  remote is often sold under many names.
- **Infrared TVs only.** Air conditioners send whole climate states, not
  button codes, and are out of scope.

## Before the model: a TV on an address nobody uses

The model needs the TV's address. When no catalogue address reaches the TV,
the app searches the 720 addresses no catalogue remote uses (`dna/sweep.py`).
This part is a search procedure, not a learned model: it is measured with the
same discipline, and it is not tuned on anything.

- **Before (up to 1.0.9):** batches of 24 addresses, one "did anything
  happen?" per batch. 22.2 answers on average, 37 at worst, about 158 s.
- **Since 1.0.10:** one continuous sweep, and the user taps "I saw it!" when
  the channel number changes. The time of the tap picks the sends on air in
  the 3 s before it; a replay, a halving and a confirmation settle them. 7.4
  to 8.0 answers on average (tap included), 9 at worst; about 66 to 69 s when
  the TV knows the first probe, 135 to 138 s when it knows only the second.
  No TV missed with the hand tapping 0.3 to 2.5 s late.

Limitations of the sweep:

- **A hand more than 3 s late misses the TV.** The window would not contain
  it; the replay says "nothing", and the sweep carries on past it.
- **Simulated, not yet measured on people.** The time to look and answer
  (2.5 s) and the hand's delay are assumptions. The first real test is a
  Stream TV that no catalogue address reached.
- **Two probes reach 69% of the catalogue's NEC remotes** (262 of 382). A
  TV whose remote knows neither probe does not react. Samsung32 and RC6 are
  covered at 100%, RC5 at 97%, Sony at 94%. The app picks its probes from
  its own copy of the catalogue (duplicates kept, plus its Skyworth sets), so
  a probe can differ from the one picked here; the procedure is the same, and
  the app's tests give the same answer counts and times.

## Use in the app

The app runs the model on the phone: `app/src/hunter/dna.ts` in the app's
private repository, a port of this code. It reads the three settings from a
file exported by `python -m dna.export` and is tested against 40 sessions
recorded here, step by step.

- No data leaves the phone; there is no server call.
- It only reorders codes. Power and source codes are never moved forward, and
  nothing is saved without the user confirming it.
- Any error leaves the app's usual order in place.
- The sweep runs in `app/src/hunter/teach.ts` (`startSweep`, `sweepSuspects`,
  `tapSweep`), and its tests replay the same simulated TVs and hands.
