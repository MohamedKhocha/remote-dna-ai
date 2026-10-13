"""How much of an unseen remote can each predictor fill in?

The test is the one the app faces: a TV whose brand is in no list. So a whole
brand is held out at a time. Holding out a single remote would be too easy,
because a brand's remotes are often near copies of each other and the answer
would still be sitting in the catalogue.

For every remote of the held-out brand, the first `k` buttons the app would
learn are revealed, and the predictor guesses all the others.

    python -m dna.evaluate
"""
from __future__ import annotations

import sys
from dataclasses import dataclass

from . import catalogue
from .catalogue import Remote
from .predict import PREDICTORS, Predictor

# The order the app learns buttons in: harmless, visible ones first, and power
# late because it switches the TV off.
REVEAL_ORDER = ["volUp", "volDown", "mute", "ok", "back", "power", "chUp", "chDown", "menu"]


def revealed(remote: Remote, k: int) -> dict[str, int]:
    names = [b for b in REVEAL_ORDER if b in remote.commands]
    names += [b for b in remote.commands if b not in names]
    return {b: remote.commands[b] for b in names[:k]}


@dataclass
class Score:
    right: int = 0
    guessed: int = 0
    remotes: int = 0

    @property
    def accuracy(self) -> float:
        return self.right / self.guessed if self.guessed else 0.0


@dataclass
class Result:
    k: int
    total: int  # remotes with more than k buttons
    with_neighbour: int  # of those, remotes another brand shares an address with
    scores: dict[str, Score]


def run(remotes: list[Remote], k: int, predictors: dict[str, Predictor] = PREDICTORS) -> Result:
    by_addr = catalogue.by_address(remotes)
    scores = {name: Score() for name in predictors}
    total = with_neighbour = 0
    for target in remotes:
        if len(target.commands) <= k:
            continue
        total += 1
        # Hold out every remote that shares a brand with the target.
        pool = [r for r in by_addr[target.where] if not (r.brands & target.brands)]
        if not pool:
            continue  # no other brand uses this address: nothing to learn from yet
        with_neighbour += 1
        known = revealed(target, k)
        wanted = [b for b in target.commands if b not in known]
        for name, predict in predictors.items():
            guesses = predict(known, pool, wanted)
            s = scores[name]
            s.remotes += 1
            s.guessed += len(wanted)
            s.right += sum(guesses[b] == target.commands[b] for b in wanted)
    return Result(k, total, with_neighbour, scores)


def report(remotes: list[Remote], ks=(1, 2, 3)) -> str:
    lines = [
        f"Unique remotes: {len(remotes)}",
        "",
        "| Confirmed buttons | Remotes with a neighbour | " + " | ".join(PREDICTORS) + " |",
        "|---|---|" + "---|" * len(PREDICTORS),
    ]
    for k in ks:
        r = run(remotes, k)
        cells = " | ".join(f"{r.scores[name].accuracy:.1%}" for name in PREDICTORS)
        lines.append(f"| {k} | {r.with_neighbour} of {r.total} ({r.with_neighbour / r.total:.0%}) | {cells} |")
    lines += ["", "Each cell: share of the remaining buttons guessed with the right command."]
    return "\n".join(lines)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else catalogue.DEFAULT_PATH
    print(report(catalogue.load(path)))
