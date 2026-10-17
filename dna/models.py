"""Find a remote from a model number read off a label or typed.

Flipper-IRDB names each dump after the TV or remote it came from
(`TVs/Hisense/Hisense_55U6K.ir`). `data/models.json` keeps those names, one
entry per dump, plus TVs tested by hand. A model number is a code, not a word,
so the match is on letters and digits only, with room for a region suffix on
the label and for one character the text recognition got wrong.

The app runs the same search (`app/src/data/models.ts` in its private
repository) on text that ML Kit reads from a photo on the phone.

    python -m dna.models        # retrieval under simulated reading errors
"""
from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "models.json"

MODEL_WORDS = re.compile(r"\b(MODEL|MOD|TYPE|MODEL NO|MODELE|MODÈLE|MODELO)\b", re.I)
SERIAL_WORDS = re.compile(r"\b(S/?N|SERIAL|SERIE|SÉRIE)\b", re.I)


def is_rating(key: str) -> bool:
    """Electrical ratings look like model numbers: 100-240V~50/60Hz becomes 100240V5060HZ."""
    return "HZ" in key or bool(re.fullmatch(r"(AC)?\d{2,6}(V|W|VA|MA|KW|VAC)(AC)?", key))


@dataclass(frozen=True)
class Model:
    brand: str
    label: str
    keys: tuple[str, ...]
    protocol: str | None
    address: int | None
    field: bool
    # A smart TV reached over Wi-Fi instead, whose infrared remote is not catalogued.
    wifi: str | None = None


def load(path: Path | str = DEFAULT_PATH) -> list[Model]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        Model(e["b"], e["m"], tuple(e["k"]), e.get("p"), e.get("a"), e["src"] == "field", e.get("wifi"))
        for e in raw["models"]
    ]


def model_key(s: str) -> str:
    """Upper-case letters and digits only: 'bn59-01199f' and 'BN5901199F' meet."""
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def candidates(text: str) -> list[str]:
    """Strings that could be a model number, likeliest first: four characters
    or more with letters and digits both, not an electrical rating, not on a
    serial-number line. Those on a line saying 'Model' come first, then those
    of model length (5 to 12). Mirrors the app."""
    scored: list[tuple[float, str]] = []
    for line in text.splitlines():
        on_model_line = bool(MODEL_WORDS.search(line))
        if not on_model_line and SERIAL_WORDS.search(line):
            continue
        for piece in re.split(r"[\s:;,()\[\]]+", line):
            k = model_key(piece)
            if not (4 <= len(k) <= 20) or not re.search(r"[A-Z]", k) or not re.search(r"[0-9]", k):
                continue
            if MODEL_WORDS.search(piece) or is_rating(k):
                continue
            shaped = 5 if 5 <= len(k) <= 12 else 0
            scored.append(((10 if on_model_line else 0) + shaped + min(len(k), 10) / 10, k))
    out: list[str] = []
    for _, k in sorted(scored, key=lambda x: -x[0]):
        if k not in out:
            out.append(k)
    return out


def _distance(a: str, b: str, limit: int) -> int:
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i]
        for j in range(1, len(b) + 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] != b[j - 1])))
        if min(cur) > limit:
            return limit + 1
        prev = cur
    return prev[-1]


def match(candidate: str, key: str) -> float:
    """1 the same; 0.9 one is the other plus a suffix; 0.8 one character off;
    0.7 two off on long keys; 0 otherwise. Mirrors the app."""
    if candidate == key:
        return 1.0
    shorter = min(len(candidate), len(key))
    if shorter >= 5 and (candidate.startswith(key) or key.startswith(candidate)):
        return 0.9
    if shorter >= 5:
        d = _distance(candidate, key, 2)
        if d == 1:
            return 0.8
        if d == 2 and shorter >= 8:
            return 0.7
    return 0.0


def search(text: str, models: list[Model], brand: str | None = None, limit: int = 5) -> list[tuple[Model, float]]:
    found = candidates(text)
    if not found:
        return []
    brands = {model_key(w) for w in ([brand] if brand else []) + text.split()}
    scored = []
    for m in models:
        s = max((match(c, k) for c in found for k in m.keys), default=0.0)
        if not s:
            continue
        s += 0.05 if model_key(m.brand) in brands else 0.0
        s += 0.02 if m.field else 0.0
        scored.append((m, min(1.0, s)))
    scored.sort(key=lambda x: -x[1])
    return scored[:limit]


# Characters text recognition often confuses on printed labels.
CONFUSABLE = {"0": "O", "O": "0", "1": "I", "I": "1", "5": "S", "S": "5", "8": "B", "B": "8", "2": "Z", "Z": "2"}


def misread(key: str, rng: random.Random) -> str:
    """The key with one confusable character swapped, if it has one."""
    spots = [i for i, ch in enumerate(key) if ch in CONFUSABLE]
    if not spots:
        return key
    i = rng.choice(spots)
    return key[:i] + CONFUSABLE[key[i]] + key[i + 1:]


def retrieval_report(models: list[Model], seed: int = 0) -> str:
    """Top-1 and top-3: is the right model's address among the answers, for a
    clean label, a label with a region suffix, and a label with one misread
    character? Distinct models can share codes, so a hit on the same
    protocol and address counts."""
    rng = random.Random(seed)
    cases = {"clean": [], "suffix": [], "misread": []}
    for m in models:
        if m.wifi:  # no infrared codes to compare
            continue
        key = m.keys[0]
        cases["clean"].append((m, f"MODEL: {key}"))
        cases["suffix"].append((m, f"MODEL: {key}XZT"))
        cases["misread"].append((m, f"MODEL: {misread(key, rng)}"))
    lines = ["| Label | Models | Right remote first | In the top 3 |", "|---|---|---|---|"]
    for name, items in cases.items():
        top1 = top3 = 0
        for m, text in items:
            hits = search(text, models, limit=3)
            where = [(h.protocol, h.address) for h, _ in hits]
            top1 += bool(where) and where[0] == (m.protocol, m.address)
            top3 += (m.protocol, m.address) in where
        n = len(items)
        lines.append(f"| {name} | {n} | {top1 / n:.1%} | {top3 / n:.1%} |")
    return "\n".join(lines)


if __name__ == "__main__":
    print(retrieval_report(load()))
