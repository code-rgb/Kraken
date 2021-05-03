import asyncio
import logging
from math import floor
from typing import Dict, Optional, Tuple

from pyrogram.errors import FloodWait
from pyrogram.types import CallbackQuery

from ..core.raw import Message
from .misc import human_readable_bytes as humanbytes
from .time import format_duration_td as time_formater
from .time import sec as time_now

_PROCESS: Dict[str, Tuple[int, int]] = {}


def get_media(msg):
    available_media = (
        "audio",
        "document",
        "photo",
        "sticker",
        "animation",
        "video",
        "voice",
        "video_note",
        "new_chat_photo",
    )
    if isinstance(msg, Message):
        for kind in available_media:
            media = getattr(msg, kind, None)
            if media is not None:
                break
        else:
            logging.debug(
                f" {__name__} - This message doesn't contain any downloadable media"
            )
            return
        return media


def get_file_id(msg) -> Optional[str]:
    if media := get_media(msg):
        return media.file_id


async def progress(
    current: int,
    total: int,
    message: Message,
    mode: str,
    filename: str = "",
    c_q: CallbackQuery = None,
):
    if message.process_is_canceled:
        # Cancel Process
        return await message._client.stop_transmission()
    # Supports callback query and message
    edit_func = c_q.edit_message_text if c_q else message.edit
    # Unique ID to track progress
    process_id = f"{message.chat.id}.{message.message_id}"
    if current == total:
        # Finished
        if process_id not in _PROCESS:
            return
        del _PROCESS[process_id]
        try:
            await edit_func(f"`finalizing {mode} process ...`")
        except FloodWait as f_w:
            await asyncio.sleep(f_w.x)
        return
    now = time_now()
    if process_id not in _PROCESS:
        _PROCESS[process_id] = (now, now)
    start, last_update_time = _PROCESS[task_id]
    # ------------------------------------ #
    if (now - last_update_time) >= 8:
        _PROCESS[task_id] = (start, now)
        # Only edit message once every 8 seconds to avoid ratelimits
        after = now - start
        speed = current / after
        eta = round((total - current) / speed)
        percentage = round(current / total * 100)
        progress_bar = (f"[{'█' * floor(15 * percentage / 100)}"
                        f"{'░' * floor(15 * (1 - percentage / 100))}]")
        progress = f"""
<i>{mode}:</i>  <code>{filename}</code>
<b>Completed:</b>  <code>{humanbytes(current)} / {humanbytes(total)}</code>
<b>Progress:</b>  <code>{progress_bar} {percentage} %</code>
<b>Speed:</b>  <code>{humanbytes(speed, postfix='/s')}</code>
<b>ETA:</b>  <code>{time_formater(eta)}</code>
"""
        try:
            await edit_func(progress)
        except FloodWait as f_w:
            await asyncio.sleep(f_w.x + 5)
