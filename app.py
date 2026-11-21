import os
import re
import copy
import json
import time
import hashlib
import threading
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
from dotenv import load_dotenv
import streamlit as st
import plotly.graph_objects as go

# Load local .env first, then safely read Streamlit Cloud Secrets without crashing locally
load_dotenv()
try:
    if "GROQ_API_KEY" in st.secrets:
        os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
    if "YOUTUBE_COOKIES" in st.secrets:
        Path("cookies.txt").write_text(st.secrets["YOUTUBE_COOKIES"], encoding="utf-8")
except Exception:
    pass

for _dir in ("temp", "outputs", "assets", "assets/fonts", "assets/emojis", "assets/emojis_3d"):
    Path(_dir).mkdir(parents=True, exist_ok=True)

from yt_auth import resolve_cookies_path, test_youtube_access
from audio_ai import analyze_video
from video_studio import (
    render_viral_reel,
    check_nvenc_available,
    STYLE_PRESETS,
)

# =============================================================================
# PAGE CONFIG & CLASSIC NAVY / GREY / WHITE / BLACK DESIGN SYSTEM
# =============================================================================
st.set_page_config(
    page_title="VeloCut — Short-Form Video Studio",
    page_icon="▣",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@600;700;800&display=swap');

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

    .block-container {
        padding-top: 1.1rem !important;
        padding-bottom: 3rem !important;
        max-width: 1160px !important;
    }

    section[data-testid="stSidebar"] {
        background-color: #0D131F !important;
        border-right: 1px solid #1E293B !important;
    }
    section[data-testid="stSidebar"] .block-container {
        padding-top: 1.4rem !important;
    }
    .side-brand {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: #64748B;
        margin-bottom: 0.85rem;
    }
    .side-section {
        font-size: 0.74rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #94A3B8;
        margin-top: 1rem;
        margin-bottom: 0.4rem;
    }

    .vc-navbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: #0D131F;
        border: 1px solid #1E293B;
        border-radius: 14px;
        padding: 0.85rem 1.35rem;
        margin-bottom: 1.6rem;
    }
    .vc-brand-wrap {
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }
    .vc-wordmark {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 1.32rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        color: #FFFFFF;
        line-height: 1;
    }
    .vc-wordmark span {
        color: #94A3B8;
        font-weight: 600;
    }
    .vc-nav-links {
        display: flex;
        align-items: center;
        gap: 1.4rem;
    }
    .vc-nav-item {
        font-size: 0.84rem;
        font-weight: 500;
        color: #94A3B8;
    }
    .vc-nav-item.active {
        color: #FFFFFF;
        font-weight: 600;
    }
    .vc-nav-badge {
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: #CBD5E1;
        background: #172338;
        border: 1px solid #283B5A;
        padding: 0.28rem 0.7rem;
        border-radius: 999px;
    }

    .vc-hero {
        margin-bottom: 1.5rem;
    }
    .vc-hero h1 {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 1.85rem;
        font-weight: 700;
        letter-spacing: -0.025em;
        color: #FFFFFF;
        margin: 0 0 0.35rem 0;
    }
    .vc-hero p {
        font-size: 0.95rem;
        color: #94A3B8;
        margin: 0;
    }

    .vc-label {
        font-size: 0.76rem;
        font-weight: 600;
        letter-spacing: 0.09em;
        text-transform: uppercase;
        color: #94A3B8;
        margin: 0.25rem 0 0.75rem 0;
    }

    .vc-eta {
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 0.5rem;
        background: #0F1726;
        border: 1px solid #1E293B;
        border-left: 3px solid #3B5B8C;
        border-radius: 10px;
        padding: 0.65rem 1rem;
        margin: 0.85rem 0 1.25rem 0;
        font-size: 0.86rem;
        color: #CBD5E1;
    }
    .vc-eta strong {
        color: #FFFFFF;
        font-weight: 600;
    }
    .vc-eta-muted {
        color: #94A3B8;
        font-size: 0.82rem;
    }

    div.stButton > button[kind="primary"] {
        background-color: #FFFFFF !important;
        color: #090C10 !important;
        border: 1px solid #FFFFFF !important;
        font-weight: 600 !important;
        border-radius: 9px !important;
        padding: 0.52rem 1.15rem !important;
        transition: all 0.15s ease !important;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #E2E8F0 !important;
        border-color: #E2E8F0 !important;
        color: #090C10 !important;
    }
    div.stButton > button[kind="secondary"],
    div.stDownloadButton > button {
        background-color: #131D30 !important;
        color: #F8FAFC !important;
        border: 1px solid #26354D !important;
        font-weight: 500 !important;
        border-radius: 9px !important;
        transition: all 0.15s ease !important;
    }
    div.stButton > button[kind="secondary"]:hover,
    div.stDownloadButton > button:hover {
        background-color: #1C2A44 !important;
        border-color: #3B5278 !important;
        color: #FFFFFF !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 1.5rem;
        border-bottom: 1px solid #1E293B;
    }
    .stTabs [data-baseweb="tab"] {
        color: #94A3B8 !important;
        font-weight: 500 !important;
        padding-bottom: 0.65rem !important;
    }
    .stTabs [aria-selected="true"] {
        color: #FFFFFF !important;
        font-weight: 600 !important;
    }
    .stTabs [data-baseweb="tab-highlight"] {
        background-color: #FFFFFF !important;
    }

    .stTextInput input, .stSelectbox [data-baseweb="select"] > div {
        background-color: #0A0E16 !important;
        border: 1px solid #243044 !important;
        border-radius: 9px !important;
        color: #F8FAFC !important;
    }
    .stTextInput input:focus {
        border-color: #64748B !important;
        box-shadow: none !important;
    }

    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #0D131F !important;
        border: 1px solid #1E293B !important;
        border-radius: 14px !important;
    }
    .vc-chip {
        display: inline-block;
        background: #162134;
        border: 1px solid #263856;
        color: #E2E8F0;
        padding: 0.2rem 0.6rem;
        border-radius: 6px;
        font-size: 0.74rem;
        font-weight: 600;
        letter-spacing: 0.03em;
        margin-right: 0.45rem;
    }
    .vc-score {
        display: inline-block;
        background: #FFFFFF;
        color: #090C10;
        padding: 0.2rem 0.65rem;
        border-radius: 6px;
        font-size: 0.78rem;
        font-weight: 700;
    }
    .vc-time-meta {
        color: #94A3B8;
        font-size: 0.83rem;
        font-weight: 500;
    }
    .vc-next-bar {
        background: #0D131F;
        border: 1px solid #223047;
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin-top: 0.9rem;
    }
    .vc-next-title {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 1rem;
        font-weight: 600;
        color: #FFFFFF;
        margin-bottom: 0.2rem;
    }
    .vc-next-sub {
        font-size: 0.86rem;
        color: #94A3B8;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

Path("temp").mkdir(exist_ok=True)
Path("outputs").mkdir(exist_ok=True)
Path("assets").mkdir(exist_ok=True)


# =============================================================================
# SILENT BACKGROUND PRE-RENDERER
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
# HELPERS & RESILIENT AUDIO-PEAK FALLBACK
# =============================================================================
def _fmt_ts(sec: float) -> str:
    sec = max(0, int(round(sec)))
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


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
    """Compute a fast per-second audio engagement curve directly via FFmpeg."""
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
    """Guarantees 1–3 high-energy clips if AI highlight scoring returns empty or refuses."""
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
                "virality_score": 88,
                "hook_title": "TOP HIGHLIGHT MOMENT",
                "reason": "Selected automatically using peak audio energy analysis.",
                "social_caption": "Watch till the end! #shorts #reels",
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
                    "virality_score": max(78, 91 - (idx - 1) * 4),
                    "hook_title": f"TOP HIGHLIGHT #{idx}",
                    "reason": "Selected automatically from the highest-energy section of your video.",
                    "social_caption": "Don't miss this moment! #shorts #viral",
                    "words": [],
                    "needs_word_sync": True,
                    "needs_title_from_clip": not skip_llm_title,
                }
            )

    result["clips"] = clips
    return result


def _cache_path_for(source: str, video_type: str, clip_goal: str, fast_heatmap: bool, min_dur: int, max_dur: int) -> Path:
    key_str = f"v9|{source}|{video_type}|{clip_goal}|{fast_heatmap}|{min_dur}|{max_dur}"
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
    eff = "full_uncropped" if transition_style == "still_static" else framing_mode
    base = 9 if fast_heatmap_mode else 14
    cv = 0 if eff in ("full_uncropped", "wide_cinematic", "blurred_fill") else int(round(avg_dur * 0.07))
    enc = max(5, int(round(avg_dur * (0.14 if nvenc_ok else 0.30))))
    mid = base + cv + enc
    return max(12, mid - 4), mid + 8


def _clean_progress_text(frac: float, raw_label: str) -> str:
    if frac < 0.22:
        return "Fetching video segment..."
    if frac < 0.35:
        return "Generating synchronized captions..."
    if frac < 0.45:
        return "Preparing visual layout and typography..."
    if frac >= 0.99:
        return "Finalizing your short..."
    m = re.search(r"~(\d+s)", raw_label)
    if m:
        return f"Rendering video ({int(frac * 100)}%) — about {m.group(1)} left"
    return f"Rendering video ({int(frac * 100)}%)..."


def _build_timeline_chart(energy_curve, clips, shown_count: int):
    x_sec = list(range(len(energy_curve)))
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x_sec, y=energy_curve, mode="lines",
            line=dict(color="#64748B", width=1.8),
            fill="tozeroy", fillcolor="rgba(100, 116, 139, 0.14)",
            hovertemplate="Time: %{x}s<br>Engagement: %{y:.0f}/100<extra></extra>",
        )
    )
    for idx, c in enumerate(clips):
        is_shown = (idx < shown_count)
        fig.add_vrect(
            x0=c["start"], x1=c["end"],
            fillcolor="rgba(255, 255, 255, 0.14)" if is_shown else "rgba(148, 163, 184, 0.06)",
            line_width=1.4 if is_shown else 0.8,
            line_color="#FFFFFF" if is_shown else "#475569",
            line_dash="solid" if is_shown else "dot",
            annotation_text=f"Clip #{c['rank']}",
            annotation_position="top left",
            annotation_font=dict(color="#F8FAFC" if is_shown else "#94A3B8", size=11),
        )
    fig.update_layout(
        height=210, margin=dict(l=8, r=8, t=22, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#0A0E16",
        xaxis=dict(title="Timeline (Seconds)", gridcolor="#1E293B", color="#94A3B8"),
        yaxis=dict(title="Engagement", range=[0, 108], gridcolor="#1E293B", color="#94A3B8"),
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
# SIDEBAR — CLEAN STUDIO CONTROLS
# =============================================================================
nvenc_ok = check_nvenc_available()

with st.sidebar:
    st.markdown('<div class="side-brand">VeloCut Studio</div>', unsafe_allow_html=True)

    st.markdown('<div class="side-section">Clip Length</div>', unsafe_allow_html=True)
    dur_range = st.slider("Duration (seconds)", 20, 75, (32, 48), label_visibility="collapsed")
    min_dur, max_dur = dur_range

    st.markdown('<div class="side-section">Caption Style</div>', unsafe_allow_html=True)
    style_name = st.selectbox("Caption Template", list(STYLE_PRESETS.keys()), index=0, label_visibility="collapsed")

    st.markdown('<div class="side-section">Camera & Transitions</div>', unsafe_allow_html=True)
    trans_map = {
        "Static Frame (Full Video, No Movement)": "still_static",
        "Blur Whip & Zoom": "blur_whip",
        "Flash Cut & Zoom": "flash_zoom",
        "Smooth Cross-Dissolve": "cross_dissolve",
    }
    trans_label = st.selectbox("Transition Style", list(trans_map.keys()), index=0, label_visibility="collapsed")
    transition_style = trans_map[trans_label]

    st.markdown('<div class="side-section">Visual Elements</div>', unsafe_allow_html=True)
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
        audio_polish = st.checkbox("Voice Boost", value=True)

    st.markdown('<div class="side-section">Ending Text</div>', unsafe_allow_html=True)
    outro_text = st.text_input("Ending CTA", value="WATCH FULL VIDEO", max_chars=24, label_visibility="collapsed")

    st.markdown('<div class="side-section">Background Music (Optional)</div>', unsafe_allow_html=True)
    bg_music_file = st.file_uploader("Upload MP3 or WAV", type=["mp3", "wav"], label_visibility="collapsed")
    bg_music_path: Optional[str] = None
    if bg_music_file is not None:
        bg_save = Path("temp") / f"bgm_{bg_music_file.name}"
        bg_save.write_bytes(bg_music_file.getbuffer())
        bg_music_path = str(bg_save)

    st.markdown('<div class="side-section">AI & Cloud Authentication</div>', unsafe_allow_html=True)
    groq_cur = os.environ.get("GROQ_API_KEY", "").strip()
    is_groq_ready = groq_cur.startswith("gsk_") and len(groq_cur) > 20
    if is_groq_ready:
        st.markdown(
            '<div style="font-size:0.75rem; color:#10B981; font-weight:600; margin-bottom:4px;">'
            '● Groq AI Connected'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="font-size:0.75rem; color:#F59E0B; font-weight:600; margin-bottom:4px;">'
            '▲ Groq API Key Required'
            '</div>',
            unsafe_allow_html=True,
        )

    entered_groq = st.text_input(
        "Groq API Key",
        value=groq_cur,
        type="password",
        placeholder="gsk_...",
        label_visibility="collapsed",
        help="Free API key from console.groq.com",
        key="groq_key_input",
    )
    if entered_groq.strip() and entered_groq.strip() != groq_cur:
        os.environ["GROQ_API_KEY"] = entered_groq.strip()
        st.rerun()

    cookies_cand = resolve_cookies_path()
    has_cookies = cookies_cand.exists() and cookies_cand.stat().st_size > 100
    if has_cookies:
        st.markdown(
            f'<div style="font-size:0.75rem; color:#10B981; font-weight:600; margin-top:6px; margin-bottom:4px;">'
            f'● YouTube Cookies Active ({cookies_cand.name})'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="font-size:0.75rem; color:#94A3B8; font-weight:500; margin-top:6px; margin-bottom:4px;">'
            '○ YouTube: Direct Mode'
            '</div>',
            unsafe_allow_html=True,
        )

    with st.expander("YouTube Cloud Cookies", expanded=False):
        st.caption("When hosted on Streamlit Cloud, YouTube may require cookies to bypass datacenter IP blocks:")
        uploaded_cookie = st.file_uploader("Upload cookies.txt", type=["txt"], key="cookie_uploader")
        if uploaded_cookie is not None:
            Path("cookies.txt").write_bytes(uploaded_cookie.getbuffer())
            st.success("cookies.txt saved and activated!")
            st.rerun()

        pasted_cookies = st.text_area("Or Paste Cookie Content", placeholder="# Netscape HTTP Cookie File...", height=60, key="paste_cookie_box")
        c_btn1, c_btn2 = st.columns(2)
        with c_btn1:
            if st.button("Apply Cookies", use_container_width=True, key="btn_apply_cookie"):
                if len(pasted_cookies.strip()) > 50:
                    Path("cookies.txt").write_text(pasted_cookies.strip(), encoding="utf-8")
                    st.success("Cookies applied!")
                    st.rerun()
                else:
                    st.warning("Paste valid cookie content.")
        with c_btn2:
            if st.button("Test YouTube", use_container_width=True, key="btn_test_yt"):
                ok, detail = test_youtube_access()
                if ok:
                    st.success(f"YouTube OK: {detail[:28]}...")
                else:
                    st.error(f"Error: {detail[:60]}")


# =============================================================================
# TOP NAVIGATION BAR & HERO
# =============================================================================
st.markdown(
    """
    <div class="vc-navbar">
        <div class="vc-brand-wrap">
            <svg width="34" height="34" viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="1.5" y="1.5" width="33" height="33" rx="9" fill="#131E33" stroke="#334B70" stroke-width="1.5"/>
                <path d="M10.5 11.5L16.5 24.5L22.5 11.5" stroke="#FFFFFF" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M21 24.5L26.5 13.5" stroke="#94A3B8" stroke-width="2.2" stroke-linecap="round"/>
                <circle cx="26.5" cy="11.5" r="1.8" fill="#FFFFFF"/>
            </svg>
            <div class="vc-wordmark">Velo<span>Cut</span></div>
        </div>
        <div class="vc-nav-links">
            <span class="vc-nav-item active">Studio</span>
            <span class="vc-nav-item">Templates</span>
            <span class="vc-nav-item">Exports</span>
            <span class="vc-nav-badge">HD 9:16</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="vc-hero">
        <h1>Turn long videos into ready-to-post shorts.</h1>
        <p>Paste a YouTube link or upload a video to extract the strongest moments with synchronized captions and clean framing.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# PREFERENCES
# =============================================================================
st.markdown('<div class="vc-label">Preferences</div>', unsafe_allow_html=True)
q1, q2, q3 = st.columns(3)

video_type_map = {
    "Full Video (Uncropped Frame)": ("full_video", "full_uncropped"),
    "Wide / Cinematic / Sports": ("wide_video", "full_uncropped"),
    "Gaming / Livestream (Screen + Facecam)": ("gaming", "streamer_split"),
    "Podcast / Two-Person Interview": ("podcast", "podcast_auto"),
    "Solo Speaker (Vertical Crop)": ("informational", "full_fill"),
}
clip_goal_map = {
    "Best Hook & Story Arc": "viral_hook",
    "Funniest / High-Energy Moment": "funny_hype",
    "Key Educational Takeaway": "educational",
    "Motivational Highlight": "motivational",
}
caption_lang_map = {
    "Hinglish (Hindi + English)": "hinglish",
    "English": "english",
    "Original Script": "native",
}

with q1:
    chosen_vtype_label = st.selectbox("Video Format", list(video_type_map.keys()), index=0)
    video_type, default_framing = video_type_map[chosen_vtype_label]

with q2:
    chosen_goal_label = st.selectbox("Highlight Focus", list(clip_goal_map.keys()), index=0)
    clip_goal = clip_goal_map[chosen_goal_label]

with q3:
    chosen_lang_label = st.selectbox("Caption Language", list(caption_lang_map.keys()), index=0)
    caption_lang = caption_lang_map[chosen_lang_label]

fast_heatmap_mode = st.toggle(
    "Fast Mode for Long Streams (jump directly to most-replayed moments)",
    value=(video_type == "gaming"),
)

with st.sidebar:
    st.markdown('<div class="side-section">Frame Layout</div>', unsafe_allow_html=True)
    framing_override_map = {
        "Match Selected Format": default_framing,
        "Full Uncropped Frame": "full_uncropped",
        "Screen + Facecam Split": "streamer_split",
        "Podcast Top / Bottom Split": "podcast_auto",
        "Vertical Face Tracking": "full_fill",
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
    <div class="vc-eta">
        <div>Estimated generation time: <strong>~{eta_low}–{eta_high} seconds</strong></div>
        <div class="vc-eta-muted">Additional clips from the same video load almost instantly.</div>
    </div>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# SOURCE INPUT
# =============================================================================
tab_yt, tab_local = st.tabs(["YouTube / Stream URL", "Local Video File"])

source_to_run: Optional[str] = None
trigger_analysis = False

with tab_yt:
    yt_col1, yt_col2 = st.columns([4.2, 1.2], vertical_alignment="bottom")
    with yt_col1:
        yt_url = st.text_input(
            "Video URL",
            placeholder="https://www.youtube.com/watch?v=...",
            label_visibility="collapsed",
            key="yt_url_input",
            on_change=_clear_previous_clips,
        )
    with yt_col2:
        if st.button("Generate Short", type="primary", use_container_width=True, key="btn_yt"):
            if not yt_url.strip().startswith(("http://", "https://")):
                _clear_previous_clips()
                st.error("Please enter a valid video URL starting with https://")
            else:
                source_to_run = yt_url.strip()
                trigger_analysis = True

with tab_local:
    loc_col1, loc_col2 = st.columns([3.4, 1.6], vertical_alignment="bottom")
    with loc_col1:
        uploaded_vid = st.file_uploader(
            "Upload MP4, MKV, or MOV",
            type=["mp4", "mkv", "mov"],
            on_change=_clear_previous_clips,
            label_visibility="collapsed",
        )
    with loc_col2:
        sample_path = Path("assets/sample.mp4")
        sample_exists = sample_path.exists() and sample_path.stat().st_size > 100000
        if st.button("Use Sample Video", use_container_width=True, disabled=not sample_exists):
            source_to_run = str(sample_path.resolve())
            trigger_analysis = True

    if uploaded_vid is not None:
        if st.button("Generate Short from Upload", type="primary", key="btn_upload"):
            Path("temp").mkdir(parents=True, exist_ok=True)
            save_path = Path("temp") / f"upload_{uploaded_vid.name}"
            if not save_path.exists() or save_path.stat().st_size != uploaded_vid.size:
                save_path.write_bytes(uploaded_vid.getbuffer())
            source_to_run = str(save_path.resolve())
            trigger_analysis = True

live_work_slot = st.container()
results_slot = st.empty()


# =============================================================================
# GENERATION PIPELINE
# =============================================================================
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
                with st.spinner("Finding the best moment in your video..."):
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
                        with st.spinner("Analyzing audio peaks to select top moments..."):
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


# =============================================================================
# RESULTS WORKSPACE
# =============================================================================
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
            f'<div class="vc-label" style="margin-top:1.1rem;">Generated Shorts ({shown_count} of {len(clips)})</div>',
            unsafe_allow_html=True,
        )

        for clip in clips[:shown_count]:
            rank = clip["rank"]
            rendered = st.session_state.rendered_reels.get(rank)

            with st.container(border=True):
                left_col, right_col = st.columns([1.4, 1.0], gap="large")

                with left_col:
                    st.markdown(
                        f"""
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.8rem;">
                            <div>
                                <span class="vc-chip">CLIP #{rank}</span>
                                <span class="vc-time-meta">{_fmt_ts(clip['start'])} – {_fmt_ts(clip['end'])} ({int(round(clip['duration']))}s)</span>
                            </div>
                            <span class="vc-score">Score {clip['virality_score']}/100</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    edited_title = st.text_input(
                        "Opening Title",
                        value=clip["hook_title"],
                        key=f"title_edit_{st.session_state.run_id}_{rank}",
                    )
                    clip["hook_title"] = edited_title

                    if clip.get("reason"):
                        st.markdown(
                            f'<p style="color:#CBD5E1; font-size:0.9rem; margin:0.4rem 0 0.9rem 0;">{clip["reason"]}</p>',
                            unsafe_allow_html=True,
                        )

                    if clip.get("social_caption"):
                        st.markdown('<div class="vc-label" style="margin-bottom:0.35rem;">Suggested Post Caption</div>', unsafe_allow_html=True)
                        st.code(clip["social_caption"], language=None)

                    with st.expander("View Transcript"):
                        preview_txt = " ".join(w["word"] for w in clip.get("words", []))
                        st.write(preview_txt or "Transcript available after rendering.")

                    st.markdown("<div style='height:0.35rem;'></div>", unsafe_allow_html=True)
                    if st.button(
                        "Apply Sidebar Style & Re-Render",
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
                        v_col, _ = st.columns([0.88, 0.12])
                        with v_col:
                            video_bytes = Path(rendered["output_path"]).read_bytes()
                            st.video(video_bytes)
                            st.download_button(
                                label="Download MP4",
                                data=video_bytes,
                                file_name=f"VeloCut_Clip_{rank}.mp4",
                                mime="video/mp4",
                                use_container_width=True,
                                key=f"dl_btn_{st.session_state.run_id}_{rank}",
                            )
                    else:
                        st.info("Click **Apply Sidebar Style & Re-Render** to generate this clip.")

        if shown_count < len(clips):
            next_clip = clips[shown_count]
            next_key = pool.make_key(st.session_state.run_id, active_source, next_clip, render_cfg)
            bg_job = pool.get_job(next_key)
            ready_note = "Ready now" if (bg_job and bg_job["status"] == "done") else "Preparing next highlight"

            st.markdown(
                f"""
                <div class="vc-next-bar">
                    <div class="vc-next-title">Want another highlight from this video?</div>
                    <div class="vc-next-sub">
                        Next: <b>{next_clip['hook_title']}</b> ({_fmt_ts(next_clip['start'])} – {_fmt_ts(next_clip['end'])}) · {ready_note}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            sp_col, btn_col = st.columns([2.6, 1.0])
            with btn_col:
                st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)
                if st.button(
                    f"Generate Clip #{next_clip['rank']}",
                    type="primary",
                    use_container_width=True,
                    key=f"get_next_{st.session_state.run_id}_{next_clip['rank']}",
                ):
                    job_now = pool.get_job(next_key)
                    if job_now and job_now["status"] == "done" and job_now.get("result"):
                        st.session_state.rendered_reels[next_clip["rank"]] = job_now["result"]
                        if job_now.get("words"):
                            next_clip["words"] = job_now["words"]
                            next_clip["needs_word_sync"] = False
                        upd = job_now.get("updated_meta") or {}
                        for k_m in ("hook_title", "reason", "social_caption"):
                            if upd.get(k_m):
                                next_clip[k_m] = upd[k_m]
                        next_clip["needs_title_from_clip"] = False
                        st.session_state.shown_count += 1
                        _kickoff_next_background_clip(
                            st.session_state.run_id, active_source, clips, st.session_state.shown_count, render_cfg
                        )
                        st.rerun()
                    elif job_now and job_now["status"] == "running":
                        with st.spinner("Finishing your next clip..."):
                            done_job = pool.wait_for_job(next_key, timeout=120.0)
                        if done_job and done_job["status"] == "done" and done_job.get("result"):
                            st.session_state.rendered_reels[next_clip["rank"]] = done_job["result"]
                            if done_job.get("words"):
                                next_clip["words"] = done_job["words"]
                                next_clip["needs_word_sync"] = False
                            upd = done_job.get("updated_meta") or {}
                            for k_m in ("hook_title", "reason", "social_caption"):
                                if upd.get(k_m):
                                    next_clip[k_m] = upd[k_m]
                            next_clip["needs_title_from_clip"] = False
                            st.session_state.shown_count += 1
                            _kickoff_next_background_clip(
                                st.session_state.run_id, active_source, clips, st.session_state.shown_count, render_cfg
                            )
                            st.rerun()
                        else:
                            st.error("Unable to generate the next clip right now.")
                    else:
                        try:
                            _render_clip_clean(active_source, next_clip, render_cfg)
                            st.session_state.shown_count += 1
                            _kickoff_next_background_clip(
                                st.session_state.run_id, active_source, clips, st.session_state.shown_count, render_cfg
                            )
                            st.rerun()
                        except Exception as e:
                            st.error(f"Could not render clip: {e}")

        st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
        with st.expander("View Video Engagement Timeline"):
            st.plotly_chart(
                _build_timeline_chart(analysis["energy_curve"], clips, shown_count),
                use_container_width=True,
            )