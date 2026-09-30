"""Eventos: lo que pasa en el grupo, contado sin nada de Telegram.

El adaptador de Telegram (o el simulador) traduce lo que recibe a uno de estos
objetos y se lo pasa al cerebro. El cerebro nunca ve un Update de Telegram.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    id: int
    name: str
    # Lo averigua el adaptador (getChatMember). El cerebro no puede preguntarle
    # a Telegram, así que confía en lo que le dicen.
    is_admin: bool = False
    # El @usuario, sin la arroba. Es opcional en Telegram: hay cuentas sin él.
    username: str | None = None
    # Quien creó el grupo (status "creator" en Telegram). También es admin.
    is_owner: bool = False
    # Una cuenta de bot. Telegram lo marca en cada usuario (User.is_bot).
    is_bot: bool = False


@dataclass(frozen=True)
class Joined:
    """Alguien entró al grupo."""
    user: User


@dataclass(frozen=True)
class Left:
    """Alguien se fue del grupo por su cuenta."""
    user: User


@dataclass(frozen=True)
class RepliedTo:
    """El mensaje al que se está respondiendo. Los comandos de moderación
    (/warn, /mute, /ban) apuntan a alguien respondiéndole un mensaje suyo."""
    message_id: int
    user: User


@dataclass(frozen=True)
class Message:
    """Alguien escribió en el grupo."""
    id: int
    user: User
    text: str
    reply_to: RepliedTo | None = None
    # Reenviado desde un canal: la forma favorita de los bots de spam.
    forwarded_from_channel: bool = False
    # Links que no se ven en el texto: en Telegram una palabra puede llevar un
    # link escondido (entity text_link). El adaptador los saca y los pone acá.
    hidden_links: tuple[str, ...] = ()


@dataclass(frozen=True)
class ButtonPressed:
    """Alguien tocó un botón de un mensaje del bot (callback_query)."""
    user: User
    data: str  # lo que el bot guardó en el botón, p. ej. "verify:42"


@dataclass(frozen=True)
class StaffList:
    """Quiénes administran el grupo: lo que devuelve getChatAdministrators
    (fundador, admins y bots con permisos). El cerebro no puede preguntarle
    a Telegram, así que el adaptador se lo cuenta: al arrancar y cada vez que
    Telegram avisa que alguien ganó o perdió la administración (update
    chat_member)."""
    users: tuple[User, ...]


@dataclass(frozen=True)
class Tick:
    """Pasó el tiempo. Sirve para lo que vence solo: la verificación que nadie
    contestó o el silencio que termina. En Telegram lo dispara un temporizador
    cada tantos segundos; en el simulador, los botones del reloj."""


Event = Joined | Left | Message | ButtonPressed | StaffList | Tick
