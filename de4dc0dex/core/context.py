from __future__ import annotations

from dataclasses import dataclass

from .config import Config
from .state import GroupState


@dataclass(frozen=True)
class Ctx:
    """Lo que toda regla necesita: la memoria, las perillas y la hora.

    La hora entra desde afuera en vez de leer el reloj del sistema. Así el
    simulador puede adelantar el tiempo y los tests pueden fijarlo.
    """
    state: GroupState
    config: Config
    now: float
