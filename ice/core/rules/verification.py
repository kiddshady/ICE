"""Verificación de nuevos miembros.

Cuando alguien entra, queda sin permiso de escribir y el bot le pone un botón.
Si lo toca a tiempo, recupera el permiso. Si no, el bot lo saca del grupo.
La mayoría de los bots de spam entran, escriben y se van: nunca tocan nada.
"""
from __future__ import annotations

from ..actions import Button, Kick, Log, Restrict, Say, Toast, Unrestrict, Unsay
from ..context import Ctx
from ..decision import Decision
from ..events import ButtonPressed, Joined, Left
from ..timefmt import duration

RULE = "verificación"


def challenge_key(user_id: int) -> str:
    return f"verify:{user_id}"


def on_join(ev: Joined, ctx: Ctx, d: Decision) -> None:
    u = ev.user
    if u.id in ctx.state.banned:
        d.info("baneados", f"{u.name} tiene ban: Telegram no le deja entrar, "
                           "así que este evento nunca le llegaría al bot.")
        d.blocked = True
        return

    m = ctx.state.member(u)
    # Si vuelve después de que lo sacaron, arranca de cero como nuevo.
    m.joined_at = ctx.now
    m.warns = 0
    m.muted_until = None
    m.recent.clear()
    m.last_texts.clear()

    if u.is_admin:
        d.passed(RULE, f"{u.name} es admin: no hace falta que se verifique.")
        return

    timeout = ctx.config.verify_timeout
    m.verify_deadline = ctx.now + timeout
    key = challenge_key(u.id)
    d.do(
        Restrict(u, until=None),
        Say(f"🔐 {u.name}: verificación pendiente. Para habilitar la escritura, "
            f"presionar el botón dentro de {duration(timeout)}. Sin verificación, "
            "la cuenta se retira del grupo.",
            button=Button("✅ Verificar", key), key=key),
        Log(f"{u.name} entró. Esperando verificación."),
    )
    d.hit(RULE, f"Entró alguien nuevo: queda sin permiso de escribir hasta que "
                f"toque el botón. Tiene {duration(timeout)}.")


def on_button(ev: ButtonPressed, ctx: Ctx, d: Decision) -> None:
    kind, _, raw = ev.data.partition(":")
    if kind != "verify" or not raw.isdigit():
        d.info("botones", f"Botón desconocido ({ev.data}): se ignora.")
        return

    target_id = int(raw)
    if ev.user.id != target_id:
        d.do(Toast("🚫 Este botón corresponde a otra cuenta."))
        d.info(RULE, f"{ev.user.name} tocó el botón de otra persona: no cuenta. "
                     "Solo le aparece un aviso a quien lo tocó.")
        return

    m = ctx.state.members.get(target_id)
    if m is None or m.verify_deadline is None:
        d.do(Toast("ℹ️ La verificación ya estaba completa."))
        d.info(RULE, "Ya había pasado la verificación: no hay nada que hacer.")
        return

    m.verify_deadline = None
    u = m.user
    d.do(
        Unrestrict(u),
        Unsay(challenge_key(u.id)),
        Toast("✅ Verificación completa. Escritura habilitada."),
        Say(f"✅ {u.name}: verificación completa. Las reglas del grupo se consultan con /reglas."),
        Log(f"{u.name} se verificó."),
    )
    d.passed(RULE, f"{u.name} tocó su botón a tiempo: recupera el permiso de "
                   "escribir y el desafío se borra.")


def on_leave(ev: Left, ctx: Ctx, d: Decision) -> None:
    m = ctx.state.members.pop(ev.user.id, None)
    if m is not None and m.verify_deadline is not None:
        d.do(Unsay(challenge_key(ev.user.id)))
        d.info(RULE, f"{ev.user.name} se fue sin verificarse: se borra el desafío.")
    else:
        d.info("miembros", f"{ev.user.name} se fue. El bot borra lo que sabía de esa persona.")


def expire(ctx: Ctx, d: Decision) -> bool:
    """Saca a los que no se verificaron a tiempo. Devuelve si sacó a alguien."""
    late = [m for m in ctx.state.members.values()
            if m.verify_deadline is not None and m.verify_deadline <= ctx.now]
    for m in late:
        u = m.user
        del ctx.state.members[u.id]
        d.do(Kick(u), Unsay(challenge_key(u.id)),
             Log(f"{u.name} no se verificó a tiempo. Fuera del grupo."))
        d.hit(RULE, f"{u.name} no tocó el botón en {duration(ctx.config.verify_timeout)}: "
                    "afuera. Es un kick, no un ban: puede volver a intentar.")
    return bool(late)
