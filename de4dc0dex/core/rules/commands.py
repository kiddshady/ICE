"""Comandos. /reglas, /warns y /staff los puede usar cualquiera; el resto, solo admins.

Las respuestas llevan un emoji adelante: son mensajes de chat y ahí ayudan a
reconocer de un vistazo qué pasó.

Los comandos de moderación apuntan a alguien de dos maneras:

- Respondiéndole un mensaje. Anda siempre.
- Con su @usuario primero: `/ban @Laura motivo`. Solo anda con cuentas que
  tienen @ y que el bot ya vio pasar: Telegram no le deja a un bot buscar a
  alguien por su @.
"""
from __future__ import annotations

from dataclasses import replace

from ..actions import Ban, DeleteMessage, Log, Restrict, Say, Unban, Unrestrict
from ..context import Ctx
from ..decision import Decision
from ..events import Message, User
from ..timefmt import duration
from . import warns

RULE = "comandos"
PUBLIC = {"reglas", "warns", "staff"}
MOD = {"warn", "unwarn", "mute", "unmute", "ban", "unban"}


def parse(text: str) -> tuple[str, str]:
    """'/warn@de4dc0dex_bot spam' -> ('warn', 'spam'). En grupos, Telegram le agrega
    @nombre_del_bot al comando cuando lo elegís del menú."""
    head, _, arg = text[1:].partition(" ")
    return head.split("@", 1)[0].lower(), arg.strip()


def target_of(msg: Message, arg: str, ctx: Ctx) -> tuple[User | None, str, str | None]:
    """A quién apunta el comando, qué queda del texto después y el @usuario
    escrito, si hubo uno. Un @usuario al principio gana sobre la respuesta.
    Sin nadie y con @: el bot no conoce ese @. Sin nadie y sin @: falta decir
    a quién."""
    first, _, rest = arg.partition(" ")
    if first.startswith("@") and len(first) > 1:
        return ctx.state.find_username(first), rest.strip(), first
    if msg.reply_to is not None:
        return msg.reply_to.user, arg, None
    return None, arg, None


def ban_text(who: str, reason: str) -> str:
    """El aviso del ban. El motivo va tal cual lo escribió el admin; si
    arranca con "por", se lo saca para que no quede "por por"."""
    reason = reason.strip()
    if reason.casefold().startswith("por "):
        reason = reason[4:].strip()
    if not reason:
        return f"🔨 {who} recibió un ban permanente."
    return f"🔨 {who} recibió un ban permanente por {reason}."


def staff_text(staff: list[User]) -> str:
    """El cartel de /staff: fundador, admins y bots, cada grupo con su título.
    Un grupo vacío no se muestra. Los anónimos ya vienen filtrados."""
    def line(u: User) -> str:
        return f"{u.name} (@{u.username})" if u.username else u.name

    owner = [u for u in staff if u.is_owner]
    bots = [u for u in staff if u.is_bot]
    admins = [u for u in staff if not u.is_owner and not u.is_bot]
    blocks = ["👥 DE4DC0DEX → STAFF"]
    for title, group in (("👑 Fundador:", owner), ("🛡️ Admins:", admins), ("🤖 Bots:", bots)):
        if group:
            blocks.append("\n".join([title, *map(line, group)]))
    return "\n\n".join(blocks)


def handle(msg: Message, ctx: Ctx, d: Decision) -> None:
    cmd, arg = parse(msg.text)
    u = msg.user

    if cmd not in PUBLIC | MOD:
        d.info(RULE, f"/{cmd} no es un comando de DE4DC0DEX: se ignora.")
        return

    if cmd == "reglas":
        d.do(Say(ctx.config.rules_text, reply_to=msg.id))
        d.passed(RULE, "/reglas es público: el bot responde con las reglas.")
        return

    if cmd == "warns":
        who, _, handle_ = target_of(msg, arg, ctx)
        if who is None and handle_:
            unknown(handle_, cmd, msg, d)
            return
        who = who or u
        n = ctx.state.member(who).warns
        d.do(Say(f"⚠️ {who.tag}: {n}/{ctx.config.max_warns} advertencias.",
                 reply_to=msg.id))
        d.passed(RULE, f"/warns es público: {who.name} tiene {n}.")
        return

    if cmd == "staff":
        if not ctx.state.staff:
            d.do(Say("ℹ️ Lista de administración no disponible por el momento.",
                     reply_to=msg.id))
            d.info(RULE, "El bot todavía no recibió la lista de administración: "
                         "el adaptador se la pasa al arrancar (getChatAdministrators).")
            return
        # El nombre y el @ más recientes que el bot vio de cada cuenta: si
        # alguien del staff se lo cambió y ya escribió, la lista sale con el
        # nuevo. El rol sigue saliendo de la lista de Telegram.
        staff = []
        for u in ctx.state.staff:
            if u.is_anonymous:
                continue
            seen = ctx.state.members.get(u.id)
            staff.append(replace(u, name=seen.user.name, username=seen.user.username)
                         if seen else u)
        d.do(Say(staff_text(staff)))
        d.passed(RULE, f"/staff es público: el bot publica quiénes administran el grupo "
                       f"({len(staff)} cuentas). Sale de getChatAdministrators, no de "
                       "los que el bot vio escribir, así que aparecen hasta los que "
                       "nunca hablaron.")
        hidden = len(ctx.state.staff) - len(staff)
        if hidden:
            d.info(RULE, f"{hidden} en modo anónimo no aparece{'n' if hidden > 1 else ''}: "
                         "Telegram igual los lista, pero eligieron no mostrarse en el "
                         "grupo y el bot respeta eso.")
        return

    # De acá para abajo, comandos de moderación.
    if not u.is_admin:
        d.do(DeleteMessage(msg.ids))
        d.hit(RULE, f"/{cmd} es solo para admins y {u.name} no lo es. "
                    "Se borra el comando sin responder, para no darle bola.")
        return

    target, arg, handle_ = target_of(msg, arg, ctx)
    if target is None and handle_:
        unknown(handle_, cmd, msg, d)
        return
    if target is None:
        d.do(Say(f"ℹ️ /{cmd} se usa respondiendo a un mensaje de la cuenta en cuestión, "
                 f"o con su @usuario: /{cmd} @usuario.", reply_to=msg.id))
        d.info(RULE, f"/{cmd} necesita saber a quién: hay que usarlo respondiendo "
                     "a un mensaje de esa persona o escribiendo su @usuario.")
        return
    if target.is_admin and cmd not in {"unwarn", "unmute", "unban"}:
        d.do(Say("🛡️ Las cuentas de administración no admiten sanciones.", reply_to=msg.id))
        d.info(RULE, f"{target.name} es admin. Telegram tampoco deja restringir "
                     "ni banear a un admin.")
        return

    m = ctx.state.member(target)
    who = target.name
    tag = target.tag  # en el grupo va con el id; en el registro, solo el nombre

    if cmd == "warn":
        d.passed(RULE, f"{u.name} es admin y le aplica /warn a {who}.")
        warns.add_warn(m, arg or "decisión de la administración", ctx, d)

    elif cmd == "unwarn":
        before = m.warns
        m.warns = max(0, m.warns - 1)
        d.do(Say(f"✅ {tag}: advertencia retirada. Total: {m.warns}/{ctx.config.max_warns}."),
             Log(f"{u.name} le sacó una advertencia a {who} ({before} a {m.warns})."))
        d.passed(RULE, f"Advertencias de {who}: de {before} a {m.warns}.")

    elif cmd == "mute":
        minutes = int(arg) if arg.isdigit() and int(arg) > 0 else None
        length = minutes * 60 if minutes else ctx.config.default_mute
        until = ctx.now + length
        m.muted_until = until
        d.do(Restrict(target, until=until),
             Say(f"🔇 {tag}: escritura restringida por {duration(length)}."),
             Log(f"{u.name} silenció a {who} por {duration(length)}."))
        how = f"{minutes} min pedidos" if minutes else "sin número, va el default"
        d.hit(RULE, f"/mute a {who} por {duration(length)} ({how}). Telegram lo "
                    "libera solo cuando vence: el restrict lleva la fecha de fin.")

    elif cmd == "unmute":
        m.muted_until = None
        d.do(Unrestrict(target), Say(f"🔊 {tag}: restricción de escritura retirada."),
             Log(f"{u.name} le sacó el silencio a {who}."))
        d.passed(RULE, f"/unmute: {who} recupera el permiso de escribir.")

    elif cmd == "ban":
        ctx.state.members.pop(target.id, None)
        ctx.state.banned[target.id] = target
        d.do(Ban(target), Say(ban_text(tag, arg)),
             Log(f"{u.name} baneó a {who}" + (f" ({arg})." if arg else ".")))
        why = f"El motivo va en el aviso: «{arg}»." if arg else "Sin motivo: el aviso no lo menciona."
        d.hit(RULE, f"/ban: {who} sale del grupo y no puede volver a entrar "
                    "hasta que lo desbaneen. Telegram borra todos sus mensajes "
                    f"del grupo. {why}")

    elif cmd == "unban":
        if ctx.state.banned.pop(target.id, None) is None:
            d.do(Say(f"ℹ️ {tag}: sin expulsión vigente.", reply_to=msg.id))
            d.info(RULE, f"{who} no tenía ban: nada que hacer.")
            return
        d.do(Unban(target), Say(f"🔓 {tag}: expulsión retirada. La cuenta puede volver a ingresar."),
             Log(f"{u.name} desbaneó a {who}."))
        d.passed(RULE, f"/unban: {who} puede volver a entrar. No vuelve solo: "
                       "tiene que entrar de nuevo con el link del grupo.")


def unknown(handle_: str, cmd: str, msg: Message, d: Decision) -> None:
    d.do(Say(f"❓ No hay registro de {handle_} en este grupo. Para aplicar /{cmd}, "
             "responder a un mensaje de esa cuenta.", reply_to=msg.id))
    d.info(RULE, f"El bot no conoce a {handle_}. Telegram no le deja buscar a "
                 "alguien por su @: solo reconoce a quien ya escribió o entró "
                 "desde que el bot está en el grupo.")
