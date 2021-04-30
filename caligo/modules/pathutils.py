#  Module: PathLib
#  Ported by: code-rgb <https://github.com/code-rgb>
#          TG: [ @DeletedUser420 ]
#
#  Copyright (C) 2021- Kraken

import os
from pathlib import Path
from typing import ClassVar

from .. import command, module, util


class PathLib(module.Module):
    name: ClassVar[str] = "Pathlib"

    @command.desc("list files and folders in the directory")
    @command.alias("ls")
    async def cmd_listdir(self, ctx: command.Context):
        if not os.path.exists(inppath := (ctx.input or ".")):
            return "path not exists!"
        path_ = Path(inppath)
        out = f"<b>PATH</b> : <code>{inppath}</code>\n\n"
        humanbytes = util.misc.human_readable_bytes
        if path_.is_dir():
            folders = ""
            files = ""
            for p_s in sorted(path_.iterdir()):
                if p_s.is_file():
                    if str(p_s).endswith((".mp3", ".flac", ".wav", ".m4a")):
                        files += "🎵"
                    elif str(p_s).endswith((".mkv", ".mp4", ".webm", ".avi", ".mov", ".flv")):
                        files += "📹"
                    elif str(p_s).endswith((".zip", ".tar", ".tar.gz", ".rar")):
                        files += "🗜"
                    elif str(p_s).endswith(
                        (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".ico", ".webp")):
                        files += "🖼"
                    else:
                        files += "📄"
                    size = os.stat(str(p_s)).st_size
                    files += f" <code>{p_s.name}</code> <i>({humanbytes(size)})</i>\n"
                else:
                    folders += f"📁 <code>{p_s.name}</code>\n"
            out += (folders + files) or "<code>empty path!</code>"
        else:
            size = os.stat(str(path_)).st_size
            out += f"📄 <code>{path_.name}</code> <i>({humanbytes(size)})</i>\n"
        await ctx.respond(out, parse_mode="html")
