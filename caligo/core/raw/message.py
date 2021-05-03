from typing import Dict, List, Optional, Set, Union

from pyrogram import Client, types
from pyrogram.errors import (
    MessageAuthorRequired,
    MessageDeleteForbidden,
    MessageIdInvalid,
    MessageNotModified,
)

_CANCEL_SET: Set[int] = set()

# Inspired from Userge


class Message(types.Message):

    def __init__(self, client: Client, segments: List[Optional[str]],
                 mvars: Dict[str, object], **kwargs):
        self._process_canceled = False
        self._kwargs = kwargs
        self._client = client
        self.segments = segments
        super().__init__(client=client, **mvars)

    @classmethod
    def _parse(cls, msg: types.Message, **kwargs):
        mvars = vars(msg)
        segments = mvars.get("segments")
        client = msg._client
        for _key in ["segments", "_client", "_process_canceled", "_kwargs"]:
            mvars.pop(_key, None)

        if mvars["reply_to_message"]:
            mvars["reply_to_message"] = cls._parse(mvars["reply_to_message"],
                                                   **kwargs)
        return cls(client=client, segments=segments, mvars=mvars, **kwargs)

    @property
    def process_is_canceled(self) -> bool:
        """Returns True if process canceled"""
        if self.message_id in _CANCEL_SET:
            _CANCEL_SET.remove(self.message_id)
            self._process_canceled = True
        return self._process_canceled

    def cancel_the_process(self) -> None:
        """Set True to the self.process_is_canceled"""
        _CANCEL_SET.add(self.message_id)

    async def edit(
        self,
        text: str,
        parse_mode: Optional[str] = object,
        entities: List["types.MessageEntity"] = None,
        disable_web_page_preview: bool = None,
        reply_markup: "types.InlineKeyboardMarkup" = None,
        sudo: bool = True,
    ) -> "Message":
        try:
            return await self._client.edit_message_text(
                chat_id=self.chat.id,
                message_id=self.message_id,
                text=text,
                parse_mode=parse_mode,
                entities=entities,
                disable_web_page_preview=disable_web_page_preview,
                reply_markup=reply_markup,
            )
        except MessageNotModified:
            return self
        except (MessageAuthorRequired, MessageIdInvalid):
            if sudo:
                msg = await self.reply(
                    text=text,
                    parse_mode=parse_mode,
                    disable_web_page_preview=disable_web_page_preview,
                    reply_markup=reply_markup,
                )
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
        reply_markup: types.InlineKeyboardMarkup = None,
    ) -> "Message":
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
            reply_markup=reply_markup,
        )

    reply_text = reply

    async def delete(self, revoke: bool = True, sudo: bool = True) -> bool:
        try:
            return bool(await super().delete(revoke=revoke))
        except MessageDeleteForbidden as m_e:
            if not sudo:
                raise m_e
            return False
