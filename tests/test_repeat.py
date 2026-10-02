import unittest

from de4dc0dex.core.config import MINUTE, Config
from de4dc0dex.core.rules.repeat import normalize

from .helpers import ADMIN, NEW, OLD, Group, kinds

TEXT = "vendo bici rodado 29, poco uso, $250.000"


class Repeat(unittest.TestCase):
    def test_same_message_within_window_is_deleted(self):
        g = Group()
        g.say(OLD, TEXT)
        d = g.at(5 * MINUTE).say(OLD, TEXT)
        self.assertEqual(kinds(d), ["DeleteMessage", "Say", "Log"])

    def test_after_window_it_is_fine(self):
        g = Group()
        g.say(OLD, TEXT)
        d = g.at(15 * MINUTE).say(OLD, TEXT)
        self.assertEqual(d.actions, [])

    def test_window_counts_from_the_one_that_stayed(self):
        g = Group()
        g.say(OLD, TEXT)
        g.at(10 * MINUTE).say(OLD, TEXT)           # borrado
        d = g.at(5 * MINUTE).say(OLD, TEXT)        # 15 min desde el primero
        self.assertEqual(d.actions, [])

    def test_case_and_spaces_do_not_matter(self):
        self.assertEqual(normalize("  Hola   GENTE "), "hola gente")
        g = Group()
        g.say(OLD, TEXT)
        d = g.at(60).say(OLD, "  " + TEXT.upper() + "  ")
        self.assertIn("DeleteMessage", kinds(d))

    def test_short_messages_count_in_buy_sell(self):
        g = Group()
        g.say(OLD, "vendo")
        d = g.at(60).say(OLD, "vendo")
        self.assertIn("DeleteMessage", kinds(d))

    def test_min_length_lets_short_messages_repeat(self):
        g = Group(Config(repeat_min_length=12))
        g.say(OLD, "jajaja")
        d = g.at(60).say(OLD, "jajaja")
        self.assertEqual(d.actions, [])

    def test_different_people_can_say_the_same(self):
        g = Group()
        g.join_verified(NEW)
        g.say(OLD, TEXT)
        d = g.at(60).say(NEW, TEXT)
        self.assertEqual(d.actions, [])

    def test_admins_can_repeat(self):
        g = Group()
        g.say(ADMIN, TEXT)
        d = g.at(60).say(ADMIN, TEXT)
        self.assertEqual(d.actions, [])

    def test_a_message_deleted_by_another_rule_does_not_count(self):
        g = Group()
        g.join_verified(NEW)
        g.say(NEW, TEXT, forwarded=True)           # borrado: reenvío siendo nuevo
        g.mod.state.members[NEW.id].joined_at -= 2 * 86400  # ya no es nuevo
        d = g.at(60).say(NEW, TEXT, forwarded=True)
        self.assertEqual(d.actions, [])


if __name__ == "__main__":
    unittest.main()
