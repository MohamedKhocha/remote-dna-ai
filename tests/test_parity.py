"""The browser demo (demo/dna.js) must ask exactly the questions the Python does.

Skipped when Node.js is not installed; CI has it, so it always runs there.
"""
import json
import shutil
import subprocess
import unittest
from collections import defaultdict
from pathlib import Path

from dna import catalogue
from dna.evaluate import fold_of
from dna.simulate import ESSENTIALS, run_session

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


if __name__ == "__main__":
    unittest.main()
