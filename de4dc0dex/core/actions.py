"""Acciones: lo que el cerebro decide hacer.

El cerebro no ejecuta nada. Devuelve una lista de acciones y el adaptador las
convierte en llamadas a la API de Telegram. Cada acción dice qué método de la
API la ejecuta (`api`), así el simulador puede mostrar exactamente qué llamada
haría el bot de verdad.
"""
from __future__ import annotations

from dataclasses import dataclass

from .events import User


@dataclass(frozen=True)
class Button:
    label: str
    data: str  # callback_data: vuelve en ButtonPressed.data cuando lo tocan


@dataclass(frozen=True)
class DeleteMessage:
    """Borra un mensaje, o todos los de un álbum juntos (Message.ids)."""
    message_ids: tuple[int, ...]
    api = "deleteMessages"


@dataclass(frozen=True)
class Restrict:
    """Le saca el permiso de escribir. `until` en segundos del reloj; None es
    hasta que alguien lo levante a mano (o hasta que se verifique)."""
    user: User
    until: float | None
    api = "restrictChatMember"


@dataclass(frozen=True)
class Unrestrict:
    user: User
    api = "restrictChatMember"  # el mismo método, con todos los permisos en true


@dataclass(frozen=True)
class Kick:
    """Lo saca del grupo pero puede volver a entrar. Telegram no tiene "kick":
    se banea y se desbanea en el acto."""
    user: User
    api = "banChatMember + unbanChatMember"


@dataclass(frozen=True)
class Ban:
    """Lo saca y no puede volver hasta que lo desbaneen. Con
    `revoke_messages`, Telegram además borra todo lo que esa cuenta mandó al
    grupo. No se puede deshacer: el /unban no devuelve los mensajes."""
    user: User
    revoke_messages: bool = True
    api = "banChatMember"


@dataclass(frozen=True)
class Unban:
    user: User
    api = "unbanChatMember"


@dataclass(frozen=True)
class Say:
    """Un mensaje del bot en el grupo. `key` le pone nombre para poder
    borrarlo después con Unsay (p. ej. el desafío de verificación)."""
    text: str
    reply_to: int | None = None
    button: Button | None = None
    key: str | None = None
    api = "sendMessage"


@dataclass(frozen=True)
class Unsay:
    """Borra un mensaje que el bot mandó antes con Say(key=...)."""
    key: str
    api = "deleteMessage"


@dataclass(frozen=True)
class Toast:
    """El cartelito que le aparece solo a quien tocó un botón."""
    text: str
    api = "answerCallbackQuery"


@dataclass(frozen=True)
class Log:
    """Una línea para el registro. El bot de verdad la escribe en su consola:
    en el grupo, cada cosa ya tiene su propio mensaje."""
    text: str
    api = "consola del bot (no es una llamada a Telegram)"


Action = (DeleteMessage | Restrict | Unrestrict | Kick | Ban | Unban
          | Say | Unsay | Toast | Log)
