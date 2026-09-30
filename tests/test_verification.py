import unittest

from ice.core.events import ButtonPressed, Joined, Left, Tick

from .helpers import ADMIN, NEW, OLD, Group, kinds


class Verification(unittest.TestCase):
    def test_join_restricts_and_sends_button(self):
        g = Group()
        d = g.handle(Joined(NEW))
        self.assertEqual(kinds(d), ["Restrict", "Say", "Log"])
        self.assertEqual(d.actions[1].button.data, f"verify:{NEW.id}")
        self.assertIsNotNone(g.member(NEW).verify_deadline)

    def test_unverified_cannot_write(self):
        g = Group()
        g.handle(Joined(NEW))
        d = g.say(NEW, "hola")
        self.assertTrue(d.blocked)
        self.assertEqual(d.actions, [])

    def test_own_button_verifies(self):
        g = Group()
        g.handle(Joined(NEW))
        d = g.at(30).handle(ButtonPressed(NEW, f"verify:{NEW.id}"))
        self.assertIn("Unrestrict", kinds(d))
        self.assertIn("Unsay", kinds(d))
        self.assertIsNone(g.member(NEW).verify_deadline)
        self.assertFalse(g.say(NEW, "hola").blocked)

    def test_someone_elses_button_does_nothing(self):
        g = Group()
        g.handle(Joined(NEW))
        d = g.handle(ButtonPressed(OLD, f"verify:{NEW.id}"))
        self.assertEqual(kinds(d), ["Toast"])
        self.assertIsNotNone(g.member(NEW).verify_deadline)

    def test_timeout_kicks(self):
        g = Group()
        g.handle(Joined(NEW))
        self.assertEqual(kinds(g.at(119).handle(Tick())), [])
        d = g.at(2).handle(Tick())
        self.assertEqual(kinds(d), ["Kick", "Unsay", "Say", "Log"])
        self.assertIsNone(g.member(NEW))

    def test_admin_skips_verification(self):
        g = Group()
        d = g.handle(Joined(ADMIN))
        self.assertEqual(d.actions, [])

    def test_leaving_unverified_removes_challenge(self):
        g = Group()
        g.handle(Joined(NEW))
        d = g.handle(Left(NEW))
        self.assertEqual(kinds(d), ["Unsay"])
        self.assertEqual(kinds(g.at(500).handle(Tick())), [])


if __name__ == "__main__":
    unittest.main()
