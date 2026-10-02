"""La memoria del bot en disco: un archivo SQLite que sobrevive a un reinicio.

Las reglas no saben que existe. Trabajan con `GroupState` en memoria, igual
que siempre, y después de cada evento el Moderator le pide al Store que
guarde. El Store compara cada miembro con lo último que escribió y solo
toca las filas que cambiaron: un Tick en el que no venció nada no escribe.

Lo que dura segundos o minutos no se guarda: los tiempos del anti-flood,
los textos del anti-repetición y cuándo pidió cada uno /reglas. Después de
un reinicio arrancan vacíos, que en el peor caso deja pasar una ráfaga, un
aviso repetido o un /reglas de más.

Las horas se guardan tal cual las da el reloj del Moderator. El bot de
verdad le pasa `time.time()`, que sigue contando aunque el programa se
apague, así que un silencio o una verificación vencen a su hora aunque el
bot haya estado caído en el medio.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from .events import User
from .state import GroupState, Member

# Sube cuando cambia la forma de las tablas. `_migrate` lleva una base vieja
# a la versión actual, paso por paso.
VERSION = 1

SCHEMA = """
CREATE TABLE members (
    user_id         INTEGER PRIMARY KEY,
    name            TEXT    NOT NULL,
    username        TEXT,
    is_admin        INTEGER NOT NULL,
    joined_at       REAL,
    warns           INTEGER NOT NULL,
    muted_until     REAL,
    verify_deadline REAL
);
CREATE TABLE banned (
    user_id  INTEGER PRIMARY KEY,
    name     TEXT NOT NULL,
    username TEXT,
    is_admin INTEGER NOT NULL
);
"""

MemberRow = tuple[int, str, str | None, int, float | None, int, float | None, float | None]
UserRow = tuple[int, str, str | None, int]


def member_row(m: Member) -> MemberRow:
    u = m.user
    return (u.id, u.name, u.username, int(u.is_admin), m.joined_at, m.warns,
            m.muted_until, m.verify_deadline)


def user_row(u: User) -> UserRow:
    return (u.id, u.name, u.username, int(u.is_admin))


class Store:
    def __init__(self, path: str | Path) -> None:
        self.db = sqlite3.connect(path)
        # WAL: si el programa se corta a mitad de una escritura, la base
        # queda como estaba antes, no rota.
        self.db.execute("PRAGMA journal_mode = WAL")
        try:
            self._migrate()
        except Exception:
            self.db.close()  # si no, el archivo queda tomado
            raise
        # Lo último que se escribió, para no volver a escribir lo mismo.
        self._members: dict[int, MemberRow] = {}
        self._banned: dict[int, UserRow] = {}

    def _migrate(self) -> None:
        (version,) = self.db.execute("PRAGMA user_version").fetchone()
        if version > VERSION:
            raise RuntimeError(f"La base es de una versión más nueva de DE4DC0DEX ({version}); "
                               f"esta entiende hasta la {VERSION}.")
        with self.db:
            if version == 0:
                self.db.executescript(SCHEMA)
            self.db.execute(f"PRAGMA user_version = {VERSION}")

    def load(self) -> GroupState:
        state = GroupState()
        for row in self.db.execute("SELECT * FROM members"):
            uid, name, username, admin, joined, warns, muted, deadline = row
            state.members[uid] = Member(
                user=User(uid, name, bool(admin), username),
                joined_at=joined, warns=warns, muted_until=muted,
                verify_deadline=deadline)
            self._members[uid] = row
        for row in self.db.execute("SELECT * FROM banned"):
            uid, name, username, admin = row
            state.banned[uid] = User(uid, name, bool(admin), username)
            self._banned[uid] = row
        return state

    def save(self, state: GroupState) -> None:
        members = {uid: member_row(m) for uid, m in state.members.items()}
        banned = {uid: user_row(u) for uid, u in state.banned.items()}
        changed_m = [r for uid, r in members.items() if self._members.get(uid) != r]
        gone_m = [(uid,) for uid in self._members.keys() - members.keys()]
        changed_b = [r for uid, r in banned.items() if self._banned.get(uid) != r]
        gone_b = [(uid,) for uid in self._banned.keys() - banned.keys()]
        if not (changed_m or gone_m or changed_b or gone_b):
            return
        # Todo junto o nada: una transacción por evento.
        with self.db:
            self.db.executemany("INSERT OR REPLACE INTO members VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                changed_m)
            self.db.executemany("DELETE FROM members WHERE user_id = ?", gone_m)
            self.db.executemany("INSERT OR REPLACE INTO banned VALUES (?, ?, ?, ?)", changed_b)
            self.db.executemany("DELETE FROM banned WHERE user_id = ?", gone_b)
        self._members = members
        self._banned = banned

    def close(self) -> None:
        self.db.close()
