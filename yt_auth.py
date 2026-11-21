import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import List, Tuple


def _find_js_runtime_args() -> List[str]:
    try:
        import deno
        deno_bin = deno.find_deno_bin()
        if deno_bin and Path(deno_bin).exists():
            return ["--js-runtimes", f"deno:{deno_bin}"]
    except Exception:
        pass
    deno_path = shutil.which("deno")
    if deno_path:
        return ["--js-runtimes", f"deno:{deno_path}"]
    node_path = shutil.which("node") or shutil.which("nodejs")
    if node_path:
        return ["--js-runtimes", f"node:{node_path}"]
    return []


def resolve_cookies_path() -> Path:
    """Finds or restores cookies.txt from local files, environment, or Streamlit Secrets."""
    for cand in (Path("cookies.txt"), Path("assets/cookies.txt")):
        if cand.exists() and cand.stat().st_size > 100:
            return cand

    # Check env / Streamlit Cloud secrets
    raw_cookies = os.environ.get("YOUTUBE_COOKIES", "").strip()
    if not raw_cookies:
        try:
            import streamlit as st
            if "YOUTUBE_COOKIES" in st.secrets:
                raw_cookies = str(st.secrets["YOUTUBE_COOKIES"]).strip()
        except Exception:
            pass

    if raw_cookies and len(raw_cookies) > 100:
        try:
            target = Path("cookies.txt")
            target.write_text(raw_cookies, encoding="utf-8")
            return target
        except Exception:
            pass

    return Path("cookies.txt")


def ytdlp_base_cmd() -> List[str]:
    """Build base yt-dlp command with JS runtime and automatic cookie authentication."""
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--force-ipv4",
        "--sleep-requests", "0.4",
        *_find_js_runtime_args(),
    ]
    cand = resolve_cookies_path()
    if cand.exists() and cand.stat().st_size > 100:
        cmd += ["--cookies", str(cand.resolve())]
    return cmd


def test_youtube_access(url: str = "https://youtu.be/OEuiB_7iPl4") -> Tuple[bool, str]:
    """Verifies whether YouTube metadata and videos are unlocked."""
    try:
        cmd = [
            *ytdlp_base_cmd(),
            "--skip-download",
            "--no-playlist",
            "--print", "%(title)s",
            url,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        if res.returncode == 0 and res.stdout.strip():
            return True, res.stdout.strip().splitlines()[0]
        err = (res.stderr or res.stdout).strip()
        return False, err or "Unknown YouTube error"
    except Exception as e:
        return False, str(e)
