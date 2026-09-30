"""Anti-repetición: nadie puede mandar el mismo mensaje dos veces seguidas
dentro de un rato. En un grupo de compra-venta es la forma más común de
inundar: pegar el mismo aviso una y otra vez para que quede arriba.

"El mismo" es después de normalizar: sin importar mayúsculas ni espacios de
más. Con `repeat_min_length` se puede dejar afuera a los mensajes cortos, que
en un grupo de charla se repiten solos ("jaja", "ok"); en compra-venta está en
0 y cuentan todos.
"""
from __future__ import annotations

from ..actions import DeleteMessage, Log, Say
from ..context import Ctx
from ..decision import Decision
from ..events import Message
from ..state import Member
from ..timefmt import duration

RULE = "anti-repetición"


def normalize(text: str) -> str:
    """'  Hola   GENTE ' -> 'hola gente'."""
    return " ".join(text.casefold().split())


def check(msg: Message, m: Member, ctx: Ctx, d: Decision) -> bool:
    """Devuelve True si saltó. Va última en la cadena de filtros: solo guarda
    los mensajes que quedan en el grupo, así un mensaje que otra regla ya
    borró no cuenta como "ya lo mandaste"."""
    cfg = ctx.config
    window = duration(cfg.repeat_window)

    # Se olvida de lo que ya salió de la ventana, para no acumular para siempre.
    for key, at in list(m.last_texts.items()):
        if ctx.now - at >= cfg.repeat_window:
            del m.last_texts[key]

    text = normalize(msg.text)
    if len(text) < cfg.repeat_min_length:
        d.passed(RULE, f"Es corto ({len(text)} caracteres, el mínimo es "
                       f"{cfg.repeat_min_length}): los mensajes cortos se pueden repetir.")
        return False

    sent_at = m.last_texts.get(text)
    if sent_at is None:
        m.last_texts[text] = ctx.now
        d.passed(RULE, f"No mandó este mismo mensaje en los últimos {window}.")
        return False

    ago = duration(ctx.now - sent_at)
    wait = duration(sent_at + cfg.repeat_window - ctx.now)
    u = m.user
    d.do(
        DeleteMessage(msg.id),
        Say(f"🔁 {u.tag}: mensaje repetido, eliminado. Se puede volver a publicar "
            f"en {wait}."),
        Log(f"{u.name}: mensaje repetido a los {ago}. Borrado."),
    )
    d.hit(RULE, f"Ya mandó este mismo mensaje hace {ago}, y la ventana es de "
                f"{window}. Se borra; el reloj sigue contando desde el primero, "
                "no desde este.")
    return True
