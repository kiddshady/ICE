"""Advertencias. Las usan /warn y las reglas automáticas (anti-links)."""
from __future__ import annotations

from ..actions import Log, Restrict, Say
from ..context import Ctx
from ..decision import Decision
from ..state import Member
from ..timefmt import duration

RULE = "advertencias"


def add_warn(m: Member, reason: str, ctx: Ctx, d: Decision) -> None:
    cfg = ctx.config
    u = m.user
    m.warns += 1
    if m.warns >= cfg.max_warns:
        m.warns = 0
        until = ctx.now + cfg.warn_mute
        m.muted_until = until
        d.do(
            Restrict(u, until=until),
            Say(f"🔇 {u.tag}: advertencia {cfg.max_warns}/{cfg.max_warns} ({reason}). "
                f"Escritura restringida por {duration(cfg.warn_mute)}."),
            Log(f"{u.name}: advertencia {cfg.max_warns}/{cfg.max_warns} ({reason}). "
                f"Silencio de {duration(cfg.warn_mute)}."),
        )
        d.hit(RULE, f"Llegó a {cfg.max_warns} de {cfg.max_warns}: silencio de "
                    f"{duration(cfg.warn_mute)} y el contador vuelve a 0.")
    else:
        d.do(
            Say(f"⚠️ {u.tag}: advertencia {m.warns}/{cfg.max_warns} ({reason})."),
            Log(f"{u.name}: advertencia {m.warns}/{cfg.max_warns} ({reason})."),
        )
        d.info(RULE, f"Suma {m.warns} de {cfg.max_warns}. A la "
                     f"{cfg.max_warns}.ª le toca silencio.")
