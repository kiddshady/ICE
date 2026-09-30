import unittest

from ice.core.actions import DeleteMessage, Say

from .helpers import OLD, Group, kinds


def deleted(d) -> tuple[int, ...]:
    return next(a.message_ids for a in d.actions if isinstance(a, DeleteMessage))


class Albums(unittest.TestCase):
    def test_a_big_album_is_not_flood(self):
        g = Group()
        d = g.album(OLD, 10, "vendo bici rodado 29")
        self.assertEqual(kinds(d), [])

    def test_many_albums_in_a_row_are_flood(self):
        g = Group()
        for i in range(5):
            g.album(OLD, 3, f"aviso {i}")
            g.at(1)
        d = g.album(OLD, 3, "aviso 5")
        self.assertIn("Restrict", kinds(d))
        self.assertEqual(len(deleted(d)), 3)

    def test_link_deletes_the_whole_album_with_one_warning(self):
        g = Group()
        d = g.album(OLD, 4, "más fotos en www.mitienda.com")
        self.assertEqual(deleted(d), (1, 2, 3, 4))
        self.assertEqual(sum(isinstance(a, Say) for a in d.actions), 1)
        self.assertEqual(g.member(OLD).warns, 1)

    def test_repeated_album_is_deleted_whole(self):
        g = Group()
        g.album(OLD, 3, "vendo heladera")
        d = g.at(60).album(OLD, 3, "vendo heladera")
        self.assertEqual(deleted(d), (4, 5, 6))
        self.assertEqual(sum(isinstance(a, Say) for a in d.actions), 1)

    def test_same_photos_without_text_are_a_repeat(self):
        # Sin texto, el adaptador pone qué fotos son: el mismo álbum reenviado
        # trae las mismas; uno nuevo, otras.
        g = Group()
        g.album(OLD, 2, "[album fotoA fotoB]")
        self.assertEqual(kinds(g.at(60).album(OLD, 2, "[album fotoC fotoD]")), [])
        self.assertIn("DeleteMessage", kinds(g.at(60).album(OLD, 2, "[album fotoA fotoB]")))
