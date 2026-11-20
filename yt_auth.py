import sys
from pathlib import Path
from typing import List


def ytdlp_base_cmd() -> List[str]:
    """Build base yt-dlp command with automatic cookies.txt authentication."""
    cmd = [sys.executable, "-m", "yt_dlp", "--sleep-requests", "0.5"]
    for cand in (Path("cookies.txt"), Path("assets/cookies.txt")):
        if cand.exists() and cand.stat().st_size > 100:
            cmd += ["--cookies", str(cand.resolve())]
            break
    return cmd
