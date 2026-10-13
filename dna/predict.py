"""Predictors: given a few confirmed buttons, guess the rest of the remote.

Each predictor has the same shape, so the evaluation can compare them:

    predict(known, pool, wanted) -> {button: command or None}

`known` is what the user has confirmed, `pool` the catalogue remotes on the
same protocol and address, `wanted` the buttons to guess.
"""
from __future__ import annotations

from collections import Counter
from typing import Callable, Iterable

from .catalogue import Remote

Predictor = Callable[[dict[str, int], list[Remote], Iterable[str]], dict[str, int | None]]


def _vote(remotes: list[Remote], button: str) -> int | None:
    """The most common command for a button; ties go to the smaller number."""
    votes = Counter(r.commands[button] for r in remotes if button in r.commands)
    if not votes:
        return None
    top = max(votes.values())
    return min(c for c, n in votes.items() if n == top)


def most_common(known: dict[str, int], pool: list[Remote], wanted: Iterable[str]) -> dict[str, int | None]:
    """Baseline: what the app does today. It ignores what is already known."""
    return {b: _vote(pool, b) for b in wanted}


def exact_match(known: dict[str, int], pool: list[Remote], wanted: Iterable[str]) -> dict[str, int | None]:
    """First rung above the baseline: vote only among remotes that agree with
    every confirmed button, and fall back to everyone when none do or when the
    agreeing remotes do not have the button at all."""
    agree = [r for r in pool if all(r.commands.get(b) == c for b, c in known.items())]
    out: dict[str, int | None] = {}
    for b in wanted:
        guess = _vote(agree, b) if agree else None
        out[b] = guess if guess is not None else _vote(pool, b)
    return out


PREDICTORS: dict[str, Predictor] = {"most_common": most_common, "exact_match": exact_match}
