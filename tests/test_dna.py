import json
import tempfile
import unittest
from pathlib import Path

from dna import catalogue, evaluate
from dna.catalogue import Remote
from dna.predict import distribution, exact_match, mixture, most_common, weights

HERE = ("nec", 4)


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


class ReferencePredictorsTest(unittest.TestCase):
    POOL = [
        remote("A", {"volUp": 2, "power": 8, "mute": 9}),
        remote("B", {"volUp": 2, "power": 8, "mute": 9}),
        remote("C", {"volUp": 3, "power": 1, "mute": 5}),
        remote("Far", {"volUp": 3, "power": 77}, address=99),
    ]

    def test_baseline_ignores_what_is_known_and_other_addresses(self):
        self.assertEqual(most_common({"volUp": 3}, HERE, self.POOL, ["power"]), {"power": 8})

    def test_exact_match_follows_the_confirmed_button(self):
        self.assertEqual(exact_match({"volUp": 3}, HERE, self.POOL, ["power", "mute"]), {"power": 1, "mute": 5})

    def test_exact_match_falls_back_when_nobody_agrees(self):
        self.assertEqual(exact_match({"volUp": 77}, HERE, self.POOL, ["power"]), {"power": 8})

    def test_a_button_nobody_has_is_left_unguessed(self):
        self.assertEqual(exact_match({"volUp": 2}, HERE, self.POOL, ["netflix"]), {"netflix": None})


class MixtureTest(unittest.TestCase):
    def test_one_wrong_button_does_not_silence_a_remote(self):
        # Two remotes say power is 8 but disagree with a confirmed mute; one
        # remote agrees on everything known and says power is 1. Exact matching
        # listens to the single remote. So does the mixture, but the others
        # keep a small voice rather than none.
        pool = [
            remote("A", {"volUp": 2, "mute": 9, "power": 8}),
            remote("B", {"volUp": 2, "mute": 9, "power": 8}),
            remote("C", {"volUp": 2, "mute": 5, "power": 1}),
        ]
        known = {"volUp": 2, "mute": 5}
        self.assertEqual(mixture(known, HERE, pool, ["power"]), {"power": 1})
        dist = distribution(weights(known, HERE, pool), "power")
        self.assertGreater(dist[1], dist[8])
        self.assertGreater(dist[8], 0)

    def test_a_layout_seen_on_another_address_helps_a_tv_alone_on_its_own(self):
        pool = [remote("Elsewhere", {"volUp": 2, "power": 8, "mute": 9}, address=77)]
        self.assertEqual(most_common({"volUp": 2}, HERE, pool, ["power"]), {"power": None})
        self.assertEqual(mixture({"volUp": 2}, HERE, pool, ["power"]), {"power": 8})

    def test_a_remote_elsewhere_that_shares_nothing_is_ignored(self):
        pool = [remote("Elsewhere", {"volUp": 3, "power": 8}, address=77)]
        self.assertEqual(mixture({"volUp": 2}, HERE, pool, ["power"]), {"power": None})

    def test_the_same_address_outweighs_another_one(self):
        pool = [
            remote("Here", {"volUp": 2, "power": 1}),
            remote("Far1", {"volUp": 2, "power": 8}, address=70),
            remote("Far2", {"volUp": 2, "power": 8}, address=71),
        ]
        self.assertEqual(mixture({"volUp": 2}, HERE, pool, ["power"]), {"power": 1})

    def test_probabilities_sum_to_one(self):
        pool = [remote("A", {"volUp": 2, "power": 8}), remote("B", {"volUp": 2, "power": 1})]
        dist = distribution(weights({"volUp": 2}, HERE, pool), "power")
        self.assertAlmostEqual(sum(dist.values()), 1.0)


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
        for groups in result.scores.values():
            self.assertEqual(groups["all"].right, 0)

    def test_remotes_alone_on_their_address_are_scored_as_their_own_group(self):
        remotes = [remote("A", {"volUp": 1, "power": 2}, address=1), remote("B", {"volUp": 1, "power": 2}, address=9)]
        result = evaluate.run(remotes, k=1)
        self.assertEqual((result.with_neighbour, result.alone), (0, 2))
        self.assertEqual(result.scores["most_common"]["alone"].right, 0)
        self.assertEqual(result.scores["mixture"]["alone"].right, 2)

    def test_buttons_are_revealed_in_the_order_the_app_learns_them(self):
        r = remote("A", {"power": 1, "menu": 2, "volDown": 3, "volUp": 4})
        self.assertEqual(list(evaluate.revealed(r, 2)), ["volUp", "volDown"])

    def test_the_two_folds_split_the_brands_and_stay_put(self):
        remotes = catalogue.load()
        folds = [evaluate.fold_of(r) for r in remotes]
        self.assertEqual(set(folds), {0, 1})
        self.assertEqual(folds, [evaluate.fold_of(r) for r in remotes])
        self.assertLess(abs(folds.count(0) - folds.count(1)), len(remotes) * 0.2)


if __name__ == "__main__":
    unittest.main()
