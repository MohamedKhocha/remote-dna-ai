import json
import tempfile
import unittest
from pathlib import Path

from dna import catalogue, evaluate
from dna.catalogue import Remote
from dna.predict import exact_match, most_common


def remote(brand, commands, protocol="nec", address=4):
    return Remote(frozenset([brand]), protocol, address, commands)


class CatalogueTest(unittest.TestCase):
    def test_the_same_remote_under_two_brands_is_one_entry(self):
        raw = {
            "v": 1,
            "brands": [
                {"b": "Alpha", "s": [{"p": "nec", "a": 4, "c": {"power": 8, "volUp": 2}}]},
                {"b": "Beta", "s": [{"p": "nec", "a": 4, "c": {"volUp": 2, "power": 8}}]},
                {"b": "Gamma", "s": [{"p": "nec", "a": 4, "c": {"power": 9}}]},
            ],
        }
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "c.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            remotes = catalogue.load(path)
        self.assertEqual(len(remotes), 2)
        self.assertEqual(remotes[0].brands, frozenset({"Alpha", "Beta"}))

    def test_the_shipped_catalogue_loads(self):
        remotes = catalogue.load()
        self.assertGreater(len(remotes), 1000)
        self.assertTrue(all(r.commands for r in remotes))


class PredictTest(unittest.TestCase):
    POOL = [
        remote("A", {"volUp": 2, "power": 8, "mute": 9}),
        remote("B", {"volUp": 2, "power": 8, "mute": 9}),
        remote("C", {"volUp": 3, "power": 1, "mute": 5}),
    ]

    def test_baseline_ignores_what_is_known(self):
        self.assertEqual(most_common({"volUp": 3}, self.POOL, ["power"]), {"power": 8})

    def test_exact_match_follows_the_confirmed_button(self):
        self.assertEqual(exact_match({"volUp": 3}, self.POOL, ["power", "mute"]), {"power": 1, "mute": 5})

    def test_exact_match_falls_back_when_nobody_agrees(self):
        self.assertEqual(exact_match({"volUp": 77}, self.POOL, ["power"]), {"power": 8})

    def test_a_button_nobody_has_is_left_unguessed(self):
        self.assertEqual(exact_match({"volUp": 2}, self.POOL, ["netflix"]), {"netflix": None})


class EvaluateTest(unittest.TestCase):
    def test_a_brand_never_predicts_itself(self):
        # Two remotes of one brand hold the only right answer for each other.
        # If the held-out brand leaked into the pool, accuracy would be 100%.
        remotes = [
            remote("Solo", {"volUp": 1, "power": 50}),
            remote("Solo", {"volUp": 1, "power": 50, "mute": 51}),
            remote("Other", {"volUp": 1, "power": 60, "mute": 61}),
        ]
        result = evaluate.run(remotes, k=1)
        for score in result.scores.values():
            self.assertEqual(score.right, 0)

    def test_remotes_alone_on_their_address_are_counted_but_not_scored(self):
        remotes = [remote("A", {"volUp": 1, "power": 2}, address=1), remote("B", {"volUp": 1, "power": 2}, address=9)]
        result = evaluate.run(remotes, k=1)
        self.assertEqual((result.total, result.with_neighbour), (2, 0))

    def test_buttons_are_revealed_in_the_order_the_app_learns_them(self):
        r = remote("A", {"power": 1, "menu": 2, "volDown": 3, "volUp": 4})
        self.assertEqual(list(evaluate.revealed(r, 2)), ["volUp", "volDown"])


if __name__ == "__main__":
    unittest.main()
