"""Duraciones en castellano, para los mensajes del bot."""
from __future__ import annotations


def duration(seconds: float) -> str:
    s = int(round(seconds))
    if s < 60:
        return f"{s} s"
    if s < 3600:
        m, rest = divmod(s, 60)
        return f"{m} min" if rest == 0 else f"{m} min {rest} s"
    # Hasta dos días va en horas: "24 h" se lee más claro que "1 día".
    if s < 2 * 86400:
        h, rest = divmod(s, 3600)
        m = rest // 60
        return f"{h} h" if m == 0 else f"{h} h {m} min"
    d, rest = divmod(s, 86400)
    h = rest // 3600
    days = "1 día" if d == 1 else f"{d} días"
    return days if h == 0 else f"{days} {h} h"
