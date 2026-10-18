import unittest

from dna import catalogue
from dna.catalogue import Remote
from dna.sweep import (
    LOOKBACK_MS,
    batch_candidates,
    deep_probes,
    frame_us,
    run_batch,
    run_sweep,
    suspects,
    sweep_candidates,
)

REMOTES = catalogue.load()
SWEEP = sweep_candidates(REMOTES)
BATCH = batch_candidates(REMOTES)


def remote(commands, address=1, protocol="nec"):
    return Remote(frozenset(["X"]), protocol, address, commands)


class ProbesTest(unittest.TestCase):
    def test_a_command_that_is_mostly_power_is_never_sent(self):
        pool = [remote({"power": 8, "volUp": 8, "one": 1, "two": 2}, a) for a in (1, 2, 3)]
        self.assertNotIn(8, deep_probes(pool))

    def test_the_second_probe_covers_the_remotes_the_first_missed(self):
        pool = [remote({"one": 1, "two": 2}, 1), remote({"one": 1, "two": 2}, 2), remote({"nine": 9}, 3)]
        self.assertEqual(deep_probes(pool), [1, 9])


class CandidatesTest(unittest.TestCase):
    def test_only_addresses_no_catalogue_remote_uses(self):
        known = {r.where for r in REMOTES}
        addresses = {(c.protocol, c.address) for c in SWEEP}
        self.assertEqual(len(addresses), 720)
        self.assertFalse(addresses & known)

    def test_the_second_pass_starts_after_the_whole_first(self):
        first = SWEEP[: len(BATCH)]
        second = SWEEP[len(BATCH):]
        self.assertEqual([(c.protocol, c.address) for c in first], [(c.protocol, c.address) for c in second])
        self.assertTrue(all(a.probes != b.probes for a, b in zip(first, second)))

    def test_frame_times_match_the_protocols(self):
        self.assertEqual(frame_us("nec", 0x12, 0x34), frame_us("nec", 0xAB, 0x01))  # always the same length
        self.assertEqual(frame_us("nec", 0, 0), 68_030)
        self.assertAlmostEqual(frame_us("rc5", 0, 0) / 1000, 24.0, delta=0.5)
        self.assertGreater(frame_us("sirc", 1, 1), 2 * 45_000)  # three repeats


class SuspectsTest(unittest.TestCase):
    def test_the_window_before_the_tap_and_the_send_overlapping_it(self):
        sent_at = {i: i * 1000.0 for i in range(6)}
        self.assertEqual(suspects(sent_at, 5500, 3000), [2, 3, 4, 5])

    def test_nothing_sent_after_the_tap(self):
        self.assertEqual(suspects({0: 0, 1: 100, 2: 200, 3: 900}, 250), [0, 1, 2])

    def test_a_tap_before_anything_went_out(self):
        self.assertEqual(suspects({}, 10), [])


class SweepTest(unittest.TestCase):
    TVS = BATCH[::9]  # every protocol, start to end of the list

    def test_every_tv_is_found_in_a_few_answers_whatever_the_hand(self):
        worst = 0
        for tv in self.TVS:
            for which in range(len(tv.probes)):
                for hand in (300, 1200, 2500):
                    out = run_sweep(SWEEP, tv, tv.probes[which], hand)
                    found = SWEEP[out.found]
                    self.assertEqual((found.protocol, found.address), (tv.protocol, tv.address))
                    worst = max(worst, out.answers)
        self.assertLessEqual(worst, 9)

    def test_far_fewer_answers_than_batches(self):
        tv = BATCH[-1]  # the very end of the list: the batch search's worst case
        self.assertGreaterEqual(run_batch(BATCH, tv, tv.probes[0]).answers, 30)
        self.assertLessEqual(run_sweep(SWEEP, tv, tv.probes[0], 1000).answers, 9)

    def test_a_stray_tap_costs_one_answer_and_the_sweep_carries_on(self):
        tv = next(c for c in BATCH if c.protocol == "samsung32")
        clean = run_sweep(SWEEP, tv, tv.probes[0], 800)
        stray = run_sweep(SWEEP, tv, tv.probes[0], 800, stray_at=5000)
        self.assertEqual(SWEEP[stray.found].address, tv.address)
        self.assertEqual(stray.answers, clean.answers + 2)  # the stray tap and its replay

    def test_a_hand_slower_than_the_window_is_missed(self):
        tv = BATCH[40]
        self.assertIsNone(run_sweep(SWEEP, tv, tv.probes[0], LOOKBACK_MS + 1500).found)


if __name__ == "__main__":
    unittest.main()
