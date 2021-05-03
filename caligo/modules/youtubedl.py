import os
import re
from collections import defaultdict
from functools import wraps
from glob import glob
from math import floor
from typing import Any, ClassVar, Dict, List, Optional, Pattern, Tuple, Union
from uuid import uuid4

import ujson
import youtube_dl
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultPhoto,
    Message,
)
from youtube_dl.utils import (
    DownloadError,
    ExtractorError,
    GeoRestrictedError,
    UnsupportedError,
)
from youtubesearchpython.__future__ import VideosSearch

from .. import command, listener, module, util

yt_result_vid = Optional[Dict[str, str]]


def loop_safe(func):

    @wraps(func)
    async def wrapper(self, *args: Any, **kwargs: Any) -> Any:
        return await util.run_sync(func, self, *args, **kwargs)

    return wrapper


class YouTube(module.Module):
    name: ClassVar[str] = "YouTube"
    yt_datafile: str
    yt_link_regex: Pattern
    base_yt_url: str
    default_thumb: str
    url_regex: Pattern

    async def on_load(self):
        self.yt_datafile = "yt_data.json"
        self.yt_link_regex = re.compile(
            r"(?:youtube\.com|youtu\.be)/(?:[\w-]+\?v=|embed/|v/|shorts/)?([\w-]{11})"
        )
        self.url_regex = re.compile(
            r"(?:https?://)?(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
        )
        self.base_yt_url = "https://www.youtube.com/watch?v="
        self.default_thumb = "https://i.imgur.com/4LwPLai.png"

    @staticmethod
    def format_line(key: str, value: str) -> str:
        return f"<b>❯  {key}</b> : {value or 'N/A'}"

    @loop_safe
    def result_formatter(
        self, results: List[Optional[Dict[str, Union[str, Dict, List]]]]
    ) -> List[yt_result_vid]:
        """
        Format yt search result to store it in yt_data.txt
        """
        out: List[yt_result_vid] = []
        for index, vid in enumerate(results):
            thumb = vid.get("thumbnails")[-1].get("url")
            msg = f'<a href={vid["link"]}><b>{vid.get("title")}</b></a>\n'
            if descripition := vid.get("descriptionSnippet"):
                msg += f"<pre>{''.join(list(map(lambda x: x['text'], descripition)))}</pre>"
            msg += f"""
{self.format_line('Duration', acc['duration'] if (acc := vid.get('accessibility')) else 'N/A')}
{self.format_line('Views', view['short'] if (view := vid.get('viewCount')) else 'N/A')}
{self.format_line('Upload Date', vid.get('publishedTime'))}
"""
            if uploader := vid.get("channel"):
                msg += self.format_line(
                    "Uploader",
                    f"<a href={uploader.get('link')}>{uploader.get('name')}</a>",
                )
            list_view = (f"<img src={thumb}><b><a href={vid['link']}>"
                         f"{index}. {acc['title'] if acc else 'N/A'}</a></b>")
            out.append(
                dict(msg=msg, thumb=thumb, yt_id=vid["id"],
                     list_view=list_view))
        return out

    @loop_safe
    def save_search(self, to_save: List[yt_result_vid]) -> str:
        try:
            with open(self.yt_datafile, "r") as f:
                file = ujson.load(f)
        except FileNotFoundError:
            file: Dict[str, List[yt_result_vid]] = {}
        key = str(uuid4())[:8]
        file[key] = to_save
        with open(self.yt_datafile, "w") as outfile:
            ujson.dump(file, outfile)
        return key

    async def yt_search(self,
                        query: str) -> Optional[Tuple[str, yt_result_vid]]:
        videosResult = await VideosSearch(query, limit=15).next()
        if videosResult and (resp := videosResult.get("result")):
            search_data = await self.result_formatter(resp)
            key = await self.save_search(search_data)
            return key, search_data[0]

    async def get_ytthumb(self, yt_id: str) -> str:
        for quality in (
                "maxresdefault.jpg",
                "hqdefault.jpg",
                "sddefault.jpg",
                "mqdefault.jpg",
                "default.jpg",
        ):
            link = f"https://i.ytimg.com/vi/{yt_id}/{quality}"
            status = await util.aiorequest(self.bot.http, link, mode="status")
            if status == 200:
                thumb_link = link
                break
        else:
            thumb_link = self.default_thumb
        return thumb_link

    @staticmethod
    def get_choice_by_id(choice_id: str, media_type: str) -> Tuple[str, str]:
        if choice_id == "mkv":
            # default format selection
            choice_str = "bestvideo+bestaudio/best"
            disp_str = "best(video+audio)"
        elif choice_id == "mp4":
            # Download best Webm / Mp4 format available or any other best if no mp4
            # available
            choice_str = ("bestvideo[ext=webm]+251/bestvideo[ext=mp4]+"
                          "(258/256/140/bestaudio[ext=m4a])/"
                          "bestvideo[ext=webm]+(250/249)/best")
            disp_str = "best(video+audio)[webm/mp4]"
        elif choice_id == "mp3":
            choice_str = "320"
            disp_str = "320 Kbps"
        else:
            disp_str = str(choice_id)
            if media_type == "v":
                # mp4 video quality + best compatible audio
                choice_str = disp_str + "+(258/256/140/bestaudio[ext=m4a])/best"
            else:  # Audio
                choice_str = disp_str
        return choice_str, disp_str

    # https://regex101.com/r/c06cbV/1
    @loop_safe
    def get_yt_video_id(self, url: str) -> Optional[str]:
        if match := self.yt_link_regex.search(url):
            return match.group(1)

    @loop_safe
    def get_download_button(
        self,
        yt_id: str,
        body: bool = False
    ) -> Union[InlineKeyboardMarkup, Dict[str, Union[str, InlineKeyboardMarkup,
                                                     None]]]:
        buttons = [[
            InlineKeyboardButton("⭐️ BEST - 📹 MKV",
                                 callback_data=f"ytdl_download_{yt_id}_mkv_v"),
            InlineKeyboardButton(
                "⭐️ BEST - 📹 WebM/MP4",
                callback_data=f"ytdl_download_{yt_id}_mp4_v",
            ),
        ]]
        best_audio_btn = [[
            InlineKeyboardButton(
                "⭐️ BEST - 🎵 320Kbps - MP3",
                callback_data=f"ytdl_download_{yt_id}_mp3_a",
            )
        ]]
        try:
            vid_data = youtube_dl.YoutubeDL({
                "no-playlist": True
            }).extract_info(f"{self.base_yt_url}{yt_id}", download=False)
        except ExtractorError:
            vid_data = None
            buttons += best_audio_btn
        else:
            humanbytes = util.misc.human_readable_bytes
            # ------------------------------------------------ #
            qual_dict = defaultdict(lambda: defaultdict(int))
            qual_list = ("1440p", "1080p", "720p", "480p", "360p", "240p",
                         "144p")
            audio_dict: Dict[int, str] = {}
            # ------------------------------------------------ #
            for video in vid_data["formats"]:
                fr_note = video.get("format_note")
                fr_id = int(video.get("format_id"))
                fr_size = video.get("filesize")
                if video.get("ext") == "mp4":
                    for frmt_ in qual_list:
                        if fr_note in (frmt_, frmt_ + "60"):
                            qual_dict[frmt_][fr_id] = fr_size
                if video.get("acodec") != "none":
                    bitrrate = int(video.get("abr", 0))
                    if bitrrate != 0:
                        audio_dict[
                            bitrrate] = f"🎵 {bitrrate}Kbps ({humanbytes(fr_size) or 'N/A'})"
            video_btns = []
            for frmt in qual_list:
                frmt_dict = qual_dict[frmt]
                if len(frmt_dict) != 0:
                    frmt_id = sorted(list(frmt_dict))[-1]
                    frmt_size = humanbytes(frmt_dict.get(frmt_id)) or "N/A"
                    video_btns.append(
                        InlineKeyboardButton(
                            f"📹 {frmt} ({frmt_size})",
                            callback_data=f"ytdl_download_{yt_id}_{frmt_id}_v",
                        ))
            buttons += util.sublists(video_btns, width=2)
            buttons += best_audio_btn
            buttons += util.sublists(
                list(
                    map(
                        lambda x: InlineKeyboardButton(
                            audio_dict[x],
                            callback_data=f"ytdl_download_{yt_id}_{x}_a"),
                        sorted(audio_dict.keys(), reverse=True),
                    )),
                width=2,
            )
        if body:
            vid_body = (
                f"<b>[{vid_data.get('title')}]({vid_data.get('webpage_url')})</b>"
                if vid_data else None)
            return {"msg": vid_body, "buttons": InlineKeyboardMarkup(buttons)}
        return InlineKeyboardMarkup(buttons)

    async def video_downloader(self, url: str, uid: str, rnd_key: str,
                               prog_func):
        options = {
            "addmetadata":
                True,
            "geo_bypass":
                True,
            "nocheckcertificate":
                True,
            "outtmpl":
                os.path.join(self.bot.getConfig.downloadPath, rnd_key,
                             "%(title)s-%(format)s.%(ext)s"),
            "logger":
                self.log,
            "progress_hooks": [prog_func],
            "format":
                uid,
            "writethumbnail":
                True,
            "prefer_ffmpeg":
                True,
            "postprocessors": [
                {
                    "key": "FFmpegMetadata"
                }
                # ERROR R15: Memory quota vastly exceeded
                # {"key": "FFmpegVideoConvertor", "preferedformat": "mp4"},
            ],
            "quiet":
                True,
            "logtostderr":
                False,
        }
        return await self.ytdownloader(url, options)

    async def audio_downloader(self, url: str, uid: str, rnd_key: str,
                               prog_func):
        options = {
            "outtmpl":
                os.path.join(self.bot.getConfig.downloadPath, rnd_key,
                             "%(title)s-%(format)s.%(ext)s"),
            "logger":
                self.log,
            "progress_hooks": [prog_func],
            "writethumbnail":
                True,
            "prefer_ffmpeg":
                True,
            "format":
                "bestaudio/best",
            "geo_bypass":
                True,
            "nocheckcertificate":
                True,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": uid,
                },
                {
                    "key": "EmbedThumbnail"
                },  # ERROR: Conversion failed!
                {
                    "key": "FFmpegMetadata"
                },
            ],
            "quiet":
                True,
            "logtostderr":
                False,
        }
        return await self.ytdownloader(url, options)

    @loop_safe
    def ytdownloader(self, url: str, options: Dict):
        try:
            with youtube_dl.YoutubeDL(options) as ytdl:
                out = ytdl.download([url])
        except DownloadError:
            self.log.error("[DownloadError] : Failed to Download Video")
        except GeoRestrictedError:
            self.log.error(
                "[GeoRestrictedError] : The uploader has not made this video"
                " available in your country")
        except Exception as all_e:
            self.log.exception(f"[{all_e.__class__.__name__}] - {all_e}")
        else:
            return out

    @loop_safe
    def generic_extractor(self, url: str) -> Optional[Dict[str, Any]]:
        buttons = [[
            InlineKeyboardButton("⭐️ BEST - 📹 Video",
                                 callback_data=f"generic_down_best_v"),
            InlineKeyboardButton("⭐️ BEST - 🎧 Audio",
                                 callback_data=f"generic_down_best_a"),
        ]]
        try:
            resp = youtube_dl.YoutubeDL({
                "no-playlist": True
            }).extract_info(url, download=False)
        except UnsupportedError:
            return self.log.error(f"[URL -> {url}] - is not NOT SUPPORTED")
        except DownloadError as d_e:
            return self.log.error(f"[URL -> {url}] - {d_e}")
        except ExtractorError:
            self.log.warning(f"[URL -> {url}] - Failed to Extract Info")
            return dict(
                msg="[No Information]",
                thumb=self.default_thumb,
                buttons=InlineKeyboardMarkup(buttons),
            )
        msg = f"<b>[{resp.get('title')}]({url})</b>\n"
        if description := resp.get("description"):
            msg += f"<pre>{description}</pre>\n"
        msg += f"""
{self.format_line("Duration", resp.get("duration"))}
{self.format_line("Uploader", resp.get("uploader"))}
"""
        if formats := resp.get("formats"):
            humanbytes = util.misc.human_readable_bytes
            buttons += util.sublists(
                list(
                    map(
                        lambda x: InlineKeyboardButton(
                            " | ".join(
                                list(
                                    filter(
                                        None,
                                        (
                                            x.get("format"),
                                            x.get("ext"),
                                            humanbytes(x["filesize"])
                                            if x.get("filesize") else None,
                                        ),
                                    ))),
                            callback_data=f"generic_down_{x.get('format_id')}",
                        ),
                        self.filter_generic_formats(formats),
                    )),
                width=1,
            )
            return dict(
                msg=msg,
                thumb=resp.get("thumbnail", self.default_thumb),
                buttons=InlineKeyboardMarkup(buttons),
            )

    def filter_generic_formats(self, raw_formats: Dict) -> Dict:
        widthset = set()

        def qual_filter(frmt) -> bool:
            if frmt.get("tbr") and frmt.get("acodec") and (width :=
                                                           frmt.get("width")):
                if not (width in widthset):
                    widthset.add(width)
                    return True
            return False

        frmt_list = list(
            filter(
                qual_filter,
                sorted(raw_formats,
                       key=lambda x: float(x.get("tbr") or 0),
                       reverse=True),
            ))[:25]
        return frmt_list if len(frmt_list) > 1 else raw_formats

    async def parse_ytquery(
        self, search_query: str
    ) -> Optional[Dict[str, Union[str, InlineKeyboardMarkup]]]:
        query_split = search_query.split()
        if len(query_split) == 1:
            # can be some text or an URL
            if match := self.yt_link_regex.search(query_split[0]):
                # youtube link
                yt_id = match.group(1)
                if vid_data := await self.get_download_button(yt_id, body=True):
                    # Add Thumbnail
                    vid_data["thumb"] = await self.get_ytthumb(yt_id)
                    return vid_data
            if self.url_regex.search(query_split[0]):
                # Matches URL regex (doesn't mean it's supported by YoutubeDL)
                return await self.generic_extractor(query_split[0])
        # YT Search if query didn't matched earlier or is of multiple words
        return await self.yt_search(search_query.strip())

    @listener.pattern(r"^ytdl\s+(.+)")
    async def on_inline_query(self, query: InlineQuery) -> None:
        if vid_data := await self.parse_ytquery(query.matches[0].group(1)):
            photo = (self.default_thumb if vid_data["thumb"].endswith(".html")
                     else vid_data["thumb"])
            await query.answer(
                results=[
                    InlineQueryResultPhoto(
                        photo_url=photo,
                        thumb_url=photo,
                        caption=vid_data["msg"],
                        reply_markup=vid_data["buttons"],
                    )
                ],
                cache_time=3,
                switch_pm_text="⬇️ Click to Download",
                switch_pm_parameter="inline",
            )

    @command.usage("[Download from youtube]")
    async def cmd_ytdl(self, ctx: command.Context) -> str:
        video_link = ctx.msg.reply_to_message.text.strip()
        rnd_id = str(uuid4())[:8]
        uid = self.get_choice_by_id("mp4", "v")
        await self.download_progress(video_link,
                                     uid[0],
                                     rnd_id,
                                     msg=ctx.msg,
                                     downtype="video")
        await ctx.respond("Done. Uploading ...")
        for file in glob(
                os.path.join(self.bot.getConfig.downloadPath, rnd_id, "*")):
            # Exclude incomplete files and thumb
            if not file.lower().endswith((".jpg", ".png", ".webp", ".part")):
                media_file = file
                break
        else:
            await ctx.respond("No Media Found", mode="error", delete_after=8)
        await ctx.msg.reply_video(
            video=media_file,
            progress=util.progress,
            supports_streaming=True,
            progress_args=(ctx.msg, "Uploading", "video.mp4"),
        )
        await ctx.msg.delete()

    async def download_progress(self, *args, msg: Union[Message, CallbackQuery],
                                downtype: str):
        last_update_time = None
        humanbytes = util.misc.human_readable_bytes
        time_formater = util.time.format_duration_td
        if isinstance(msg, Message):
            edit_func = msg.edit
        elif isinstance(msg, CallbackQuery):
            edit_func = msg.edit_message_text
        else:
            raise TypeError(f"Unsupported msg type '{type(msg)}'")

        def prog_func(prog_data: Dict) -> None:
            nonlocal last_update_time
            now = util.time.sec()
            # Only edit message once every 8 seconds to avoid ratelimits
            if (last_update_time is None
                    or (now - last_update_time).total_seconds() >= 8):
                if prog_data.get("status") == "finished":
                    progress = "🔄  Download Finished Now Converting."
                else:
                    # ------------ Progress Info ------------ #
                    if not ((eta := prog_data.get("eta")) and
                            (speed := prog_data.get("speed"))):
                        return
                    current = prog_data.get("downloaded_bytes")
                    total = prog_data.get("total_bytes")
                    filename = prog_data.get("filename")
                    # ---------------------------------------- #
                    percentage = round(current / total * 100)
                    progress_bar = (
                        f"[{'█' * floor(15 * percentage / 100)}"
                        f"{'░' * floor(15 * (1 - percentage / 100))}]")
                    progress = f"""
<i>Downloading:</i>  <code>{filename}</code>
<b>Completed:</b>  <code>{humanbytes(current)} / {humanbytes(total)}</code>
<b>Progress:</b>  <code>{progress_bar} {percentage} %</code>
<b>Speed:</b>  <code>{humanbytes(speed, postfix='/s')}</code>
<b>ETA:</b>  <code>{time_formater(eta)}</code>
"""
                self.bot.loop.create_task(edit_func(progress))
                last_update_time = now

        if downtype == "video":
            return await self.video_downloader(*args, prog_func)
        if downtype == "audio":
            return await self.audio_downloader(*args, prog_func)
