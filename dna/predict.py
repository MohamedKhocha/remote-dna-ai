"""Predictors: given a few confirmed buttons, guess the rest of the remote.

Each predictor has the same shape, so the evaluation can compare them:

    predict(known, where, pool, wanted) -> {button: command or None}

`known` is what the user has confirmed, `where` the (protocol, address) the TV
listens on, `pool` every catalogue remote that speaks the same protocol, and
`wanted` the buttons to guess.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Callable, Iterable

from .catalogue import Remote

Where = tuple[str, int]
Predictor = Callable[[dict[str, int], Where, list[Remote], Iterable[str]], dict[str, int | None]]


def _vote(remotes: list[Remote], button: str) -> int | None:
    """The most common command for a button; ties go to the smaller number."""
    votes = Counter(r.commands[button] for r in remotes if button in r.commands)
    if not votes:
        return None
    top = max(votes.values())
    return min(c for c, n in votes.items() if n == top)


def most_common(known: dict[str, int], where: Where, pool: list[Remote], wanted: Iterable[str]) -> dict[str, int | None]:
    """Baseline: what the app does today. The most frequent command on this
    address, whatever is already known."""
    here = [r for r in pool if r.where == where]
    return {b: _vote(here, b) for b in wanted}


def exact_match(known: dict[str, int], where: Where, pool: list[Remote], wanted: Iterable[str]) -> dict[str, int | None]:
    """Vote only among remotes on this address that agree with every confirmed
    button; fall back to the whole address when none do."""
    here = [r for r in pool if r.where == where]
    agree = [r for r in here if all(r.commands.get(b) == c for b, c in known.items())]
    out: dict[str, int | None] = {}
    for b in wanted:
        guess = _vote(agree, b) if agree else None
        out[b] = guess if guess is not None else _vote(here, b)
    return out


# Chosen on half of the brands (fold 0 in evaluate.py) and never touched while
# looking at the other half, which is the one the README reports.
MISMATCH = 0.05  # how much a remote keeps of its weight per button it gets wrong
ELSEWHERE = 0.05  # starting weight of a remote on another address
UNKNOWN = 0.5  # a remote that lacks a confirmed button neither agrees nor disagrees


def weights(known: dict[str, int], where: Where, pool: list[Remote]) -> list[tuple[Remote, float]]:
    """How much each catalogue remote resembles the one being rebuilt.

    A remote on the same address starts at 1. One on another address starts
    much lower and counts only if it shares at least one confirmed button:
    makers reuse a button layout across addresses, and that is the only way to
    say anything about a TV whose address no other brand uses.

    Disagreeing with a confirmed button shrinks the weight instead of removing
    the remote. Catalogue entries carry mistakes, and a remote that is right
    about four buttons and wrong about one still knows a great deal.
    """
    out: list[tuple[Remote, float]] = []
    for r in pool:
        same = r.where == where
        w = 1.0 if same else ELSEWHERE
        hits = 0
        for button, command in known.items():
            if button not in r.commands:
                w *= UNKNOWN
            elif r.commands[button] == command:
                w *= 1 - MISMATCH
                hits += 1
            else:
                w *= MISMATCH
        if same or hits:
            out.append((r, w))
    return out


def distribution(weighted: list[tuple[Remote, float]], button: str) -> dict[int, float]:
    """Probability of each command for one button, from the weighted remotes."""
    votes: dict[int, float] = defaultdict(float)
    for r, w in weighted:
        if button in r.commands:
            votes[r.commands[button]] += w
    total = sum(votes.values())
    return {c: v / total for c, v in votes.items()} if total else {}


def mixture(known: dict[str, int], where: Where, pool: list[Remote], wanted: Iterable[str]) -> dict[str, int | None]:
    """The model: every resembling remote votes with its weight."""
    weighted = weights(known, where, pool)
    out: dict[str, int | None] = {}
    for b in wanted:
        dist = distribution(weighted, b)
        out[b] = max(dist, key=lambda c: (dist[c], -c)) if dist else None
    return out


PREDICTORS: dict[str, Predictor] = {"most_common": most_common, "exact_match": exact_match, "mixture": mixture}
