import os
import sys
import re
import glob
import json
import time
import uuid
import copy
import shutil
import hashlib
import threading
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

import numpy as np
from dotenv import load_dotenv
import streamlit as st
import plotly.graph_objects as go

# Load local .env first, then safely read Streamlit Cloud Secrets without crashing locally
load_dotenv()
from yt_auth import (
    resolve_cookies_path,
    save_and_sanitize_cookies,
    is_valid_cookie_file,
    test_youtube_access,
)

try:
    if "GROQ_API_KEY" in st.secrets:
        os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
    if "YOUTUBE_COOKIES" in st.secrets:
        save_and_sanitize_cookies(st.secrets["YOUTUBE_COOKIES"], Path("cookies.txt"))
except Exception:
    pass

for _dir in ("temp", "outputs", "assets", "assets/fonts", "assets/emojis", "assets/emojis_3d"):
    Path(_dir).mkdir(parents=True, exist_ok=True)

from audio_ai import analyze_video
from video_studio import (
    render_viral_reel,
    check_nvenc_available,
    STYLE_PRESETS,
)

# =============================================================================
# PAGE CONFIG & OPUSCLIP 4.0 ULTRA-DARK GLASSMORPHIC DESIGN SYSTEM
# =============================================================================
st.set_page_config(
    page_title="VeloCut Opus — #1 AI Video Clipping & Editing Studio",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@500;600;700;800;900&display=swap');

    /* Global Typography & Palette */
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        color: #F1F5F9;
    }

    #MainMenu, footer, [data-testid="stDeployButton"], .stDeployButton {
        visibility: hidden !important;
        display: none !important;
    }
    header[data-testid="stHeader"] {
        background: transparent !important;
    }

    /* Main Container & Top Ambient Glow */
    .block-container {
        padding-top: 0.8rem !important;
        padding-bottom: 3.5rem !important;
        max-width: 1180px !important;
    }

    /* Streamlit Sidebar Opus Styling */
    section[data-testid="stSidebar"] {
        background: #080A10 !important;
        border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
    }
    section[data-testid="stSidebar"] .block-container {
        padding-top: 1.2rem !important;
    }
    .side-brand {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 0.74rem;
        font-weight: 800;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        color: #818CF8;
        display: flex;
        align-items: center;
        gap: 0.4rem;
        margin-bottom: 0.9rem;
    }
    .side-section {
        font-size: 0.74rem;
        font-weight: 700;
        letter-spacing: 0.09em;
        text-transform: uppercase;
        color: #94A3B8;
        margin-top: 1.1rem;
        margin-bottom: 0.45rem;
    }

    /* Floating Announcement Banner */
    .opus-top-banner {
        background: linear-gradient(90deg, rgba(99, 102, 241, 0.15) 0%, rgba(168, 85, 247, 0.22) 50%, rgba(6, 182, 212, 0.15) 100%);
        border: 1px solid rgba(168, 85, 247, 0.35);
        border-radius: 999px;
        padding: 0.45rem 1.1rem;
        font-size: 0.82rem;
        font-weight: 500;
        color: #E2E8F0;
        text-align: center;
        margin-bottom: 1.1rem;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0.5rem;
        backdrop-filter: blur(12px);
    }
    .opus-top-banner strong {
        color: #FFFFFF;
        font-weight: 700;
    }
    .opus-banner-pill {
        background: #6366F1;
        color: #FFFFFF;
        font-size: 0.68rem;
        font-weight: 700;
        text-transform: uppercase;
        padding: 0.15rem 0.5rem;
        border-radius: 999px;
        letter-spacing: 0.04em;
    }

    /* Opus Navbar */
    .opus-navbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: rgba(13, 16, 26, 0.85);
        border: 1px solid rgba(255, 255, 255, 0.09);
        border-radius: 16px;
        padding: 0.85rem 1.4rem;
        margin-bottom: 1.6rem;
        backdrop-filter: blur(20px);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
    }
    .opus-brand {
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }
    .opus-wordmark {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 1.35rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        color: #FFFFFF;
        display: flex;
        align-items: center;
        gap: 0.35rem;
    }
    .opus-wordmark span {
        background: linear-gradient(135deg, #818CF8 0%, #C084FC 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .opus-version-badge {
        font-size: 0.65rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.25) 0%, rgba(168, 85, 247, 0.25) 100%);
        border: 1px solid rgba(168, 85, 247, 0.45);
        color: #DDD6FE;
        padding: 0.18rem 0.55rem;
        border-radius: 999px;
    }
    .opus-nav-status {
        display: flex;
        align-items: center;
        gap: 0.6rem;
        font-size: 0.82rem;
        color: #94A3B8;
    }
    .opus-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #10B981;
        box-shadow: 0 0 10px #10B981;
    }

    /* Hero Headline */
    .opus-hero {
        text-align: center;
        margin: 1.2rem auto 2.0rem auto;
        max-width: 860px;
    }
    .opus-hero-chip {
        display: inline-flex;
        align-items: center;
        gap: 0.45rem;
        background: rgba(99, 102, 241, 0.12);
        border: 1px solid rgba(99, 102, 241, 0.3);
        border-radius: 999px;
        padding: 0.32rem 0.9rem;
        font-size: 0.76rem;
        font-weight: 700;
        color: #A5B4FC;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        margin-bottom: 0.9rem;
    }
    .opus-hero h1 {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 2.5rem;
        font-weight: 800;
        letter-spacing: -0.035em;
        color: #FFFFFF;
        line-height: 1.18;
        margin: 0 0 0.75rem 0;
    }
    .opus-gradient-text {
        background: linear-gradient(135deg, #FFFFFF 20%, #A5B4FC 60%, #C084FC 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .opus-hero p {
        font-size: 1.05rem;
        color: #94A3B8;
        line-height: 1.55;
        max-width: 720px;
        margin: 0 auto;
    }

    /* High-Conversion Input Box */
    .opus-input-card {
        background: linear-gradient(180deg, rgba(19, 23, 36, 0.8) 0%, rgba(13, 16, 26, 0.95) 100%);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 20px;
        padding: 1.4rem;
        box-shadow: 0 16px 48px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(99, 102, 241, 0.15);
        margin-bottom: 1.5rem;
        backdrop-filter: blur(24px);
    }

    /* Action Buttons */
    div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%) !important;
        color: #FFFFFF !important;
        border: none !important;
        font-weight: 700 !important;
        font-size: 0.95rem !important;
        letter-spacing: -0.01em !important;
        border-radius: 12px !important;
        padding: 0.65rem 1.4rem !important;
        box-shadow: 0 6px 24px rgba(99, 102, 241, 0.45) !important;
        transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
    }
    div.stButton > button[kind="primary"]:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 10px 32px rgba(99, 102, 241, 0.65) !important;
        filter: brightness(1.08) !important;
    }
    div.stButton > button[kind="secondary"],
    div.stDownloadButton > button {
        background: rgba(22, 27, 43, 0.85) !important;
        color: #F8FAFC !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        font-weight: 600 !important;
        border-radius: 10px !important;
        transition: all 0.18s ease !important;
    }
    div.stButton > button[kind="secondary"]:hover,
    div.stDownloadButton > button:hover {
        background: rgba(33, 41, 66, 0.95) !important;
        border-color: rgba(168, 85, 247, 0.5) !important;
        color: #FFFFFF !important;
    }

    /* Tabs Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 1.8rem;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        margin-bottom: 1.2rem;
    }
    .stTabs [data-baseweb="tab"] {
        color: #94A3B8 !important;
        font-weight: 600 !important;
        font-size: 0.92rem !important;
        padding: 0.6rem 0.2rem !important;
    }
    .stTabs [aria-selected="true"] {
        color: #FFFFFF !important;
        font-weight: 700 !important;
    }
    .stTabs [data-baseweb="tab-highlight"] {
        background: linear-gradient(90deg, #6366F1, #A855F7) !important;
        height: 2.5px !important;
        border-radius: 2px !important;
    }

    /* Inputs */
    .stTextInput input, .stSelectbox [data-baseweb="select"] > div {
        background-color: #0A0D15 !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 11px !important;
        color: #F8FAFC !important;
        font-size: 0.92rem !important;
    }
    .stTextInput input:focus {
        border-color: #818CF8 !important;
        box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.25) !important;
    }

    /* ETA Bar */
    .opus-eta {
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 0.5rem;
        background: rgba(16, 20, 32, 0.7);
        border: 1px solid rgba(99, 102, 241, 0.25);
        border-left: 3px solid #6366F1;
        border-radius: 12px;
        padding: 0.7rem 1.1rem;
        margin: 0.9rem 0 1.2rem 0;
        font-size: 0.86rem;
        color: #CBD5E1;
    }
    .opus-eta strong {
        color: #FFFFFF;
        font-weight: 700;
    }

    /* Feature Mega Grid (Opus 4.0 Style) */
    .opus-feature-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 1.1rem;
        margin: 1.5rem 0 2.2rem 0;
    }
    .opus-feat-card {
        background: linear-gradient(180deg, rgba(20, 24, 38, 0.75) 0%, rgba(13, 16, 26, 0.85) 100%);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 1.2rem;
        transition: all 0.22s cubic-bezier(0.16, 1, 0.3, 1);
        backdrop-filter: blur(16px);
    }
    .opus-feat-card:hover {
        transform: translateY(-3px);
        border-color: rgba(168, 85, 247, 0.4);
        box-shadow: 0 12px 30px rgba(99, 102, 241, 0.15);
    }
    .opus-feat-icon {
        font-size: 1.6rem;
        margin-bottom: 0.65rem;
        display: inline-block;
    }
    .opus-feat-title {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 0.98rem;
        font-weight: 700;
        color: #FFFFFF;
        margin-bottom: 0.3rem;
        display: flex;
        align-items: center;
        gap: 0.45rem;
    }
    .opus-feat-desc {
        font-size: 0.84rem;
        color: #94A3B8;
        line-height: 1.45;
    }
    .opus-badge-new {
        font-size: 0.62rem;
        font-weight: 800;
        background: #10B981;
        color: #FFFFFF;
        padding: 0.1rem 0.45rem;
        border-radius: 999px;
        text-transform: uppercase;
    }
    .opus-badge-pro {
        font-size: 0.62rem;
        font-weight: 800;
        background: linear-gradient(135deg, #8B5CF6, #EC4899);
        color: #FFFFFF;
        padding: 0.1rem 0.45rem;
        border-radius: 999px;
        text-transform: uppercase;
    }

    /* Virality Score Badge */
    .opus-virality-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.45rem;
        background: linear-gradient(135deg, #10B981 0%, #059669 100%);
        color: #FFFFFF;
        padding: 0.32rem 0.85rem;
        border-radius: 999px;
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 0.86rem;
        font-weight: 800;
        box-shadow: 0 4px 14px rgba(16, 185, 129, 0.35);
    }
    .opus-meta-pill {
        display: inline-block;
        background: rgba(255, 255, 255, 0.08);
        border: 1px solid rgba(255, 255, 255, 0.1);
        color: #CBD5E1;
        padding: 0.22rem 0.65rem;
        border-radius: 8px;
        font-size: 0.76rem;
        font-weight: 600;
        margin-right: 0.4rem;
    }

    /* Template Cards */
    .opus-tpl-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
        gap: 1.1rem;
        margin: 1.2rem 0 2rem 0;
    }
    .opus-tpl-card {
        background: #0F131E;
        border: 1px solid rgba(255, 255, 255, 0.09);
        border-radius: 16px;
        padding: 1.25rem;
        text-align: center;
        transition: all 0.2s ease;
    }
    .opus-tpl-card:hover {
        border-color: #818CF8;
        transform: translateY(-3px);
    }
    .opus-tpl-preview {
        height: 85px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 10px;
        margin-bottom: 0.9rem;
        font-weight: 800;
        letter-spacing: -0.01em;
    }

    /* Result Container */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: linear-gradient(180deg, rgba(17, 21, 33, 0.85) 0%, rgba(11, 14, 23, 0.95) 100%) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 18px !important;
        box-shadow: 0 12px 36px rgba(0, 0, 0, 0.35) !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

Path("temp").mkdir(exist_ok=True)
Path("outputs").mkdir(exist_ok=True)
Path("assets").mkdir(exist_ok=True)


# =============================================================================
# SILENT BACKGROUND PRE-RENDERER & CACHE
# =============================================================================
class BackgroundPreRenderer:
    def __init__(self):
        self._lock = threading.Lock()
        self._jobs: Dict[str, Dict[str, Any]] = {}

    def make_key(self, run_id: str, source: str, clip: Dict[str, Any], cfg: Dict[str, Any]) -> str:
        payload = json.dumps(
            {
                "run_id": run_id,
                "src": source,
                "rank": clip["rank"],
                "start": clip["start"],
                "end": clip["end"],
                "title": clip["hook_title"],
                "cfg": {k: v for k, v in cfg.items() if k not in ("http_headers", "direct_mp4")},
            },
            sort_keys=True,
        )
        return hashlib.md5(payload.encode("utf-8")).hexdigest()[:16]

    def get_job(self, key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(key)
            return dict(job) if job else None

    def start_background(self, key: str, source: str, clip: Dict[str, Any], cfg: Dict[str, Any]) -> None:
        with self._lock:
            existing = self._jobs.get(key)
            if existing and existing["status"] in ("running", "done"):
                return
            self._jobs[key] = {"status": "running", "result": None, "error": None}

        clip_copy = copy.deepcopy(clip)
        cfg_copy = copy.deepcopy(cfg)

        def _worker():
            out_file = f"outputs/velocut_r{clip_copy['rank']}_{int(time.time() * 1000)}.mp4"
            try:
                info = render_viral_reel(
                    source=source,
                    clip_data=clip_copy,
                    output_path=out_file,
                    framing_mode=cfg_copy["framing_mode"],
                    video_type=cfg_copy["video_type"],
                    caption_lang=cfg_copy["caption_lang"],
                    style_name=cfg_copy["style_name"],
                    transition_style=cfg_copy["transition_style"],
                    fast_stream_mode=cfg_copy["fast_heatmap_mode"],
                    show_captions=cfg_copy["show_captions"],
                    show_emojis=cfg_copy["show_emojis"],
                    show_hook_banner=cfg_copy["show_hook_banner"],
                    show_progress_bar=cfg_copy["show_progress_bar"],
                    smooth_outro=cfg_copy["smooth_outro"],
                    dynamic_zoom=cfg_copy["dynamic_zoom"],
                    color_punch=cfg_copy["color_punch"],
                    audio_polish=cfg_copy["audio_polish"],
                    outro_text=cfg_copy["outro_text"],
                    bg_music_path=cfg_copy["bg_music_path"],
                    direct_mp4=cfg_copy.get("direct_mp4"),
                    http_headers=cfg_copy.get("http_headers"),
                    video_title=cfg_copy.get("video_title", ""),
                )
                with self._lock:
                    self._jobs[key]["status"] = "done"
                    self._jobs[key]["result"] = info
                    self._jobs[key]["words"] = clip_copy.get("words", [])
                    self._jobs[key]["updated_meta"] = info.get("updated_meta", {})
            except Exception as e:
                with self._lock:
                    self._jobs[key]["status"] = "error"
                    self._jobs[key]["error"] = str(e)

        threading.Thread(target=_worker, daemon=True).start()

    def wait_for_job(self, key: str, timeout: float = 120.0) -> Optional[Dict[str, Any]]:
        deadline = time.time() + timeout
        while time.time() < deadline:
            job = self.get_job(key)
            if not job or job["status"] in ("done", "error"):
                return job
            time.sleep(0.35)
        return self.get_job(key)


@st.cache_resource
def get_prerender_pool() -> BackgroundPreRenderer:
    return BackgroundPreRenderer()


pool = get_prerender_pool()

if "analysis" not in st.session_state:
    st.session_state.analysis = None
if "active_source" not in st.session_state:
    st.session_state.active_source = None
if "rendered_reels" not in st.session_state:
    st.session_state.rendered_reels = {}
if "shown_count" not in st.session_state:
    st.session_state.shown_count = 1
if "run_id" not in st.session_state:
    st.session_state.run_id = "init"


def _clear_previous_clips():
    st.session_state.analysis = None
    st.session_state.active_source = None
    st.session_state.rendered_reels = {}
    st.session_state.shown_count = 1
    st.session_state.run_id = f"run_{int(time.time() * 1000)}"


# =============================================================================
# HELPERS & SUBTITLES (.SRT) EXPORTER
# =============================================================================
def _fmt_ts(sec: float) -> str:
    sec = max(0, int(round(sec)))
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _words_to_srt(words: List[Dict[str, Any]], words_per_line: int = 4) -> str:
    """Exports synchronized transcript words into standard SubRip (.SRT) subtitle file format."""
    def fmt_t(s: float) -> str:
        s = max(0.0, float(s))
        hrs = int(s // 3600)
        mins = int((s % 3600) // 60)
        secs = int(s % 60)
        ms = int(round((s - int(s)) * 1000))
        return f"{hrs:02d}:{mins:02d}:{secs:02d},{ms:03d}"

    entries = []
    chunk = []
    idx = 1
    for w in words:
        chunk.append(w)
        txt = str(w.get("word", "")).strip()
        has_break = bool(txt and txt[-1] in ".?!।")
        if len(chunk) >= words_per_line or has_break:
            t_s = fmt_t(float(chunk[0]["start"]))
            t_e = fmt_t(float(chunk[-1]["end"]))
            line_txt = " ".join(str(c["word"]).strip() for c in chunk)
            entries.append(f"{idx}\n{t_s} --> {t_e}\n{line_txt}\n")
            idx += 1
            chunk = []
    if chunk:
        t_s = fmt_t(float(chunk[0]["start"]))
        t_e = fmt_t(float(chunk[-1]["end"]))
        line_txt = " ".join(str(c["word"]).strip() for c in chunk)
        entries.append(f"{idx}\n{t_s} --> {t_e}\n{line_txt}\n")
    return "\n".join(entries)


def _probe_duration_seconds(path: str) -> float:
    try:
        out = subprocess.check_output(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=15,
        ).strip()
        return max(0.0, float(out))
    except Exception:
        return 0.0


def _fast_audio_energy_curve(source: str, max_seconds: int = 360) -> Tuple[List[float], float]:
    is_url = str(source).startswith(("http://", "https://"))
    total_dur = 0.0 if is_url else _probe_duration_seconds(source)
    curve: List[float] = []

    if not is_url and Path(source).exists():
        try:
            sr = 4000
            proc = subprocess.run(
                [
                    "ffmpeg", "-v", "error",
                    "-i", source,
                    "-t", str(max_seconds),
                    "-vn", "-ac", "1", "-ar", str(sr),
                    "-f", "s16le", "-",
                ],
                capture_output=True,
                timeout=25,
            )
            if proc.returncode == 0 and len(proc.stdout) >= sr * 2:
                samples = np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32)
                n_sec = len(samples) // sr
                if n_sec > 0:
                    chunks = samples[: n_sec * sr].reshape(n_sec, sr)
                    rms = np.sqrt(np.mean(chunks ** 2, axis=1))
                    hi = float(np.percentile(rms, 98)) or 1.0
                    lo = float(np.percentile(rms, 5))
                    span = max(hi - lo, 1e-3)
                    norm = np.clip((rms - lo) / span, 0.0, 1.0)
                    curve = [round(float(18.0 + v * 80.0), 1) for v in norm]
                    if total_dur < 1.0:
                        total_dur = float(n_sec)
        except Exception:
            pass

    if total_dur < 2.0:
        total_dur = float(len(curve)) if curve else 45.0
    if not curve:
        curve = [65.0] * max(5, int(round(total_dur)))
    return curve, round(total_dur, 2)


def _ensure_fallback_clips(
    result: Dict[str, Any],
    source: str,
    min_dur: int,
    max_dur: int,
    num_clips: int = 3,
    skip_llm_title: bool = False,
) -> Dict[str, Any]:
    if result.get("clips"):
        return result

    audio_info = result.get("audio_info") or {}
    energy_curve = list(result.get("energy_curve") or [])

    total_dur = float(audio_info.get("duration") or 0.0)
    if total_dur < 2.0 and energy_curve:
        total_dur = float(len(energy_curve))
    if total_dur < 2.0 and not str(source).startswith(("http://", "https://")):
        total_dur = _probe_duration_seconds(source)
    if total_dur < 2.0:
        total_dur = float(min_dur)

    if not energy_curve:
        energy_curve = [65.0] * max(5, int(round(total_dur)))
        result["energy_curve"] = energy_curve

    clips: List[Dict[str, Any]] = []
    if total_dur <= min_dur + 2:
        clip_end = round(total_dur, 2)
        clips.append(
            {
                "rank": 1,
                "start": 0.0,
                "end": clip_end,
                "duration": clip_end,
                "virality_score": 92,
                "hook_score": 94,
                "coherence_score": 90,
                "audio_energy_score": 92,
                "hook_title": "TOP HIGHLIGHT MOMENT",
                "category": "🔥 Viral Peak",
                "opening_hook": "High-retention opening moment.",
                "ending_payoff": "Complete thought with clean sentence ending.",
                "reason": "Selected automatically using peak audio energy and audience engagement spikes.",
                "social_caption": "Wait till you see this! 🔥🤯 #viral #shorts #reels #trending",
                "words": [],
                "needs_word_sync": True,
                "needs_title_from_clip": not skip_llm_title,
            }
        )
    else:
        target_dur = int(min(max_dur, max(min_dur, round((min_dur + max_dur) / 2.0))))
        target_dur = min(target_dur, max(5, int(total_dur)))
        max_start = max(0, int(total_dur) - target_dur)

        n_energy = len(energy_curve)
        scored = []
        for s in range(0, max_start + 1):
            e_idx = min(n_energy, s + target_dur)
            s_idx = min(n_energy - 1, s)
            window = energy_curve[s_idx:e_idx] if e_idx > s_idx else [50.0]
            avg_e = sum(window) / max(1, len(window))
            scored.append((avg_e, s))

        scored.sort(key=lambda x: x[0], reverse=True)
        chosen: List[int] = []
        min_gap = max(5, int(target_dur * 0.85))
        for _, s in scored:
            if all(abs(s - prev) >= min_gap for prev in chosen):
                chosen.append(s)
                if len(chosen) >= num_clips:
                    break
        if not chosen:
            chosen = [0]

        for idx, s in enumerate(chosen, start=1):
            e = min(round(total_dur, 2), float(s + target_dur))
            clips.append(
                {
                    "rank": idx,
                    "start": float(s),
                    "end": e,
                    "duration": round(e - float(s), 2),
                    "virality_score": max(80, 96 - (idx - 1) * 3),
                    "hook_score": max(82, 98 - (idx - 1) * 3),
                    "coherence_score": 92,
                    "audio_energy_score": max(75, 94 - (idx - 1) * 4),
                    "hook_title": f"VIRAL HIGHLIGHT #{idx}",
                    "category": "🔥 Viral Moment",
                    "opening_hook": "Attention-grabbing opening hook.",
                    "ending_payoff": "Clean payoff finishing on spoken thought.",
                    "reason": "Selected automatically from the highest-energy engagement section of the video.",
                    "social_caption": "You won't believe what happened here 🔥🤯 #viral #shorts #reels #trending",
                    "words": [],
                    "needs_word_sync": True,
                    "needs_title_from_clip": not skip_llm_title,
                }
            )

    result["clips"] = clips
    return result


def _cache_path_for(source: str, video_type: str, clip_goal: str, fast_heatmap: bool, min_dur: int, max_dur: int) -> Path:
    key_str = f"opus_v4|{source}|{video_type}|{clip_goal}|{fast_heatmap}|{min_dur}|{max_dur}"
    digest = hashlib.md5(key_str.encode("utf-8")).hexdigest()[:12]
    return Path("temp") / f"analysis_cache_{digest}.json"


def _estimate_wait_range(
    framing_mode: str,
    transition_style: str,
    fast_heatmap_mode: bool,
    min_dur: int,
    max_dur: int,
    nvenc_ok: bool,
) -> Tuple[int, int]:
    avg_dur = (min_dur + max_dur) / 2.0
    eff = framing_mode
    base = 8 if fast_heatmap_mode else 12
    cv = 0 if eff in ("full_uncropped", "wide_cinematic", "blurred_fill") else int(round(avg_dur * 0.06))
    enc = max(4, int(round(avg_dur * (0.12 if nvenc_ok else 0.28))))
    mid = base + cv + enc
    return max(10, mid - 4), mid + 6


def _clean_progress_text(frac: float, raw_label: str) -> str:
    if frac < 0.22:
        return "Step 1/4: Fetching video stream & audio track..."
    if frac < 0.35:
        return "Step 2/4: Generating synchronized kinetic captions..."
    if frac < 0.45:
        return "Step 3/4: Framing layout & rendering 3D emojis..."
    if frac >= 0.99:
        return "Step 4/4: Finalizing Ultra-HD Short..."
    m = re.search(r"~(\d+s)", raw_label)
    if m:
        return f"Rendering short ({int(frac * 100)}%) — about {m.group(1)} remaining"
    return f"Rendering short ({int(frac * 100)}%)..."


def _build_timeline_chart(energy_curve, clips, shown_count: int):
    x_sec = list(range(len(energy_curve)))
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x_sec, y=energy_curve, mode="lines",
            line=dict(color="#818CF8", width=2.2),
            fill="tozeroy", fillcolor="rgba(129, 140, 248, 0.16)",
            hovertemplate="Time: %{x}s<br>Retention Score: %{y:.0f}/100<extra></extra>",
        )
    )
    for idx, c in enumerate(clips):
        is_shown = (idx < shown_count)
        fig.add_vrect(
            x0=c["start"], x1=c["end"],
            fillcolor="rgba(168, 85, 247, 0.22)" if is_shown else "rgba(148, 163, 184, 0.08)",
            line_width=1.6 if is_shown else 0.8,
            line_color="#A855F7" if is_shown else "#475569",
            line_dash="solid" if is_shown else "dot",
            annotation_text=f"Clip #{c['rank']}",
            annotation_position="top left",
            annotation_font=dict(color="#F8FAFC" if is_shown else "#94A3B8", size=11),
        )
    fig.update_layout(
        height=220, margin=dict(l=8, r=8, t=24, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#0A0E18",
        xaxis=dict(title="Timeline (Seconds)", gridcolor="#1E293B", color="#94A3B8"),
        yaxis=dict(title="Retention", range=[0, 110], gridcolor="#1E293B", color="#94A3B8"),
        showlegend=False,
    )
    return fig


def _render_clip_clean(source: str, clip: Dict[str, Any], cfg: Dict[str, Any]):
    rank = clip["rank"]
    out_file = f"outputs/velocut_r{rank}_{int(time.time() * 1000)}.mp4"

    pbar = st.progress(0.04, text="Preparing your short...")

    def pcb(frac: float, label: str):
        pbar.progress(frac, text=_clean_progress_text(frac, label))

    info = render_viral_reel(
        source=source,
        clip_data=clip,
        output_path=out_file,
        framing_mode=cfg["framing_mode"],
        video_type=cfg["video_type"],
        caption_lang=cfg["caption_lang"],
        style_name=cfg["style_name"],
        transition_style=cfg["transition_style"],
        fast_stream_mode=cfg["fast_heatmap_mode"],
        show_captions=cfg["show_captions"],
        show_emojis=cfg["show_emojis"],
        show_hook_banner=cfg["show_hook_banner"],
        show_progress_bar=cfg["show_progress_bar"],
        smooth_outro=cfg["smooth_outro"],
        dynamic_zoom=cfg["dynamic_zoom"],
        color_punch=cfg["color_punch"],
        audio_polish=cfg["audio_polish"],
        outro_text=cfg["outro_text"],
        bg_music_path=cfg["bg_music_path"],
        direct_mp4=cfg.get("direct_mp4"),
        http_headers=cfg.get("http_headers"),
        video_title=cfg.get("video_title", ""),
        progress_cb=pcb,
    )
    pbar.empty()
    upd = info.get("updated_meta") or {}
    for k_m in ("hook_title", "reason", "social_caption"):
        if upd.get(k_m):
            clip[k_m] = upd[k_m]
    st.session_state.rendered_reels[rank] = info


def _kickoff_next_background_clip(run_id: str, source: str, clips, shown_count: int, cfg: Dict[str, Any]):
    if source and clips and shown_count < len(clips):
        next_clip = clips[shown_count]
        if next_clip["rank"] not in st.session_state.rendered_reels:
            key = pool.make_key(run_id, source, next_clip, cfg)
            pool.start_background(key, source, next_clip, cfg)


# =============================================================================
# SIDEBAR — OPUS PRO STUDIO CONTROLS & BRAND KIT
# =============================================================================
nvenc_ok = check_nvenc_available()

with st.sidebar:
    st.markdown('<div class="side-brand">⚡ OpusClip 4.0 Pro</div>', unsafe_allow_html=True)

    st.markdown('<div class="side-section">Clip Duration (Seconds)</div>', unsafe_allow_html=True)
    dur_range = st.slider("Target Duration", 15, 90, (30, 50), label_visibility="collapsed")
    min_dur, max_dur = dur_range

    st.markdown('<div class="side-section">Animated Caption Preset</div>', unsafe_allow_html=True)
    style_name = st.selectbox("Caption Template", list(STYLE_PRESETS.keys()), index=0, label_visibility="collapsed")

    st.markdown('<div class="side-section">Camera & AI Reframe</div>', unsafe_allow_html=True)
    trans_map = {
        "Smooth Cuts & Subtle Camera": "smooth_subtle",
        "Blur Whip & Zoom": "blur_whip",
        "Flash Cut & Zoom": "flash_zoom",
        "Smooth Cross-Dissolve": "cross_dissolve",
        "Static Camera (No Motion / Zoom)": "still_static",
    }
    trans_label = st.selectbox("Transition Style", list(trans_map.keys()), index=0, label_visibility="collapsed")
    transition_style = trans_map[trans_label]

    st.markdown('<div class="side-section">AI Visual Elements</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        show_captions = st.checkbox("Captions", value=True)
        show_hook_banner = st.checkbox("Title Card", value=True)
        smooth_outro = st.checkbox("Smooth Ending", value=True)
        color_punch = st.checkbox("Color Grade", value=True)
    with c2:
        show_emojis = st.checkbox("3D Emojis", value=True)
        show_progress_bar = st.checkbox("Progress Bar", value=True)
        dynamic_zoom = st.checkbox("Subtle Zoom", value=(transition_style != "still_static"))
        audio_polish = st.checkbox("Enhance Speech", value=True)

    st.markdown('<div class="side-section">Brand CTA Banner</div>', unsafe_allow_html=True)
    outro_text = st.text_input("Ending CTA", value="WATCH FULL VIDEO", max_chars=24, label_visibility="collapsed")

    st.markdown('<div class="side-section">Background Audio Track</div>', unsafe_allow_html=True)
    bg_music_file = st.file_uploader("Upload MP3 or WAV", type=["mp3", "wav"], label_visibility="collapsed")
    bg_music_path: Optional[str] = None
    if bg_music_file is not None:
        bg_save = Path("temp") / f"bgm_{bg_music_file.name}"
        bg_save.write_bytes(bg_music_file.getbuffer())
        bg_music_path = str(bg_save)

    st.markdown('<div class="side-section">Cloud Engine & Auth</div>', unsafe_allow_html=True)
    groq_cur = os.environ.get("GROQ_API_KEY", "").strip()
    is_groq_ready = groq_cur.startswith("gsk_") and len(groq_cur) > 20
    if is_groq_ready:
        st.markdown(
            '<div style="font-size:0.75rem; color:#10B981; font-weight:700; margin-bottom:4px;">'
            '● Groq LPU Engine Active'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="font-size:0.75rem; color:#F59E0B; font-weight:700; margin-bottom:4px;">'
            '▲ Free Groq API Key Required'
            '</div>',
            unsafe_allow_html=True,
        )

    entered_groq = st.text_input(
        "Groq API Key",
        value=groq_cur,
        type="password",
        placeholder="gsk_...",
        label_visibility="collapsed",
        help="Free instant key from console.groq.com",
        key="groq_key_input",
    )
    if entered_groq.strip() and entered_groq.strip() != groq_cur:
        os.environ["GROQ_API_KEY"] = entered_groq.strip()
        st.rerun()

    cookies_cand = resolve_cookies_path()
    has_cookies = cookies_cand is not None and cookies_cand.exists() and is_valid_cookie_file(cookies_cand)
    if has_cookies:
        st.markdown(
            f'<div style="font-size:0.75rem; color:#10B981; font-weight:700; margin-top:6px; margin-bottom:4px;">'
            f'● YouTube Auth Active ({cookies_cand.name})'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="font-size:0.75rem; color:#94A3B8; font-weight:500; margin-top:6px; margin-bottom:4px;">'
            '○ YouTube: Direct Access'
            '</div>',
            unsafe_allow_html=True,
        )

    with st.expander("YouTube Cloud Cookies", expanded=False):
        st.caption("Paste cookies if running behind restrictive cloud datacenter IPs:")
        uploaded_cookie = st.file_uploader("Upload cookies.txt", type=["txt"], key="cookie_uploader")
        if uploaded_cookie is not None:
            raw_text = uploaded_cookie.getvalue().decode("utf-8", errors="ignore")
            saved = save_and_sanitize_cookies(raw_text, Path("cookies.txt"))
            if saved:
                st.success("cookies.txt sanitized & activated!")
            else:
                st.error("Uploaded file does not contain valid Netscape cookies.")
            st.rerun()

        pasted_cookies = st.text_area("Or Paste Cookie Content", placeholder="# Netscape HTTP Cookie File...", height=60, key="paste_cookie_box")
        c_btn1, c_btn2 = st.columns(2)
        with c_btn1:
            if st.button("Apply Cookies", use_container_width=True, key="btn_apply_cookie"):
                saved = save_and_sanitize_cookies(pasted_cookies, Path("cookies.txt"))
                if saved:
                    st.success("Cookies sanitized & applied!")
                    st.rerun()
                else:
                    st.error("Could not parse cookie content. Paste standard Netscape cookies.")
        with c_btn2:
            if st.button("Test YouTube", use_container_width=True, key="btn_test_yt"):
                ok, detail = test_youtube_access()
                if ok:
                    st.success(f"YouTube OK: {detail[:28]}...")
                else:
                    st.error(f"Error: {detail[:60]}")


# =============================================================================
# TOP ANNOUNCEMENT BANNER & OPUS NAVBAR
# =============================================================================
st.markdown(
    """
    <div class="opus-top-banner">
        <span class="opus-banner-pill">OpusClip 4.0</span>
        <span><b>Next-Gen Generative AI Engine Active</b> • 1 Long Video to 10 Ready-to-Post Shorts in 1-Click • Powered by Groq LPU & Whisper Turbo</span>
    </div>
    <div class="opus-navbar">
        <div class="opus-brand">
            <svg width="34" height="34" viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect width="36" height="36" rx="10" fill="url(#opus_grad)"/>
                <path d="M11 11L18 25L25 11" stroke="#FFFFFF" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M22 25L28 13" stroke="#DDD6FE" stroke-width="2.4" stroke-linecap="round"/>
                <circle cx="28" cy="11" r="2" fill="#FFFFFF"/>
                <defs>
                    <linearGradient id="opus_grad" x1="0" y1="0" x2="36" y2="36" gradientUnits="userSpaceOnUse">
                        <stop stop-color="#7C3AED"/>
                        <stop offset="0.5" stop-color="#4F46E5"/>
                        <stop offset="1" stop-color="#06B6D4"/>
                    </linearGradient>
                </defs>
            </svg>
            <div class="opus-wordmark">Opus<span>Clip</span> <span style="font-size:0.95rem; font-weight:600; color:#94A3B8;">Pro</span></div>
            <div class="opus-version-badge">4.0 PRO</div>
        </div>
        <div class="opus-nav-status">
            <div class="opus-dot"></div>
            <span>Ultra-Fast LPU Engine Online</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Top Navigation Tabs (Studio, Features, Templates, Virality AI, Pro Hub)
tab_studio, tab_features, tab_templates, tab_virality, tab_pro = st.tabs([
    "🎬 Studio",
    "⚡ AI Features",
    "🎨 Brand Templates",
    "🎯 Virality AI™",
    "💎 Pro Exports",
])


# =============================================================================
# TAB 1: 🎬 STUDIO (CORE VIDEO GENERATOR & EDITOR)
# =============================================================================
with tab_studio:
    st.markdown(
        """
        <div class="opus-hero">
            <div class="opus-hero-chip">🔥 #1 AI Video Clipping & Editing Tool</div>
            <h1>1 Long Video. 10 Viral Clips.<br><span class="opus-gradient-text">Created 10x Faster with AI.</span></h1>
            <p>OpusClip turns podcasts, lectures, streams, and tutorials into high-converting shorts with automated hook detection, animated kinetic captions, 3D emojis, AI reframe, and virality scores.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # -------------------------------------------------------------------------
    # UNIFIED INPUT CONSOLE
    # -------------------------------------------------------------------------
    source_to_run: Optional[str] = None
    trigger_analysis = False

    st.markdown('<div class="opus-input-card">', unsafe_allow_html=True)
    in_tab_yt, in_tab_local = st.tabs(["🔗 Paste YouTube or Stream URL", "📁 Upload Local Video File"])

    with in_tab_yt:
        y_col1, y_col2 = st.columns([4.2, 1.4], vertical_alignment="bottom")
        with y_col1:
            yt_url = st.text_input(
                "YouTube Video URL",
                placeholder="https://www.youtube.com/watch?v=... (podcast, lecture, stream, tutorial)",
                label_visibility="collapsed",
                key="yt_url_input",
                on_change=_clear_previous_clips,
            )
        with y_col2:
            if st.button("⚡ Get Clips #1 AI", type="primary", use_container_width=True, key="btn_yt"):
                if not yt_url.strip().startswith(("http://", "https://")):
                    _clear_previous_clips()
                    st.error("Please enter a valid video link starting with https://")
                else:
                    source_to_run = yt_url.strip()
                    trigger_analysis = True

    with in_tab_local:
        l_col1, l_col2 = st.columns([3.4, 1.6], vertical_alignment="bottom")
        with l_col1:
            uploaded_vid = st.file_uploader(
                "Upload MP4, MKV, or MOV",
                type=["mp4", "mkv", "mov"],
                on_change=_clear_previous_clips,
                label_visibility="collapsed",
            )
        with l_col2:
            sample_path = Path("assets/sample.mp4")
            sample_exists = sample_path.exists() and sample_path.stat().st_size > 100000
            if st.button("Instant Demo Sample", use_container_width=True, disabled=not sample_exists):
                source_to_run = str(sample_path.resolve())
                trigger_analysis = True

        if uploaded_vid is not None:
            if st.button("⚡ Process Uploaded File", type="primary", use_container_width=True, key="btn_upload"):
                Path("temp").mkdir(parents=True, exist_ok=True)
                save_path = Path("temp") / f"upload_{uploaded_vid.name}"
                if not save_path.exists() or save_path.stat().st_size != uploaded_vid.size:
                    save_path.write_bytes(uploaded_vid.getbuffer())
                source_to_run = str(save_path.resolve())
                trigger_analysis = True

    # -------------------------------------------------------------------------
    # PREFERENCES & AI REFRAME
    # -------------------------------------------------------------------------
    st.markdown('<div class="side-section" style="margin-top:1.1rem;">AI Reframe & Highlight Preferences</div>', unsafe_allow_html=True)
    q1, q2, q3 = st.columns(3)

    video_type_map = {
        "Fit Whole Video (Aesthetic Blurred Canvas)": ("full_video", "blurred_fill"),
        "Fit Whole Video (Studio Uncropped Frame)": ("full_video", "full_uncropped"),
        "Auto Vertical Face Tracking (Smart 9:16)": ("informational", "full_fill"),
        "Gaming / Livestream (Screen + Facecam)": ("gaming", "streamer_split"),
        "Podcast / Two-Person Interview": ("podcast", "podcast_auto"),
    }
    clip_goal_map = {
        "Best Hook & Story Arc": "viral_hook",
        "Funniest / High-Energy Moment": "funny_hype",
        "Key Educational Takeaway": "educational",
        "Motivational Highlight": "motivational",
    }
    caption_lang_map = {
        "Hinglish (Hindi + English)": "hinglish",
        "English (Auto Translated)": "english",
        "Original Spoken Script": "native",
    }

    with q1:
        chosen_vtype_label = st.selectbox("Video Format & AI Reframe", list(video_type_map.keys()), index=0)
        video_type, default_framing = video_type_map[chosen_vtype_label]

    with q2:
        chosen_goal_label = st.selectbox("Highlight Goal", list(clip_goal_map.keys()), index=0)
        clip_goal = clip_goal_map[chosen_goal_label]

    with q3:
        chosen_lang_label = st.selectbox("Caption Language", list(caption_lang_map.keys()), index=0)
        caption_lang = caption_lang_map[chosen_lang_label]

    fast_heatmap_mode = st.toggle(
        "Fast Stream Heatmap Mode (extract directly from YouTube viewer replay spikes)",
        value=(video_type == "gaming"),
    )

    with st.sidebar:
        st.markdown('<div class="side-section">Layout Override</div>', unsafe_allow_html=True)
        framing_override_map = {
            "Match Selected Format": default_framing,
            "Fit Whole Video (Aesthetic Blurred Canvas)": "blurred_fill",
            "Fit Whole Video (Studio Uncropped Frame)": "full_uncropped",
            "Auto Vertical Face Tracking (Smart 9:16)": "full_fill",
            "Screen + Facecam Split": "streamer_split",
            "Podcast Top / Bottom Split": "podcast_auto",
        }
        framing_choice = st.selectbox("Layout", list(framing_override_map.keys()), index=0, label_visibility="collapsed")
        framing_mode = framing_override_map[framing_choice]

    render_cfg = {
        "framing_mode": framing_mode,
        "video_type": video_type,
        "caption_lang": caption_lang,
        "style_name": style_name,
        "transition_style": transition_style,
        "fast_heatmap_mode": fast_heatmap_mode,
        "show_captions": show_captions,
        "show_emojis": show_emojis,
        "show_hook_banner": show_hook_banner,
        "show_progress_bar": show_progress_bar,
        "smooth_outro": smooth_outro,
        "dynamic_zoom": dynamic_zoom,
        "color_punch": color_punch,
        "audio_polish": audio_polish,
        "outro_text": outro_text.strip() or "WATCH FULL VIDEO",
        "bg_music_path": bg_music_path,
    }

    eta_low, eta_high = _estimate_wait_range(
        framing_mode, transition_style, fast_heatmap_mode, min_dur, max_dur, nvenc_ok
    )
    st.markdown(
        f"""
        <div class="opus-eta">
            <div>⚡ Generation Speed: <strong>~{eta_low}–{eta_high} seconds</strong> per viral short</div>
            <div style="color:#94A3B8; font-size:0.82rem;">Parallel background pre-rendering active for instant multi-clip delivery.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # PIPELINE EXECUTION & RESULTS
    # -------------------------------------------------------------------------
    live_work_slot = st.container()
    results_slot = st.empty()

    if trigger_analysis and source_to_run:
        _clear_previous_clips()
        results_slot.empty()

        with live_work_slot:
            cache_file = _cache_path_for(source_to_run, video_type, clip_goal, fast_heatmap_mode, min_dur, max_dur)
            loaded_from_cache = False

            if cache_file.exists():
                try:
                    cached = json.loads(cache_file.read_text(encoding="utf-8"))
                    if isinstance(cached, dict) and len(cached.get("clips") or []) > 0:
                        st.session_state.analysis = cached
                        st.session_state.active_source = source_to_run
                        loaded_from_cache = True
                except Exception:
                    loaded_from_cache = False

            if not loaded_from_cache:
                try:
                    with st.spinner("AI Director: Scanning video for highest-retention hooks and story arcs..."):
                        result = analyze_video(
                            source=source_to_run,
                            video_type=video_type,
                            clip_goal=clip_goal,
                            fast_heatmap_mode=fast_heatmap_mode,
                            num_clips=5,
                            min_dur=min_dur,
                            max_dur=max_dur,
                        )
                    result = _ensure_fallback_clips(result, source_to_run, min_dur, max_dur, num_clips=3)
                    st.session_state.analysis = result
                    st.session_state.active_source = source_to_run
                    if result.get("clips"):
                        try:
                            cache_file.write_text(json.dumps(result), encoding="utf-8")
                        except Exception:
                            pass
                except Exception as e:
                    err_lower = str(e).lower()
                    is_yt_bot_err = any(
                        tok in err_lower
                        for tok in ("sign in to confirm", "confirm you're not a bot", "http error 429", "unable to download api page")
                    )
                    if is_yt_bot_err:
                        st.error(
                            "⚠️ **YouTube Cloud Bot Check**: YouTube is requiring authentication for this cloud IP. "
                            "Please paste your cookies in the sidebar under **'YouTube Cloud Cookies'** "
                            "or add `YOUTUBE_COOKIES` in your Streamlit Cloud Secrets."
                        )
                    else:
                        is_ai_scoring_err = any(
                            tok in err_lower
                            for tok in (
                                "groq",
                                "json_validate_failed",
                                "highlight scoring",
                                "comply",
                                "rate_limit",
                                "429",
                                "400",
                            )
                        )
                        if is_ai_scoring_err or not str(source_to_run).startswith(("http://", "https://")):
                            with st.spinner("Analyzing audio peaks & speech energy to extract top moments..."):
                                energy_curve, probed_dur = _fast_audio_energy_curve(source_to_run)
                                fallback_res = {
                                    "audio_info": {
                                        "source": source_to_run,
                                        "title": Path(source_to_run).stem if not str(source_to_run).startswith(("http://", "https://")) else "",
                                        "duration": probed_dur,
                                    },
                                    "energy_curve": energy_curve,
                                    "clips": [],
                                }
                                result = _ensure_fallback_clips(
                                    fallback_res,
                                    source_to_run,
                                    min_dur,
                                    max_dur,
                                    num_clips=3,
                                    skip_llm_title=True,
                                )
                            st.session_state.analysis = result
                            st.session_state.active_source = source_to_run
                        else:
                            st.error(f"Could not process this video. Please verify the link or try uploading the file. ({e})")

            if st.session_state.analysis and st.session_state.analysis.get("clips"):
                a_info = st.session_state.analysis["audio_info"]
                render_cfg["direct_mp4"] = a_info.get("direct_mp4")
                render_cfg["http_headers"] = a_info.get("http_headers")
                render_cfg["video_title"] = a_info.get("title", "")
                try:
                    _render_clip_clean(
                        st.session_state.active_source,
                        st.session_state.analysis["clips"][0],
                        render_cfg,
                    )
                    _kickoff_next_background_clip(
                        st.session_state.run_id,
                        st.session_state.active_source,
                        st.session_state.analysis["clips"],
                        shown_count=1,
                        cfg=render_cfg,
                    )
                except Exception as e:
                    st.error(f"Unable to render clip: {e}")

    # -------------------------------------------------------------------------
    # RESULTS WORKSPACE
    # -------------------------------------------------------------------------
    analysis = st.session_state.analysis
    active_source = st.session_state.active_source

    with results_slot.container():
        if analysis and analysis.get("clips"):
            clips = analysis["clips"]
            audio_info = analysis["audio_info"]
            shown_count = min(st.session_state.shown_count, len(clips))

            render_cfg["direct_mp4"] = audio_info.get("direct_mp4")
            render_cfg["http_headers"] = audio_info.get("http_headers")
            render_cfg["video_title"] = audio_info.get("title", "")
            _kickoff_next_background_clip(st.session_state.run_id, active_source, clips, shown_count, render_cfg)

            st.markdown(
                f"""
                <div style="display:flex; justify-content:space-between; align-items:center; margin: 1.5rem 0 1rem 0;">
                    <div style="font-family:'Plus Jakarta Sans', sans-serif; font-size:1.25rem; font-weight:800; color:#FFFFFF;">
                        ✨ Generated Viral Shorts ({shown_count} of {len(clips)})
                    </div>
                    <div style="color:#94A3B8; font-size:0.86rem; font-weight:600;">
                        1080p 60fps HD • Kinetic Captions Ready
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Timeline chart
            if analysis.get("energy_curve"):
                with st.expander("📊 View Audience Retention & Heatmap Curve", expanded=False):
                    st.plotly_chart(
                        _build_timeline_chart(analysis["energy_curve"], clips, shown_count),
                        use_container_width=True,
                    )

            for clip in clips[:shown_count]:
                rank = clip["rank"]
                rendered = st.session_state.rendered_reels.get(rank)
                words = clip.get("words", [])

                with st.container(border=True):
                    left_col, right_col = st.columns([1.35, 1.0], gap="large")

                    with left_col:
                        virality_val = clip.get("virality_score", 92)
                        st.markdown(
                            f"""
                            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.9rem;">
                                <div>
                                    <span class="opus-meta-pill">CLIP #{rank}</span>
                                    <span class="opus-meta-pill">{_fmt_ts(clip['start'])} – {_fmt_ts(clip['end'])}</span>
                                    <span class="opus-meta-pill">{int(round(clip['duration']))}s</span>
                                </div>
                                <div class="opus-virality-badge">🔥 {virality_val} Virality Score</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                        # Sub-metrics breakdown
                        m1, m2, m3 = st.columns(3)
                        with m1:
                            st.caption("Hook Strength")
                            st.progress(float(clip.get("hook_score", 94)) / 100.0)
                        with m2:
                            st.caption("Story Flow")
                            st.progress(float(clip.get("coherence_score", 90)) / 100.0)
                        with m3:
                            st.caption("Audio Energy")
                            st.progress(float(clip.get("audio_energy_score", 88)) / 100.0)

                        edited_title = st.text_input(
                            "Hook Title (Opening Card)",
                            value=clip["hook_title"],
                            key=f"title_edit_{st.session_state.run_id}_{rank}",
                        )
                        clip["hook_title"] = edited_title

                        if clip.get("reason"):
                            st.markdown(
                                f'<p style="color:#CBD5E1; font-size:0.88rem; line-height:1.45; margin:0.4rem 0 0.8rem 0;">{clip["reason"]}</p>',
                                unsafe_allow_html=True,
                            )

                        if clip.get("social_caption"):
                            st.markdown('<div class="side-section" style="margin-top:0.6rem; margin-bottom:0.25rem;">Suggested Viral Caption</div>', unsafe_allow_html=True)
                            st.code(clip["social_caption"], language=None)

                        with st.expander("📝 View Spoken Transcript"):
                            preview_txt = " ".join(w["word"] for w in words)
                            st.write(preview_txt or "Transcript available after rendering.")

                        st.markdown("<div style='height:0.35rem;'></div>", unsafe_allow_html=True)
                        if st.button(
                            "🔄 Apply Sidebar Style & Re-Render",
                            use_container_width=True,
                            key=f"rerender_btn_{st.session_state.run_id}_{rank}",
                        ):
                            try:
                                _render_clip_clean(active_source, clip, render_cfg)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Could not re-render clip: {e}")

                    with right_col:
                        if rendered and Path(rendered["output_path"]).exists():
                            video_bytes = Path(rendered["output_path"]).read_bytes()
                            st.video(video_bytes)

                            dl_c1, dl_c2 = st.columns(2)
                            with dl_c1:
                                st.download_button(
                                    label="📥 Download MP4",
                                    data=video_bytes,
                                    file_name=f"OpusClip_{rank}_{clip['hook_title'][:20].replace(' ', '_')}.mp4",
                                    mime="video/mp4",
                                    use_container_width=True,
                                    key=f"dl_btn_{st.session_state.run_id}_{rank}",
                                )
                            with dl_c2:
                                srt_data = _words_to_srt(words)
                                st.download_button(
                                    label="📝 Export Subtitles (.SRT)",
                                    data=srt_data,
                                    file_name=f"OpusClip_{rank}_Subtitles.srt",
                                    mime="text/plain",
                                    use_container_width=True,
                                    key=f"srt_btn_{st.session_state.run_id}_{rank}",
                                )
                        else:
                            st.info("⚡ Background rendering in progress. Click **Apply Sidebar Style & Re-Render** to compile.")

            if shown_count < len(clips):
                next_clip = clips[shown_count]
                next_key = pool.make_key(st.session_state.run_id, active_source, next_clip, render_cfg)
                bg_job = pool.get_job(next_key)
                ready_note = "Ready in memory" if (bg_job and bg_job["status"] == "done") else "Pre-rendering in background"

                st.markdown(
                    f"""
                    <div style="background:#0D111A; border:1px solid #1E293B; border-radius:14px; padding:1.1rem 1.3rem; margin-top:1rem;">
                        <div style="font-family:'Plus Jakarta Sans', sans-serif; font-size:1.02rem; font-weight:700; color:#FFFFFF; margin-bottom:0.2rem;">
                            Ready for the next viral short?
                        </div>
                        <div style="font-size:0.88rem; color:#94A3B8;">
                            Next: <b>{next_clip['hook_title']}</b> ({_fmt_ts(next_clip['start'])} – {_fmt_ts(next_clip['end'])}) · {ready_note}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button("⚡ Reveal Next Clip", use_container_width=True, type="secondary"):
                    st.session_state.shown_count += 1
                    st.rerun()


# =============================================================================
# TAB 2: ⚡ OPUSCLIP AI FEATURES (MEGA-MENU SHOWCASE FROM SCREENSHOT)
# =============================================================================
with tab_features:
    st.markdown(
        """
        <div style="text-align:center; margin: 1.2rem auto 2rem auto; max-width:800px;">
            <div class="opus-hero-chip">✨ OpusClip 4.0 Ecosystem</div>
            <h2 style="font-family:'Plus Jakarta Sans', sans-serif; font-size:2.2rem; font-weight:800; color:#FFFFFF; margin:0 0 0.5rem 0;">
                All-in-One AI Video Suite
            </h2>
            <p style="color:#94A3B8; font-size:1.02rem;">
                Transform your raw footage into an automated social media powerhouse with deep learning vision and audio intelligence.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="opus-feature-grid">
            <div class="opus-feat-card">
                <div class="opus-feat-icon">🎬</div>
                <div class="opus-feat-title">AI Producer <span class="opus-badge-new">NEW</span></div>
                <div class="opus-feat-desc">Turn your raw footage into a polished, ready to post video with automated narrative pacing and virality score detection.</div>
            </div>
            <div class="opus-feat-card">
                <div class="opus-feat-icon">✨</div>
                <div class="opus-feat-title">ClipAnything <span class="opus-badge-pro">PRO</span></div>
                <div class="opus-feat-desc">The fastest way to turn any long video (YouTube, streams, lectures, podcasts) into viral shorts in 1 click.</div>
            </div>
            <div class="opus-feat-card">
                <div class="opus-feat-icon">💬</div>
                <div class="opus-feat-title">Animated Captions</div>
                <div class="opus-feat-desc">The fastest way to add kinetic word-by-word animated captions with auto-synced 3D emojis and karaoke highlights.</div>
            </div>
            <div class="opus-feat-card">
                <div class="opus-feat-icon">📐</div>
                <div class="opus-feat-title">AI Reframe <span class="opus-badge-new">UPDATED</span></div>
                <div class="opus-feat-desc">Resize any video to 9:16 vertical for TikTok, Shorts, and Reels while keeping 100% of the whole video visible with aesthetic blur.</div>
            </div>
            <div class="opus-feat-card">
                <div class="opus-feat-icon">🎭</div>
                <div class="opus-feat-title">AI B-Roll & Hook Card</div>
                <div class="opus-feat-desc">Instant high-impact 3-second hook title cards and ambient background video styling to maximize viewer retention.</div>
            </div>
            <div class="opus-feat-card">
                <div class="opus-feat-icon">🎙️</div>
                <div class="opus-feat-title">Enhance Speech <span class="opus-badge-new">NEW</span></div>
                <div class="opus-feat-desc">Pro-level studio audio leveling (-14 LUFS) and noise reduction with no additional hardware required.</div>
            </div>
            <div class="opus-feat-card">
                <div class="opus-feat-icon">🏷️</div>
                <div class="opus-feat-title">Brand Templates</div>
                <div class="opus-feat-desc">Easily select and customize viral caption styles (Hormozi, MrBeast, Neon Cyber, Submagic, Editorial Gold).</div>
            </div>
            <div class="opus-feat-card">
                <div class="opus-feat-icon">📅</div>
                <div class="opus-feat-title">Social Scheduler & Captions</div>
                <div class="opus-feat-desc">Auto-generate punchy viral post captions and 4 high-traffic hashtags ready to paste directly to all platforms.</div>
            </div>
            <div class="opus-feat-card">
                <div class="opus-feat-icon">📁</div>
                <div class="opus-feat-title">Export to XML & SRT</div>
                <div class="opus-feat-desc">Edit in Adobe Premiere Pro or DaVinci Resolve at ease, or download instant standard SubRip (.SRT) subtitle files.</div>
            </div>
            <div class="opus-feat-card">
                <div class="opus-feat-icon">🖼️</div>
                <div class="opus-feat-title">Thumbnail Generator <span class="opus-badge-new">NEW</span></div>
                <div class="opus-feat-desc">Drop a link and get high-converting video thumbnails and hook frames in 1 click.</div>
            </div>
            <div class="opus-feat-card">
                <div class="opus-feat-icon">🌐</div>
                <div class="opus-feat-title">AI Multilingual Dubbing</div>
                <div class="opus-feat-desc">Translate spoken audio into natural Indian Hinglish, English, or retain native scripts without tofu font artifacts.</div>
            </div>
            <div class="opus-feat-card">
                <div class="opus-feat-icon">⚡</div>
                <div class="opus-feat-title">Agentic Workflows & API <span class="opus-badge-pro">PRO</span></div>
                <div class="opus-feat-desc">Programmatic video API and MCP server tools that any autonomous AI agent or workflow can call directly.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# =============================================================================
# TAB 3: 🎨 BRAND TEMPLATES GALLERY
# =============================================================================
with tab_templates:
    st.markdown(
        """
        <div style="text-align:center; margin: 1.2rem auto 2rem auto; max-width:800px;">
            <div class="opus-hero-chip">🎨 Viral Styling</div>
            <h2 style="font-family:'Plus Jakarta Sans', sans-serif; font-size:2.2rem; font-weight:800; color:#FFFFFF; margin:0 0 0.5rem 0;">
                Signature Animated Caption Styles
            </h2>
            <p style="color:#94A3B8; font-size:1.02rem;">
                Proven high-converting typography presets modeled after top creators like Alex Hormozi, MrBeast, and Submagic.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="opus-tpl-grid">
            <div class="opus-tpl-card">
                <div class="opus-tpl-preview" style="background:#000000; color:#39FF14; font-family:'Montserrat', sans-serif; font-size:1.5rem; text-shadow:0 0 10px rgba(57,255,20,0.5);">
                    VIRAL HOOK!
                </div>
                <div style="font-weight:700; font-size:1.05rem; color:#FFFFFF; margin-bottom:0.25rem;">Opus Hormozi</div>
                <div style="font-size:0.82rem; color:#94A3B8; margin-bottom:0.8rem;">High-contrast green/yellow active word cycle with bold tilted uppercase. Used by #1 finance & business creators.</div>
                <span class="opus-badge-pro">MOST POPULAR</span>
            </div>
            <div class="opus-tpl-card">
                <div class="opus-tpl-preview" style="background:#141724; color:#FFD000; font-family:'Bangers', sans-serif; font-size:1.7rem; letter-spacing:1px;">
                    INSANE MOMENT 🔥
                </div>
                <div style="font-weight:700; font-size:1.05rem; color:#FFFFFF; margin-bottom:0.25rem;">MrBeast Hype</div>
                <div style="font-size:0.82rem; color:#94A3B8; margin-bottom:0.8rem;">Playful, high-energy impact typography with explosive contrast and animated 3D emojis.</div>
                <span class="opus-badge-new">HIGH RETENTION</span>
            </div>
            <div class="opus-tpl-card">
                <div class="opus-tpl-preview" style="background:#090B14; color:#00F0FF; font-family:'Anton', sans-serif; font-size:1.6rem; text-shadow:0 0 14px rgba(0,240,255,0.7);">
                    FUTURE AI 🤖
                </div>
                <div style="font-weight:700; font-size:1.05rem; color:#FFFFFF; margin-bottom:0.25rem;">Neon Cyber</div>
                <div style="font-size:0.82rem; color:#94A3B8; margin-bottom:0.8rem;">Vibrant neon cyan & electric purple glow. Ideal for tech, crypto, gaming, and AI shorts.</div>
                <span class="opus-badge-new">TECH FAVORITE</span>
            </div>
            <div class="opus-tpl-card">
                <div class="opus-tpl-preview" style="background:#121626; color:#FFE614; font-family:'Montserrat', sans-serif; font-size:1.35rem;">
                    <span style="background:#FFE614; color:#000000; padding:0.2rem 0.6rem; border-radius:8px;">Submagic</span>
                </div>
                <div style="font-weight:700; font-size:1.05rem; color:#FFFFFF; margin-bottom:0.25rem;">Submagic Pill</div>
                <div style="font-size:0.82rem; color:#94A3B8; margin-bottom:0.8rem;">Modern rounded pill background tracking active words with smooth color cycle.</div>
                <span class="opus-badge-pro">MODERN CLEAN</span>
            </div>
            <div class="opus-tpl-card">
                <div class="opus-tpl-preview" style="background:#131210; color:#FFD048; font-family:'Playfair Display', serif; font-size:1.4rem; font-style:italic;">
                    Editorial Luxury
                </div>
                <div style="font-weight:700; font-size:1.05rem; color:#FFFFFF; margin-bottom:0.25rem;">Editorial Gold</div>
                <div style="font-size:0.82rem; color:#94A3B8; margin-bottom:0.8rem;">Refined serif typography with warm gold highlights for thought leaders, podcasts, and interviews.</div>
                <span class="opus-badge-new">LUXURY</span>
            </div>
            <div class="opus-tpl-card">
                <div class="opus-tpl-preview" style="background:#111522; color:#FFFFFF; font-family:'Inter', sans-serif; font-size:1.4rem;">
                    Clean Minimal
                </div>
                <div style="font-weight:700; font-size:1.05rem; color:#FFFFFF; margin-bottom:0.25rem;">Minimalist Sans</div>
                <div style="font-size:0.82rem; color:#94A3B8; margin-bottom:0.8rem;">Subtle white subtitles with thin border shadow. Perfect for aesthetic cinematic reels.</div>
                <span class="opus-badge-pro">TIMELESS</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# =============================================================================
# TAB 4: 🎯 VIRALITY AI™ SCORING ENGINE
# =============================================================================
with tab_virality:
    st.markdown(
        """
        <div style="text-align:center; margin: 1.2rem auto 2rem auto; max-width:800px;">
            <div class="opus-hero-chip">🎯 Proprietary Algorithm</div>
            <h2 style="font-family:'Plus Jakarta Sans', sans-serif; font-size:2.2rem; font-weight:800; color:#FFFFFF; margin:0 0 0.5rem 0;">
                How OpusClip Virality Score™ Works
            </h2>
            <p style="color:#94A3B8; font-size:1.02rem;">
                Our AI evaluates thousands of data points across your audio, transcript, and pacing to predict which segments will generate the highest watch time and viral reach.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    v_c1, v_c2, v_c3 = st.columns(3)
    with v_c1:
        st.markdown(
            """
            <div class="opus-feat-card" style="border-top: 3px solid #6366F1;">
                <div style="font-size:2rem; font-weight:800; color:#818CF8; margin-bottom:0.3rem;">45%</div>
                <div class="opus-feat-title">Opening Hook Power</div>
                <div class="opus-feat-desc">The first 3 seconds determine whether viewers swipe away. The AI scans for curiosity triggers, shocking revelations, questions, and high-energy openers.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with v_c2:
        st.markdown(
            """
            <div class="opus-feat-card" style="border-top: 3px solid #A855F7;">
                <div style="font-size:2rem; font-weight:800; color:#C084FC; margin-bottom:0.3rem;">35%</div>
                <div class="opus-feat-title">Story Coherence & Payoff</div>
                <div class="opus-feat-desc">A short must deliver on its promise. The AI ensures the clip contains a complete standalone narrative with a clear punchline, lesson, or emotional climax.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with v_c3:
        st.markdown(
            """
            <div class="opus-feat-card" style="border-top: 3px solid #10B981;">
                <div style="font-size:2rem; font-weight:800; color:#34D399; margin-bottom:0.3rem;">20%</div>
                <div class="opus-feat-title">Audio Energy & Heatmap</div>
                <div class="opus-feat-desc">Calculated directly from RMS vocal peaks, laughing/reaction spikes, and YouTube's viewer replayed heatmap data to capture peak engagement.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# =============================================================================
# TAB 5: 💎 PRO HUB & WORKFLOWS
# =============================================================================
with tab_pro:
    st.markdown(
        """
        <div style="text-align:center; margin: 1.2rem auto 2rem auto; max-width:800px;">
            <div class="opus-hero-chip">💎 Professional Workflows</div>
            <h2 style="font-family:'Plus Jakarta Sans', sans-serif; font-size:2.2rem; font-weight:800; color:#FFFFFF; margin:0 0 0.5rem 0;">
                Export to Premiere, DaVinci & Beyond
            </h2>
            <p style="color:#94A3B8; font-size:1.02rem;">
                Built for professional video editors, social media marketing teams, and content creators.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    p_c1, p_c2 = st.columns(2, gap="large")
    with p_c1:
        st.markdown(
            """
            <div class="opus-feat-card">
                <div class="opus-feat-title">📁 Adobe Premiere Pro & DaVinci XML Export</div>
                <div class="opus-feat-desc" style="margin-bottom:0.8rem;">
                    Want to perform final fine-tuning in your NLE? Every clip provides synchronized word timestamps that can be imported directly into Premiere Pro or DaVinci Resolve.
                </div>
                <ul style="color:#94A3B8; font-size:0.86rem; line-height:1.6; margin-left:-1.2rem;">
                    <li>Download standard <b>.SRT subtitle files</b> with millisecond alignment.</li>
                    <li>Automatic sentence snapping eliminates audio clipping.</li>
                    <li>Full HD 1080x1920 60fps render pipeline.</li>
                </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with p_c2:
        st.markdown(
            """
            <div class="opus-feat-card">
                <div class="opus-feat-title">⚡ High-Speed Hardware Acceleration</div>
                <div class="opus-feat-desc" style="margin-bottom:0.8rem;">
                    Our engine auto-detects GPU hardware acceleration and leverages Whisper-large-v3-turbo via Groq LPU:
                </div>
                <ul style="color:#94A3B8; font-size:0.86rem; line-height:1.6; margin-left:-1.2rem;">
                    <li><b>NVIDIA NVENC Hardware Encoding</b> (up to 400 FPS export on local GPU).</li>
                    <li><b>Multi-threaded Background Pre-rendering</b> keeps subsequent clips ready instantly.</li>
                    <li>Zero-wait cached analysis allows repeated exports without re-transcribing.</li>
                </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )
