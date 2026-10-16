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
  is switched off for them.
- **It can lose a session.** When the answers point to the wrong remote, it
  chases it for a few questions before the evidence turns.
- **The simulation assumes perfect answers.** Real users miss a reaction or
  name the wrong button. The app replays and confirms each answer, but the
  model has not been measured against human mistakes yet.
- **The catalogue has errors and gaps.** Brand names in it are unreliable: one
  remote is often sold under many names.
- **Infrared TVs only.** Air conditioners send whole climate states, not
  button codes, and are out of scope.

## Use in the app

The app runs the model on the phone: `app/src/hunter/dna.ts` in the app's
private repository, a port of this code. It reads the three settings from a
file exported by `python -m dna.export` and is tested against 40 sessions
recorded here, step by step.

- No data leaves the phone; there is no server call.
- It only reorders codes. Power and source codes are never moved forward, and
  nothing is saved without the user confirming it.
- Any error leaves the app's usual order in place.
