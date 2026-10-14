# Remote DNA AI

The learning part of [REMOTE DNA](https://play.google.com/store/apps/details?id=com.beinteck.remotedna),
an Android app that turns a phone into the remote for a TV or air conditioner.

## The problem

When a remote is lost or broken, a TV that works becomes unusable. Remote apps
carry lists of codes for global brands, but many sets sold in Algeria and North
Africa carry local brand names that no list knows.

REMOTE DNA already handles such a TV: it finds the address the TV listens on,
then learns the buttons one at a time by asking the user what the TV did. That
works, and it is slow, because one address is often shared by dozens of
different remotes that give the same command numbers to different buttons.

## What this repository does

It asks one question: **once a few buttons are confirmed, how much of the rest
of the remote can be predicted?** Every button predicted correctly is a question
the user is not asked.

Status, 14 October 2026: the data, the evaluation method, two reference
predictors and a first model are in place.

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

## Run it

Python 3.11 or later. No dependencies.

```
python -m unittest        # tests
python -m dna.evaluate    # the tables above (the held-out half)
python -m dna.evaluate --fold all
```

## Layout

| Path | What it is |
|---|---|
| `data/catalogue.json` | Known remotes: protocol, address, button to command |
| `dna/catalogue.py` | Loads the catalogue and folds exact duplicates |
| `dna/predict.py` | The baseline, exact matching, and the model (`mixture`) |
| `dna/evaluate.py` | Evaluation with the target's brand removed, on a fixed half of the brands |
| `tests/` | Unit tests, including one that the held-out brand cannot leak |

## What existed before, and what is built here

- **Before the Thirduni project month:** the REMOTE DNA app (published on Google
  Play on 4 October 2026), its infrared engine, and the catalogue in `data/`.
  The app's source code is private and is not part of this repository.
- **Built during the project month:** everything else in this repository.

Built by Mohamed Khocha with Claude Code as a coding assistant.

## Rights

See `NOTICE` for the source code and `DATA.md` for the catalogue.
