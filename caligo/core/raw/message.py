import re
from typing import Dict, List, Optional, Pattern, Union

from pyrogram import Client, errors, raw, types, utils

# Inspired from Userge
class Message(types.Message):

    def __init__(self, client: Client, mvar: Dict, **kwargs):
        self.is_kraken = True
        if mvar.get("segments"):
            self.segments = mvar["segments"]
            del mvar["segments"]
        self._client = client
        del mvar["_client"]
        super().__init__(client=client, **mvar)

    @classmethod
    def _parse(cls, msg: types.Message, **kwargs):
        mvars = vars(msg)
        if mvars['reply_to_message']:
            mvars['reply_to_message'] = cls._parse(mvars['reply_to_message'],
                                                   **kwargs)
        return cls(client=msg._client, mvar=mvars, **kwargs)

    async def edit(self,
                   text: str,
                   parse_mode: Optional[str] = object,
                   entities: List["types.MessageEntity"] = None,
                   disable_web_page_preview: bool = None,
                   reply_markup: "types.InlineKeyboardMarkup" = None,
                   sudo: bool = True) -> "Message":
        try:
            return await self._client.edit_message_text(
                chat_id=self.chat.id,
                message_id=self.message_id,
                text=text,
                parse_mode=parse_mode,
                entities=entities,
                disable_web_page_preview=disable_web_page_preview,
                reply_markup=reply_markup)
        except errors.MessageNotModified:
            return self
        except (errors.MessageAuthorRequired, errors.MessageIdInvalid):
            if sudo:
                msg = await self.reply(
                    text=text,
                    parse_mode=parse_mode,
                    disable_web_page_preview=disable_web_page_preview,
                    reply_markup=reply_markup)
                if isinstance(msg, types.Message):
                    self.message_id = msg.message_id
                return msg

    edit_text = edit

    async def reply(
            self,
            text: str,
            quote: Optional[bool] = None,
            parse_mode: Union[str, object] = object,
            disable_web_page_preview: Optional[bool] = None,
            disable_notification: Optional[bool] = None,
            reply_to_message_id: Optional[int] = None,
            reply_markup: types.InlineKeyboardMarkup = None) -> 'Message':
        if quote is None:
            quote = self.chat.type != "private"
        if reply_to_message_id is None and quote:
            reply_to_message_id = self.message_id
        return await self._client.send_message(
            chat_id=self.chat.id,
            text=text,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview,
            disable_notification=disable_notification,
            reply_to_message_id=reply_to_message_id,
            reply_markup=reply_markup)

    reply_text = reply

    async def delete(self, revoke: bool = True, sudo: bool = True) -> bool:
        try:
            return bool(await super().delete(revoke=revoke))
        except errors.MessageDeleteForbidden as m_e:
            if not sudo:
                raise m_e
            return False
