import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from de4dc0dex.core import Moderator, Store
from de4dc0dex.core.config import MINUTE
from de4dc0dex.core.events import Joined, Left, Tick

from .helpers import ADMIN, NEW, OLD, SPAM, Group, kinds


class Restart(unittest.TestCase):
    """Cada test hace algo, apaga el bot y lo vuelve a prender con el mismo
    archivo. Lo que importa es qué recuerda el bot nuevo."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "de4dc0dex.db"
        self.stores = []
        self.g = Group(store=self.open())
        self.g.handle(Tick())  # guarda a los que ya estaban

    def tearDown(self):
        for s in self.stores:
            s.close()
        self.dir.cleanup()

    def open(self):
        s = Store(self.path)
        self.stores.append(s)
        return s

    def restart(self):
        """Apaga y prende: el mismo reloj, un Moderator nuevo."""
        self.stores[-1].close()
        self.g.mod = Moderator(store=self.open())

    def test_warns_survive(self):
        self.g.say(ADMIN, "/warn", reply_to=(1, OLD))
        self.restart()
        self.assertEqual(self.g.member(OLD).warns, 1)

    def test_mute_survives_and_still_blocks(self):
        self.g.say(ADMIN, "/mute 10", reply_to=(1, OLD))
        self.restart()
        self.assertTrue(self.g.at(MINUTE).say(OLD, "hola").blocked)

    def test_pending_verification_still_expires(self):
        self.g.handle(Joined(NEW))
        self.restart()
        d = self.g.at(3 * MINUTE).handle(Tick())
        self.assertIn("Kick", kinds(d))

    def test_verified_newcomer_is_still_new(self):
        self.g.join_verified(NEW)
        self.restart()
        d = self.g.at(MINUTE).say(NEW, "vendo", forwarded=True)
        self.assertIn("DeleteMessage", kinds(d))

    def test_ban_survives(self):
        self.g.mod.state.member(SPAM)
        self.g.say(ADMIN, "/ban @promocripto")
        self.restart()
        self.assertTrue(self.g.handle(Joined(SPAM)).blocked)
        d = self.g.say(ADMIN, "/unban @promocripto")
        self.assertIn("Unban", kinds(d))

    def test_usernames_survive(self):
        self.restart()
        d = self.g.say(ADMIN, "/warn @cami")
        self.assertNotIn("No hay registro", d.actions[0].text)
        self.assertEqual(self.g.member(OLD).warns, 1)

    def test_rename_noticed_across_restart(self):
        self.restart()
        d = self.g.say(replace(OLD, name="Camila"), "vendo mesa")
        self.assertEqual(kinds(d), ["Say", "Log"])

    def test_someone_who_left_is_forgotten(self):
        self.g.join_verified(NEW)
        self.g.handle(Left(NEW))
        self.restart()
        self.assertIsNone(self.g.member(NEW))

    def test_nothing_changed_writes_nothing(self):
        db = self.stores[-1].db
        before = db.total_changes
        self.g.at(5).handle(Tick())
        self.assertEqual(db.total_changes, before)

    def test_newer_database_is_refused(self):
        self.stores[-1].close()
        con = sqlite3.connect(self.path)
        con.execute("PRAGMA user_version = 99")
        con.close()
        with self.assertRaises(RuntimeError):
            Store(self.path)


if __name__ == "__main__":
    unittest.main()
