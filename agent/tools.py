"""What the Remote DNA agent can do, in plain Python.

Every function here works on the same catalogue and model as `dna/`, needs no
language model and no network, and is tested by `tests/test_agent_tools.py`.
`agent/remote_agent.py` wraps them as LangChain tools; `agent/mcp_server.py`
offers the read-only ones to any MCP client.
"""
from __future__ import annotations

from collections import Counter
from functools import lru_cache

from dna import catalogue, models, predict
from dna.catalogue import Remote
from dna.simulate import ESSENTIALS

# Buttons a session tries to rebuild. Power comes last on purpose: a wrong
# guess that turns the TV off costs the user a walk to the set.
WANTED = ESSENTIALS + ["chUp", "chDown", "menu", "power"]

# Local brand -> the maker whose remotes it uses. Only pairs checked on a real
# TV belong here; anything else stays unknown rather than guessed.
LOCAL_MAKERS = {"IRIS": "Skyworth"}


@lru_cache(maxsize=1)
def remotes() -> tuple[Remote, ...]:
    return tuple(catalogue.load())


@lru_cache(maxsize=1)
def model_list() -> tuple[models.Model, ...]:
    return tuple(models.load())


def find_model(label_text: str, brand: str | None = None, limit: int = 3) -> list[dict]:
    """Model numbers on a label (or typed) -> the TVs they most likely are."""
    out = []
    for m, score in models.search(label_text, list(model_list()), brand=brand, limit=limit):
        out.append({
            "brand": m.brand,
            "model": m.label,
            "protocol": m.protocol,
            "address": m.address,
            "wifi": m.wifi,
            "tested_on_a_real_tv": m.field,
            "score": round(score, 2),
        })
    return out


def brand_addresses(brand: str, limit: int = 5) -> dict:
    """Where a brand's TVs listen, most catalogue remotes first.

    A local brand with no remotes of its own is looked up under its maker,
    when the pair is known."""
    wanted = brand.strip().upper()
    maker = LOCAL_MAKERS.get(wanted)
    names = {wanted} | ({maker.upper()} if maker else set())
    mine = [r for r in remotes() if any(b.upper() in names for b in r.brands)]
    counts = Counter(r.where for r in mine)
    shared = {w: set() for w in counts}
    for r in remotes():
        if r.where in shared:
            shared[r.where] |= {b for b in r.brands if b.upper() not in names}
    out = {
        "brand": brand,
        "maker": maker,
        "addresses": [
            {"protocol": p, "address": a, "remotes": n, "other_brands_on_it": len(shared[(p, a)])}
            for (p, a), n in counts.most_common(limit)
        ],
    }
    if not mine:
        out["note"] = ("No catalogue remote for this brand. Ask for the model number on the label "
                       "(back of the TV), or use the deep search in the app.")
    return out


def predict_buttons(protocol: str, address: int, confirmed: dict[str, int], wanted: list[str] | None = None) -> dict[str, int]:
    """The model's best command for every wanted button not yet confirmed."""
    pool = [r for r in remotes() if r.protocol == protocol]
    todo = [b for b in (wanted or WANTED) if b not in confirmed]
    guesses = predict.mixture(confirmed, (protocol, address), pool, todo)
    return {b: c for b, c in guesses.items() if c is not None}


def known_addresses(protocol: str) -> int:
    return sum(1 for r in remotes() if r.protocol == protocol)


class VirtualTV:
    """A TV that reacts like a real one: only to its own address, and only to
    commands its remote has. Used by the demo and the tests, never by the app."""

    def __init__(self, protocol: str, address: int, commands: dict[str, int]):
        self.protocol, self.address = protocol, address
        self._button_of = {c: b for b, c in commands.items()}

    @classmethod
    def from_model(cls, label_text: str) -> "VirtualTV":
        hit = find_model(label_text, limit=1)
        if not hit or hit[0]["protocol"] is None:
            raise ValueError(f"no infrared TV matches {label_text!r}")
        where = (hit[0]["protocol"], hit[0]["address"])
        here = [r for r in remotes() if r.where == where]
        if not here:
            raise ValueError(f"no catalogue remote on {where}")
        # The richest remote on that address plays the TV's own remote.
        return cls(*where, max(here, key=lambda r: len(r.commands)).commands)

    def receive(self, protocol: str, address: int, command: int) -> str | None:
        """The button the TV obeys, or None when nothing visible happens."""
        if (protocol, address) != (self.protocol, self.address):
            return None
        return self._button_of.get(command)
