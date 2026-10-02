import unittest
from itertools import count

from de4dc0dex.core.events import Tick

from .helpers import ADMIN, OLD, Group, kinds

# Cada mensaje distinto, para que no salte el anti-repetición: acá se prueba
# solo la cantidad.
_n = count(1)


def ad() -> str:
    return f"vendo cosa número {next(_n)}"


class Flood(unittest.TestCase):
    def test_five_fast_messages_are_fine(self):
        g = Group()
        for _ in range(5):
            d = g.at(1).say(OLD, ad())
        self.assertEqual(d.actions, [])

    def test_sixth_in_window_mutes(self):
        g = Group()
        for _ in range(5):
            g.at(1).say(OLD, ad())
        d = g.at(1).say(OLD, ad())
        self.assertEqual(kinds(d), ["DeleteMessage", "Restrict", "Say", "Log"])
        self.assertTrue(g.say(OLD, ad()).blocked)

    def test_slow_messages_never_trip(self):
        g = Group()
        for _ in range(20):
            d = g.at(3).say(OLD, ad())
        self.assertEqual(d.actions, [])

    def test_mute_expires(self):
        g = Group()
        for _ in range(6):
            g.at(1).say(OLD, ad())
        g.at(601).handle(Tick())
        self.assertIsNone(g.member(OLD).muted_until)
        self.assertFalse(g.say(OLD, ad()).blocked)

    def test_admins_are_not_filtered(self):
        g = Group()
        for _ in range(10):
            d = g.say(ADMIN, "hola")
        self.assertEqual(d.actions, [])


if __name__ == "__main__":
    unittest.main()
