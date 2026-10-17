import random
import unittest

from dna import models


class ModelSearchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = models.load()

    def test_reads_the_model_line_of_a_label(self):
        label = "SKYWORTH GROUP\nMODEL: 43G7200\nAC 100-240V 50/60Hz\nSN 2024A12345678"
        self.assertEqual(models.candidates(label)[0], "43G7200")

    def test_ignores_sizes_years_and_words(self):
        self.assertEqual(models.candidates("Smart TV 4K 2019 LED"), [])

    def test_finds_the_field_tested_tv(self):
        (hit, score), *_ = models.search("MODEL: 43G7200", self.index)
        self.assertEqual((hit.brand, hit.protocol, hit.address, hit.field), ("IRIS", "samsung32", 14, True))
        self.assertEqual(score, 1.0)

    def test_tolerates_a_suffix_and_a_misread_character(self):
        self.assertAlmostEqual(models.match("55U6KXZT", "55U6K"), 0.9)
        self.assertAlmostEqual(models.match("55U6X", "55U6K"), 0.8)
        self.assertEqual(models.match("1234", "1235"), 0.0)  # too short to guess

    def test_misread_swaps_one_confusable_character(self):
        out = models.misread("B3228HD", random.Random(1))
        self.assertEqual(len(out), 7)
        self.assertEqual(sum(a != b for a, b in zip(out, "B3228HD")), 1)

    def test_report_runs(self):
        self.assertIn("| misread |", models.retrieval_report(self.index))


if __name__ == "__main__":
    unittest.main()
