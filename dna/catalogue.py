"""The catalogue of known remotes, as the model sees it.

A remote is a protocol, an address, and a map from button name to command
number. The same remote is often sold under several brand names, so exact
duplicates are folded into one entry that remembers every brand it came from.
"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "catalogue.json"


@dataclass(frozen=True)
class Remote:
    brands: frozenset[str]
    protocol: str
    address: int
    commands: dict[str, int]

    @property
    def where(self) -> tuple[str, int]:
        """What a TV listens on: every remote here reaches the same devices."""
        return (self.protocol, self.address)


def load(path: Path | str = DEFAULT_PATH) -> list[Remote]:
    """Unique remotes, in catalogue order."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    brands_of: dict[tuple, set[str]] = defaultdict(set)
    first_seen: dict[tuple, dict] = {}
    for brand in raw["brands"]:
        for s in brand["s"]:
            key = (s["p"], s["a"], tuple(sorted(s["c"].items())))
            brands_of[key].add(brand["b"])
            first_seen.setdefault(key, s)
    return [
        Remote(frozenset(brands_of[key]), s["p"], s["a"], dict(s["c"]))
        for key, s in first_seen.items()
    ]


def by_address(remotes: list[Remote]) -> dict[tuple[str, int], list[Remote]]:
    out: dict[tuple[str, int], list[Remote]] = defaultdict(list)
    for r in remotes:
        out[r.where].append(r)
    return out
