"""The browser demo must give exactly the answers the Python does: the model
(demo/dna.js), the model-number search (demo/models.js) and the deep search
(demo/sweep.js).

Skipped when Node.js is not installed; CI has it, so it always runs there.
"""
import json
import random
import shutil
import subprocess
import unittest
from collections import defaultdict
from pathlib import Path

from dna import catalogue, models
from dna.evaluate import fold_of
from dna.simulate import ESSENTIALS, run_session
from dna.sweep import batch_candidates, run_batch, run_sweep, sweep_candidates

ROOT = Path(__file__).resolve().parent.parent


@unittest.skipUnless(shutil.which("node"), "Node.js is not installed")
class ParityTest(unittest.TestCase):
    def test_javascript_and_python_ask_the_same_number_of_questions_everywhere(self):
        done = subprocess.run(["node", str(ROOT / "demo" / "parity.mjs")], capture_output=True, text=True, check=True)
        js = json.loads(done.stdout)

        remotes = catalogue.load()
        by_protocol = defaultdict(list)
        for r in remotes:
            by_protocol[r.protocol].append(r)
        py = []
        for t in remotes:
            if not any(b in t.commands for b in ESSENTIALS):
                continue
            pool = [r for r in by_protocol[t.protocol] if not (r.brands & t.brands)]
            py.append([fold_of(t), run_session(t, pool, False), run_session(t, pool, True)])

        self.assertEqual(js["remotes"], len(remotes))
        self.assertEqual(len(js["sessions"]), len(py))
        mismatches = [i for i, (a, b) in enumerate(zip(js["sessions"], py)) if a != b]
        self.assertEqual(mismatches, [], f"{len(mismatches)} sessions differ, first at {mismatches[:5]}")

    def test_model_search_and_deep_search_match_the_python(self):
        index = models.load()
        rng = random.Random(0)
        texts = []
        for m in index:
            key = m.keys[0]
            texts += [f"MODEL: {key}", f"MODEL: {key}XZT", f"MODEL: {models.misread(key, rng)}", key[2:]]
        texts += [IRIS_LABEL, "Model No.: 43E6A", "G7200", "nothing here"]
        hands = [300, 1200, 2500]
        ask = {"models": texts, "sweep": {"step": 9, "hands": hands}}
        done = subprocess.run(
            ["node", str(ROOT / "demo" / "parity-extra.mjs")],
            input=json.dumps(ask), capture_output=True, text=True, check=True, encoding="utf-8",
        )
        js = json.loads(done.stdout)

        py_models = [
            [[h.label, h.protocol, h.address, round(s * 1000)] for h, s in models.search(t, index, limit=3)] for t in texts
        ]
        differ = [t for t, a, b in zip(texts, js["models"], py_models) if a != b]
        self.assertEqual(differ, [], f"{len(differ)} searches differ, first: {differ[:3]}")

        remotes = catalogue.load()
        sweep, batch = sweep_candidates(remotes), batch_candidates(remotes)
        self.assertEqual(js["sweep"]["candidates"], len(sweep))
        py_sessions = []
        for t in range(0, len(batch), 9):
            tv = batch[t]
            for knows in tv.probes:
                old = run_batch(batch, tv, knows)
                row = [t, knows, old.found, old.answers, round(old.seconds * 1000)]
                for hand in hands:
                    out = run_sweep(sweep, tv, knows, hand)
                    row += [out.found, out.answers, round(out.seconds * 1000)]
                py_sessions.append(row)
        self.assertEqual(len(js["sweep"]["sessions"]), len(py_sessions))
        differ = [a[:2] for a, b in zip(js["sweep"]["sessions"], py_sessions) if a != b]
        self.assertEqual(differ, [], f"{len(differ)} deep searches differ, first: {differ[:3]}")


IRIS_LABEL = "\n".join([
    "ATTENTION:",
    "POUR EVITER UN CHOC ELECTRIQUE, NE PAS ENLEVER LE COUVERT.",
    "43G7200",
    "IRIS",
    "ALIMENTATION : 100-240V~50/60Hz 95W",
])


if __name__ == "__main__":
    unittest.main()
