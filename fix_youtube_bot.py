import sys
import subprocess
from pathlib import Path

# 1. Create shared yt-dlp auth helper
yt_auth_code = '''import sys
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
'''
Path("yt_auth.py").write_text(yt_auth_code, encoding="utf-8")
print("[OK] Created yt_auth.py")

# 2. Patch audio_ai.py and video_studio.py automatically
for fname in ("audio_ai.py", "video_studio.py"):
    p = Path(fname)
    if not p.exists():
        print(f"[WARN] {fname} not found")
        continue
    text = p.read_text(encoding="utf-8")
    if "from yt_auth import ytdlp_base_cmd" not in text:
        text = "from yt_auth import ytdlp_base_cmd\n" + text
    old_snip = 'sys.executable, "-m", "yt_dlp",'
    if old_snip in text:
        text = text.replace(old_snip, "*ytdlp_base_cmd(),")
        p.write_text(text, encoding="utf-8")
        print(f"[OK] Patched {fname} to auto-use cookies.txt")
    else:
        print(f"[OK] {fname} already patched")

# 3. Verify cookies.txt on the exact YouTube video
cookie_file = Path("cookies.txt") if Path("cookies.txt").exists() else Path("assets/cookies.txt")
if not cookie_file.exists():
    print("\n[ACTION NEEDED] Save your exported cookies.txt inside ClipPulse/ and re-run this script.")
else:
    print(f"\n[OK] Found {cookie_file.name} ({cookie_file.stat().st_size} bytes). Testing YouTube...")
    from yt_auth import ytdlp_base_cmd
    res = subprocess.run(
        [
            *ytdlp_base_cmd(),
            "--skip-download",
            "--no-playlist",
            "--print", "%(title)s (%(duration)ss)",
            "https://youtu.be/OEuiB_7iPl4",
        ],
        capture_output=True,
        text=True,
    )
    if res.returncode == 0:
        print(f"[SUCCESS] YouTube unlocked! -> {res.stdout.strip()}")
    else:
        print(f"[ERROR] YouTube test output:\n{res.stderr.strip()}")