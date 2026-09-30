import unittest

from ice.core.events import Message

from .helpers import ADMIN, OLD, Group, kinds


def edit(g: Group, user, msg_id: int, text: str, album: tuple[int, ...] = ()):
    return g.handle(Message(msg_id, user, text, album=album, edited=True))


class Edits(unittest.TestCase):
    def test_adding_a_link_by_editing_is_punished(self):
        g = Group()
        g.say(OLD, "vendo bici")
        d = edit(g, OLD, 1, "vendo bici, más fotos en www.mitienda.com")
        self.assertEqual(kinds(d), ["DeleteMessage", "Say", "Log"])
        self.assertIn("link agregado al editar un mensaje", d.actions[1].text)
        self.assertEqual(g.member(OLD).warns, 1)

    def test_editing_without_links_is_fine(self):
        g = Group()
        g.say(OLD, "vendo bici")
        self.assertEqual(kinds(edit(g, OLD, 1, "vendo bici rodado 29")), [])

    def test_edits_are_not_flood_nor_repeats(self):
        g = Group()
        g.say(OLD, "vendo bici")
        for i in range(8):
            d = edit(g, OLD, 1, "vendo bici")  # la misma edición, una y otra vez
            self.assertEqual(kinds(d), [])

    def test_edits_are_not_commands(self):
        g = Group()
        g.say(ADMIN, "hola")
        self.assertEqual(kinds(edit(g, ADMIN, 1, "/reglas")), [])

    def test_admins_can_edit_links_in(self):
        g = Group()
        g.say(ADMIN, "aviso")
        self.assertEqual(kinds(edit(g, ADMIN, 1, "aviso www.grupo.com")), [])

    def test_editing_an_album_caption_deletes_the_whole_album(self):
        g = Group()
        g.album(OLD, 3, "vendo heladera")
        d = edit(g, OLD, 1, "vendo heladera t.me/canalspam", album=(1, 2, 3))
        self.assertEqual(d.actions[0].message_ids, (1, 2, 3))
