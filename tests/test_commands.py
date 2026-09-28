import unittest

from ice.core.events import Joined

from .helpers import ADMIN, NEW, OLD, SPAM, Group, kinds


class Commands(unittest.TestCase):
    def test_rules_is_public(self):
        g = Group()
        d = g.say(OLD, "/reglas")
        self.assertEqual(kinds(d), ["Say"])

    def test_bot_suffix_is_ignored(self):
        g = Group()
        self.assertEqual(kinds(g.say(OLD, "/reglas@ice_bot")), ["Say"])

    def test_mod_command_from_non_admin_is_deleted(self):
        g = Group()
        d = g.say(OLD, "/ban", reply_to=(1, ADMIN))
        self.assertEqual(kinds(d), ["DeleteMessage"])

    def test_mod_command_needs_reply(self):
        g = Group()
        d = g.say(ADMIN, "/warn")
        self.assertEqual(kinds(d), ["Say"])
        self.assertEqual(g.member(OLD).warns, 0)

    def test_warn_counts_up_to_mute(self):
        g = Group()
        for _ in range(2):
            g.say(ADMIN, "/warn", reply_to=(1, OLD))
        self.assertEqual(g.member(OLD).warns, 2)
        d = g.say(ADMIN, "/warn", reply_to=(1, OLD))
        self.assertIn("Restrict", kinds(d))
        self.assertEqual(g.member(OLD).warns, 0)

    def test_unwarn(self):
        g = Group()
        g.say(ADMIN, "/warn", reply_to=(1, OLD))
        g.say(ADMIN, "/unwarn", reply_to=(1, OLD))
        self.assertEqual(g.member(OLD).warns, 0)

    def test_mute_with_minutes(self):
        g = Group()
        g.say(ADMIN, "/mute 5", reply_to=(1, OLD))
        self.assertEqual(g.member(OLD).muted_until, g.now + 300)
        g.say(ADMIN, "/unmute", reply_to=(1, OLD))
        self.assertFalse(g.say(OLD, "hola").blocked)

    def test_admins_cannot_be_punished(self):
        g = Group()
        d = g.say(ADMIN, "/ban", reply_to=(1, ADMIN))
        self.assertNotIn("Ban", kinds(d))

    def test_ban_blocks_rejoin_until_unban(self):
        g = Group()
        g.say(ADMIN, "/ban", reply_to=(1, NEW))
        self.assertTrue(g.handle(Joined(NEW)).blocked)
        g.say(ADMIN, "/unban", reply_to=(1, NEW))
        self.assertFalse(g.handle(Joined(NEW)).blocked)


class BanByUsername(unittest.TestCase):
    def test_ban_with_reason(self):
        g = Group()
        d = g.say(ADMIN, "/ban @Cami ofrecer servicios sexuales")
        self.assertEqual(kinds(d), ["Ban", "Say", "Log"])
        self.assertEqual(d.actions[1].text,
                         "Cami recibió un ban permanente por ofrecer servicios sexuales.")
        self.assertIn(OLD.id, g.mod.state.banned)

    def test_ban_without_reason_does_not_mention_one(self):
        g = Group()
        d = g.say(ADMIN, "/ban @cami")
        self.assertEqual(d.actions[1].text, "Cami recibió un ban permanente.")

    def test_reason_starting_with_por_is_not_doubled(self):
        g = Group()
        d = g.say(ADMIN, "/ban @cami Por spam")
        self.assertEqual(d.actions[1].text, "Cami recibió un ban permanente por spam.")

    def test_ban_by_reply_takes_the_reason_too(self):
        g = Group()
        d = g.say(ADMIN, "/ban vender armas", reply_to=(1, OLD))
        self.assertEqual(d.actions[1].text, "Cami recibió un ban permanente por vender armas.")

    def test_ban_wipes_their_messages(self):
        g = Group()
        d = g.say(ADMIN, "/ban @cami")
        self.assertTrue(d.actions[0].revoke_messages)

    def test_unknown_username(self):
        g = Group()
        d = g.say(ADMIN, "/ban @nadie spam")
        self.assertEqual(kinds(d), ["Say"])
        self.assertIn("No hay registro de @nadie", d.actions[0].text)

    def test_username_wins_over_reply(self):
        g = Group()
        g.mod.state.member(SPAM)
        g.say(ADMIN, "/ban @promocripto", reply_to=(1, OLD))
        self.assertIn(SPAM.id, g.mod.state.banned)
        self.assertNotIn(OLD.id, g.mod.state.banned)

    def test_unban_by_username(self):
        g = Group()
        g.say(ADMIN, "/ban @cami")
        g.say(ADMIN, "/unban @cami")
        self.assertNotIn(OLD.id, g.mod.state.banned)

    def test_admins_cannot_be_banned_by_username(self):
        g = Group()
        d = g.say(ADMIN, "/ban @fran")
        self.assertNotIn("Ban", kinds(d))

    def test_mute_by_username_with_minutes(self):
        g = Group()
        g.say(ADMIN, "/mute @cami 5")
        self.assertEqual(g.member(OLD).muted_until, g.now + 300)

    def test_rules_are_general(self):
        g = Group()
        text = g.say(OLD, "/reglas").actions[0].text
        self.assertNotIn("compra", text)
        self.assertIn("6. Contenido prohibido: ban directo.", text)


if __name__ == "__main__":
    unittest.main()
