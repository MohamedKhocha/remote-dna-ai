"""The agent's tools, without a language model: standard library only."""
import unittest

from agent import tools


class FindModelTest(unittest.TestCase):
    def test_label_text_finds_the_field_tested_iris(self):
        hit = tools.find_model("MODEL: 43G7200  100-240V~ 50/60Hz")[0]
        self.assertEqual((hit["brand"], hit["protocol"], hit["address"]), ("IRIS", "samsung32", 14))
        self.assertTrue(hit["tested_on_a_real_tv"])

    def test_nothing_that_looks_like_a_model(self):
        self.assertEqual(tools.find_model("hello"), [])


class BrandTest(unittest.TestCase):
    def test_known_brand_lists_its_addresses_most_used_first(self):
        found = tools.brand_addresses("samsung")["addresses"]
        self.assertTrue(found)
        self.assertEqual(found, sorted(found, key=lambda a: -a["remotes"]))

    def test_local_brand_names_its_maker_and_says_when_nothing_is_known(self):
        out = tools.brand_addresses("Iris")
        self.assertEqual(out["maker"], "Skyworth")
        if not out["addresses"]:
            self.assertIn("model number", out["note"])


class PredictTest(unittest.TestCase):
    def test_confirmed_buttons_are_not_guessed_again_and_power_is_last(self):
        guesses = tools.predict_buttons("samsung32", 14, {"volUp": 20})
        self.assertNotIn("volUp", guesses)
        self.assertEqual(list(guesses)[-1], "power")
        self.assertTrue(all(isinstance(c, int) for c in guesses.values()))


class VirtualTVTest(unittest.TestCase):
    def setUp(self):
        self.tv = tools.VirtualTV.from_model("43G7200")

    def test_reacts_only_on_its_own_address(self):
        cmd = tools.predict_buttons("samsung32", 14, {}, ["volUp"])["volUp"]
        self.assertEqual(self.tv.receive("samsung32", 14, cmd), "volUp")
        self.assertIsNone(self.tv.receive("samsung32", 15, cmd))
        self.assertIsNone(self.tv.receive("nec", 14, cmd))

    def test_wifi_or_unknown_model_is_refused(self):
        with self.assertRaises(ValueError):
            tools.VirtualTV.from_model("no model here")


if __name__ == "__main__":
    unittest.main()
