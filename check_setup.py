import os
import sys
import shutil
import subprocess
from pathlib import Path
from dotenv import load_dotenv

print("=" * 60)
print("       VeloCut Studio / ClipPulse — Environment Health Check")
print("=" * 60)

# 1. Check .env & Groq API Key
load_dotenv()
api_key = os.getenv("GROQ_API_KEY", "").strip()
if api_key.startswith("gsk_"):
    print(f"[OK] GROQ_API_KEY loaded ({api_key[:8]}...)")
else:
    print("[FAIL] GROQ_API_KEY missing or invalid in .env (should start with gsk_)")

# 2. Check FFmpeg + NVIDIA NVENC Hardware Acceleration
ffmpeg_path = shutil.which("ffmpeg")
ffprobe_path = shutil.which("ffprobe")
if ffmpeg_path and ffprobe_path:
    print(f"[OK] FFmpeg found: {ffmpeg_path}")
    enc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-encoders"],
        capture_output=True, text=True
    ).stdout
    if "h264_nvenc" in enc:
        print("[OK] NVIDIA GPU encoder (h264_nvenc) available — ULTRA-FAST rendering enabled!")
    else:
        print("[INFO] Using CPU encoder (libx264 ultrafast) — clean fast rendering")
else:
    print("[FAIL] FFmpeg not found. Restart VS Code or run: winget install -e --id Gyan.FFmpeg")

# 3. Check Python libraries
packages = [
    ("streamlit", "streamlit"),
    ("groq", "groq"),
    ("yt_dlp", "yt-dlp"),
    ("cv2", "opencv-python"),
    ("mediapipe", "mediapipe"),
    ("numpy", "numpy"),
    ("scipy", "scipy"),
    ("plotly", "plotly"),
    ("PIL", "pillow"),
    ("dotenv", "python-dotenv"),
    ("deno", "deno"),
]
for mod, name in packages:
    try:
        m = __import__(mod)
        ver = getattr(m, "__version__", "installed")
        print(f"[OK] {name} ({ver})")
    except Exception as e:
        print(f"[FAIL] {name} missing: {e}")

# 4. Check MediaPipe API mode
try:
    import mediapipe as mp
    has_solutions = hasattr(mp, "solutions")
    has_tasks = hasattr(mp, "tasks")
    print(f"[INFO] MediaPipe API -> tasks={has_tasks}, solutions={has_solutions}")
except Exception:
    pass

# 5. Check assets folder
assets = Path("assets")
fonts = list(assets.glob("*.ttf")) + list((assets / "fonts").glob("*.ttf"))
videos = list(assets.glob("*.mp4"))
emojis_3d = list((assets / "emojis_3d").glob("*.png"))
tflite = list(assets.glob("*.tflite"))
print(f"[{'OK' if fonts else 'WARN'}] Fonts in assets/: {[f.name for f in fonts]}")
print(f"[{'OK' if videos else 'WARN'}] Sample videos in assets/: {[v.name for v in videos]}")
print(f"[{'OK' if emojis_3d else 'WARN'}] 3D emojis in assets/emojis_3d/: {len(emojis_3d)} icons")
print(f"[{'OK' if tflite else 'WARN'}] BlazeFace model in assets/: {[m.name for m in tflite]}")

# 6. Live Groq API Ping
if api_key.startswith("gsk_"):
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        res = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[{"role": "user", "content": "Reply with only the word READY"}],
            max_tokens=64,
            reasoning_effort="low",
        )
        ans = (res.choices[0].message.content or "").strip()
        print(f"[OK] Live Groq API test passed -> {ans}")
    except Exception as e:
        print(f"[FAIL] Groq API test error: {e}")

# 7. Live YouTube Unlock Test
try:
    from yt_auth import test_youtube_access, resolve_cookies_path
    c_path = resolve_cookies_path()
    c_status = f"with cookies ({c_path.name})" if c_path.exists() and c_path.stat().st_size > 100 else "direct mode"
    print(f"[INFO] Testing YouTube connectivity ({c_status})...")
    ok, detail = test_youtube_access()
    if ok:
        print(f"[OK] YouTube unlocked -> {detail}")
    else:
        print(f"[WARN] YouTube check failed: {detail}")
except Exception as e:
    print(f"[WARN] YouTube check error: {e}")

print("=" * 60)
