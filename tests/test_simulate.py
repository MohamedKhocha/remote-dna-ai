import unittest

from dna.catalogue import Remote
from dna.simulate import GIVE_UP, catalogue_order, run_session


def remote(brand, commands, address=4, protocol="rc5"):
    return Remote(frozenset([brand]), protocol, address, commands)


ESSENTIAL_LAYOUT = {"volUp": 16, "volDown": 17, "mute": 13, "ok": 59, "back": 10}


class SimulateTest(unittest.TestCase):
    def test_the_catalogue_order_tries_known_commands_before_the_blind_sweep(self):
        pool = [remote("A", {"volUp": 30, "power": 12})]
        order = catalogue_order(("rc5", 4), pool, ["volUp"])
        self.assertEqual(order[:2], [30, 12])  # needed first, power last among known
        self.assertEqual(len(order), 64)  # then every other RC5 command once

    def test_a_remote_identical_to_one_in_the_catalogue_takes_one_question_per_button(self):
        target = remote("Target", dict(ESSENTIAL_LAYOUT))
        pool = [remote("Twin", dict(ESSENTIAL_LAYOUT))]
        self.assertEqual(run_session(target, pool, use_model=True), 5)
        self.assertEqual(run_session(target, pool, use_model=False), 5)

    def test_the_model_follows_the_remote_the_answers_point_to(self):
        # Three remotes share the address. Two use one layout; the target uses
        # the third. Once volUp is confirmed the model switches to the right
        # remote, while the fixed order keeps trying the majority's commands.
        majority = {"volUp": 1, "volDown": 2, "mute": 3, "ok": 4, "back": 5}
        minority = {"volUp": 20, "volDown": 21, "mute": 22, "ok": 23, "back": 24}
        pool = [remote("A", dict(majority)), remote("B", dict(majority)), remote("C", dict(minority))]
        target = remote("Target", dict(minority))
        self.assertLess(run_session(target, pool, use_model=True), run_session(target, pool, use_model=False))

    def test_a_session_whose_commands_lie_outside_the_protocol_gives_up(self):
        target = remote("Target", {"volUp": 900})
        self.assertEqual(run_session(target, [], use_model=False), GIVE_UP)


if __name__ == "__main__":
    unittest.main()
