"""Anti-flood: nadie puede mandar muchos mensajes seguidos.

Se guarda la hora de los últimos mensajes de cada uno y se miran solo los que
caen dentro de la ventana (los últimos `flood_window` segundos). Si en esa
ventana hay más de `flood_max`, el mensaje que se pasó se borra y la persona
queda en silencio un rato.
"""
from __future__ import annotations

from ..actions import DeleteMessage, Log, Restrict, Say
from ..context import Ctx
from ..decision import Decision
from ..events import Message
from ..state import Member
from ..timefmt import duration

RULE = "anti-flood"


def check(msg: Message, m: Member, ctx: Ctx, d: Decision) -> bool:
    """Devuelve True si saltó (y entonces no hace falta seguir mirando)."""
    cfg = ctx.config
    q = m.recent
    q.append(ctx.now)
    # Los que ya salieron de la ventana no cuentan.
    while q and ctx.now - q[0] > cfg.flood_window:
        q.popleft()

    count = len(q)
    window = duration(cfg.flood_window)
    if count <= cfg.flood_max:
        d.passed(RULE, f"{count} de {cfg.flood_max} mensajes permitidos en {window}.")
        return False

    u = m.user
    until = ctx.now + cfg.flood_mute
    m.muted_until = until
    q.clear()
    d.do(
        DeleteMessage(msg.id),
        Restrict(u, until=until),
        Say(f"{u.name}: demasiados mensajes seguidos. Escritura restringida por "
            f"{duration(cfg.flood_mute)}."),
        Log(f"{u.name}: flood ({count} mensajes en {window}). "
            f"Silencio de {duration(cfg.flood_mute)}."),
    )
    d.hit(RULE, f"{count} mensajes en {window}, el máximo es {cfg.flood_max}. "
                f"Se borra este y queda {duration(cfg.flood_mute)} sin poder escribir.")
    return True
