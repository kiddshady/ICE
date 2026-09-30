"""La traducción de Telegram a eventos. Necesita aiogram (requirements.txt);
sin él, estos tests se saltean y el resto sigue andando."""
import unittest
from datetime import datetime

try:
    from aiogram.types import (Chat, ChatMemberAdministrator, ChatMemberBanned, ChatMemberLeft,
                               ChatMemberMember, ChatMemberRestricted, MessageEntity,
                               MessageOriginChannel, PhotoSize)
    from aiogram.types import Message as TgMessage, User as TgUser

    from ice.tg import translate
except ImportError:
    translate = None

WHEN = datetime(2026, 9, 30)


def restricted(is_member: bool):
    flags = {name: False for name in ChatMemberRestricted.model_fields
             if name.startswith("can_")}
    return ChatMemberRestricted(**{**flags, "user": USER, "until_date": WHEN,
                                   "is_member": is_member})


def message(**kw):
    return TgMessage(message_id=1, date=WHEN, chat=Chat(id=-100, type="supergroup"),
                     from_user=USER, **kw)


if translate:
    USER = TgUser(id=7, is_bot=False, first_name="Juan")


@unittest.skipIf(translate is None, "falta aiogram")
class Transitions(unittest.TestCase):
    def test_join_and_leave(self):
        left, member = ChatMemberLeft(user=USER), ChatMemberMember(user=USER)
        self.assertEqual(translate.transition(left, member), "join")
        self.assertEqual(translate.transition(member, left), "leave")

    def test_restricted_member_who_leaves_is_a_leave(self):
        # Alguien que se fue sin verificarse sigue "restricted", pero afuera.
        self.assertEqual(translate.transition(restricted(True), restricted(False)), "leave")

    def test_restricting_is_not_a_join(self):
        self.assertIsNone(translate.transition(ChatMemberMember(user=USER), restricted(True)))

    def test_a_ban_is_not_a_leave(self):
        banned = ChatMemberBanned(user=USER, until_date=WHEN)
        self.assertIsNone(translate.transition(ChatMemberMember(user=USER), banned))

    def test_promotion_changes_staff(self):
        flags = {name: False for name, f in ChatMemberAdministrator.model_fields.items()
                 if name.startswith("can_") and f.is_required()}
        admin = ChatMemberAdministrator(user=USER, is_anonymous=False,
                                        **flags)
        self.assertTrue(translate.staff_changed(ChatMemberMember(user=USER), admin))
        self.assertFalse(translate.staff_changed(ChatMemberMember(user=USER), restricted(True)))


@unittest.skipIf(translate is None, "falta aiogram")
class Messages(unittest.TestCase):
    def test_text_and_caption(self):
        self.assertEqual(translate.text_of(message(text="vendo bici")), "vendo bici")
        photo = [PhotoSize(file_id="a", file_unique_id="u1", width=1, height=1)]
        self.assertEqual(translate.text_of(message(photo=photo, caption="vendo bici")),
                         "vendo bici")

    def test_same_photo_without_text_is_the_same_message(self):
        def photo(uid):
            return message(photo=[PhotoSize(file_id="x", file_unique_id=uid, width=1, height=1)])
        self.assertEqual(translate.text_of(photo("u1")), translate.text_of(photo("u1")))
        self.assertNotEqual(translate.text_of(photo("u1")), translate.text_of(photo("u2")))

    def test_hidden_link(self):
        m = message(text="mirá acá", entities=[
            MessageEntity(type="text_link", offset=5, length=3, url="https://spam.xyz")])
        self.assertEqual(translate.hidden_links(m), ("https://spam.xyz",))

    def test_forward_from_channel(self):
        origin = MessageOriginChannel(date=WHEN, chat=Chat(id=-5, type="channel"), message_id=3)
        self.assertTrue(translate.from_channel(message(text="promo", forward_origin=origin)))
        self.assertFalse(translate.from_channel(message(text="hola")))

    def test_service_messages_are_not_messages(self):
        self.assertFalse(translate.is_user_content(message(new_chat_members=[USER])))
        self.assertTrue(translate.is_user_content(message(text="hola")))
