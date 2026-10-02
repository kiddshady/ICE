"""La respuesta del cerebro a un evento: qué hacer y por qué.

`actions` es lo que se ejecuta. `steps` es el razonamiento, regla por regla,
que el simulador muestra en el panel "Por qué". Al bot real no le hace falta,
pero lo va a usar igual para el registro.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .actions import Action


@dataclass(frozen=True)
class Step:
    rule: str
    # "hit": la regla saltó y hubo acción. "pass": la regla miró y dejó pasar.
    # "info": un dato del recorrido, sin veredicto.
    verdict: str
    detail: str


@dataclass
class Decision:
    steps: list[Step] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)
    # True cuando Telegram mismo no dejaría que el evento ocurra (alguien
    # restringido que intenta escribir, un baneado que intenta entrar). El
    # simulador lo usa para no mostrar lo que en el grupo real no pasaría.
    blocked: bool = False

    def hit(self, rule: str, detail: str) -> None:
        self.steps.append(Step(rule, "hit", detail))

    def passed(self, rule: str, detail: str) -> None:
        self.steps.append(Step(rule, "pass", detail))

    def info(self, rule: str, detail: str) -> None:
        self.steps.append(Step(rule, "info", detail))

    def do(self, *actions: Action) -> None:
        self.actions.extend(actions)
