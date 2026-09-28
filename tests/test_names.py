import unittest
from dataclasses import replace

from ice.core.config import MINUTE
from ice.core.events import ButtonPressed, Joined, Tick

from .helpers import ADMIN, NEW, OLD, Group, kinds

CAMILA = replace(OLD, name="Camila")


class Names(unittest.TestCase):
    def test_rename_is_announced(self):
        g = Group()
        d = g.say(CAMILA, "vendo mesa")
        self.assertEqual(kinds(d), ["Say", "Log"])
        self.assertIn("«Cami» ahora figura como «Camila»", d.actions[0].text)
        self.assertEqual(g.member(OLD).user.name, "Camila")

    def test_announced_only_once(self):
        g = Group()
        g.say(CAMILA, "vendo mesa")
        d = g.at(60).say(CAMILA, "vendo silla")
        self.assertEqual(d.actions, [])

    def test_same_name_says_nothing(self):
        g = Group()
        d = g.say(OLD, "vendo mesa")
        self.assertEqual(d.actions, [])

    def test_first_time_seen_is_not_a_rename(self):
        g = Group()
        d = g.say(replace(NEW, name="Juancito"), "vendo mesa")
        self.assertEqual(d.actions, [])

    def test_still_announced_when_the_message_is_deleted(self):
        g = Group()
        d = g.say(CAMILA, "miren www.estafa.xyz")
        self.assertEqual(kinds(d)[:2], ["Say", "Log"])
        self.assertIn("DeleteMessage", kinds(d))

    def test_noticed_through_a_reply(self):
        g = Group()
        d = g.say(ADMIN, "¿sigue disponible?", reply_to=(1, CAMILA))
        self.assertEqual(kinds(d), ["Say", "Log"])
        self.assertEqual(g.member(OLD).user.name, "Camila")

    def test_noticed_through_a_button(self):
        g = Group()
        g.handle(Joined(NEW))
        d = g.handle(ButtonPressed(replace(NEW, name="Juancito"), f"verify:{NEW.id}"))
        self.assertEqual(kinds(d)[:2], ["Say", "Log"])

    def test_muted_rename_waits_until_the_bot_can_see_it(self):
        g = Group()
        g.say(ADMIN, "/mute 10", reply_to=(1, OLD))
        blocked = g.at(60).say(CAMILA, "hola")
        self.assertTrue(blocked.blocked)
        self.assertEqual(g.member(OLD).user.name, "Cami")
        g.at(10 * MINUTE).handle(Tick())
        d = g.say(CAMILA, "vendo mesa")
        self.assertEqual(kinds(d), ["Say", "Log"])

    def test_admin_rename_only_goes_to_the_log(self):
        g = Group()
        d = g.say(replace(ADMIN, name="Fran Admin"), "buenas")
        self.assertEqual(kinds(d), ["Log"])


if __name__ == "__main__":
    unittest.main()
