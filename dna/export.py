"""Write what the phone app needs: the model's settings and a parity fixture.

    python -m dna.export

export/dna-model.json   the three settings, the version and the commit they
                        come from. The app already ships the catalogue, so the
                        settings are all it needs to run the same model.
export/dna-parity.json  real sessions from the held-out half, replayed answer
                        by answer with the scores the model gave after each
                        one. The app's tests replay them and must find the
                        same numbers.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from collections import defaultdict
from pathlib import Path

from . import catalogue
from .evaluate import REPORTED_FOLD, fold_of
from .predict import ELSEWHERE, MISMATCH, UNKNOWN
from .simulate import ESSENTIALS, Session, has_neighbours, run_session

OUT = Path(__file__).resolve().parent.parent / "export"
MODEL_VERSION = 1
SESSIONS = 40
STEPS = 12


def commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main() -> None:
    OUT.mkdir(exist_ok=True)
    data = catalogue.DEFAULT_PATH.read_bytes()
    model = {
        "version": MODEL_VERSION,
        "source": "https://github.com/MohamedKhocha/remote-dna-ai",
        "commit": commit(),
        "catalogue_sha256": hashlib.sha256(data).hexdigest(),
        "mismatch": MISMATCH,
        "elsewhere": ELSEWHERE,
        "unknown": UNKNOWN,
    }
    (OUT / "dna-model.json").write_text(json.dumps(model, indent=2) + "\n", encoding="utf-8")

    remotes = catalogue.load()
    by_protocol = defaultdict(list)
    for r in remotes:
        by_protocol[r.protocol].append(r)
    cases = []
    for index, target in enumerate(remotes):
        if len(cases) == SESSIONS:
            break
        if fold_of(target) != REPORTED_FOLD or not all(b in target.commands for b in ESSENTIALS):
            continue
        pool = [r for r in by_protocol[target.protocol] if not (r.brands & target.brands)]
        if not has_neighbours(target.where, pool):
            continue
        trace: list = []
        run_session(target, pool, True, trace)
        session = Session(target.where, pool)
        found: set[str] = set()
        steps = []
        for command, button in trace[:STEPS]:
            missing = [b for b in ESSENTIALS if b not in found]
            top = sorted(session.score(missing).items(), key=lambda kv: (-kv[1], kv[0]))[:3]
            steps.append({"missing": missing, "top": [[c, round(s, 12)] for c, s in top], "command": command, "button": button})
            session.learn(command, button)
            if button in ESSENTIALS:
                found.add(button)
        cases.append({"target": index, "brands": sorted(target.brands), "protocol": target.protocol, "address": target.address, "steps": steps})
    fixture = {"catalogue_sha256": model["catalogue_sha256"], "model": model, "cases": cases}
    (OUT / "dna-parity.json").write_text(json.dumps(fixture) + "\n", encoding="utf-8")
    print(f"model {model['commit']}: {len(cases)} sessions, {sum(len(c['steps']) for c in cases)} steps")


if __name__ == "__main__":
    main()
