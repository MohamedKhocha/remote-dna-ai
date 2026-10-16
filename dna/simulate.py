"""How many questions does a user answer before the remote works?

This replays the app's "Teach my TV" session on a remote whose brand is in no
list. The app sends one command at a time and the user says what the TV did:
a button name, or nothing. Every send is one question. The session ends when
the essential buttons are all found.

Two ways of choosing the next command are compared:

- `catalogue_order` is what the app does today. Commands seen on this address
  are tried in a fixed order, the ones usually meaning a needed button first,
  then everything else, then a blind sweep of every number the protocol allows.
- `model_order` asks the model after every answer: which untried command is
  most likely to be one of the buttons still missing? It learns from "nothing
  happened" too, because a catalogue remote that uses that command for any
  button cannot be this TV's remote.

Power is left out of the essentials on purpose. The app sends it last because
it switches the TV off, so both strategies treat it the same way.

    python -m dna.simulate            # fold 1, the reported numbers
"""
from __future__ import annotations

import argparse
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Callable, Iterator

from . import catalogue
from .catalogue import Remote
from .evaluate import REPORTED_FOLD, fold_of
from .predict import ELSEWHERE, MISMATCH, UNKNOWN, Where

ESSENTIALS = ["volUp", "volDown", "mute", "ok", "back"]
# The largest command each protocol can carry; the blind sweep stops there.
COMMAND_MAX = {"rc5": 63, "sirc": 127, "sirc15": 127, "sirc20": 127}
# A session longer than this is counted as a failure: nobody answers 300 questions.
GIVE_UP = 300

Strategy = Callable[[Where, list[Remote]], Iterator[int]]


def sweep(protocol: str) -> range:
    return range(COMMAND_MAX.get(protocol, 255) + 1)


def catalogue_order(where: Where, pool: list[Remote], targets: list[str]) -> list[int]:
    """The app's current queue, fixed before the first question."""
    here = [r for r in pool if r.where == where]
    votes: dict[int, Counter] = defaultdict(Counter)
    for r in here:
        for button, command in r.commands.items():
            votes[command][button] += 1
    meaning = {c: v.most_common(1)[0] for c, v in votes.items()}
    needed = set(targets)

    def rank(c: int) -> tuple:
        label, count = meaning[c]
        group = 2 if label == "power" else 0 if label in needed else 1
        return (group, -count, c)

    ordered = sorted(meaning, key=rank)
    return ordered + [c for c in sweep(where[0]) if c not in meaning]


@dataclass
class Session:
    """What the model knows part-way through a session."""

    where: Where
    pool: list[Remote]
    weight: list[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.weight = [1.0 if r.where == self.where else ELSEWHERE for r in self.pool]
        self.hits = [0] * len(self.pool)
        self.by_command = [{c: b for b, c in r.commands.items()} for r in self.pool]

    def learn(self, command: int, button: str | None) -> None:
        for i, r in enumerate(self.pool):
            meant = self.by_command[i].get(command)
            if button is None:
                # Nothing happened, so this TV has no button on that command.
                if meant is not None:
                    self.weight[i] *= MISMATCH
            elif button not in r.commands:
                self.weight[i] *= UNKNOWN
            elif r.commands[button] == command:
                self.weight[i] *= 1 - MISMATCH
                self.hits[i] += 1
            else:
                self.weight[i] *= MISMATCH

    def score(self, missing: list[str]) -> dict[int, float]:
        """For each command, how likely it is to be one of the missing buttons."""
        out: dict[int, float] = defaultdict(float)
        for i, r in enumerate(self.pool):
            # A remote elsewhere speaks only once it has agreed with something.
            if r.where != self.where and not self.hits[i]:
                continue
            w = self.weight[i]
            for b in missing:
                c = r.commands.get(b)
                if c is not None:
                    out[c] += w
        return out


def run_session(target: Remote, pool: list[Remote], use_model: bool) -> int:
    """Questions asked until the target's essentials are all found."""
    targets = [b for b in ESSENTIALS if b in target.commands]
    meaning = {c: b for b, c in target.commands.items()}
    found: set[str] = set()
    tried: set[int] = set()
    fixed = catalogue_order(target.where, pool, targets)
    session = Session(target.where, pool) if use_model else None
    questions = 0
    while len(found) < len(targets) and questions < GIVE_UP:
        if session is None:
            command = next((c for c in fixed if c not in tried), None)
        else:
            missing = [b for b in targets if b not in found]
            scores = session.score(missing)
            untried = {c: s for c, s in scores.items() if c not in tried and s > 0}
            if untried:
                command = max(untried, key=lambda c: (untried[c], -c))
            else:
                command = next((c for c in fixed if c not in tried), None)
        if command is None:
            # Every number the protocol allows has been tried: the target's
            # commands lie outside it, so this session cannot finish.
            return GIVE_UP
        tried.add(command)
        questions += 1
        button = meaning.get(command)
        if button in targets:
            found.add(button)
        if session is not None:
            session.learn(command, button)
    return questions


@dataclass
class Summary:
    sessions: int
    mean: float
    median: float
    gave_up: int


def summarise(counts: list[int]) -> Summary:
    return Summary(len(counts), statistics.fmean(counts), statistics.median(counts), sum(c >= GIVE_UP for c in counts))


def run(remotes: list[Remote], fold: int | None = REPORTED_FOLD) -> dict[str, dict[str, Summary]]:
    by_protocol: dict[str, list[Remote]] = defaultdict(list)
    for r in remotes:
        by_protocol[r.protocol].append(r)
    counts: dict[str, dict[str, list[int]]] = {
        name: {g: [] for g in ("all", "near", "alone")} for name in ("catalogue_order", "model_order")
    }
    for target in remotes:
        if fold is not None and fold_of(target) != fold:
            continue
        if not any(b in target.commands for b in ESSENTIALS):
            continue
        pool = [r for r in by_protocol[target.protocol] if not (r.brands & target.brands)]
        group = "near" if any(r.where == target.where for r in pool) else "alone"
        for name, use_model in (("catalogue_order", False), ("model_order", True)):
            n = run_session(target, pool, use_model)
            counts[name][group].append(n)
            counts[name]["all"].append(n)
    return {name: {g: summarise(v) for g, v in groups.items() if v} for name, groups in counts.items()}


def report(remotes: list[Remote], fold: int | None = REPORTED_FOLD) -> str:
    result = run(remotes, fold)
    which = "all brands" if fold is None else f"fold {fold} of the brands"
    lines = [
        f"Questions asked until the essential buttons ({', '.join(ESSENTIALS)}) are found. {which}.",
        "",
        "| Remotes | Sessions | Today: mean | Today: median | Model: mean | Model: median |",
        "|---|---|---|---|---|---|",
    ]
    titles = {"all": "Every remote", "near": "Address shared with another brand", "alone": "Alone on its address"}
    for g, title in titles.items():
        a, b = result["catalogue_order"].get(g), result["model_order"].get(g)
        if a and b:
            lines.append(f"| {title} | {a.sessions} | {a.mean:.1f} | {a.median:.0f} | {b.mean:.1f} | {b.median:.0f} |")
    gave = result["catalogue_order"]["all"].gave_up, result["model_order"]["all"].gave_up
    lines += ["", f"Sessions still unfinished after {GIVE_UP} questions: today {gave[0]}, model {gave[1]}."]
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--fold", default=str(REPORTED_FOLD), choices=["0", "1", "all"])
    args = parser.parse_args()
    print(report(catalogue.load(), None if args.fold == "all" else int(args.fold)))
