"""How much of an unseen remote can each predictor fill in?

The test is the one the app faces: a TV whose brand is in no list. So every
remote of the target's brand is removed from the catalogue before predicting.
Removing only the target would be too easy, because a brand's remotes are
often near copies of each other and the answer would still be sitting there.

For each target the first `k` buttons the app would learn are revealed, and
the predictor guesses all the others.

Settings in predict.py were chosen on fold 0 of the brands. The numbers that
count are those of fold 1, which nothing was tuned on.

    python -m dna.evaluate            # fold 1, the reported numbers
    python -m dna.evaluate --fold 0   # the half used for choosing settings
    python -m dna.evaluate --fold all
"""
from __future__ import annotations

import argparse
import zlib
from collections import defaultdict
from dataclasses import dataclass, field

from . import catalogue
from .catalogue import Remote
from .predict import PREDICTORS, Predictor

# The order the app learns buttons in: harmless, visible ones first, and power
# late because it switches the TV off.
REVEAL_ORDER = ["volUp", "volDown", "mute", "ok", "back", "power", "chUp", "chDown", "menu"]
REPORTED_FOLD = 1


def revealed(remote: Remote, k: int) -> dict[str, int]:
    names = [b for b in REVEAL_ORDER if b in remote.commands]
    names += [b for b in remote.commands if b not in names]
    return {b: remote.commands[b] for b in names[:k]}


def fold_of(remote: Remote) -> int:
    """Which half a remote belongs to, decided by its brand name alone so the
    split is the same on every machine and every run."""
    return zlib.crc32(min(remote.brands).encode("utf-8")) % 2


@dataclass
class Score:
    right: int = 0
    guessed: int = 0

    def add(self, right: int, guessed: int) -> None:
        self.right += right
        self.guessed += guessed

    @property
    def accuracy(self) -> float:
        return self.right / self.guessed if self.guessed else 0.0


@dataclass
class Result:
    k: int
    with_neighbour: int = 0  # targets another brand shares an address with
    alone: int = 0  # targets no other brand shares an address with
    # scores[predictor]["near" | "alone" | "all"]
    scores: dict[str, dict[str, Score]] = field(default_factory=dict)


def run(remotes: list[Remote], k: int, fold: int | None = None, predictors: dict[str, Predictor] = PREDICTORS) -> Result:
    by_protocol: dict[str, list[Remote]] = defaultdict(list)
    for r in remotes:
        by_protocol[r.protocol].append(r)
    result = Result(k, scores={name: {g: Score() for g in ("near", "alone", "all")} for name in predictors})
    for target in remotes:
        if len(target.commands) <= k or (fold is not None and fold_of(target) != fold):
            continue
        pool = [r for r in by_protocol[target.protocol] if not (r.brands & target.brands)]
        near = any(r.where == target.where for r in pool)
        if near:
            result.with_neighbour += 1
        else:
            result.alone += 1
        known = revealed(target, k)
        wanted = [b for b in target.commands if b not in known]
        for name, predict in predictors.items():
            guesses = predict(known, target.where, pool, wanted)
            right = sum(guesses[b] == target.commands[b] for b in wanted)
            result.scores[name]["near" if near else "alone"].add(right, len(wanted))
            result.scores[name]["all"].add(right, len(wanted))
    return result


def report(remotes: list[Remote], fold: int | None = REPORTED_FOLD, ks=(1, 2, 3, 5)) -> str:
    which = "all brands" if fold is None else f"fold {fold} of the brands"
    lines = [f"Unique remotes: {len(remotes)}. Evaluated on {which}.", ""]
    for group, title in (
        ("all", "Every remote"),
        ("near", "Remotes whose address another brand also uses"),
        ("alone", "Remotes alone on their address"),
    ):
        lines += [f"{title}", "", "| Confirmed buttons | Remotes | " + " | ".join(PREDICTORS) + " |", "|---|---|" + "---|" * len(PREDICTORS)]
        for k in ks:
            r = run(remotes, k, fold)
            count = {"all": r.with_neighbour + r.alone, "near": r.with_neighbour, "alone": r.alone}[group]
            cells = " | ".join(f"{r.scores[name][group].accuracy:.1%}" for name in PREDICTORS)
            lines.append(f"| {k} | {count} | {cells} |")
        lines.append("")
    lines.append("Each cell: share of the remaining buttons guessed with the right command.")
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--fold", default=str(REPORTED_FOLD), choices=["0", "1", "all"])
    parser.add_argument("--catalogue", default=str(catalogue.DEFAULT_PATH))
    args = parser.parse_args()
    print(report(catalogue.load(args.catalogue), None if args.fold == "all" else int(args.fold)))
