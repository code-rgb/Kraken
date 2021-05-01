import asyncio
from typing import ClassVar, Dict, List, Optional, Union, Tuple, Pattern, Any
from uuid import uuid4
import youtube_dl
import ujson
from youtubesearchpython.__future__ import VideosSearch
from collections import defaultdict
from .. import command, listener, module, util
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from functools import wraps
from youtube_dl.utils import DownloadError, ExtractorError, GeoRestrictedError

yt_result_vid = Optional[Dict[str, str]]


def loop_safe(func):
    @wraps(func)
    async def wrapper(self, *args: Any, **kwargs: Any) -> Any:
        return await utils.run_sync(func, self, *args: Any, **kwargs: Any)
    return wrapper

class YouTube(module.Module):
    name: ClassVar[str] = "YouTube"
    yt_datafile: str
    yt_link_regex: Pattern
    base_yt_url: str

    async def on_load(self):
        self.yt_datafile = "yt_data.json"
        self.yt_link_regex = re.compile(r"(?:youtube\.com|youtu\.be)/(?:[\w-]+\?v=|embed/|v/|shorts/)?([\w-]{11})")
        self.base_yt_url = "https://www.youtube.com/watch?v="


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
            list_view = (
                f"<img src={thumb}><b><a href={vid['link']}>"
                f"{index}. {acc['title'] if acc else 'N/A'}</a></b>"
            )
            out.append(dict(msg=msg, thumb=thumb, yt_id=vid["id"], list_view=list_view))
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

    async def yt_search(self, query: str) -> Optional[Tuple[str, yt_result_vid]]:
        videosResult = await VideosSearch(query, limit=15).next()
        if videosResult and (resp := videosResult.get("result")):
            search_data = await self.result_formatter(resp)
            key  = await self.save_search(search_data)
            return key, search_data[0]


    async def get_ytthumb(self, yt_id: str) -> str:
        for quality in ("maxresdefault.jpg", "hqdefault.jpg", "sddefault.jpg", "mqdefault.jpg", "default.jpg"):
            link = f"https://i.ytimg.com/vi/{yt_id}/{quality}"
            status = await util.aiorequest(self.bot.http, link, mode="status")
            if status == 200:
                thumb_link = link
                break
        else:
            thumb_link = "https://i.imgur.com/4LwPLai.png"
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
            choice_str = ("bestvideo[ext=webm]+251/bestvideo[ext=mp4]+
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
    def get_yt_video_id(self, url: str) -> Optional[str]:
        if match := self.yt_link_regex.search(url)
            return match.group(1)

    @loop_safe
    def get_download_button(self, yt_id: str, body: bool = False) -> Union[InlineKeyboardMarkup, Tuple[Optional[str], InlineKeyboardMarkup]]:
        buttons = [
            [
                InlineKeyboardButton(
                    "⭐️ BEST - 📹 MKV", callback_data=f"ytdl_download_{yt_id}_mkv_v"
                ),
                InlineKeyboardButton(
                    "⭐️ BEST - 📹 WebM/MP4",
                    callback_data=f"ytdl_download_{yt_id}_mp4_v",
                ),
            ]
        ]
        best_audio_btn = [
            [
                InlineKeyboardButton(
                    "⭐️ BEST - 🎵 320Kbps - MP3", callback_data=f"ytdl_download_{yt_id}_mp3_a"
                )
            ]
        ]
        try:
            vid_data = youtube_dl.YoutubeDL({"no-playlist": True}).extract_info(
                f"{self.base_yt_url}{yt_id}", download=False
            )
        except ExtractorError:
            vid_data = None
            buttons += best_audio_btn
        else:
            humanbytes = util.misc.human_readable_bytes
            # ------------------------------------------------ #
            qual_dict = defaultdict(lambda: defaultdict(int))
            qual_list = ("144p", "240p", "360p", "480p", "720p", "1080p", "1440p")
            audio_dict : Dict[int, str] = {}
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
                            bitrrate
                        ] = f"🎵 {bitrrate}Kbps ({humanbytes(fr_size) or 'N/A'})"
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
                        )
                    )
            buttons += util.sublists(video_btns, width=2)
            buttons += best_audio_btn
            buttons += util.sublists(
                list(map(lambda x: InlineKeyboardButton(audio_dict[x], callback_data=f"ytdl_download_{yt_id}_{x}_a", sorted(audio_dict.keys())))), 
                width=2,
            )
        if body:
            vid_body = f"<b>[{vid_data.get('title')}]({vid_data.get('webpage_url')})</b>" if vid_data else None
            return vid_body, InlineKeyboardMarkup(buttons)
        return InlineKeyboardMarkup(buttons)
        