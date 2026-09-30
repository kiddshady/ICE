"""Cambios de nombre: el bot avisa cuando alguien aparece con otro nombre.

En compra-venta es una señal clásica de estafa: alguien vende, cobra, se
cambia el nombre y sigue como si fuera otra persona, o se pone el nombre de
un admin para pedir pagos por privado.

Telegram no le avisa al bot cuando alguien se cambia el nombre. El bot lo
nota recién cuando esa persona hace algo que le llega (escribe o toca un
botón) y el nombre no coincide con el que tenía anotado. Por eso esta regla
se fija antes de que la memoria se actualice.
"""
from __future__ import annotations

from ..actions import Log, Say
from ..context import Ctx
from ..decision import Decision
from ..events import User

RULE = "nombres"


def check(user: User, ctx: Ctx, d: Decision) -> None:
    m = ctx.state.members.get(user.id)
    if m is None:
        # Es la primera vez que el bot la ve: no tiene con qué comparar.
        return
    old = m.user.name
    if old == user.name:
        return

    m.user = user
    if user.is_admin:
        d.do(Log(f"Cambio de nombre (admin): «{old}» ahora figura como «{user.name}»."))
        d.info(RULE, f"{old} ahora se llama {user.name}. Es admin: se anota en el "
                     "registro, pero no se avisa en el grupo.")
        return

    d.do(
        Say(f"✏️ Cambio de nombre: «{old}» ahora figura como «{user.name}»."),
        Log(f"Cambio de nombre: «{old}» ahora figura como «{user.name}»."),
    )
    d.hit(RULE, f"El bot la tenía anotada como {old} y ahora escribe como "
                f"{user.name}: se avisa en el grupo. Telegram no avisa los "
                "cambios de nombre, así que el bot lo nota recién ahora.")
