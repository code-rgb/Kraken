import logging
from typing import Optional

from pyrogram.types import Message


# https://github.com/pyrogram/pyrogram/blob/master/pyrogram/methods/messages/download_media.py#L103
def get_media(msg):
    available_media = ("audio", "document", "photo", "sticker", "animation", "video", "voice", "video_note",
                       "new_chat_photo")
    if isinstance(msg, Message):
        for kind in available_media:
            media = getattr(msg, kind, None)
            if media is not None:
                break
        else:
            return logging.debug(f" {__name__} - This message doesn't contain any downloadable media")
        return media


def get_file_id(msg) -> Optional[str]:
    if media := get_media(msg):
        return media.file_id
