"""La memoria del bot: qué sabe de cada miembro.

Vive en memoria mientras el bot corre. Para que sobreviva a un reinicio, el
Moderator la guarda en SQLite después de cada evento (ver store.py). Las
reglas no se enteran: siempre trabajan con esto.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from .events import User


@dataclass
class Member:
    user: User
    # Cuándo entró. None = ya estaba cuando llegó el bot: se lo trata como
    # alguien de siempre, no como nuevo.
    joined_at: float | None = None
    warns: int = 0
    # Hasta cuándo está silenciado. None = no lo está.
    muted_until: float | None = None
    # Hasta cuándo tiene para verificarse. None = ya está verificado.
    verify_deadline: float | None = None
    # Cuándo mandó sus últimos mensajes, para medir el flood.
    recent: deque[float] = field(default_factory=deque)
    # Sus últimos mensajes (normalizados) y cuándo los mandó, para el
    # anti-repetición.
    last_texts: dict[str, float] = field(default_factory=dict)


@dataclass
class GroupState:
    members: dict[int, Member] = field(default_factory=dict)
    banned: dict[int, User] = field(default_factory=dict)
    # La administración, tal como la contó el adaptador (evento StaffList).
    # No se guarda en disco: al arrancar, el adaptador la vuelve a pedir.
    staff: list[User] = field(default_factory=list)

    def member(self, user: User) -> Member:
        """El registro de un usuario; si no lo conocía, lo crea como alguien
        de siempre. Actualiza el nombre y si es admin, que pueden cambiar."""
        m = self.members.get(user.id)
        if m is None:
            m = Member(user=user)
            self.members[user.id] = m
        else:
            m.user = user
        return m

    def find_username(self, username: str) -> User | None:
        """Quién tiene ese @usuario, entre los que el bot ya vio. Telegram no
        le deja a un bot buscar a una persona por su @: solo puede reconocer
        a quien ya pasó por el grupo desde que el bot está."""
        wanted = username.lstrip("@").casefold()
        known = [m.user for m in self.members.values()] + list(self.banned.values())
        return next((u for u in known
                     if u.username and u.username.casefold() == wanted), None)
