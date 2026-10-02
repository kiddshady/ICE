import unittest

from de4dc0dex.core.config import DAY, Config
from de4dc0dex.core.events import Message, User
from de4dc0dex.core.rules.links import find_links

from .helpers import ADMIN, NEW, OLD, Group, kinds


class LinkDetection(unittest.TestCase):
    def found(self, text):
        return find_links(Message(1, User(9, "x"), text))

    def test_finds_common_links(self):
        for text in ("mirá https://algo.com/x", "entrá a t.me/canalspam",
                     "www.ganaplata.net", "cripto-gratis.xyz ya"):
            with self.subTest(text=text):
                self.assertTrue(self.found(text))

    def test_ignores_normal_text(self):
        for text in ("hola, ¿cómo andan?", "nos vemos a las 10.30", "S.A. de C.V.",
                     "el archivo informe.pdf"):
            with self.subTest(text=text):
                self.assertFalse(self.found(text))


class Links(unittest.TestCase):
    def test_newcomer_link_is_deleted_and_warned(self):
        g = Group()
        g.join_verified(NEW)
        d = g.at(60).say(NEW, "miren www.cripto.xyz")
        self.assertEqual(kinds(d), ["DeleteMessage", "Say", "Log"])
        self.assertEqual(g.member(NEW).warns, 1)

    def test_hidden_link_counts(self):
        g = Group()
        g.join_verified(NEW)
        d = g.say(NEW, "tocá acá", hidden_links=("https://spam.ru",))
        self.assertIn("DeleteMessage", kinds(d))

    def test_forward_from_channel_counts(self):
        g = Group()
        g.join_verified(NEW)
        d = g.say(NEW, "oferta imperdible", forwarded=True)
        self.assertIn("DeleteMessage", kinds(d))

    def test_links_are_banned_even_after_newcomer_period(self):
        g = Group()
        g.join_verified(NEW)
        d = g.at(DAY + 1).say(NEW, "miren https://umaza.edu.ar")
        self.assertIn("DeleteMessage", kinds(d))

    def test_links_are_banned_for_old_members(self):
        g = Group()
        d = g.say(OLD, "las fotos: https://drive.google.com/abc")
        self.assertIn("DeleteMessage", kinds(d))
        self.assertEqual(g.member(OLD).warns, 1)

    def test_admins_can_post_links(self):
        g = Group()
        d = g.say(ADMIN, "reglamento completo: https://umaza.edu.ar")
        self.assertEqual(d.actions, [])

    def test_forward_is_fine_after_newcomer_period(self):
        g = Group()
        g.join_verified(NEW)
        d = g.at(DAY + 1).say(NEW, "oferta imperdible", forwarded=True)
        self.assertEqual(d.actions, [])


class LinksForMembers(unittest.TestCase):
    """Con `links_for_members`, los links solo se prohíben al principio."""

    def test_old_members_can_post_links(self):
        g = Group(Config(links_for_members=True))
        d = g.say(OLD, "las fotos: https://drive.google.com/abc")
        self.assertEqual(d.actions, [])

    def test_newcomers_still_cannot(self):
        g = Group(Config(links_for_members=True))
        g.join_verified(NEW)
        d = g.say(NEW, "miren www.cripto.xyz")
        self.assertIn("DeleteMessage", kinds(d))

    def test_after_newcomer_period_links_are_fine(self):
        g = Group(Config(links_for_members=True))
        g.join_verified(NEW)
        d = g.at(DAY + 1).say(NEW, "miren https://umaza.edu.ar")
        self.assertEqual(d.actions, [])

    def test_three_links_mute(self):
        g = Group()
        g.join_verified(NEW)
        for i in range(3):
            d = g.at(10).say(NEW, f"spam{i}.xyz")
        self.assertIn("Restrict", kinds(d))
        self.assertEqual(g.member(NEW).warns, 0)
        self.assertTrue(g.say(NEW, "hola").blocked)


if __name__ == "__main__":
    unittest.main()
