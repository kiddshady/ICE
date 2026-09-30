"""Las perillas del bot. Todos los tiempos van en segundos.

Supuesto de base: ICE modera un grupo de compra-venta y servicios. Ahí cada
mensaje es un aviso, y los valores de abajo están pensados para eso. Las
reglas que se muestran con /reglas, en cambio, son generales: sirven para
cualquier grupo.
"""
from __future__ import annotations

from dataclasses import dataclass

MINUTE = 60
HOUR = 60 * MINUTE
DAY = 24 * HOUR


@dataclass(frozen=True)
class Config:
    # Verificación: cuánto tiene alguien nuevo para tocar el botón.
    verify_timeout: float = 2 * MINUTE

    # Anti-flood: más de `flood_max` mensajes en `flood_window` segundos.
    flood_max: int = 5
    flood_window: float = 8
    flood_mute: float = 10 * MINUTE

    # Anti-links. Los links están prohibidos para todas las cuentas (salvo
    # admins). Con `links_for_members` en True, en cambio, solo se prohíben
    # durante el período inicial y después se permiten.
    links_for_members: bool = False
    # Período inicial: durante este tiempo desde que entró, alguien es
    # "nuevo" y no puede reenviar mensajes de canales.
    newcomer_period: float = DAY

    # Anti-repetición: el mismo mensaje no se puede mandar dos veces en
    # `repeat_window`. Los de menos de `repeat_min_length` caracteres no
    # cuentan. En compra-venta va en 0 (cuentan todos): nadie charla, así que
    # repetir hasta un "vendo" corto es inundar. En un grupo de charla
    # convendría ~12, para no borrar cada "jaja" u "ok".
    repeat_window: float = 15 * MINUTE
    repeat_min_length: int = 0

    # Advertencias: al llegar a `max_warns`, silencio por `warn_mute`.
    max_warns: int = 3
    warn_mute: float = DAY

    # /mute sin número de minutos.
    default_mute: float = HOUR

    # La 6 no la aplica ninguna regla automática: es el /ban de un admin.
    rules_text: str = (
        "📜 Reglas del grupo:\n"
        "1. Sin links.\n"
        "2. Sin reenvíos de canales durante las primeras 24 h en el grupo.\n"
        "3. Sin ráfagas de mensajes seguidos.\n"
        "4. Sin repetir un aviso antes de 15 min.\n"
        "5. Tres advertencias: escritura restringida por 24 h.\n"
        "6. Contenido prohibido: ban directo."
    )
