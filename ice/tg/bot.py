"""El adaptador: traduce los updates de Telegram a eventos, se los pasa al
cerebro y convierte sus acciones en llamadas a la API.

Es lo mismo que hace `sim/session.py`, pero contra un grupo de verdad. El
cerebro no se entera de la diferencia.

Un cerebro por grupo, cada uno con su memoria en `data/<id del grupo>.db`.
"""
from __future__ import annotations

import asyncio
import platform
import time
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramMigrateToChat
from aiogram.types import (BotCommand, BotCommandScopeAllChatAdministrators,
                           BotCommandScopeAllGroupChats, CallbackQuery, ChatMemberUpdated,
                           ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup,
                           Message as TgMessage, ReplyParameters, User as TgUser)

from ..core import Moderator, Store
from ..core.actions import (Ban, DeleteMessage, Kick, Log, Restrict, Say, Toast, Unban,
                            Unrestrict, Unsay)
from ..core.decision import Decision
from ..core.events import (ButtonPressed, Event, Joined, Left, Message, RepliedTo, StaffList,
                           Tick, User)
from . import translate

# Cuánto se espera, desde la última foto de un álbum, a que lleguen las demás.
# Telegram las manda todas juntas, en milisegundos: esto es margen de sobra.
ALBUM_WAIT = 1.5

# Cada cuánto se le avisa al cerebro que pasó el tiempo: es lo que hace vencer
# las verificaciones. Unos segundos de más en un plazo de 2 minutos no importan.
TICK_EVERY = 5

UPDATES = ["message", "callback_query", "chat_member", "my_chat_member"]

MUTED = ChatPermissions(**{name: False for name in ChatPermissions.model_fields})

PUBLIC_COMMANDS = [
    BotCommand(command="reglas", description="Las reglas del grupo"),
    BotCommand(command="warns", description="Cuántas advertencias tenés"),
    BotCommand(command="staff", description="Quiénes administran el grupo"),
]
ADMIN_COMMANDS = PUBLIC_COMMANDS + [
    BotCommand(command="warn", description="Advertir (respondiendo o con @usuario)"),
    BotCommand(command="unwarn", description="Sacar una advertencia"),
    BotCommand(command="mute", description="Silenciar [minutos]"),
    BotCommand(command="unmute", description="Sacar el silencio"),
    BotCommand(command="ban", description="Banear [motivo]"),
    BotCommand(command="unban", description="Desbanear"),
]


def log(text: str) -> None:
    print(time.strftime("%H:%M:%S"), text, flush=True)


class Group:
    """Un grupo moderado: su cerebro y lo que el adaptador tiene que recordar
    de Telegram, que el cerebro no sabe."""

    def __init__(self, chat_id: int, db: Path) -> None:
        self.id = chat_id
        self.title = str(chat_id)
        self.mod = Moderator(store=Store(db))
        # Quiénes son admins (getChatAdministrators). El cerebro se entera por
        # el campo is_admin de cada User que le llega.
        self.admins: set[int] = set()
        self.staff_loaded = False
        # Los mensajes que el bot mandó con Say(key=...), para poder borrarlos
        # con Unsay. Viven en memoria: si el bot se reinicia con un desafío de
        # verificación abierto, ese mensaje queda y hay que borrarlo a mano.
        self.said: dict[str, int] = {}


class Album:
    """Las fotos de un álbum que van llegando, hasta que se completa."""

    def __init__(self) -> None:
        self.parts: list[TgMessage] = []
        self.last = 0.0
        self.task: asyncio.Task | None = None  # que el recolector no se pierda


class ICE:
    def __init__(self, bot: Bot, data: Path, notify_chat: int | None) -> None:
        self.bot = bot
        self.data = data
        self.notify_chat = notify_chat
        self.groups: dict[int, Group] = {}
        self.albums: dict[tuple[int, str], Album] = {}
        self.me: TgUser | None = None

        r = Router()
        groups = F.chat.type.in_({"group", "supergroup"})
        r.message.register(self.on_message, groups)
        r.message.register(self.on_private, F.chat.type == "private")
        r.callback_query.register(self.on_button)
        r.chat_member.register(self.on_member, groups)
        r.my_chat_member.register(self.on_me, groups)
        self.dp = Dispatcher()
        self.dp.include_router(r)

    # ---------------------------------------------------------------- arranque

    async def run(self) -> None:
        self.me = await self.bot.get_me()
        log(f"Conectado como @{self.me.username}.")
        self.data.mkdir(exist_ok=True)
        # Los grupos que ya tenían memoria: así sus verificaciones y silencios
        # vencen aunque todavía no haya llegado ningún mensaje de ellos.
        for db in sorted(self.data.glob("*.db")):
            try:
                await self.group(int(db.stem))
            except TelegramMigrateToChat:
                self.forget(int(db.stem))
            except (ValueError, TelegramAPIError) as e:
                log(f"No se pudo retomar {db.name}: {e}")
        await self.bot.set_my_commands(PUBLIC_COMMANDS, BotCommandScopeAllGroupChats())
        await self.bot.set_my_commands(ADMIN_COMMANDS, BotCommandScopeAllChatAdministrators())
        ticker = asyncio.create_task(self.tick_forever())
        log("Escuchando. Ctrl+C para cortar.")
        await self.announce()
        try:
            await self.dp.start_polling(self.bot, allowed_updates=UPDATES,
                                        handle_signals=False)
        finally:
            ticker.cancel()
            for g in self.groups.values():
                g.mod.store.close()

    async def group(self, chat_id: int) -> Group:
        """El grupo con ese id; si es la primera vez que aparece, lo arma. Si
        el id es de un grupo que ya pasó a supergrupo, TelegramMigrateToChat."""
        g = self.groups.get(chat_id)
        if g is None:
            g = Group(chat_id, self.data / f"{chat_id}.db")
            self.groups[chat_id] = g
            chat = await self.bot.get_chat(chat_id)
            g.title = chat.title or g.title
            # Antes de anunciar nada: un grupo que ya migró recién se delata acá.
            await self.refresh_staff(g, warn=False)
            log(f"Moderando «{g.title}» ({chat_id}).")
            if chat.type == "group":
                log(f"  Ojo: «{g.title}» es un grupo básico y ahí Telegram no deja "
                    "restringir a nadie. Para pasarlo a supergrupo: Editar grupo > "
                    "Historial del chat para nuevos miembros > Visible.")
            self.warn_if_not_admin(g)
        elif not g.staff_loaded:
            await self.refresh_staff(g)
        return g

    async def announce(self) -> None:
        """Avisa por ICE_NOTIFY_CHAT que ICE se conectó. Es lo único que
        manda ahí: lo que pasa en el grupo ya lo cuenta en el grupo."""
        if self.notify_chat is None:
            return
        try:
            await self.bot.send_message(
                self.notify_chat,
                f"🟢 ICE ONLINE\nNode: {platform.node()}\nTime: {time.strftime('%H:%M:%S')}")
        except TelegramAPIError as e:
            log(f"No pude avisar en ICE_NOTIFY_CHAT ({self.notify_chat}): {e}\n"
                "  Si es un chat privado, primero hay que mandarle /start al bot: "
                "Telegram no deja que un bot le escriba a alguien que nunca le habló.")

    def forget(self, chat_id: int) -> None:
        """Borra un grupo que ya no existe con ese id. Pasa cuando Telegram
        convierte un grupo básico en supergrupo (al hacer admin al bot, por
        ejemplo): el supergrupo tiene otro id y arranca su propia memoria. La
        del básico no sirve: ahí el bot no podía sancionar a nadie."""
        g = self.groups.pop(chat_id, None)
        if g is not None:
            g.mod.store.close()
        for suffix in ("", "-wal", "-shm"):
            (self.data / f"{chat_id}.db{suffix}").unlink(missing_ok=True)
        log(f"El grupo {chat_id} pasó a ser supergrupo: se borra su memoria vieja.")

    async def refresh_staff(self, g: Group, warn: bool = True) -> None:
        try:
            members = await self.bot.get_chat_administrators(g.id)
        except TelegramMigrateToChat:
            raise
        except TelegramAPIError as e:
            log(f"  No pude pedir los admins de «{g.title}»: {e}")
            return
        staff = tuple(
            User(id=cm.user.id, name=cm.user.full_name, is_admin=True,
                 username=cm.user.username, is_owner=cm.status == "creator",
                 is_bot=cm.user.is_bot, is_anonymous=bool(getattr(cm, "is_anonymous", False)))
            for cm in members)
        g.admins = {u.id for u in staff}
        g.staff_loaded = True
        await self.feed(g, StaffList(staff))
        if warn:
            self.warn_if_not_admin(g)

    def warn_if_not_admin(self, g: Group) -> None:
        if g.staff_loaded and self.me and self.me.id not in g.admins:
            log(f"  Ojo: ICE no es admin en «{g.title}». Sin eso no ve los mensajes "
                "ni puede borrar, silenciar ni banear.")

    # ---------------------------------------------------------------- de Telegram al cerebro

    def user(self, g: Group, u: TgUser) -> User:
        return User(id=u.id, name=u.full_name, is_admin=u.id in g.admins,
                    username=u.username, is_bot=u.is_bot)

    def sender(self, g: Group, m: TgMessage) -> User | None:
        """Quién escribió. Un admin anónimo escribe con el nombre del grupo
        (sender_chat es el grupo mismo). Si escribe un canal, None: el cerebro
        piensa en personas, y a un canal no se lo puede silenciar."""
        if m.sender_chat is not None:
            if m.sender_chat.id != g.id or m.from_user is None:
                return None
            return User(id=m.from_user.id, name=g.title, is_admin=True, is_anonymous=True)
        if m.from_user is None:
            return None
        return self.user(g, m.from_user)

    async def on_message(self, m: TgMessage) -> None:
        if m.migrate_from_chat_id is not None:
            self.forget(m.migrate_from_chat_id)
        g = await self.group(m.chat.id)
        if not translate.is_user_content(m):
            return
        if m.media_group_id is None:
            await self.consider(g, [m])
            return
        # Una foto de un álbum: se guarda hasta que lleguen las demás.
        key = (g.id, m.media_group_id)
        album = self.albums.get(key)
        if album is None:
            album = self.albums[key] = Album()
            album.task = asyncio.create_task(self.close_album(g, key))
        album.parts.append(m)
        album.last = time.monotonic()

    async def close_album(self, g: Group, key: tuple[int, str]) -> None:
        album = self.albums[key]
        while (left := album.last + ALBUM_WAIT - time.monotonic()) > 0:
            await asyncio.sleep(left)
        del self.albums[key]
        try:
            await self.consider(g, sorted(album.parts, key=lambda m: m.message_id))
        except Exception as e:  # es una tarea suelta: si falla, que se vea
            log(f"[{g.title}] Error con un álbum: {e!r}")

    async def consider(self, g: Group, parts: list[TgMessage]) -> None:
        """Le pasa al cerebro un mensaje, o un álbum entero como uno solo."""
        m = parts[0]
        who = self.sender(g, m)
        if who is None:
            log(f"[{g.title}] Mensaje de un canal ({m.sender_chat.title}): ICE no lo mira.")
            return
        reply = None
        r = m.reply_to_message
        # En los grupos con temas, todo mensaje "responde" a la creación del tema.
        if r is not None and r.forum_topic_created is None:
            target = self.sender(g, r)
            if target is not None:
                reply = RepliedTo(r.message_id, target)
        await self.feed(g, Message(
            id=m.message_id, user=who, text=translate.album_text(parts), reply_to=reply,
            forwarded_from_channel=any(translate.from_channel(p) for p in parts),
            hidden_links=tuple(link for p in parts for link in translate.hidden_links(p)),
            album=tuple(p.message_id for p in parts) if len(parts) > 1 else ()))

    async def on_private(self, m: TgMessage) -> None:
        """Por privado ICE no modera nada: solo dice el id del chat, que es lo
        que hace falta para ICE_NOTIFY_CHAT."""
        await m.answer(f"🆔 Este chat es el {m.chat.id}.\nPara que ICE avise acá cuando se "
                       f"conecta: ICE_NOTIFY_CHAT={m.chat.id} en el .env.")

    async def on_button(self, q: CallbackQuery) -> None:
        if q.message is None or q.message.chat.type not in ("group", "supergroup"):
            await q.answer()
            return
        g = await self.group(q.message.chat.id)
        d = await self.feed(g, ButtonPressed(self.user(g, q.from_user), q.data or ""))
        toasts = [a.text for a in d.actions if isinstance(a, Toast)]
        # Telegram espera una respuesta a cada botón aunque no haya cartel: si
        # no, el botón se queda con el relojito dando vueltas.
        await q.answer(toasts[-1] if toasts else None)

    async def on_member(self, u: ChatMemberUpdated) -> None:
        g = await self.group(u.chat.id)
        if translate.staff_changed(u.old_chat_member, u.new_chat_member):
            await self.refresh_staff(g)
        who = self.user(g, u.new_chat_member.user)
        match translate.transition(u.old_chat_member, u.new_chat_member):
            case "join":
                await self.feed(g, Joined(who))
            case "leave":
                await self.feed(g, Left(who))

    async def on_me(self, u: ChatMemberUpdated) -> None:
        """A ICE lo agregaron, lo hicieron admin o le cambiaron los permisos."""
        g = await self.group(u.chat.id)
        await self.refresh_staff(g)

    async def tick_forever(self) -> None:
        while True:
            await asyncio.sleep(TICK_EVERY)
            for g in list(self.groups.values()):
                try:
                    await self.feed(g, Tick())
                except Exception as e:  # que un grupo roto no frene el reloj de los demás
                    log(f"[{g.title}] Error en el reloj: {e!r}")

    # ---------------------------------------------------------------- del cerebro a Telegram

    async def feed(self, g: Group, event: Event) -> Decision:
        d = g.mod.handle(event, time.time())
        for s in d.steps:
            if s.verdict == "hit":
                log(f"[{g.title}] {s.rule}: {s.detail}")
        for a in d.actions:
            try:
                await self.apply(g, a)
            except TelegramAPIError as e:
                log(f"[{g.title}] Falló {a.api}: {e}")
        return d

    async def apply(self, g: Group, a) -> None:
        bot, chat = self.bot, g.id
        match a:
            case DeleteMessage():
                await bot.delete_messages(chat, list(a.message_ids))
            case Restrict():
                await bot.restrict_chat_member(
                    chat, a.user.id, MUTED,
                    until_date=int(a.until) if a.until is not None else None)
            case Unrestrict():
                # Vuelve a los permisos que el grupo le da a todos, no a "todo
                # permitido": si el grupo no deja mandar encuestas, tampoco a él.
                chat_info = await bot.get_chat(chat)
                allowed = chat_info.permissions or ChatPermissions(
                    **{name: True for name in ChatPermissions.model_fields})
                await bot.restrict_chat_member(chat, a.user.id, allowed)
            case Kick():
                await bot.ban_chat_member(chat, a.user.id)
                await bot.unban_chat_member(chat, a.user.id, only_if_banned=True)
            case Ban():
                await bot.ban_chat_member(chat, a.user.id, revoke_messages=a.revoke_messages)
            case Unban():
                await bot.unban_chat_member(chat, a.user.id, only_if_banned=True)
            case Say():
                sent = await bot.send_message(
                    chat, a.text,
                    reply_parameters=(ReplyParameters(message_id=a.reply_to,
                                                      allow_sending_without_reply=True)
                                      if a.reply_to else None),
                    reply_markup=(InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text=a.button.label, callback_data=a.button.data)
                    ]]) if a.button else None))
                if a.key:
                    g.said[a.key] = sent.message_id
            case Unsay():
                msg_id = g.said.pop(a.key, None)
                if msg_id is not None:
                    await bot.delete_message(chat, msg_id)
            case Log():
                # Solo a la consola: cada Log ya tiene su mensaje en el grupo,
                # salvo los cambios de nombre de admins, que no se anuncian.
                log(f"[{g.title}] {a.text}")
            case Toast():
                pass  # lo contesta on_button: va en la respuesta al botón
