"""Lone-address TVs: ascending sweep vs an order from the whole protocol.

Run from the repository root:  python -I experiments/lone_prior.py . <fold>

Recorded in MODEL_CARD.md: chosen on fold 0 (used_all), worse on fold 1, not kept.
"""
import statistics
import sys
from collections import Counter, defaultdict

sys.path.insert(0, sys.argv[1])
from dna import catalogue  # noqa: E402
from dna.evaluate import fold_of  # noqa: E402
from dna.simulate import ESSENTIALS, GIVE_UP, has_neighbours, sweep  # noqa: E402

FOLD = int(sys.argv[2])


def protocol_prior(protocol, pool, targets, mode):
    """Commands ranked by how often the protocol's remotes use them for a needed button."""
    need = Counter()
    other = Counter()
    power = Counter()
    for r in pool:
        for b, c in r.commands.items():
            if b in targets:
                need[c] += 1
            elif b == "power":
                power[c] += 1
            else:
                other[c] += 1
    allc = list(sweep(protocol))
    if mode == "need":
        key = lambda c: (-need[c], c)
    elif mode == "need_nopower":
        # Commands that are often power go to the back, as the app already does.
        key = lambda c: (power[c] > need[c], -need[c], c)
    elif mode == "used":
        key = lambda c: (power[c] > need[c] + other[c], -(need[c] + other[c]), c)
    elif mode == "used_all":
        key = lambda c: (power[c] > need[c] + other[c], -(need[c] + other[c] + power[c]), c)
    elif mode == "used_need2":
        key = lambda c: (power[c] > need[c] + other[c], -(2 * need[c] + other[c]), c)
    return sorted(allc, key=key)


def questions(order, target, targets):
    meaning = {c: b for b, c in target.commands.items()}
    found = set()
    for q, c in enumerate(order, 1):
        b = meaning.get(c)
        if b in targets:
            found.add(b)
            if len(found) == len(targets):
                return q
        if q >= GIVE_UP:
            return GIVE_UP
    return GIVE_UP


remotes = catalogue.load()
by_protocol = defaultdict(list)
for r in remotes:
    by_protocol[r.protocol].append(r)
res = defaultdict(list)
duel = defaultdict(lambda: [0, 0, 0])
for t in remotes:
    if fold_of(t) != FOLD:
        continue
    targets = [b for b in ESSENTIALS if b in t.commands]
    if not targets:
        continue
    pool = [r for r in by_protocol[t.protocol] if not (r.brands & t.brands)]
    if has_neighbours(t.where, pool):
        continue
    base = questions(list(sweep(t.protocol)), t, targets)
    res["sweep"].append(base)
    for mode in ("used", "used_all", "used_need2"):
        n = questions(protocol_prior(t.protocol, pool, targets, mode), t, targets)
        res[mode].append(n)
        duel[mode][0 if n < base else 1 if n == base else 2] += 1
for k, v in res.items():
    print(f"{k:14s} n={len(v)} mean={statistics.fmean(v):.1f} median={statistics.median(v):.0f} gave_up={sum(x >= GIVE_UP for x in v)}"
          + (f"  fewer/same/more vs sweep: {duel[k]}" if k in duel else ""))
