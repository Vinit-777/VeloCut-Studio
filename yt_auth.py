import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import List, Tuple, Optional


def sanitize_netscape_cookies(raw: str) -> str:
    """Cleans, normalizes, and repairs Netscape HTTP Cookie File text.
    Strips leading/trailing indentation, removes wrapping quotes,
    ensures proper '# Netscape HTTP Cookie File' header, converts space-delimited
    columns to tabs if needed, and filters invalid lines.
    """
    if not raw or not raw.strip():
        return ""

    text = raw.strip()
    if (text.startswith('"""') and text.endswith('"""')) or (text.startswith("'''") and text.endswith("'''")):
        text = text[3:-3].strip()
    elif (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        text = text[1:-1].strip()

    lines = [line.strip() for line in text.splitlines()]
    while lines and not lines[0]:
        lines.pop(0)

    if not lines:
        return ""

    out_lines = ["# Netscape HTTP Cookie File", "# Sanitized for yt-dlp"]
    has_cookie_rows = False

    for line in lines:
        if not line:
            continue
        if line.startswith("#"):
            if "netscape" in line.lower() or "http cookie file" in line.lower():
                continue
            out_lines.append(line)
            continue

        parts = [p.strip() for p in (line.split("\t") if "\t" in line else line.split()) if p != ""]
        if len(parts) >= 7:
            domain = parts[0]
            flag = parts[1].upper() if parts[1].upper() in ("TRUE", "FALSE") else parts[1]
            path = parts[2]
            secure = parts[3].upper() if parts[3].upper() in ("TRUE", "FALSE") else parts[3]
            expiry = parts[4]
            name = parts[5]
            value = "\t".join(parts[6:]) if len(parts) > 7 else parts[6]
            out_lines.append(f"{domain}\t{flag}\t{path}\t{secure}\t{expiry}\t{name}\t{value}")
            has_cookie_rows = True
        elif len(parts) >= 6:
            out_lines.append("\t".join(parts) + "\t")
            has_cookie_rows = True

    if not has_cookie_rows:
        return ""

    return "\n".join(out_lines) + "\n"


def is_valid_cookie_file(path: Path) -> bool:
    """Verifies that a cookie file has the correct Netscape header and at least one cookie row."""
    try:
        if not path.exists() or path.stat().st_size < 30:
            return False
        content = path.read_text(encoding="utf-8", errors="ignore")
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        if not lines:
            return False
        if not (lines[0].startswith("# Netscape HTTP Cookie File") or lines[0].startswith("# HTTP Cookie File")):
            return False
        return any(not l.startswith("#") and "\t" in l for l in lines)
    except Exception:
        return False


def save_and_sanitize_cookies(raw_text: str, target: Path = Path("cookies.txt")) -> Optional[Path]:
    """Cleans raw cookie text and saves to target. Returns target if valid, else None."""
    cleaned = sanitize_netscape_cookies(raw_text)
    if not cleaned:
        return None
    try:
        target.write_text(cleaned, encoding="utf-8")
        if is_valid_cookie_file(target):
            return target
    except Exception:
        pass
    return None


def resolve_cookies_path() -> Optional[Path]:
    """Finds, sanitizes, and returns a verified valid cookies.txt path, or None."""
    # 1. Check existing local cookie files and sanitize in-place if needed
    for cand in (Path("cookies.txt"), Path("assets/cookies.txt")):
        if cand.exists() and cand.stat().st_size > 30:
            if not is_valid_cookie_file(cand):
                try:
                    raw = cand.read_text(encoding="utf-8", errors="ignore")
                    save_and_sanitize_cookies(raw, cand)
                except Exception:
                    pass
            if is_valid_cookie_file(cand):
                return cand

    # 2. Check Streamlit Cloud Secrets / Environment Variable
    raw_cookies = os.environ.get("YOUTUBE_COOKIES", "").strip()
    if not raw_cookies:
        try:
            import streamlit as st
            if "YOUTUBE_COOKIES" in st.secrets:
                raw_cookies = str(st.secrets["YOUTUBE_COOKIES"]).strip()
        except Exception:
            pass

    if raw_cookies and len(raw_cookies) > 30:
        saved = save_and_sanitize_cookies(raw_cookies, Path("cookies.txt"))
        if saved and is_valid_cookie_file(saved):
            return saved

    return None


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


def ytdlp_base_cmd() -> List[str]:
    """Build base yt-dlp command with JS runtime and ONLY valid verified cookies."""
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--force-ipv4",
        "--sleep-requests", "0.4",
        *_find_js_runtime_args(),
    ]
    cand = resolve_cookies_path()
    if cand and is_valid_cookie_file(cand):
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
