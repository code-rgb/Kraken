#  Module: Songlink
#  Author: code-rgb <https://github.com/code-rgb>
#          TG: [ @DeletedUser420 ]
#
#  Copyright (C) 2021 - Kraken

import re
from html import escape
from typing import ClassVar, Dict, Optional, Tuple
from urllib.parse import quote

import aiohttp
from pyrogram.types import Message

from .. import command, module, util


class SongLink(module.Module):
    name: ClassVar[str] = "SongLink"
    uri: str

    async def on_load(self) -> None:
        self.uri = "https://api.song.link/v1-alpha.1/links?url="

    

    @staticmethod
    async def find_url_from_msg(
            ctx: command.Context) -> Optional[Tuple[str, Message]]:
        reply = ctx.msg.reply_to_message
        msg_instance, link = None, None
        if ctx.input:
            link = ctx.input.strip()
            msg_instance = ctx.msg
        elif reply and (reply.text or reply.caption):
            txt = reply.text or reply.caption
            msg_instance = reply
            try:
                url_e = [
                    x for x in (
                        msg_instance.entities or msg_instance.caption_entities)
                    if x.type in ("url", "text_link")
                ]
            except TypeError:
                pass
            else:
                if len(url_e) > 0:
                    y = url_e[0]
                    link = (txt[y.offset:(y.offset + y.length)]
                            if y.type == "url" else y.url)
        if msg_instance and link:
            return link, msg_instance

    @staticmethod
    def beautify(text: str) -> str:
        match = re.search(r"[A-Z]", text)
        if match:
            x = match.group(0)
            text = text.replace(x, " " + x)
        text = text.title()
        if "Youtube" in text:
            out = text.replace("Youtube", "YouTube")
        elif "Soundcloud" in text:
            out = text.replace("Soundcloud", "SoundCloud")
        else:
            out = text
        return out

    @staticmethod
    def htmlink(text: str, link: str) -> str:
        return f"<a href={escape(link)}>{escape(text)}</a>"

    def get_data(self, resp: Dict) -> str:
        platforms = resp["linksByPlatform"]
        data_ = resp["entitiesByUniqueId"][resp["entityUniqueId"]]
        title = data_.get("title")
        artist = data_.get("artistName")
        thumb = data_.get("thumbnailUrl")
        des = f"[\u200c]({thumb})" if thumb else ""
        if title:
            des += f"{self.htmlink(title, platforms[data_['platforms'][0]].get('url'))}"
        if artist:
            des += f"\nARTIST(S): __{artist}__"
        des += "\n\n🎧  LISTEN ON:\n<b>" + "  |  ".join([
            f"{self.htmlink(self.beautify(x), platforms[x].get('url'))}"
            for x in platforms
            if x != "itunes"
        ])
        return des + "</b>"

    @command.desc("link to a song on any supported music streaming platform")
    async def cmd_songlink(self, ctx: command.Context):
        if not (link := (await self.find_url_from_msg(ctx))):
            return "__No Valid URL Found !__", 5
        link = link[0]
        await ctx.respond(f'🔎 Searching for `"{link}"`')

        if not (resp := await util.aiorequest(self.bot.http, self.uri + quote(link), mode="json")):
            return "Oops something went wrong! Please try again later."
        await ctx.respond(self.get_data(resp) or "404 Not Found")
