"""Atajos para escribir los tests en pocas líneas."""
from __future__ import annotations

from de4dc0dex.core import Config, Moderator
from de4dc0dex.core.events import Joined, Message, RepliedTo, User

ADMIN = User(1, "Fran", is_admin=True, username="fran")
OLD = User(2, "Cami", username="cami")      # estaba antes que el bot
NEW = User(3, "Juan")                       # entra durante el test; sin @
SPAM = User(4, "PromoCripto", username="promocripto")


class Group:
    """Un grupo para tests: el reloj lo maneja el test, no el sistema."""

    def __init__(self, config: Config | None = None, store=None) -> None:
        self.mod = Moderator(config, store)
        self.now = 1000.0
        self._next = 1
        for u in (ADMIN, OLD):
            self.mod.state.member(u)

    def at(self, seconds: float) -> "Group":
        self.now += seconds
        return self

    def handle(self, event):
        return self.mod.handle(event, self.now)

    def say(self, user: User, text: str, reply_to: tuple[int, User] | None = None,
            forwarded: bool = False, hidden_links: tuple[str, ...] = ()):
        msg = Message(self._next, user, text,
                      reply_to=RepliedTo(*reply_to) if reply_to else None,
                      forwarded_from_channel=forwarded, hidden_links=hidden_links)
        self._next += 1
        return self.handle(msg)

    def album(self, user: User, photos: int, text: str = ""):
        """Un álbum: llega al cerebro como un solo mensaje con los ids de
        todas sus fotos, como lo junta el adaptador."""
        ids = tuple(range(self._next, self._next + photos))
        self._next += photos
        return self.handle(Message(ids[0], user, text, album=ids))

    def join_verified(self, user: User) -> None:
        """Entra y toca su botón: queda como nuevo pero verificado."""
        from de4dc0dex.core.events import ButtonPressed
        self.handle(Joined(user))
        self.handle(ButtonPressed(user, f"verify:{user.id}"))

    def member(self, user: User):
        return self.mod.state.members.get(user.id)


def kinds(decision) -> list[str]:
    """Los nombres de las acciones, p. ej. ['DeleteMessage', 'Say']."""
    return [type(a).__name__ for a in decision.actions]
