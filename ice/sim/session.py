"""Un grupo de mentira alrededor del cerebro de verdad.

La sesión hace lo que en la vida real hacen Telegram y el adaptador: arma los
eventos, se los pasa al Moderator y ejecuta sus acciones sobre un chat falso.
Todo entra y sale como diccionarios simples (JSON), así la página del
simulador no necesita saber nada de Python.
"""
from __future__ import annotations

import time
import unicodedata
from dataclasses import dataclass, replace
from typing import Any

from ..core import Moderator
from ..core.context import Ctx
from ..core.actions import (Ban, DeleteMessage, Kick, Log, Restrict, Say, Toast,
                            Unban, Unrestrict, Unsay)
from ..core.decision import Decision
from ..core.events import ButtonPressed, Joined, Left, Message, RepliedTo, Tick, User
from ..core.rules.links import is_newcomer
from ..core.timefmt import duration

BOT = User(id=0, name="ICE", is_admin=True)


@dataclass
class Person:
    user: User
    role: str       # cómo lo presenta el simulador
    present: bool   # está en el grupo


class Session:
    def __init__(self) -> None:
        self.reset()

    # ---------------------------------------------------------------- reloj
    # El reloj corre solo, como el de verdad, y los botones lo adelantan.
    # Si el reloj no corriera, cinco mensajes escritos a mano caerían todos
    # en el mismo segundo y el anti-flood saltaría siempre.

    @property
    def now(self) -> float:
        return self._offset + (time.monotonic() - self._start)

    # ---------------------------------------------------------------- estado

    def reset(self) -> None:
        self.mod = Moderator()
        self._start = time.monotonic()
        self._offset = 0.0
        self.people: dict[int, Person] = {}
        self.chat: list[dict[str, Any]] = []
        self.traces: list[dict[str, Any]] = []
        self.log: list[dict[str, Any]] = []
        self._next_msg = 1
        self._next_user = 1
        self._bot_msgs: dict[str, dict[str, Any]] = {}

        self._add("Fran", "admin, creó el grupo", admin=True, present=True)
        self._add("Cami", "miembro de siempre", present=True)
        self._add("Juan", "persona nueva")
        self._add("PromoCripto", "bot de spam")
        # Los que ya estaban cuando llegó el bot: el cerebro los conoce como
        # miembros de siempre (joined_at = None).
        for p in self.people.values():
            if p.present:
                self.mod.state.member(p.user)
        self._system("Simulación nueva de un grupo de compra-venta. Fran y Cami "
                     "ya estaban cuando llegó ICE.")

    def _add(self, name: str, role: str, admin: bool = False,
             present: bool = False) -> Person:
        user = User(id=self._next_user, name=name, is_admin=admin,
                    username=self._username_for(name))
        self._next_user += 1
        p = Person(user=user, role=role, present=present)
        self.people[user.id] = p
        return p

    def _username_for(self, name: str) -> str:
        """Un @usuario a partir del nombre: "Juan Pérez" -> "juanperez". Si ya
        lo tiene otra persona, le suma un número."""
        plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
        base = "".join(c for c in plain.lower() if c.isalnum() or c == "_") or "usuario"
        taken = {p.user.username for p in self.people.values()}
        handle, n = base, 2
        while handle in taken:
            handle, n = f"{base}{n}", n + 1
        return handle

    # ---------------------------------------------------------------- entrada

    def handle(self, cmd: dict[str, Any]) -> dict[str, Any]:
        op = cmd.get("op")
        notice = None
        if op == "join":
            notice = self._join(self._person(cmd))
        elif op == "leave":
            self._leave(self._person(cmd))
        elif op == "send":
            notice = self._send(self._person(cmd), str(cmd.get("text", "")),
                                cmd.get("reply_to"), bool(cmd.get("forwarded")))
        elif op == "burst":
            notice = self._burst(self._person(cmd))
        elif op == "press":
            notice = self._press(self._person(cmd), str(cmd.get("data", "")))
        elif op == "advance":
            self._offset += float(cmd.get("seconds", 0))
            self._tick(always=True, label=f"El reloj avanzó {duration(float(cmd['seconds']))}")
        elif op == "tick":
            self._tick(always=False, label="Pasó el tiempo")
        elif op == "rename":
            notice = self._rename(self._person(cmd), str(cmd.get("name", "")))
        elif op == "add_user":
            name = str(cmd.get("name", "")).strip()[:24]
            if name:
                self._add(name, "persona nueva")
        elif op == "reset":
            self.reset()
        return self.snapshot(notice)

    def _person(self, cmd: dict[str, Any]) -> Person:
        return self.people[int(cmd["user"])]

    # ---------------------------------------------------------------- acciones del usuario

    def _join(self, p: Person) -> str | None:
        d = self.mod.handle(Joined(p.user), self.now)
        self._trace(f"{p.user.name} intenta entrar al grupo", "join", d)
        if d.blocked:
            return "Telegram bloquea el ingreso: la cuenta tiene una expulsión permanente."
        p.present = True
        self._system(f"{p.user.name} entró al grupo.")
        self._apply(d)
        return None

    def _leave(self, p: Person) -> None:
        p.present = False
        self._system(f"{p.user.name} se fue del grupo.")
        d = self.mod.handle(Left(p.user), self.now)
        self._trace(f"{p.user.name} se fue", "leave", d)
        self._apply(d)

    def _send(self, p: Person, text: str, reply_to: Any, forwarded: bool) -> str | None:
        text = text.strip()
        if not text:
            return None
        target = self._find_msg(reply_to)
        msg = Message(
            id=self._next_msg,
            user=p.user,
            text=text,
            reply_to=RepliedTo(target["msg_id"], self._user_of(target)) if target else None,
            forwarded_from_channel=forwarded,
        )
        d = self.mod.handle(msg, self.now)
        short = text if len(text) <= 40 else text[:39] + "..."
        self._trace(f"{p.user.name} escribe: {short}", "message", d)
        if d.blocked:
            return "Telegram bloquea el mensaje: la cuenta tiene la escritura restringida."
        self._next_msg += 1
        self.chat.append({
            "kind": "user", "msg_id": msg.id, "user_id": p.user.id,
            "name": p.user.name, "admin": p.user.is_admin, "text": text,
            "forwarded": forwarded, "reply": self._reply_view(target),
            "deleted": False, "at": self.now,
        })
        self._apply(d)
        return None

    def _rename(self, p: Person, name: str) -> str | None:
        """Se cambia el nombre en su perfil. Telegram no lo muestra en el grupo
        ni se lo avisa al bot: el cerebro no se entera hasta que le llegue algo
        de esa persona, así que acá no se lo llama."""
        name = name.strip()[:24]
        if not name or name == p.user.name:
            return None
        old = p.user.name
        p.user = replace(p.user, name=name)
        return (f"{old} ahora se llama {name}. Telegram no se lo avisa al bot: "
                "ICE se entera cuando escriba, toque un botón o alguien le responda.")

    def _burst(self, p: Person) -> str | None:
        """Siete mensajes seguidos, uno por segundo."""
        notice = None
        for i in range(1, 8):
            notice = self._send(p, f"mensaje seguido {i}", None, False) or notice
            self._offset += 1
        return notice

    def _press(self, p: Person, data: str) -> str | None:
        d = self.mod.handle(ButtonPressed(p.user, data), self.now)
        self._trace(f"{p.user.name} toca un botón", "button", d)
        toasts = [a.text for a in d.actions if isinstance(a, Toast)]
        self._apply(d)
        return toasts[-1] if toasts else None

    def _tick(self, always: bool, label: str) -> None:
        d = self.mod.handle(Tick(), self.now)
        idle = all(s.rule == "reloj" for s in d.steps)
        if always or not idle:
            self._trace(label, "tick", d)
        self._apply(d)

    # ---------------------------------------------------------------- ejecutar acciones

    def _apply(self, d: Decision) -> None:
        """Lo que hace el adaptador de Telegram, pero sobre el chat falso."""
        for a in d.actions:
            match a:
                case DeleteMessage():
                    for item in self.chat:
                        if item.get("msg_id") == a.message_id:
                            item["deleted"] = True
                case Kick():
                    self.people[a.user.id].present = False
                    self._system(f"ICE sacó a {a.user.name} del grupo.")
                case Ban():
                    self.people[a.user.id].present = False
                    if a.revoke_messages:
                        for item in self.chat:
                            if item["kind"] == "user" and item["user_id"] == a.user.id:
                                item["deleted"] = True
                    self._system(f"ICE baneó a {a.user.name}.")
                case Say():
                    item = {
                        "kind": "bot", "msg_id": self._next_msg, "user_id": BOT.id,
                        "name": BOT.name, "admin": True, "text": a.text,
                        "button": ({"label": a.button.label, "data": a.button.data}
                                   if a.button else None),
                        "reply": self._reply_view(self._find_msg(a.reply_to)),
                        "deleted": False, "at": self.now,
                    }
                    self._next_msg += 1
                    self.chat.append(item)
                    if a.key:
                        self._bot_msgs[a.key] = item
                case Unsay():
                    item = self._bot_msgs.pop(a.key, None)
                    if item:
                        item["deleted"] = True
                        item["button"] = None
                case Log():
                    self.log.append({"at": self.now, "text": a.text})
                case Restrict() | Unrestrict() | Unban() | Toast():
                    pass  # no cambian nada visible del chat

    # ---------------------------------------------------------------- ayudantes

    def _system(self, text: str) -> None:
        self.chat.append({"kind": "system", "text": text, "at": self.now})

    def _find_msg(self, msg_id: Any) -> dict[str, Any] | None:
        if msg_id is None:
            return None
        return next((m for m in self.chat if m.get("msg_id") == int(msg_id)), None)

    def _user_of(self, item: dict[str, Any]) -> User:
        return BOT if item["kind"] == "bot" else self.people[item["user_id"]].user

    @staticmethod
    def _reply_view(item: dict[str, Any] | None) -> dict[str, Any] | None:
        if not item:
            return None
        return {"msg_id": item["msg_id"], "name": item["name"], "text": item["text"][:80]}

    def _trace(self, title: str, kind: str, d: Decision) -> None:
        self.traces.append({
            "n": len(self.traces) + 1,
            "at": self.now,
            "title": title,
            "kind": kind,
            "blocked": d.blocked,
            "steps": [{"rule": s.rule, "verdict": s.verdict, "detail": s.detail}
                      for s in d.steps],
            "actions": [{"api": a.api, "detail": self._describe(a)} for a in d.actions],
        })

    def _describe(self, a: Any) -> str:
        match a:
            case DeleteMessage():
                return f"borra el mensaje #{a.message_id}"
            case Restrict():
                if a.until is None:
                    return f"{a.user.name} queda sin permiso de escribir, sin fecha de fin"
                return f"{a.user.name} queda sin permiso de escribir por {duration(a.until - self.now)}"
            case Unrestrict():
                return f"{a.user.name} recupera el permiso de escribir"
            case Kick():
                return f"saca a {a.user.name}; puede volver a entrar"
            case Ban():
                if a.revoke_messages:
                    return (f"saca a {a.user.name}; no puede volver. Con revoke_messages: "
                            "Telegram borra todos sus mensajes del grupo")
                return f"saca a {a.user.name}; no puede volver"
            case Unban():
                return f"{a.user.name} puede volver a entrar"
            case Say():
                extra = f" (con botón «{a.button.label}»)" if a.button else ""
                return f"«{a.text}»{extra}"
            case Unsay():
                return "borra el desafío de verificación que había mandado"
            case Toast():
                return f"aviso que ve solo quien tocó el botón: «{a.text}»"
            case Log():
                return a.text
        return ""

    # ---------------------------------------------------------------- salida

    def snapshot(self, notice: str | None = None) -> dict[str, Any]:
        now = self.now
        state = self.mod.state
        cfg = self.mod.config
        people = []
        for p in self.people.values():
            m = state.members.get(p.user.id)
            status: dict[str, Any] = {
                "present": p.present,
                "banned": p.user.id in state.banned,
                "warns": m.warns if m else 0,
                "verify_left": (m.verify_deadline - now
                                if m and m.verify_deadline is not None else None),
                "mute_left": (m.muted_until - now
                              if m and m.muted_until is not None and m.muted_until > now
                              else None),
                "newcomer_left": (m.joined_at + cfg.newcomer_period - now
                                  if m and p.present and is_newcomer(m, Ctx(state, cfg, now))
                                  else None),
            }
            people.append({"id": p.user.id, "name": p.user.name, "role": p.role,
                           "username": p.user.username,
                           "admin": p.user.is_admin, **status})
        return {
            "now": now,
            "max_warns": cfg.max_warns,
            "people": people,
            "chat": self.chat,
            "traces": self.traces,
            "log": self.log,
            "notice": notice,
        }
