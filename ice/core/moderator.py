"""El cerebro: recibe un evento, pasa por las reglas y devuelve una Decision.

Es la única puerta de entrada. El simulador y el adaptador de Telegram llaman
a `Moderator.handle` exactamente igual; por eso lo que funciona en uno
funciona en el otro.
"""
from __future__ import annotations

from .config import Config
from .context import Ctx
from .decision import Decision
from .events import ButtonPressed, Event, Joined, Left, Message, StaffList, Tick
from .rules import commands, flood, links, names, repeat, verification
from .state import GroupState
from .store import Store
from .timefmt import duration


class Moderator:
    def __init__(self, config: Config | None = None, store: Store | None = None) -> None:
        """Sin `store`, la memoria vive solo mientras el programa está
        prendido (el simulador y los tests). Con `store`, arranca de lo que
        quedó guardado y guarda después de cada evento."""
        self.config = config or Config()
        self.store = store
        self.state = store.load() if store else GroupState()

    def handle(self, event: Event, now: float) -> Decision:
        d = self._decide(event, now)
        if self.store:
            self.store.save(self.state)
        return d

    def _decide(self, event: Event, now: float) -> Decision:
        ctx = Ctx(self.state, self.config, now)
        d = Decision()
        match event:
            case Joined():
                verification.on_join(event, ctx, d)
            case Left():
                verification.on_leave(event, ctx, d)
            case ButtonPressed():
                names.check(event.user, ctx, d)
                verification.on_button(event, ctx, d)
            case Message() if event.edited:
                self._on_edit(event, ctx, d)
            case Message():
                self._on_message(event, ctx, d)
            case StaffList():
                ctx.state.staff = list(event.users)
                d.info("staff", f"El adaptador le pasó la lista de administración "
                                f"({len(event.users)} cuentas). Queda anotada para /staff.")
            case Tick():
                self._on_tick(ctx, d)
        return d

    def _on_message(self, msg: Message, ctx: Ctx, d: Decision) -> None:
        # 1. Permisos. Estos casos no los decide el bot: Telegram directamente
        #    no deja escribir a alguien restringido. Se miran antes de tocar la
        #    memoria: un mensaje que nunca llega no puede actualizar el nombre.
        known = ctx.state.members.get(msg.user.id)
        if known is not None and known.verify_deadline is not None:
            d.info("permisos", f"{msg.user.name} todavía no se verificó: Telegram "
                               "no le deja escribir, así que el mensaje nunca le llega al bot.")
            d.blocked = True
            return
        if known is not None and known.muted_until is not None and known.muted_until > ctx.now:
            d.info("permisos", f"A {msg.user.name} le quedan "
                               f"{duration(known.muted_until - ctx.now)} de silencio: Telegram no le "
                               "deja escribir, así que el mensaje nunca le llega al bot.")
            d.blocked = True
            return

        # 2. Nombres: se comparan con los anotados antes de que la memoria los
        #    pise. Una respuesta trae también el nombre actual de a quién se
        #    responde, así que el cambio se nota aunque esa persona no escriba.
        names.check(msg.user, ctx, d)
        if msg.reply_to is not None and msg.reply_to.user.id != msg.user.id:
            names.check(msg.reply_to.user, ctx, d)
        m = ctx.state.member(msg.user)

        # 3. Comandos: van por su lado y no pasan por los filtros.
        if msg.text.startswith("/"):
            commands.handle(msg, ctx, d)
            return

        # 4. Los admins no se filtran.
        if msg.user.is_admin:
            d.passed("admins", f"{msg.user.name} es admin: los filtros no se le aplican.")
            return

        # 5. Filtros, en orden. El primero que salta corta la cadena: si ya
        #    se borró el mensaje, no tiene sentido seguir mirándolo. El
        #    anti-repetición va último porque guarda los mensajes que pasan.
        for rule in (flood.check, links.check, repeat.check):
            if rule(msg, m, ctx, d):
                return
        d.passed("resultado", "Ningún filtro saltó: el mensaje queda.")

    def _on_edit(self, msg: Message, ctx: Ctx, d: Decision) -> None:
        """Alguien editó un mensaje que ya estaba en el grupo. Lo único que
        una edición puede meter es un link, así que pasa solo por el
        anti-links. El anti-flood y el anti-repetición no aplican: editar no
        manda nada nuevo ni sube el aviso en el chat. Tampoco los comandos.

        Sin mirar permisos: si la edición llegó, Telegram la dejó pasar."""
        names.check(msg.user, ctx, d)
        m = ctx.state.member(msg.user)
        if msg.user.is_admin:
            d.passed("admins", f"{msg.user.name} es admin: los filtros no se le aplican.")
            return
        if not links.check(msg, m, ctx, d):
            d.passed("resultado", "La edición no metió nada prohibido: el mensaje queda.")

    def _on_tick(self, ctx: Ctx, d: Decision) -> None:
        kicked = verification.expire(ctx, d)

        freed = [m for m in ctx.state.members.values()
                 if m.muted_until is not None and m.muted_until <= ctx.now]
        for m in freed:
            m.muted_until = None
            d.info("silencios", f"Terminó el silencio de {m.user.name}. Telegram lo "
                                "libera solo (el restrict tenía fecha de fin); el bot "
                                "solo lo anota en su memoria.")

        if not kicked and not freed:
            d.info("reloj", "No venció nada.")
