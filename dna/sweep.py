"""Finding a TV on an address that no remote in the catalogue uses.

When no catalogue address reaches the TV, the app tries the addresses nobody
uses (720 of them in NEC, Samsung32, RC6, RC5 and Sony), with number keys,
whose effect is visible: the channel number changes.

Up to 1.0.9 this was a batch search: 24 addresses per send, then "did
anything happen?", up to 30 times, before the replay, the halving and the
final confirmation. A yes/no answer carries at most one bit, and most
answers were "no".

Since 1.0.10 it is a sweep. The phone sends every address back to back
without stopping, and the user taps "I saw it!" once, when the TV reacts.
The moment of the tap says which addresses were on air just before it: a
window of a few seconds, a couple of dozen addresses out of 1,440 sends, so
the tap alone carries about six bits. The usual replay, halving and
confirmation settle the window.

The sweep goes over the whole space with a first probe, then again with a
second. Each probe is chosen by greedy set cover over the protocol's
catalogue remotes: the command the most of them implement, then the one
that reaches the most remotes the first missed. Commands that are power or
source on more than a fifth of the remotes using them are never sent. Most
TVs know the first probe, so most sweeps end within the first pass.

Times come from the app's own frame encoders (air time of each frame plus
the 45 ms gap it leaves between frames), a fixed pause after each answer,
and a fixed time to look and answer. The hand's delay between the TV's
reaction and the tap is a parameter: the sweep must work for slow hands.

    python -m dna.sweep
"""
from __future__ import annotations

import argparse
import statistics
from dataclasses import dataclass
from typing import Callable

from . import catalogue
from .catalogue import Remote

# Address spaces a cheap TV may listen on, likeliest first. NECext is left
# out: 65,536 addresses are too many to sweep by hand.
DEEP_SPACES = [("nec", 256), ("samsung32", 256), ("rc6", 256), ("rc5", 32), ("sirc", 32)]
UNSAFE = ("power", "source")
PROBES = 2
# The window of sends a tap points to; long enough for a slow hand.
LOOKBACK_MS = 3000
# The batch search the sweep replaced.
BATCH = 24

FRAME_GAP_MS = 45  # silence after every frame (app: hunter/burst.ts)
SETTLE_MS = 700  # pause after every answer before the next send
LOOK_MS = 2500  # time to look at the TV and answer one yes/no question


@dataclass(frozen=True)
class Candidate:
    protocol: str
    address: int
    probes: tuple[int, ...]


# ------------------------------------------------------------------ probes


def deep_probes(remotes: list[Remote], count: int = PROBES) -> list[int]:
    """Greedy set cover over `remotes`, safe commands only.

    Once every remote is covered, the next probe is the most used one: the TV
    looked for is in no catalogue, so its remote may know neither.
    """
    who: dict[int, set[int]] = {}
    unsafe: dict[int, int] = {}
    for i, r in enumerate(remotes):
        for key, value in r.commands.items():
            who.setdefault(value, set()).add(i)
            if key in UNSAFE:
                unsafe[value] = unsafe.get(value, 0) + 1
    safe = sorted(v for v, users in who.items() if 5 * unsafe.get(v, 0) < len(users))
    left = set(range(len(remotes)))
    probes: list[int] = []
    while len(probes) < count:
        best, score = None, -1
        for v in safe:
            if v in probes:
                continue
            s = len(who[v] & left) * len(remotes) + len(who[v])
            if s > score:
                best, score = v, s
        if best is None:
            break
        probes.append(best)
        left -= who[best]
    return probes


def _spaces(remotes: list[Remote]) -> list[tuple[str, list[int], list[int]]]:
    """Each deep space: its protocol, its unknown addresses and its probes."""
    known = {r.where for r in remotes}
    out = []
    for protocol, size in DEEP_SPACES:
        probes = deep_probes([r for r in remotes if r.protocol == protocol])
        addresses = [a for a in range(size) if (protocol, a) not in known]
        if probes and addresses:
            out.append((protocol, addresses, probes))
    return out


def sweep_candidates(remotes: list[Remote]) -> list[Candidate]:
    """The sweep's order: every address with the first probe, then with the second."""
    spaces = _spaces(remotes)
    return [
        Candidate(protocol, a, (probes[p],))
        for p in range(PROBES)
        for protocol, addresses, probes in spaces
        if p < len(probes)
        for a in addresses
    ]


def batch_candidates(remotes: list[Remote]) -> list[Candidate]:
    """The batch search's order: every address once, with both probes."""
    return [Candidate(protocol, a, tuple(probes)) for protocol, addresses, probes in _spaces(remotes) for a in addresses]


# ------------------------------------------------------------------- timing


def _bits(value: int, count: int) -> list[int]:
    return [(value >> i) & 1 for i in range(count)]


def frame_us(protocol: str, address: int, command: int) -> int:
    """Air time of one frame, in microseconds, as the app's encoders build it."""
    if protocol == "nec":
        # Address and command each followed by their inverse: always 16 ones and 16 zeros.
        return 9000 + 4500 + 16 * (562 + 1687) + 16 * (562 + 562) + 562
    if protocol == "samsung32":
        bits = _bits(address, 8) * 2 + _bits(command, 8) + _bits(command ^ 0xFF, 8)
        return 4500 + 4500 + sum(560 + (1690 if b else 560) for b in bits) + 560
    if protocol == "rc5":
        # 14 Manchester bits of 2 x 889 us; the leading idle half is dropped.
        return 14 * 2 * 889 - 889
    if protocol == "rc6":
        # Leader, start, three mode bits, the double-length trailer, 16 data
        # bits; a final half of silence (a data bit of 1) is not sent.
        total = 2666 + 889 + 4 * 2 * 444 + 2 * 889 + 16 * 2 * 444
        return total - (444 if command & 1 else 0)
    if protocol == "sirc":
        # 7 command bits then 5 address bits, sent three times 45 ms apart.
        bits = _bits(command & 0x7F, 7) + _bits(address & 0x1F, 5)
        frame = 2400 + 600 + sum((1200 if b else 600) + 600 for b in bits)
        gap = max(45000 - frame, 10000)
        return 2 * (frame + gap - 600) + frame - 600
    raise ValueError(protocol)


def send_ms(c: Candidate) -> float:
    """How long one candidate takes to go out: every probe, each with its gap."""
    return sum(frame_us(c.protocol, c.address, p) / 1000 + FRAME_GAP_MS for p in c.probes)


# ---------------------------------------------------------------- searching

Reacts = Callable[[list[int]], bool]


def suspects(sent_at: dict[int, float], tap_at: float, lookback: float = LOOKBACK_MS) -> list[int]:
    """The sends on air in the `lookback` before the tap, and the one already
    on air when that window opens (its frames overlap it)."""
    sent = sorted((t, i) for i, t in sent_at.items() if t <= tap_at)
    if not sent:
        return []
    inside = [i for t, i in sent if t >= tap_at - lookback]
    before = [i for t, i in sent if t < tap_at - lookback]
    out = ([before[-1]] if before else []) + inside
    return out or [sent[-1][1]]


@dataclass
class Outcome:
    found: int | None
    answers: int
    seconds: float


def settle(group: list[int], reacts: Reacts, cost: Callable[[list[int]], float]) -> Outcome:
    """Replay the group, halve it while it reacts, confirm the last one alone.
    The same steps as the app's `answerFind` after a "yes"."""
    answers, ms = 1, cost(group)
    if not reacts(group):
        return Outcome(None, answers, ms / 1000)
    current = group
    while len(current) > 1:
        mid = (len(current) + 1) // 2
        half = current[:mid]
        answers, ms = answers + 1, ms + cost(half)
        current = half if reacts(half) else current[mid:]
    answers, ms = answers + 1, ms + cost(current)
    return Outcome(current[0] if reacts(current) else None, answers, ms / 1000)


def run_sweep(cands: list[Candidate], tv: Candidate, knows: int, hand_ms: float, stray_at: float | None = None) -> Outcome:
    """One deep search by sweep. The TV listens on `tv`'s address and knows
    the probe `knows`; the hand taps `hand_ms` after the frame it reacted to."""
    air = [send_ms(c) for c in cands]
    hit = lambda c: c.protocol == tv.protocol and c.address == tv.address and knows in c.probes
    reacts: Reacts = lambda group: any(hit(cands[i]) for i in group)
    cost = lambda group: sum(air[i] for i in group) + LOOK_MS + SETTLE_MS
    sent_at: dict[int, float] = {}
    clock, answers, cursor = 0.0, 0, 0
    while cursor < len(cands):
        tap = None
        for i in range(cursor, len(cands)):
            if tap is not None and clock >= tap:
                break
            sent_at[i] = clock
            clock += air[i]
            if stray_at is not None and clock >= stray_at:
                tap, stray_at = stray_at, None
            elif tap is None and hit(cands[i]):
                tap = clock + hand_ms
        if tap is None:
            return Outcome(None, answers, clock / 1000)
        group = suspects(sent_at, tap)
        answers += 1  # the tap
        out = settle(group, reacts, cost)
        clock = tap + SETTLE_MS + out.seconds * 1000
        answers += out.answers
        if out.found is not None:
            return Outcome(out.found, answers, clock / 1000)
        cursor = max(group) + 1  # a stray tap: carry on after the window
    return Outcome(None, answers, clock / 1000)


def run_batch(cands: list[Candidate], tv: Candidate, knows: int, batch: int = BATCH) -> Outcome:
    """One deep search the old way: batches, one yes/no question each."""
    air = [send_ms(c) for c in cands]
    reacts: Reacts = lambda group: any(
        cands[i].protocol == tv.protocol and cands[i].address == tv.address and knows in cands[i].probes for i in group
    )
    cost = lambda group: sum(air[i] for i in group) + LOOK_MS + SETTLE_MS
    answers, seconds = 0, 0.0
    for start in range(0, len(cands), batch):
        group = list(range(start, min(start + batch, len(cands))))
        answers, seconds = answers + 1, seconds + cost(group) / 1000
        if reacts(group):
            out = settle(group, reacts, cost)
            return Outcome(out.found, answers + out.answers, seconds + out.seconds)
    return Outcome(None, answers, seconds)


# ------------------------------------------------------------------ report


@dataclass
class Row:
    label: str
    sessions: int
    mean_answers: float
    max_answers: int
    mean_seconds: float
    missed: int


def _row(label: str, outcomes: list[Outcome], expected: list[int]) -> Row:
    missed = sum(o.found is None or o.found != e for o, e in zip(outcomes, expected))
    answers = [o.answers for o in outcomes]
    return Row(label, len(outcomes), statistics.mean(answers), max(answers), statistics.mean(o.seconds for o in outcomes), missed)


def run(remotes: list[Remote], hands: tuple[int, ...] = (700, 1800)) -> list[Row]:
    sweep = sweep_candidates(remotes)
    batch = batch_candidates(remotes)
    rows = []
    for name, which in (("first probe", 0), ("second probe only", 1)):
        # A TV for every unknown address, knowing only one of the two probes.
        tvs = [b for b in batch if len(b.probes) > which]
        knows = [b.probes[which] for b in tvs]
        old = [run_batch(batch, tv, k) for tv, k in zip(tvs, knows)]
        rows.append(_row(f"batches of {BATCH}, TV knows the {name}", old, [batch.index(tv) for tv in tvs]))
        index = {(c.protocol, c.address, c.probes[0]): i for i, c in enumerate(sweep)}
        expected = [index[(tv.protocol, tv.address, k)] for tv, k in zip(tvs, knows)]
        for hand in hands:
            new = [run_sweep(sweep, tv, k, hand) for tv, k in zip(tvs, knows)]
            rows.append(_row(f"sweep, TV knows the {name}, tap {hand / 1000:.1f} s late", new, expected))
    return rows


def report(remotes: list[Remote]) -> str:
    sweep = sweep_candidates(remotes)
    addresses = {(c.protocol, c.address) for c in sweep}
    total = sum(send_ms(c) for c in sweep) / 1000
    one_pass = sum(send_ms(c) for c in sweep[: len(addresses)]) / 1000
    lines = [
        f"Deep search over {len(addresses)} addresses no catalogue remote uses "
        f"({len(sweep)} sends; one pass {one_pass:.0f} s of air, both {total:.0f} s).",
        "",
        "| Search | TVs | Answers: mean | Answers: max | Time: mean | Missed |",
        "|---|---|---|---|---|---|",
    ]
    for r in run(remotes):
        lines.append(
            f"| {r.label} | {r.sessions} | {r.mean_answers:.1f} | {r.max_answers} | {r.mean_seconds:.0f} s | {r.missed} |"
        )
    lines += [
        "",
        f"Answers include the tap. Time counts the air, {SETTLE_MS} ms after each answer and "
        f"{LOOK_MS / 1000:.1f} s to look and answer each yes/no question.",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__.split("\n")[0]).parse_args()
    print(report(catalogue.load()))
