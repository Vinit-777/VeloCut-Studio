import os
import sys
import shutil
import subprocess
from pathlib import Path
from dotenv import load_dotenv

print("=" * 55)
print("       ClipPulse — Environment Health Check")
print("=" * 55)

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
        print("[INFO] Using CPU encoder (libx264 ultrafast) — still fast (~6-10s per clip)")
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
]
for mod, name in packages:
    try:
        m = __import__(mod)
        ver = getattr(m, "__version__", "installed")
        print(f"[OK] {name} ({ver})")
    except Exception as e:
        print(f"[FAIL] {name} missing: {e}")

# 4. Check MediaPipe API mode (newer 0.10.31+ uses Tasks API instead of mp.solutions)
try:
    import mediapipe as mp
    has_solutions = hasattr(mp, "solutions")
    has_tasks = hasattr(mp, "tasks")
    print(f"[INFO] MediaPipe API -> tasks={has_tasks}, solutions={has_solutions}")
except Exception:
    pass

# 5. Check assets folder
assets = Path("assets")
fonts = list(assets.glob("*.ttf")) if assets.exists() else []
videos = list(assets.glob("*.mp4")) if assets.exists() else []
print(f"[{'OK' if fonts else 'WARN'}] Fonts in assets/: {[f.name for f in fonts]}")
print(f"[{'OK' if videos else 'WARN'}] Sample videos in assets/: {[v.name for v in videos]}")

# 6. Live Groq API Ping
if api_key.startswith("gsk_"):
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        res = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[{"role": "user", "content": "Reply with only the word READY"}],
            max_tokens=16,
            reasoning_effort="low",
        )
        print(f"[OK] Live Groq API test passed -> {res.choices[0].message.content.strip()}")
    except Exception as e:
        print(f"[FAIL] Groq API test error: {e}")

print("=" * 55)