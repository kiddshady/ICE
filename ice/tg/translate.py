"""De Telegram a eventos del cerebro: las partes que no hablan con la red.

Están separadas de `bot.py` para poder testearlas sin un bot ni internet:
reciben objetos de aiogram y devuelven datos simples.
"""
from __future__ import annotations

from aiogram.enums import ChatMemberStatus, ContentType
from aiogram.types import ChatMember, Message as TgMessage, MessageOriginChannel

# Lo que manda una persona. Todo lo demás son mensajes de servicio ("entró
# Fulano", "cambió la foto del grupo"...) y el cerebro no los ve como
# mensajes.
USER_CONTENT = {
    ContentType.TEXT, ContentType.PHOTO, ContentType.VIDEO, ContentType.ANIMATION,
    ContentType.DOCUMENT, ContentType.AUDIO, ContentType.VOICE, ContentType.VIDEO_NOTE,
    ContentType.STICKER, ContentType.CONTACT, ContentType.LOCATION, ContentType.VENUE,
    ContentType.POLL, ContentType.DICE, ContentType.STORY, ContentType.PAID_MEDIA,
    ContentType.LIVE_PHOTO, ContentType.CHECKLIST, ContentType.GAME,
}

ADMIN = {ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR}


def is_user_content(m: TgMessage) -> bool:
    return m.content_type in USER_CONTENT


def text_of(m: TgMessage) -> str:
    """El texto que miran las reglas. Una foto o un sticker sin texto se
    cuentan por su archivo (`file_unique_id` es el mismo si se vuelve a mandar
    la misma foto): así el anti-repetición agarra la misma foto dos veces,
    pero no confunde dos fotos distintas sin texto."""
    if m.text is not None:
        return m.text
    if m.caption:
        return m.caption
    media = ((m.photo[-1] if m.photo else None) or m.sticker or m.video or m.animation
             or m.document or m.audio or m.voice or m.video_note)
    if media is not None:
        return f"[{m.content_type} {media.file_unique_id}]"
    return f"[{m.content_type}]"


def hidden_links(m: TgMessage) -> tuple[str, ...]:
    """Los links escondidos detrás de una palabra (entity text_link)."""
    entities = m.entities or m.caption_entities or []
    return tuple(e.url for e in entities if e.type == "text_link" and e.url)


def from_channel(m: TgMessage) -> bool:
    return isinstance(m.forward_origin, MessageOriginChannel)


def in_group(cm: ChatMember) -> bool:
    """Si está adentro. Ojo con "restricted": alguien restringido que se va
    sigue figurando como restricted, con is_member en False."""
    if cm.status in ADMIN or cm.status == ChatMemberStatus.MEMBER:
        return True
    return cm.status == ChatMemberStatus.RESTRICTED and cm.is_member


def transition(old: ChatMember, new: ChatMember) -> str | None:
    """Qué significa un cambio de estado (update chat_member) para el cerebro:
    "join", "leave" o nada. Un ban o un kick no son "leave": los hizo el bot
    (o un admin) y el cerebro ya lo sabe, o no le importa."""
    before, after = in_group(old), in_group(new)
    if not before and after:
        return "join"
    if before and not after and new.status != ChatMemberStatus.KICKED:
        return "leave"
    return None


def staff_changed(old: ChatMember, new: ChatMember) -> bool:
    """Alguien ganó, perdió o cambió su administración: hay que volver a
    pedir la lista."""
    return old.status in ADMIN or new.status in ADMIN
