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

Status, 13 October 2026: the data, the evaluation method and two reference
predictors are in place. The model itself is the work of the coming weeks.

## First results

A whole brand is held out at a time, so the test is a TV whose brand is in no
list. The first buttons the app would learn are revealed and the rest are
guessed.

| Confirmed buttons | Remotes with a neighbour | most_common | exact_match |
|---|---|---|---|
| 1 | 916 of 1258 (73%) | 54.5% | 60.9% |
| 2 | 916 of 1258 (73%) | 54.3% | 60.1% |
| 3 | 904 of 1235 (73%) | 54.3% | 59.0% |

Each cell is the share of the remaining buttons guessed with the right command.

- `most_common` is what the app does today: the most frequent command for each
  button on that address, whatever is already known.
- `exact_match` votes only among catalogue remotes that agree with every
  confirmed button.

What this says:

- One confirmed button already carries information: about six points.
- Exact matching does not get better with a second and a third button. It
  throws away remotes that differ in one place. A model that weighs partial
  agreement is the next step.
- 27% of remotes have no neighbour: no other brand uses their address. Nothing
  here can help them yet. Learning button layouts across addresses is the
  step after that, and the one that matters most for unknown TVs.

## Run it

Python 3.11 or later. No dependencies.

```
python -m unittest        # tests
python -m dna.evaluate    # the table above
```

## Layout

| Path | What it is |
|---|---|
| `data/catalogue.json` | Known remotes: protocol, address, button to command |
| `dna/catalogue.py` | Loads the catalogue and folds exact duplicates |
| `dna/predict.py` | The predictors being compared |
| `dna/evaluate.py` | Leave-one-brand-out evaluation |
| `tests/` | Unit tests, including one that the held-out brand cannot leak |

## What existed before, and what is built here

- **Before the Thirduni project month:** the REMOTE DNA app (published on Google
  Play on 4 October 2026), its infrared engine, and the catalogue in `data/`.
  The app's source code is private and is not part of this repository.
- **Built during the project month:** everything else in this repository.

Built by Mohamed Khocha with Claude Code as a coding assistant.

## Rights

See `NOTICE` for the source code and `DATA.md` for the catalogue.
