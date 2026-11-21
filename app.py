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
from marketing_ai import (
    generate_viral_thumbnail,
    extract_thumbnail_frame,
    get_recommended_frame_timestamps,
    generate_social_suite,
)

# =============================================================================
# PAGE CONFIG & CLIPPULSE STUDIO v4 — LIQUID GLASS DESIGN SYSTEM
# =============================================================================
st.set_page_config(
    page_title="ClipPulse Studio — AI Short-Form Video Generator",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Anton&family=Bangers&family=Inter:wght@400;500;600;700&family=Montserrat:ital,wght@0,700;0,800;0,900;1,800;1,900&family=Playfair+Display:ital,wght@0,700;1,700;1,900&family=Plus+Jakarta+Sans:wght@500;600;700;800;900&family=Poppins:wght@600;700;800;900&display=swap');

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

    /* Main Container */
    .block-container {
        padding-top: 0.8rem !important;
        padding-bottom: 3.5rem !important;
        max-width: 1140px !important;
    }

    /* ======== LIQUID GLASS SIDEBAR ======== */
    @keyframes liquidShift {
        0% { background-position: 0% 0%; }
        50% { background-position: 100% 100%; }
        100% { background-position: 0% 0%; }
    }
    @keyframes pulseGlow {
        0%, 100% { box-shadow: 0 0 15px rgba(99, 102, 241, 0.25); border-color: rgba(99, 102, 241, 0.35); }
        50% { box-shadow: 0 0 30px rgba(168, 85, 247, 0.45); border-color: rgba(168, 85, 247, 0.65); }
    }
    @keyframes timerPulse {
        0%, 100% { border-color: rgba(99, 102, 241, 0.4); box-shadow: 0 0 16px rgba(99, 102, 241, 0.2); }
        50% { border-color: rgba(6, 182, 212, 0.7); box-shadow: 0 0 28px rgba(6, 182, 212, 0.35); }
    }

    section[data-testid="stSidebar"] {
        background: linear-gradient(165deg, rgba(8, 11, 22, 0.94) 0%, rgba(18, 14, 38, 0.90) 50%, rgba(6, 9, 18, 0.96) 100%) !important;
        backdrop-filter: blur(28px) saturate(190%) !important;
        border-right: 1px solid rgba(99, 102, 241, 0.18) !important;
        position: relative !important;
    }
    section[data-testid="stSidebar"]::after {
        content: '';
        position: absolute;
        top: 0; right: 0; bottom: 0; width: 2.5px;
        background: linear-gradient(180deg, #6366F1 0%, #A855F7 35%, #06B6D4 70%, #6366F1 100%);
        background-size: 100% 300%;
        animation: liquidShift 6s ease infinite;
        opacity: 0.75;
    }
    section[data-testid="stSidebar"] .block-container {
        padding-top: 1.1rem !important;
    }

    .cp-side-brand {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 0.76rem;
        font-weight: 800;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        background: linear-gradient(135deg, #818CF8 0%, #C084FC 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        display: flex;
        align-items: center;
        gap: 0.45rem;
        margin-bottom: 0.9rem;
    }
    .cp-glass-card {
        background: rgba(18, 22, 38, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 14px;
        padding: 0.85rem 0.95rem;
        margin-bottom: 0.75rem;
        backdrop-filter: blur(16px);
        transition: all 0.2s ease;
    }
    .cp-glass-card:hover {
        border-color: rgba(168, 85, 247, 0.35);
        background: rgba(22, 28, 48, 0.7);
    }
    .side-section {
        font-size: 0.73rem;
        font-weight: 700;
        letter-spacing: 0.09em;
        text-transform: uppercase;
        color: #94A3B8;
        margin-top: 0.85rem;
        margin-bottom: 0.35rem;
    }

    /* ======== FLOATING ANNOUNCEMENT BANNER ======== */
    .cp-top-banner {
        background: linear-gradient(90deg, rgba(99, 102, 241, 0.16) 0%, rgba(168, 85, 247, 0.22) 50%, rgba(6, 182, 212, 0.16) 100%);
        border: 1px solid rgba(168, 85, 247, 0.35);
        border-radius: 999px;
        padding: 0.45rem 1.15rem;
        font-size: 0.82rem;
        font-weight: 500;
        color: #E2E8F0;
        text-align: center;
        margin-bottom: 1.1rem;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0.5rem;
        backdrop-filter: blur(14px);
    }
    .cp-top-banner strong {
        color: #FFFFFF;
        font-weight: 700;
    }
    .cp-banner-pill {
        background: #6366F1;
        color: #FFFFFF;
        font-size: 0.66rem;
        font-weight: 700;
        text-transform: uppercase;
        padding: 0.15rem 0.52rem;
        border-radius: 999px;
        letter-spacing: 0.04em;
    }

    /* ======== NAVBAR ======== */
    .cp-navbar {
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
    .cp-brand {
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }
    .cp-wordmark {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 1.35rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        color: #FFFFFF;
        display: flex;
        align-items: center;
        gap: 0.35rem;
    }
    .cp-wordmark span {
        background: linear-gradient(135deg, #818CF8 0%, #C084FC 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .cp-version-badge {
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
    .cp-nav-status {
        display: flex;
        align-items: center;
        gap: 0.6rem;
        font-size: 0.82rem;
        color: #94A3B8;
    }
    .cp-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #10B981;
        box-shadow: 0 0 10px #10B981;
    }

    /* ======== HERO ======== */
    .cp-hero {
        text-align: center;
        margin: 1.2rem auto 2.2rem auto;
        max-width: 980px;
    }
    .cp-hero-chip {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.14);
        border-radius: 999px;
        padding: 0.38rem 1.15rem;
        font-size: 0.78rem;
        font-weight: 700;
        color: #94A3B8;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        margin-bottom: 1.2rem;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
    }
    .cp-hero-title {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: clamp(2.1rem, 4.4vw, 3.4rem);
        font-weight: 800;
        letter-spacing: -0.035em;
        color: #FFFFFF;
        line-height: 1.24;
        margin: 0;
    }
    .cp-title-top {
        color: #FFFFFF;
    }
    .cp-title-bottom {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 0.65rem;
        flex-wrap: wrap;
        margin-top: 0.4rem;
        vertical-align: middle;
    }

    /* Modern sleek rectangular glass badge (non-pill, rectangular with crisp 10px corners) */
    .cp-modern-badge {
        position: relative;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        vertical-align: middle;
        margin: 0 0.2rem;
        padding: 0.18rem 1.15rem;
        border-radius: 10px;
        background: rgba(16, 21, 35, 0.82);
        border: 1.5px solid rgba(129, 140, 248, 0.4);
        box-shadow: 0 10px 32px rgba(0, 0, 0, 0.6), inset 0 0 16px rgba(99, 102, 241, 0.2);
        backdrop-filter: blur(28px) saturate(180%);
        -webkit-backdrop-filter: blur(28px) saturate(180%);
        overflow: hidden;
        line-height: 1.2;
    }
    .cp-badge-aurora {
        position: absolute;
        inset: -80%;
        background: radial-gradient(circle at 25% 35%, rgba(244, 114, 182, 0.55) 0%, transparent 45%),
                    radial-gradient(circle at 75% 65%, rgba(56, 189, 248, 0.5) 0%, transparent 45%),
                    radial-gradient(circle at 45% 80%, rgba(168, 85, 247, 0.5) 0%, transparent 50%),
                    radial-gradient(circle at 80% 25%, rgba(251, 146, 60, 0.45) 0%, transparent 45%),
                    rgba(255, 255, 255, 0.05);
        filter: blur(22px);
        animation: cpAuroraSwirl 10s ease-in-out infinite alternate;
        pointer-events: none;
    }
    @keyframes cpAuroraSwirl {
        0% { transform: rotate(0deg) scale(1.0) translate(0px, 0px); }
        50% { transform: rotate(180deg) scale(1.35) translate(-25px, 15px); }
        100% { transform: rotate(360deg) scale(1.05) translate(15px, -15px); }
    }
    .cp-words-grid {
        display: inline-grid;
        place-items: center;
        position: relative;
        z-index: 2;
    }
    .cp-word {
        grid-area: 1 / 1;
        font-family: inherit;
        font-size: 1em;
        font-weight: 800;
        color: #FFFFFF;
        white-space: nowrap;
        letter-spacing: -0.02em;
        text-shadow: 0 2px 14px rgba(0, 0, 0, 0.7);
        line-height: 1.25;
        text-transform: capitalize;
    }
    .cp-word.w1 {
        animation: wordCycle1 9s cubic-bezier(0.16, 1, 0.3, 1) infinite;
    }
    .cp-word.w2 {
        animation: wordCycle2 9s cubic-bezier(0.16, 1, 0.3, 1) infinite;
    }
    .cp-word.w3 {
        animation: wordCycle3 9s cubic-bezier(0.16, 1, 0.3, 1) infinite;
    }
    @keyframes wordCycle1 {
        0% { opacity: 1; transform: translateY(0) scale(1); filter: blur(0); }
        28% { opacity: 1; transform: translateY(0) scale(1); filter: blur(0); }
        32% { opacity: 0; transform: translateY(-8px) scale(0.97); filter: blur(3px); }
        33.3%, 95% { opacity: 0; transform: translateY(8px) scale(0.97); filter: blur(3px); }
        98% { opacity: 0; transform: translateY(8px) scale(0.97); filter: blur(3px); }
        100% { opacity: 1; transform: translateY(0) scale(1); filter: blur(0); }
    }
    @keyframes wordCycle2 {
        0%, 28% { opacity: 0; transform: translateY(8px) scale(0.97); filter: blur(3px); }
        33.3% { opacity: 1; transform: translateY(0) scale(1); filter: blur(0); }
        61% { opacity: 1; transform: translateY(0) scale(1); filter: blur(0); }
        65% { opacity: 0; transform: translateY(-8px) scale(0.97); filter: blur(3px); }
        66.6%, 100% { opacity: 0; transform: translateY(8px) scale(0.97); filter: blur(3px); }
    }
    @keyframes wordCycle3 {
        0%, 61% { opacity: 0; transform: translateY(8px) scale(0.97); filter: blur(3px); }
        66.6% { opacity: 1; transform: translateY(0) scale(1); filter: blur(0); }
        94% { opacity: 1; transform: translateY(0) scale(1); filter: blur(0); }
        98% { opacity: 0; transform: translateY(-8px) scale(0.97); filter: blur(3px); }
        100% { opacity: 0; transform: translateY(8px) scale(0.97); filter: blur(3px); }
    }
    .cp-gradient-text {
        background: linear-gradient(135deg, #FFFFFF 20%, #A5B4FC 60%, #C084FC 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .cp-hero p, .cp-hero-sub {
        font-size: clamp(1.0rem, 1.8vw, 1.15rem);
        color: #94A3B8;
        line-height: 1.6;
        max-width: 780px;
        margin: 1.3rem auto 0 auto;
    }
    @media (max-width: 768px) {
        .cp-hero-title {
            font-size: 1.85rem !important;
        }
        .cp-title-bottom {
            flex-direction: column;
            gap: 0.4rem;
        }
        .cp-modern-badge {
            padding: 0.15rem 0.85rem;
            border-radius: 8px;
        }
    }

    /* ======== INPUT CARD ======== */
    .cp-input-card {
        background: linear-gradient(180deg, rgba(19, 23, 36, 0.8) 0%, rgba(13, 16, 26, 0.95) 100%);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 20px;
        padding: 1.4rem;
        box-shadow: 0 16px 48px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(99, 102, 241, 0.15);
        margin-bottom: 1.5rem;
        backdrop-filter: blur(24px);
    }

    /* ======== LIVE COUNTDOWN TIMER ======== */
    .cp-timer-box {
        background: linear-gradient(135deg, rgba(16, 20, 36, 0.85) 0%, rgba(20, 15, 42, 0.85) 100%);
        border: 1.5px solid rgba(99, 102, 241, 0.4);
        border-radius: 16px;
        padding: 1.1rem 1.4rem;
        margin: 1.2rem 0;
        animation: timerPulse 2.5s ease-in-out infinite;
        backdrop-filter: blur(20px);
    }
    .cp-timer-grid {
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 1rem;
    }
    .cp-timer-clock {
        font-family: 'Plus Jakarta Sans', monospace;
        font-size: 2.1rem;
        font-weight: 800;
        color: #FFFFFF;
        letter-spacing: -0.02em;
    }

    /* ======== BUTTONS ======== */
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

    /* ======== TABS ======== */
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

    /* ======== INPUTS ======== */
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

    /* ======== FONT PATTERNS FOR CAPTION PRESETS (ORIGINAL STYLES) ======== */
    .font-pattern-hormozi {
        font-family: 'Montserrat', sans-serif !important;
        font-weight: 900 !important;
        text-transform: uppercase !important;
        color: #39FF14 !important;
        letter-spacing: 0.05em !important;
        text-shadow: 0 0 10px rgba(57, 255, 20, 0.5) !important;
        transform: rotate(-1.5deg);
        display: inline-block;
    }
    .font-pattern-beast {
        font-family: 'Bangers', cursive, sans-serif !important;
        font-size: 1.25rem !important;
        letter-spacing: 1.5px !important;
        color: #FFD000 !important;
        text-shadow: 1px 1px 0px #000, 2px 2px 0px #FF731D !important;
        display: inline-block;
    }
    .font-pattern-neon {
        font-family: 'Anton', sans-serif !important;
        letter-spacing: 1.2px !important;
        text-transform: uppercase !important;
        color: #00F0FF !important;
        text-shadow: 0 0 12px rgba(0, 240, 255, 0.8), 0 0 20px rgba(0, 240, 255, 0.4) !important;
        display: inline-block;
    }
    .font-pattern-minimal {
        font-family: 'Poppins', sans-serif !important;
        font-weight: 600 !important;
        color: #F8FAFC !important;
        letter-spacing: 0.02em !important;
        display: inline-block;
    }
    .font-pattern-submagic {
        font-family: 'Montserrat', sans-serif !important;
        font-weight: 800 !important;
        background: #FFE614 !important;
        color: #0A0D14 !important;
        padding: 0.15rem 0.6rem !important;
        border-radius: 6px !important;
        text-transform: uppercase !important;
        display: inline-block;
        letter-spacing: 0.02em !important;
    }
    .font-pattern-editorial {
        font-family: 'Playfair Display', serif !important;
        font-style: italic !important;
        font-weight: 700 !important;
        font-size: 1.15rem !important;
        color: #FFD048 !important;
        text-shadow: 0 0 8px rgba(255, 208, 72, 0.4) !important;
        display: inline-block;
    }

    /* BaseWeb Selectbox Dropdown Menu Options Styled in their EXACT Font Patterns */
    ul[role="listbox"] li:nth-child(1),
    div[data-baseweb="popover"] li:nth-child(1) {
        font-family: 'Montserrat', sans-serif !important;
        font-weight: 900 !important;
        text-transform: uppercase !important;
        color: #39FF14 !important;
        letter-spacing: 0.05em !important;
        text-shadow: 0 0 8px rgba(57, 255, 20, 0.45) !important;
        background: #090B12 !important;
        padding: 10px 14px !important;
    }
    ul[role="listbox"] li:nth-child(2),
    div[data-baseweb="popover"] li:nth-child(2) {
        font-family: 'Bangers', cursive, sans-serif !important;
        font-size: 1.25rem !important;
        letter-spacing: 1.5px !important;
        color: #FFD000 !important;
        text-shadow: 1px 1px 0px #000, 2px 2px 0px #FF731D !important;
        background: #10131E !important;
        padding: 10px 14px !important;
    }
    ul[role="listbox"] li:nth-child(3),
    div[data-baseweb="popover"] li:nth-child(3) {
        font-family: 'Anton', sans-serif !important;
        font-size: 1.15rem !important;
        letter-spacing: 1.2px !important;
        text-transform: uppercase !important;
        color: #00F0FF !important;
        text-shadow: 0 0 10px rgba(0, 240, 255, 0.8) !important;
        background: #090E1A !important;
        padding: 10px 14px !important;
    }
    ul[role="listbox"] li:nth-child(4),
    div[data-baseweb="popover"] li:nth-child(4) {
        font-family: 'Poppins', sans-serif !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
        color: #F8FAFC !important;
        background: #0F1322 !important;
        padding: 10px 14px !important;
    }
    ul[role="listbox"] li:nth-child(5),
    div[data-baseweb="popover"] li:nth-child(5) {
        font-family: 'Montserrat', sans-serif !important;
        font-weight: 800 !important;
        color: #0A0D14 !important;
        background: #FFE614 !important;
        border-radius: 6px !important;
        margin: 4px 8px !important;
        padding: 8px 14px !important;
        text-transform: uppercase !important;
    }
    ul[role="listbox"] li:nth-child(6),
    div[data-baseweb="popover"] li:nth-child(6) {
        font-family: 'Playfair Display', serif !important;
        font-style: italic !important;
        font-weight: 700 !important;
        font-size: 1.15rem !important;
        color: #FFD048 !important;
        text-shadow: 0 0 8px rgba(255, 208, 72, 0.4) !important;
        background: #14120F !important;
        padding: 10px 14px !important;
    }

    .cp-font-preview-box {
        border-radius: 12px;
        padding: 0.75rem 0.9rem;
        text-align: center;
        margin-top: 0.55rem;
        margin-bottom: 0.65rem;
        backdrop-filter: blur(16px);
        transition: all 0.25s ease;
    }

    /* ======== ETA BAR ======== */
    .cp-eta {
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
    .cp-eta strong {
        color: #FFFFFF;
        font-weight: 700;
    }

    /* ======== FEATURE CARDS ======== */
    .cp-feature-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 1.1rem;
        margin: 1.5rem 0 2.2rem 0;
    }
    .cp-feat-card {
        background: linear-gradient(180deg, rgba(20, 24, 38, 0.75) 0%, rgba(13, 16, 26, 0.85) 100%);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 1.2rem;
        transition: all 0.22s cubic-bezier(0.16, 1, 0.3, 1);
        backdrop-filter: blur(16px);
    }
    .cp-feat-card:hover {
        transform: translateY(-3px);
        border-color: rgba(168, 85, 247, 0.4);
        box-shadow: 0 12px 30px rgba(99, 102, 241, 0.15);
    }
    .cp-feat-icon {
        font-size: 1.6rem;
        margin-bottom: 0.65rem;
        display: inline-block;
    }
    .cp-feat-title {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 0.98rem;
        font-weight: 700;
        color: #FFFFFF;
        margin-bottom: 0.3rem;
        display: flex;
        align-items: center;
        gap: 0.45rem;
    }
    .cp-feat-desc {
        font-size: 0.84rem;
        color: #94A3B8;
        line-height: 1.45;
    }
    .cp-badge-active {
        font-size: 0.62rem;
        font-weight: 800;
        background: #10B981;
        color: #FFFFFF;
        padding: 0.12rem 0.48rem;
        border-radius: 999px;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    .cp-badge-roadmap {
        font-size: 0.62rem;
        font-weight: 800;
        background: rgba(245, 158, 11, 0.2);
        border: 1px solid rgba(245, 158, 11, 0.45);
        color: #FCD34D;
        padding: 0.12rem 0.48rem;
        border-radius: 999px;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }

    /* ======== VIRALITY BADGES ======== */
    .cp-virality-badge {
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
    .cp-meta-pill {
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

    /* ======== TEMPLATES ======== */
    .cp-tpl-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
        gap: 1.1rem;
        margin: 1.2rem 0 2rem 0;
    }
    .cp-tpl-card {
        background: #0F131E;
        border: 1px solid rgba(255, 255, 255, 0.09);
        border-radius: 16px;
        padding: 1.25rem;
        text-align: center;
        transition: all 0.2s ease;
    }
    .cp-tpl-card:hover {
        border-color: #818CF8;
        transform: translateY(-3px);
    }
    .cp-tpl-preview {
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
            out_file = f"outputs/clippulse_r{clip_copy['rank']}_{int(time.time() * 1000)}.mp4"
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
if "generation_start_time" not in st.session_state:
    st.session_state.generation_start_time = None
if "first_clip_duration_record" not in st.session_state:
    st.session_state.first_clip_duration_record = None


def _clear_previous_clips():
    st.session_state.analysis = None
    st.session_state.active_source = None
    st.session_state.rendered_reels = {}
    st.session_state.shown_count = 1
    st.session_state.run_id = f"run_{int(time.time() * 1000)}"
    st.session_state.generation_start_time = None
    st.session_state.first_clip_duration_record = None


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
    key_str = f"clippulse_v4|{source}|{video_type}|{clip_goal}|{fast_heatmap}|{min_dur}|{max_dur}"
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
    base = 6 if fast_heatmap_mode else 10
    cv = 0 if eff in ("full_uncropped", "wide_cinematic", "blurred_fill") else int(round(avg_dur * 0.05))
    enc = max(4, int(round(avg_dur * (0.10 if nvenc_ok else 0.24))))
    mid = base + cv + enc
    return max(8, mid - 3), mid + 5


def _clean_progress_text(frac: float, raw_label: str) -> str:
    if frac < 0.22:
        return "Step 1/4: Fetching video stream & extracting audio (~3s)..."
    if frac < 0.38:
        return "Step 2/4: Transcribing speech & word alignment via Whisper (~5s)..."
    if frac < 0.50:
        return "Step 3/4: Framing 9:16 layout & 3D emojis (~4s)..."
    if frac >= 0.99:
        return "Step 4/4: Finalizing Ultra-HD Short..."
    m = re.search(r"~(\d+s)", raw_label)
    if m:
        return f"Step 4/4: Encoding HQ Reel ({int(frac * 100)}%) — about {m.group(1)} remaining"
    return f"Step 4/4: Encoding HQ Reel ({int(frac * 100)}%)..."


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


def _render_clip_clean(source: str, clip: Dict[str, Any], cfg: Dict[str, Any], timer_placeholder=None, est_sec: int = 24):
    rank = clip["rank"]
    out_file = f"outputs/clippulse_r{rank}_{int(time.time() * 1000)}.mp4"

    pbar = st.progress(0.04, text="Preparing your short...")
    t_start = time.time()

    def pcb(frac: float, label: str):
        elapsed = time.time() - t_start
        rem = max(1, int(round(est_sec - elapsed))) if elapsed < est_sec else 2
        pbar.progress(frac, text=_clean_progress_text(frac, label))
        if timer_placeholder is not None:
            timer_placeholder.markdown(
                f"""
                <div class="cp-timer-box">
                    <div class="cp-timer-grid">
                        <div>
                            <div style="font-size:0.72rem; font-weight:800; text-transform:uppercase; letter-spacing:0.12em; color:#818CF8; margin-bottom:0.2rem;">⏱️ PRECISE ESTIMATE TIMER</div>
                            <div class="cp-timer-clock">{elapsed:.1f}s <span style="font-size:1.1rem; color:#94A3B8; font-weight:600;">/ ~{est_sec}s target</span></div>
                        </div>
                        <div style="text-align:right;">
                            <div style="font-size:0.75rem; color:#A5B4FC; font-weight:700;">First Clip Delivery: <span style="color:#10B981;">~{rem}s remaining</span></div>
                            <div style="font-size:0.75rem; color:#94A3B8;">Status: {_clean_progress_text(frac, label).split('(')[0]}</div>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

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
# SIDEBAR — LIQUID GLASS STUDIO CONTROLS
# =============================================================================
nvenc_ok = check_nvenc_available()

with st.sidebar:
    st.markdown('<div class="cp-side-brand">⚡ ClipPulse Studio</div>', unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="side-section">Clip Duration (Seconds)</div>', unsafe_allow_html=True)
        dur_range = st.slider("Target Duration", 15, 90, (30, 50), label_visibility="collapsed")
        min_dur, max_dur = dur_range

        st.markdown('<div class="side-section">Animated Caption Preset</div>', unsafe_allow_html=True)
        # Display friendly names
        style_list = list(STYLE_PRESETS.keys())
        # Put Pulse Hormozi first if present
        if "Pulse Hormozi" in style_list:
            style_list.remove("Pulse Hormozi")
            style_list.insert(0, "Pulse Hormozi")
        if "Opus Hormozi" in style_list:
            style_list.remove("Opus Hormozi")

        if "active_caption_preset" not in st.session_state:
            st.session_state.active_caption_preset = style_list[0]

        cur_idx = style_list.index(st.session_state.active_caption_preset) if st.session_state.active_caption_preset in style_list else 0
        style_name = st.selectbox(
            "Caption Template",
            style_list,
            index=cur_idx,
            label_visibility="collapsed",
            key="sb_caption_template_select",
        )
        st.session_state.active_caption_preset = style_name

        # Live Font Pattern Badge — Written in each font's exact authentic typography pattern!
        font_style_previews = {
            "Pulse Hormozi": """
                <div class="cp-font-preview-box" style="background:#05070B; border:1.5px solid #39FF14; box-shadow:0 0 16px rgba(57,255,20,0.3);">
                    <div class="font-pattern-hormozi" style="font-size:1.4rem;">PULSE HORMOZI</div>
                    <div style="font-size:0.72rem; color:#86EFAC; margin-top:5px; font-weight:600;">Font: Montserrat-ExtraBold (Tilted Green)</div>
                </div>
            """,
            "Beast Mode": """
                <div class="cp-font-preview-box" style="background:#10131E; border:1.5px solid #FFD000; box-shadow:0 0 16px rgba(255,208,0,0.3);">
                    <div class="font-pattern-beast" style="font-size:1.6rem;">BEAST MODE 🔥</div>
                    <div style="font-size:0.72rem; color:#FDE68A; margin-top:4px; font-weight:600;">Font: Bangers-Regular (Comic Impact)</div>
                </div>
            """,
            "Neon Cyber": """
                <div class="cp-font-preview-box" style="background:#070A14; border:1.5px solid #00F0FF; box-shadow:0 0 18px rgba(0,240,255,0.35);">
                    <div class="font-pattern-neon" style="font-size:1.4rem;">NEON CYBER 🤖</div>
                    <div style="font-size:0.72rem; color:#7DD3FC; margin-top:5px; font-weight:600;">Font: Anton-Regular (Electric Cyan)</div>
                </div>
            """,
            "Minimal Glass": """
                <div class="cp-font-preview-box" style="background:#0F1322; border:1.5px solid rgba(255,255,255,0.25); box-shadow:0 0 14px rgba(255,255,255,0.12);">
                    <div class="font-pattern-minimal" style="font-size:1.2rem;">Minimal Glass</div>
                    <div style="font-size:0.72rem; color:#94A3B8; margin-top:5px; font-weight:600;">Font: Poppins-ExtraBold (Clean Sans)</div>
                </div>
            """,
            "Submagic Pill": """
                <div class="cp-font-preview-box" style="background:#0E111C; border:1.5px solid #FFE614; box-shadow:0 0 16px rgba(255,230,20,0.3);">
                    <div class="font-pattern-submagic" style="font-size:1.15rem;">SUBMAGIC PILL</div>
                    <div style="font-size:0.72rem; color:#FDE68A; margin-top:7px; font-weight:600;">Font: Montserrat-ExtraBold (Active Yellow Pill)</div>
                </div>
            """,
            "Editorial Gold": """
                <div class="cp-font-preview-box" style="background:#12100C; border:1.5px solid #FFD048; box-shadow:0 0 16px rgba(255,208,72,0.3);">
                    <div class="font-pattern-editorial" style="font-size:1.35rem;">Editorial Gold</div>
                    <div style="font-size:0.72rem; color:#FDE68A; margin-top:5px; font-weight:600;">Font: PlayfairDisplay-BoldItalic (Luxury Serif)</div>
                </div>
            """,
        }
        st.markdown(font_style_previews.get(style_name, ""), unsafe_allow_html=True)

        st.markdown('<div class="side-section">Camera & Motion</div>', unsafe_allow_html=True)
        trans_map = {
            "Smooth Cuts & Subtle Camera": "smooth_subtle",
            "Blur Whip & Zoom": "blur_whip",
            "Flash Cut & Zoom": "flash_zoom",
            "Smooth Cross-Dissolve": "cross_dissolve",
            "Static Camera (No Motion / Zoom)": "still_static",
        }
        trans_label = st.selectbox("Transition Style", list(trans_map.keys()), index=0, label_visibility="collapsed")
        transition_style = trans_map[trans_label]

        st.markdown('<div class="side-section">Visual Enhancements</div>', unsafe_allow_html=True)
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

        st.markdown('<div class="side-section">Background Music (Optional)</div>', unsafe_allow_html=True)
        bg_music_file = st.file_uploader("Upload MP3 or WAV", type=["mp3", "wav"], label_visibility="collapsed")
        bg_music_path: Optional[str] = None
        if bg_music_file is not None:
            bg_save = Path("temp") / f"bgm_{bg_music_file.name}"
            bg_save.write_bytes(bg_music_file.getbuffer())
            bg_music_path = str(bg_save)

        st.markdown('<div class="side-section">AI Engine & Auth</div>', unsafe_allow_html=True)
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
# TOP ANNOUNCEMENT BANNER & NAVBAR
# =============================================================================
st.markdown(
    """
    <div class="cp-top-banner">
        <span class="cp-banner-pill">AI Engine</span>
        <span><b>ClipPulse AI Engine Active</b> • 1 Long Video to 10 Ready-to-Post Viral Shorts in 1-Click • Whisper Turbo + Groq LPU</span>
    </div>
    <div class="cp-navbar">
        <div class="cp-brand">
            <svg width="34" height="34" viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect width="36" height="36" rx="10" fill="url(#cp_grad)"/>
                <path d="M7 18H12L15 9L21 27L24 18H29" stroke="#FFFFFF" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>
                <circle cx="29" cy="18" r="2.2" fill="#00F0FF"/>
                <defs>
                    <linearGradient id="cp_grad" x1="0" y1="0" x2="36" y2="36" gradientUnits="userSpaceOnUse">
                        <stop stop-color="#4F46E5"/>
                        <stop offset="0.5" stop-color="#7C3AED"/>
                        <stop offset="1" stop-color="#06B6D4"/>
                    </linearGradient>
                </defs>
            </svg>
            <div class="cp-wordmark">Clip<span>Pulse</span> <span style="font-size:0.95rem; font-weight:600; color:#94A3B8;">Studio</span></div>
        </div>
        <div class="cp-nav-status">
            <div class="cp-dot"></div>
            <span>Ultra-Fast LPU Engine Online</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Top Navigation Tabs
tab_studio, tab_templates, tab_features, tab_virality, tab_pro = st.tabs([
    "🎬 Studio",
    "🎨 Caption Styles",
    "⚡ Built-in Features & Roadmap",
    "🎯 Virality AI™",
    "💎 Pro Exports",
])


# =============================================================================
# TAB 1: 🎬 STUDIO (CORE VIDEO GENERATOR & EDITOR)
# =============================================================================
with tab_studio:
    st.markdown(
        """
        <div class="cp-hero">
            <div class="cp-hero-chip">#1 AI Video Editor & Clipping Tool</div>
            <h1 class="cp-hero-title">
                <div class="cp-title-top">Turn any Video into</div>
                <div class="cp-title-bottom">
                    <span class="cp-modern-badge">
                        <span class="cp-badge-aurora"></span>
                        <span class="cp-words-grid">
                            <span class="cp-word w1">Viral Shorts</span>
                            <span class="cp-word w2">Ready-To-Post Clips</span>
                            <span class="cp-word w3">10x Reach</span>
                        </span>
                    </span>
                </div>
            </h1>
            <p class="cp-hero-sub">
                Paste a link or drop a raw take, and ClipPulse clips, edits, sizes and publishes them to all social platforms in one click.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # -------------------------------------------------------------------------
    # UNIFIED INPUT CONSOLE
    # -------------------------------------------------------------------------
    source_to_run: Optional[str] = None
    trigger_analysis = False

    st.markdown('<div class="cp-input-card">', unsafe_allow_html=True)
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
            if st.button("⚡ Generate Shorts", type="primary", use_container_width=True, key="btn_yt"):
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
    mid_eta = int(round((eta_low + eta_high) / 2.0))

    st.markdown(
        f"""
        <div class="cp-eta">
            <div>⏱️ Precise First-Clip Delivery: <strong>~{mid_eta} seconds</strong> ({eta_low}–{eta_high}s based on {'GPU NVENC' if nvenc_ok else 'CPU'})</div>
            <div style="color:#94A3B8; font-size:0.82rem;">Parallel background pre-rendering active for instant multi-clip delivery.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # PIPELINE EXECUTION & RESULTS
    # -------------------------------------------------------------------------
    timer_slot = st.empty()
    live_work_slot = st.container()
    results_slot = st.empty()

    if trigger_analysis and source_to_run:
        _clear_previous_clips()
        results_slot.empty()
        st.session_state.generation_start_time = time.time()
        start_ts = st.session_state.generation_start_time

        # Initial Precise Timer Card
        timer_slot.markdown(
            f"""
            <div class="cp-timer-box">
                <div class="cp-timer-grid">
                    <div>
                        <div style="font-size:0.72rem; font-weight:800; text-transform:uppercase; letter-spacing:0.12em; color:#818CF8; margin-bottom:0.2rem;">⏱️ PRECISE ESTIMATE TIMER</div>
                        <div class="cp-timer-clock">0.0s <span style="font-size:1.1rem; color:#94A3B8; font-weight:600;">/ ~{mid_eta}s target</span></div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-size:0.75rem; color:#A5B4FC; font-weight:700;">First Clip Delivery: <span style="color:#10B981;">~{mid_eta}s remaining</span></div>
                        <div style="font-size:0.75rem; color:#94A3B8;">Status: Initializing AI engine & analyzing video...</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

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
                        timer_placeholder=timer_slot,
                        est_sec=mid_eta,
                    )
                    total_dur = round(time.time() - start_ts, 1)
                    st.session_state.first_clip_duration_record = total_dur
                    timer_slot.markdown(
                        f"""
                        <div class="cp-timer-box" style="border-color:#10B981; animation:none; box-shadow: 0 0 24px rgba(16, 185, 129, 0.25);">
                            <div class="cp-timer-grid">
                                <div>
                                    <div style="font-size:0.72rem; font-weight:800; text-transform:uppercase; letter-spacing:0.12em; color:#10B981; margin-bottom:0.2rem;">🎉 FIRST CLIP DELIVERED</div>
                                    <div class="cp-timer-clock" style="color:#10B981;">{total_dur}s <span style="font-size:1.1rem; color:#A7F3D0; font-weight:600;">(Target: ~{mid_eta}s)</span></div>
                                </div>
                                <div style="text-align:right;">
                                    <div style="font-size:0.8rem; color:#FFFFFF; font-weight:700;">1080p 60fps HD Short Ready</div>
                                    <div style="font-size:0.75rem; color:#94A3B8;">Subtitles (.SRT) and MP4 available below</div>
                                </div>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
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

            speed_note = ""
            if st.session_state.first_clip_duration_record:
                speed_note = f"⚡ First clip rendered in {st.session_state.first_clip_duration_record}s • "

            st.markdown(
                f"""
                <div style="display:flex; justify-content:space-between; align-items:center; margin: 1.5rem 0 1rem 0;">
                    <div style="font-family:'Plus Jakarta Sans', sans-serif; font-size:1.25rem; font-weight:800; color:#FFFFFF;">
                        ✨ Generated Viral Shorts ({shown_count} of {len(clips)})
                    </div>
                    <div style="color:#94A3B8; font-size:0.86rem; font-weight:600;">
                        {speed_note}1080p 60fps HD • Kinetic Captions Ready
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
                                    <span class="cp-meta-pill">CLIP #{rank}</span>
                                    <span class="cp-meta-pill">{_fmt_ts(clip['start'])} – {_fmt_ts(clip['end'])}</span>
                                    <span class="cp-meta-pill">{int(round(clip['duration']))}s</span>
                                </div>
                                <div class="cp-virality-badge">🔥 {virality_val} Virality Score</div>
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
                                slug = clip['hook_title'][:20].replace(' ', '_')
                                st.download_button(
                                    label="📥 Download MP4",
                                    data=video_bytes,
                                    file_name=f"ClipPulse_{rank}_{slug}.mp4",
                                    mime="video/mp4",
                                    use_container_width=True,
                                    key=f"dl_btn_{st.session_state.run_id}_{rank}",
                                )
                            with dl_c2:
                                srt_data = _words_to_srt(words)
                                st.download_button(
                                    label="📝 Export Subtitles (.SRT)",
                                    data=srt_data,
                                    file_name=f"ClipPulse_{rank}_Subtitles.srt",
                                    mime="text/plain",
                                    use_container_width=True,
                                    key=f"srt_btn_{st.session_state.run_id}_{rank}",
                                )
                        else:
                            st.info("⚡ Background rendering in progress. Click **Apply Sidebar Style & Re-Render** to compile.")

                    # =========================================================
                    # CREATOR TOOLKIT: THUMBNAIL STUDIO & AI CAPTIONS / HASHTAGS
                    # =========================================================
                    st.markdown("<div style='height: 0.5rem;'></div>", unsafe_allow_html=True)
                    st.divider()

                    tool_c1, tool_c2 = st.columns(2, gap="large")

                    with tool_c1:
                        with st.expander("🖼️ Auto Thumbnail Generator", expanded=False):
                            st.caption("Generate high-CTR YouTube Shorts & Reels cover images with bold typography.")
                            th_col_a, th_col_b = st.columns([1.2, 1.0])
                            with th_col_a:
                                th_style = st.selectbox(
                                    "Visual Style Preset",
                                    [
                                        "Hormozi Impact (Yellow/Green Pop)",
                                        "Neon Cyber (Cyan/Pink Glow)",
                                        "Beast Mode (Comic Yellow/Red)",
                                        "Clean Editorial (Luxury Glow)",
                                        "Cinematic Drama (High-Contrast Red)",
                                    ],
                                    key=f"th_style_{rank}",
                                )
                                th_headline = st.text_input("Hook Headline Text", value=clip["hook_title"][:45], key=f"th_head_{rank}")
                            with th_col_b:
                                th_ratio = st.radio(
                                    "Aspect Ratio",
                                    ["9:16 Vertical", "16:9 Landscape"],
                                    horizontal=True,
                                    key=f"th_ratio_{rank}",
                                )
                                th_badge = st.text_input("Badge / Sticker", value="MUST WATCH 🔥", key=f"th_badge_{rank}")

                            clip_dur = max(2.0, float(clip["end"] - clip["start"]))
                            ts_options = get_recommended_frame_timestamps(clip_dur)
                            ts_labels = [opt[0] for opt in ts_options]
                            chosen_ts_label = st.selectbox("Keyframe Frame", ts_labels, index=min(1, len(ts_labels)-1), key=f"th_ts_sel_{rank}")
                            chosen_ts = next(opt[1] for opt in ts_options if opt[0] == chosen_ts_label)

                            gen_th_btn = st.button("✨ Render Thumbnail", key=f"btn_gen_th_{rank}", use_container_width=True, type="primary")

                            th_state_key = f"thumb_{st.session_state.run_id}_{rank}"
                            video_source_for_thumb = (rendered["output_path"] if rendered and Path(rendered["output_path"]).exists() else active_source)

                            if gen_th_btn or (th_state_key not in st.session_state):
                                style_key_map = {
                                    "Hormozi Impact (Yellow/Green Pop)": "hormozi",
                                    "Neon Cyber (Cyan/Pink Glow)": "neon",
                                    "Beast Mode (Comic Yellow/Red)": "beast",
                                    "Clean Editorial (Luxury Glow)": "luxury",
                                    "Cinematic Drama (High-Contrast Red)": "drama",
                                }
                                ratio_key = "9:16" if "9:16" in th_ratio else "16:9"

                                frame_img = None
                                if video_source_for_thumb and not str(video_source_for_thumb).startswith(("http://", "https://")):
                                    frame_img = extract_thumbnail_frame(video_source_for_thumb, chosen_ts)
                                elif rendered and Path(rendered["output_path"]).exists():
                                    frame_img = extract_thumbnail_frame(rendered["output_path"], chosen_ts)

                                if frame_img is not None:
                                    th_result = generate_viral_thumbnail(
                                        base_image=frame_img,
                                        headline=th_headline,
                                        style_preset=style_key_map.get(th_style, "hormozi"),
                                        aspect_ratio=ratio_key,
                                        badge_label=th_badge,
                                        position="bottom",
                                    )
                                    import io
                                    buf = io.BytesIO()
                                    th_result.save(buf, format="JPEG", quality=95)
                                    st.session_state[th_state_key] = buf.getvalue()

                            if th_state_key in st.session_state and st.session_state[th_state_key]:
                                th_bytes = st.session_state[th_state_key]
                                st.image(th_bytes, caption=f"Cover Preview ({th_ratio})", use_container_width=True)
                                slug = clip['hook_title'][:20].replace(' ', '_')
                                st.download_button(
                                    label="📥 Download Thumbnail (JPG)",
                                    data=th_bytes,
                                    file_name=f"ClipPulse_Thumbnail_r{rank}_{slug}.jpg",
                                    mime="image/jpeg",
                                    use_container_width=True,
                                    key=f"dl_th_{rank}",
                                )
                            else:
                                st.info("Click **✨ Render Thumbnail** to preview cover image.")

                    with tool_c2:
                        with st.expander("🏷️ AI Caption & Viral Hashtag Generator", expanded=False):
                            cap_state_key = f"caps_{st.session_state.run_id}_{rank}"
                            
                            regen_caps = st.button("🔄 Generate / Refresh Social Copy", key=f"btn_regen_caps_{rank}", use_container_width=True, type="secondary")
                            
                            if regen_caps or (cap_state_key not in st.session_state):
                                with st.spinner("Writing optimized copy for YouTube, IG, TikTok & LinkedIn..."):
                                    clip_transcript = " ".join(str(w.get("word", "")).strip() for w in words)
                                    video_title_val = (st.session_state.analysis.get("title", "") if st.session_state.analysis else "") or clip["hook_title"]
                                    caps_data = generate_social_suite(
                                        transcript_text=clip_transcript,
                                        hook_title=clip["hook_title"],
                                        video_title=video_title_val,
                                    )
                                    st.session_state[cap_state_key] = caps_data
                            
                            if cap_state_key in st.session_state:
                                cdata = st.session_state[cap_state_key]
                                src_engine = cdata.get("source", "ClipPulse Engine")
                                st.markdown(f"<div style='font-size:0.75rem; color:#10B981; margin-bottom:0.4rem;'>● {src_engine}</div>", unsafe_allow_html=True)
                                
                                tab_yt, tab_ig, tab_tt, tab_li = st.tabs([
                                    "YouTube Shorts",
                                    "Instagram Reels",
                                    "TikTok",
                                    "LinkedIn",
                                ])
                                
                                with tab_yt:
                                    yt = cdata.get("youtube", {})
                                    st.caption("Clickable Video Title:")
                                    st.code(yt.get("title", ""), language=None)
                                    st.caption("Description & Algorithmic Tags:")
                                    st.text_area("YouTube Description", yt.get("description", ""), height=130, key=f"yt_desc_{rank}", label_visibility="collapsed")
                                    st.caption("Search Tags:")
                                    st.code(yt.get("tags", ""), language=None)

                                with tab_ig:
                                    ig = cdata.get("instagram", {})
                                    st.caption("Scroll-Stopping Hook:")
                                    st.code(ig.get("hook", ""), language=None)
                                    st.caption("Full Reel Caption (Ready to Paste):")
                                    st.text_area("Instagram Caption", ig.get("caption", ""), height=150, key=f"ig_cap_{rank}", label_visibility="collapsed")

                                with tab_tt:
                                    tt = cdata.get("tiktok", {})
                                    st.caption("Punchy TikTok Caption & Tags:")
                                    st.text_area("TikTok Caption", tt.get("caption", ""), height=110, key=f"tt_cap_{rank}", label_visibility="collapsed")

                                with tab_li:
                                    li = cdata.get("linkedin", {})
                                    st.caption("Thought-Leadership Post:")
                                    st.text_area("LinkedIn Post", li.get("post", ""), height=150, key=f"li_post_{rank}", label_visibility="collapsed")

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
# TAB 2: 🎨 CAPTION STYLES (REAL KINETIC PRESETS GALLERY)
# =============================================================================
with tab_templates:
    st.markdown(
        """
        <div style="text-align:center; margin: 1.2rem auto 2rem auto; max-width:800px;">
            <div class="cp-hero-chip">🎨 Kinetic Typography</div>
            <h2 style="font-family:'Plus Jakarta Sans', sans-serif; font-size:2.2rem; font-weight:800; color:#FFFFFF; margin:0 0 0.5rem 0;">
                Signature Animated Caption Styles
            </h2>
            <p style="color:#94A3B8; font-size:1.02rem;">
                Select any style in the sidebar. All fonts auto-download and render with word-by-word animation and 3D emojis.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="cp-tpl-grid">
            <div class="cp-tpl-card">
                <div class="cp-tpl-preview" style="background:#000000; color:#39FF14; font-family:'Montserrat', sans-serif; font-size:1.5rem; text-shadow:0 0 10px rgba(57,255,20,0.5);">
                    VIRAL HOOK!
                </div>
                <div><span class="font-pattern-hormozi" style="font-size:1.25rem; margin-bottom:0.25rem;">Pulse Hormozi</span></div>
                <div style="font-size:0.82rem; color:#94A3B8; margin-bottom:0.8rem;">High-contrast green/yellow active word cycle with bold tilted uppercase. Used by #1 finance & business creators.</div>
                <span class="cp-badge-active">ACTIVE PRESET</span>
            </div>
            <div class="cp-tpl-card">
                <div class="cp-tpl-preview" style="background:#141724; color:#FFD000; font-family:'Bangers', sans-serif; font-size:1.7rem; letter-spacing:1px;">
                    INSANE MOMENT 🔥
                </div>
                <div><span class="font-pattern-beast" style="font-size:1.45rem; margin-bottom:0.25rem;">Beast Mode</span></div>
                <div style="font-size:0.82rem; color:#94A3B8; margin-bottom:0.8rem;">Playful, high-energy impact typography with explosive contrast and animated 3D emojis.</div>
                <span class="cp-badge-active">ACTIVE PRESET</span>
            </div>
            <div class="cp-tpl-card">
                <div class="cp-tpl-preview" style="background:#090B14; color:#00F0FF; font-family:'Anton', sans-serif; font-size:1.6rem; text-shadow:0 0 14px rgba(0,240,255,0.7);">
                    FUTURE AI 🤖
                </div>
                <div><span class="font-pattern-neon" style="font-size:1.3rem; margin-bottom:0.25rem;">Neon Cyber</span></div>
                <div style="font-size:0.82rem; color:#94A3B8; margin-bottom:0.8rem;">Vibrant neon cyan & electric purple glow. Ideal for tech, crypto, gaming, and AI shorts.</div>
                <span class="cp-badge-active">ACTIVE PRESET</span>
            </div>
            <div class="cp-tpl-card">
                <div class="cp-tpl-preview" style="background:#121626; color:#FFE614; font-family:'Montserrat', sans-serif; font-size:1.35rem;">
                    <span style="background:#FFE614; color:#000000; padding:0.2rem 0.6rem; border-radius:8px;">Submagic</span>
                </div>
                <div><span class="font-pattern-submagic" style="font-size:1.05rem; margin-bottom:0.35rem;">Submagic Pill</span></div>
                <div style="font-size:0.82rem; color:#94A3B8; margin-bottom:0.8rem;">Modern rounded pill background tracking active words with smooth color cycle.</div>
                <span class="cp-badge-active">ACTIVE PRESET</span>
            </div>
            <div class="cp-tpl-card">
                <div class="cp-tpl-preview" style="background:#131210; color:#FFD048; font-family:'Playfair Display', serif; font-size:1.4rem; font-style:italic;">
                    Editorial Luxury
                </div>
                <div><span class="font-pattern-editorial" style="font-size:1.35rem; margin-bottom:0.25rem;">Editorial Gold</span></div>
                <div style="font-size:0.82rem; color:#94A3B8; margin-bottom:0.8rem;">Refined serif typography with warm gold highlights for thought leaders, podcasts, and interviews.</div>
                <span class="cp-badge-active">ACTIVE PRESET</span>
            </div>
            <div class="cp-tpl-card">
                <div class="cp-tpl-preview" style="background:#111522; color:#FFFFFF; font-family:'Inter', sans-serif; font-size:1.4rem;">
                    Clean Minimal
                </div>
                <div><span class="font-pattern-minimal" style="font-size:1.2rem; margin-bottom:0.25rem;">Minimal Glass</span></div>
                <div style="font-size:0.82rem; color:#94A3B8; margin-bottom:0.8rem;">Subtle white subtitles with thin border shadow. Perfect for aesthetic cinematic reels.</div>
                <span class="cp-badge-active">ACTIVE PRESET</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# =============================================================================
# TAB 3: ⚡ BUILT-IN FEATURES & ROADMAP (HONEST FEATURE SUITE)
# =============================================================================
with tab_features:
    st.markdown(
        """
        <div style="text-align:center; margin: 1.2rem auto 2rem auto; max-width:800px;">
            <div class="cp-hero-chip">⚡ Architecture & Features</div>
            <h2 style="font-family:'Plus Jakarta Sans', sans-serif; font-size:2.2rem; font-weight:800; color:#FFFFFF; margin:0 0 0.5rem 0;">
                Full Feature Suite & Status
            </h2>
            <p style="color:#94A3B8; font-size:1.02rem;">
                Here is a transparent breakdown of all fully working production features vs. upcoming modules.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="side-section" style="font-size:0.88rem; color:#10B981;">● Active & Built-in Features (Fully Functional)</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="cp-feature-grid">
            <div class="cp-feat-card">
                <div class="cp-feat-icon">📐</div>
                <div class="cp-feat-title">AI Reframe & Canvas <span class="cp-badge-active">ACTIVE</span></div>
                <div class="cp-feat-desc">5 layout modes: Fit Whole Video with Aesthetic Blur, Studio Uncropped, OpenCV Face Tracking, Screen+Facecam Split, and Podcast Auto.</div>
            </div>
            <div class="cp-feat-card">
                <div class="cp-feat-icon">💬</div>
                <div class="cp-feat-title">Kinetic Animated Captions <span class="cp-badge-active">ACTIVE</span></div>
                <div class="cp-feat-desc">Word-by-word synchronized animations with karaoke color cycle, Google font auto-fetch, and custom typography presets.</div>
            </div>
            <div class="cp-feat-card">
                <div class="cp-feat-icon">🔥</div>
                <div class="cp-feat-title">3D Emojis Animation <span class="cp-badge-active">ACTIVE</span></div>
                <div class="cp-feat-desc">Keyword-driven Fluent & Apple 3D emojis auto-spawn on spoken emotional beats with spring physics and floating animations.</div>
            </div>
            <div class="cp-feat-card">
                <div class="cp-feat-icon">🎯</div>
                <div class="cp-feat-title">Virality AI™ Scoring <span class="cp-badge-active">ACTIVE</span></div>
                <div class="cp-feat-desc">Multi-pillar evaluation combining Opening Hook Power (45%), Story Coherence (35%), and Audio Excitement Peaks (20%).</div>
            </div>
            <div class="cp-feat-card">
                <div class="cp-feat-icon">🎙️</div>
                <div class="cp-feat-title">Studio Audio Enhancement <span class="cp-badge-active">ACTIVE</span></div>
                <div class="cp-feat-desc">Loudnorm audio leveling normalized to -14 LUFS with voice EQ clarity, noise suppression, and background music auto-ducking.</div>
            </div>
            <div class="cp-feat-card">
                <div class="cp-feat-icon">📝</div>
                <div class="cp-feat-title">Export to Subtitles (.SRT) <span class="cp-badge-active">ACTIVE</span></div>
                <div class="cp-feat-desc">Millisecond-accurate SubRip .SRT subtitle export for instant import into Premiere Pro, DaVinci Resolve, or CapCut.</div>
            </div>
            <div class="cp-feat-card">
                <div class="cp-feat-icon">⚡</div>
                <div class="cp-feat-title">Hardware Acceleration <span class="cp-badge-active">ACTIVE</span></div>
                <div class="cp-feat-desc">Auto NVENC GPU encoding when available, with multi-threaded silent pre-rendering of upcoming clips in background memory.</div>
            </div>
            <div class="cp-feat-card">
                <div class="cp-feat-icon">🌐</div>
                <div class="cp-feat-title">Hinglish / English Captions <span class="cp-badge-active">ACTIVE</span></div>
                <div class="cp-feat-desc">Zero-tofu Indian Hinglish transliteration and English auto-translation for seamless Indian & global social reach.</div>
            </div>
            <div class="cp-feat-card">
                <div class="cp-feat-icon">🖼️</div>
                <div class="cp-feat-title">Auto Thumbnail Generator <span class="cp-badge-active">ACTIVE</span></div>
                <div class="cp-feat-desc">One-click 9:16 vertical & 16:9 landscape cover image extraction from peak moments with Hormozi, Neon Cyber, and Beast typography presets.</div>
            </div>
            <div class="cp-feat-card">
                <div class="cp-feat-icon">🏷️</div>
                <div class="cp-feat-title">AI Captions & Viral Hashtags <span class="cp-badge-active">ACTIVE</span></div>
                <div class="cp-feat-desc">Instant multi-platform copy generation for YouTube Shorts, Instagram Reels, TikTok, and LinkedIn with algorithmic hashtag clustering.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="side-section" style="font-size:0.88rem; color:#F59E0B; margin-top:2rem;">⏳ In Development (Future Roadmap)</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="cp-feature-grid">
            <div class="cp-feat-card" style="opacity:0.85;">
                <div class="cp-feat-icon">🎭</div>
                <div class="cp-feat-title">AI B-Roll Insertion <span class="cp-badge-roadmap">ROADMAP</span></div>
                <div class="cp-feat-desc">Contextual visual B-roll generated via text-to-video models to cover speech pauses and enhance retention.</div>
            </div>
            <div class="cp-feat-card" style="opacity:0.85;">
                <div class="cp-feat-icon">📅</div>
                <div class="cp-feat-title">Multi-Platform Scheduler <span class="cp-badge-roadmap">ROADMAP</span></div>
                <div class="cp-feat-desc">Direct OAuth publishing to YouTube Shorts, Instagram Reels, and TikTok with optimal post timing.</div>
            </div>
            <div class="cp-feat-card" style="opacity:0.85;">
                <div class="cp-feat-icon">🗣️</div>
                <div class="cp-feat-title">Multi-Voice AI Dubbing <span class="cp-badge-roadmap">ROADMAP</span></div>
                <div class="cp-feat-desc">Voice cloning and speech dubbing across 14 languages preserving the original speaker's pitch and emotion.</div>
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
            <div class="cp-hero-chip">🎯 Proprietary Algorithm</div>
            <h2 style="font-family:'Plus Jakarta Sans', sans-serif; font-size:2.2rem; font-weight:800; color:#FFFFFF; margin:0 0 0.5rem 0;">
                How ClipPulse Virality Score™ Works
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
            <div class="cp-feat-card" style="border-top: 3px solid #6366F1;">
                <div style="font-size:2rem; font-weight:800; color:#818CF8; margin-bottom:0.3rem;">45%</div>
                <div class="cp-feat-title">Opening Hook Power</div>
                <div class="cp-feat-desc">The first 3 seconds determine whether viewers swipe away. The AI scans for curiosity triggers, shocking revelations, questions, and high-energy openers.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with v_c2:
        st.markdown(
            """
            <div class="cp-feat-card" style="border-top: 3px solid #A855F7;">
                <div style="font-size:2rem; font-weight:800; color:#C084FC; margin-bottom:0.3rem;">35%</div>
                <div class="cp-feat-title">Story Coherence & Payoff</div>
                <div class="cp-feat-desc">A short must deliver on its promise. The AI ensures the clip contains a complete standalone narrative with a clear punchline, lesson, or emotional climax.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with v_c3:
        st.markdown(
            """
            <div class="cp-feat-card" style="border-top: 3px solid #10B981;">
                <div style="font-size:2rem; font-weight:800; color:#34D399; margin-bottom:0.3rem;">20%</div>
                <div class="cp-feat-title">Audio Energy & Heatmap</div>
                <div class="cp-feat-desc">Calculated directly from RMS vocal peaks, laughing/reaction spikes, and YouTube's viewer replayed heatmap data to capture peak engagement.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# =============================================================================
# TAB 5: 💎 PRO EXPORTS & WORKFLOWS
# =============================================================================
with tab_pro:
    st.markdown(
        """
        <div style="text-align:center; margin: 1.2rem auto 2rem auto; max-width:800px;">
            <div class="cp-hero-chip">💎 Professional Workflows</div>
            <h2 style="font-family:'Plus Jakarta Sans', sans-serif; font-size:2.2rem; font-weight:800; color:#FFFFFF; margin:0 0 0.5rem 0;">
                Export to Premiere, DaVinci & CapCut
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
            <div class="cp-feat-card">
                <div class="cp-feat-title">📁 Adobe Premiere Pro & DaVinci Subtitle Export</div>
                <div class="cp-feat-desc" style="margin-bottom:0.8rem;">
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
            <div class="cp-feat-card">
                <div class="cp-feat-title">⚡ High-Speed Hardware Acceleration</div>
                <div class="cp-feat-desc" style="margin-bottom:0.8rem;">
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
