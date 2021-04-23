#  Module: Spotify Music Downloader (SMD)
#  Author: code-rgb <https://github.com/code-rgb>
#          TG: [ @DeletedUser420 ]
#
#  Copyright (C) 2021 - Kraken

from .. import command, module, util
from pyrogram.errors import BadRequest

class Smd(module.Module):
    name: ClassVar[str] = "Smd"

    @command.desc("Find Songs fast")
    async def cmd_smd(self, ctx: command.Context):
        if not ctx.input:
            return "__Provide a song name or artist name to search__"
        await ctx.respond(f"🔎 __Searching for__ **{ctx.input}**")
        chat_id = ctx.msg.chat.id
        try:
            async for m in ctx.bot.client.search_messages(
                -1001356426755, query=ctx.input.strip(), limit=1, filter="audio"
            ):
                await m.copy(chat_id, caption="")
                break
            else:
                return "⚠️ Song Not Found !"
        except BadRequest:
            return "Join [THIS](https://t.me/joinchat/UNluAx4vPQt6kBJl) channel first"
            
