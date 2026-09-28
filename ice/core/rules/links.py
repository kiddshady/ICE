"""Anti-links, en dos partes:

1. Links: en un grupo de compra-venta los avisos van con texto y foto, no con
   links. Un link casi siempre lleva a otro lado (un canal, una estafa, una
   tienda que no es del grupo), así que no se permiten para nadie. Los admins
   no pasan por los filtros, así que ellos sí pueden.
2. Reenvíos de canal: los que recién entraron no pueden reenviar mensajes de
   canales. Es la otra cara de la verificación: un bot de spam que logró tocar
   el botón igual no puede hacer lo único que vino a hacer.
"""
from __future__ import annotations

import re

from ..actions import DeleteMessage
from ..context import Ctx
from ..decision import Decision
from ..events import Message
from ..state import Member
from ..timefmt import duration
from . import warns

RULE = "anti-links"

# Cualquier cosa con http(s)://, www., t.me/, o un dominio con una terminación
# común. No es perfecto (nada lo es con links), pero agarra lo típico del spam.
LINK_RE = re.compile(
    r"(?i)(?:https?://|www\.|t\.me/|telegram\.me/)\S+"
    r"|\b[\w-]+\.(?:com|net|org|io|ru|xyz|ar|me|gg|link|info|site|top|click|app)\b(?:/\S*)?"
)


def find_links(msg: Message) -> list[str]:
    return LINK_RE.findall(msg.text) + list(msg.hidden_links)


def is_newcomer(m: Member, ctx: Ctx) -> bool:
    return m.joined_at is not None and ctx.now - m.joined_at < ctx.config.newcomer_period


def check(msg: Message, m: Member, ctx: Ctx, d: Decision) -> bool:
    """Devuelve True si saltó."""
    cfg = ctx.config
    newcomer = is_newcomer(m, ctx)
    period = duration(cfg.newcomer_period)
    seniority = ("estaba antes que el bot" if m.joined_at is None
                 else f"lleva {duration(ctx.now - m.joined_at)} en el grupo")

    # 1. Links.
    links = find_links(msg)
    if links and (newcomer or not cfg.links_for_members):
        found = "un link" if len(links) == 1 else f"{len(links)} links"
        if msg.hidden_links:
            found += " (uno escondido detrás de una palabra)"
        if cfg.links_for_members:
            why = (f"Entró hace poco ({seniority}, el período es de {period}) "
                   f"y el mensaje tiene {found}.")
            reason = f"link dentro del período inicial de {period}"
        else:
            why = (f"El mensaje tiene {found}, y en este grupo no se permiten "
                   f"links para nadie, sin importar la antigüedad ({seniority}).")
            reason = "link no permitido en el grupo"
        return _punish(msg, m, ctx, d, why, reason)

    # 2. Reenvíos de canal.
    if msg.forwarded_from_channel and newcomer:
        why = (f"Entró hace poco ({seniority}, el período es de {period}) y el "
               "mensaje es un reenvío de canal.")
        return _punish(msg, m, ctx, d, why,
                       f"reenvío de canal dentro del período inicial de {period}")

    if links:
        d.passed(RULE, f"Tiene links, pero los miembros que pasaron el período "
                       f"inicial pueden mandarlos ({seniority}).")
    elif msg.forwarded_from_channel:
        d.passed(RULE, f"Es un reenvío de canal, pero ya pasó el período inicial "
                       f"({seniority}).")
    else:
        d.passed(RULE, "El mensaje no tiene links.")
    return False


def _punish(msg: Message, m: Member, ctx: Ctx, d: Decision,
            why: str, reason: str) -> bool:
    d.do(DeleteMessage(msg.id))
    d.hit(RULE, f"{why} Se borra y suma una advertencia.")
    warns.add_warn(m, reason, ctx, d)
    return True
