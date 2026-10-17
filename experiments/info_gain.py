"""Information gain: does asking the most informative command save questions?

Today's model sends the untried command most likely to be a missing button.
This adds how much the answer is expected to narrow down which remote the TV
is: the drop in entropy over the remotes still in play, weighted by lam.

    value(c) = P(c is a missing button) + lam * information_gain(c)

lam = 0 is today's model exactly. lam is chosen on fold 0 only; fold 1 is
measured once, with the chosen value.

Run from the repository root:
    python -I experiments/info_gain.py . 0          # tune: several lam values
    python -I experiments/info_gain.py . 1 <lam>    # held-out: one value
"""
from __future__ import annotations

import math
import statistics
import sys
from collections import defaultdict

sys.path.insert(0, sys.argv[1])
from dna import catalogue  # noqa: E402
from dna.evaluate import fold_of  # noqa: E402
from dna.simulate import ESSENTIALS, GIVE_UP, Session, catalogue_order, has_neighbours  # noqa: E402


def entropy(ws: list[float]) -> float:
    total = sum(ws)
    if total <= 0:
        return 0.0
    return -sum(w / total * math.log(w / total) for w in ws if w > 0)


def session_questions(target, pool, lam: float) -> int:
    targets = [b for b in ESSENTIALS if b in target.commands]
    meaning = {c: b for b, c in target.commands.items()}
    found: set[str] = set()
    tried: set[int] = set()
    fixed = catalogue_order(target.where, pool, targets)
    s = Session(target.where, pool)
    questions = 0
    while len(found) < len(targets) and questions < GIVE_UP:
        missing = [b for b in targets if b not in found]
        active = [i for i, r in enumerate(s.pool) if r.where == s.where or s.hits[i]]
        mass = sum(s.weight[i] for i in active)
        hit = s.score(missing)
        h0 = entropy([s.weight[i] for i in active]) if lam else 0.0
        candidates = set()
        for i in active:
            candidates.update(s.by_command[i])
        candidates -= tried
        best, best_value = None, 0.0
        for c in sorted(candidates):
            p_hit = hit.get(c, 0.0) / mass if mass else 0.0
            gain = 0.0
            if lam:
                groups: dict[object, list[float]] = defaultdict(list)
                for i in active:
                    groups[s.by_command[i].get(c)].append(s.weight[i])
                expected = sum(sum(g) / mass * entropy(g) for g in groups.values())
                gain = h0 - expected
            value = p_hit + lam * gain
            if value > best_value:
                best, best_value = c, value
        command = best if best is not None else next((c for c in fixed if c not in tried), None)
        if command is None:
            return GIVE_UP
        tried.add(command)
        questions += 1
        button = meaning.get(command)
        if button in targets:
            found.add(button)
        s.learn(command, button)
    return questions


def main() -> None:
    fold = int(sys.argv[2])
    lams = [float(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else [0.0, 0.02, 0.05, 0.1, 0.2, 0.5]
    remotes = catalogue.load()
    by_protocol = defaultdict(list)
    for r in remotes:
        by_protocol[r.protocol].append(r)
    sessions = []
    for t in remotes:
        if fold_of(t) != fold or not any(b in t.commands for b in ESSENTIALS):
            continue
        pool = [r for r in by_protocol[t.protocol] if not (r.brands & t.brands)]
        if has_neighbours(t.where, pool):  # the model only steers here
            sessions.append((t, pool))
    base = [session_questions(t, p, 0.0) for t, p in sessions]
    print(f"fold {fold}: {len(sessions)} sessions on shared addresses")
    for lam in lams:
        n = base if lam == 0 else [session_questions(t, p, lam) for t, p in sessions]
        duel = [sum(a < b for a, b in zip(n, base)), sum(a == b for a, b in zip(n, base)), sum(a > b for a, b in zip(n, base))]
        print(f"lam={lam:<5} mean={statistics.fmean(n):.1f} median={statistics.median(n):.0f} "
              f"total={sum(n)} gave_up={sum(x >= GIVE_UP for x in n)}  fewer/same/more vs lam=0: {duel}")


if __name__ == "__main__":
    main()
