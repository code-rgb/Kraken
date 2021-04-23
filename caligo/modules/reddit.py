import re
from html import escape
from typing import ClassVar, Dict, Optional, Tuple, Pattern
from urllib.parse import quote

import aiohttp
from pyrogram.types import Message, InlineQuery

from .. import command, module, util, listener


class RedditDl(module.Module):
    name: ClassVar[str] = "Reddit"
    http: aiohttp.ClientSession
    uri: str
    thumb_regex: Pattern

    async def on_load(self) -> None:
        self.thumb_regex = re.compile(
            r"https?://preview\.redd\.it/\w+\.(?:jpg|jpeg|png)\?width=(?:[2][1-9][0-9]|[3-9][0-9]{2}|[0-9]{4,})"
        )
        self.http = self.bot.http
        self.uri = "https://meme-api.herokuapp.com/gimme"

    def get_rthumb(self, result: Dict) -> str:
        """get thumbnail of size 210 and above"""
        thumb = None
        if thumbs := result.get("preview"):
            while not thumb:
                if len(thumbs) == 1:
                    thumb = thumbs[0]
                else:
                    t_img = thumbs.pop(0)
                    if self.thumb_regex.search(t_img):
                        thumb = t_img
        return thumb.replace("\u0026", "&") if thumb else result.get("url")

    @staticmethod
    def parse_rpost(r: Dict) -> Optional[Dict[str, str]]:
        if r.get("code"):
            return f"**ERROR (code: {r['code']})** : `{r.get('message')}`"
        if not r.get('url'):
            return "Coudn't find any reddit post with image or gif, Please try again"
        caption = f"""
<b>{r['title']}</b>
<code>Posted by u/{r['author']}
↕️ {r['ups']}</code>"""
        if r["spoiler"]:
            caption += "\n⚠️ Post marked as **SPOILER**"
        if r["nsfw"]:
            caption += "\n🔞 Post marked as **ADULT**"
        return dict(caption=caption, postlink=r["postLink"],subreddit=r["subreddit"],media_url=r["url"])

    # @command.desc("get post from reddit")
    async def cmd_reddit(self, ctx: command.Context):
        await ctx.respond("`Processing ...`")
        rjson = await util.aiorequest.get(session=self.http, url=self.uri, mode="json")
        result = self.parse_rpost(rjson)
        if isinstance(result, str): # Error
            return result 
        chat_id = ctx.msg.chat.id
        reply_id = ctx.msg.reply_to_message.message_id if ctx.msg.reply_to_message else None
        caption = result["caption"] + f"\nSource: [r/{result['subreddit']}]({result['postlink']})"
        if result["media_url"].endswith(".gif"):
            await self.bot.client.send_animation(
                chat_id=chat_id,
                animation=result["media_url"],
                caption=caption,
                reply_to_message_id=reply_id,
            )
        else:
            await self.bot.client.send_photo(
                chat_id=chat_id,
                photo=result["media_url"],
                caption=caption,
                reply_to_message_id=reply_id,
            )
        await ctx.msg.delete()


    @listener.pattern(r"(?i)^reddit\s{0,}(?:(?:r/)?([A-Za-z]+)\.)?$")
    async def on_inline_query(self, query: InlineQuery) -> None:
        if subreddit := query.matches[0].group(1):
            pass
        else:
            pass