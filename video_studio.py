import os
import re
import sys
import math
import time
import uuid
import threading
import urllib.parse
import urllib.request
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from audio_ai import (
    transcribe_and_snap_clip,
    convert_words_language,
    generate_clip_metadata_from_words,
    ytdlp_base_cmd,
)


# =============================================================================
# 1. OPUSCLIP-INSPIRED VIRAL CAPTION TEMPLATES + GOOGLE FONT AUTO-FETCH
# =============================================================================
FONT_DOWNLOAD_URLS: Dict[str, str] = {
    "Montserrat-ExtraBold.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/montserrat/static/Montserrat-ExtraBold.ttf",
    "Bangers-Regular.ttf":      "https://raw.githubusercontent.com/google/fonts/main/ofl/bangers/Bangers-Regular.ttf",
    "Anton-Regular.ttf":        "https://raw.githubusercontent.com/google/fonts/main/ofl/anton/Anton-Regular.ttf",
    "Poppins-ExtraBold.ttf":    "https://raw.githubusercontent.com/google/fonts/main/ofl/poppins/Poppins-ExtraBold.ttf",
    "Playfair-BoldItalic.ttf":  "https://raw.githubusercontent.com/google/fonts/main/ofl/playfairdisplay/static/PlayfairDisplay-BoldItalic.ttf",
}

STYLE_PRESETS: Dict[str, Dict[str, Any]] = {
    "Opus Hormozi": {
        "mode": "hormozi_kinetic",
        "font_file": "Montserrat-ExtraBold.ttf",
        "font_size": 60,
        "uppercase": True,
        "base_text": (255, 255, 255),
        "active_cycle": [(57, 255, 20), (255, 230, 0), (0, 240, 255)],
        "accent_rgb": (57, 255, 20),
        "pill_text": (12, 14, 16),
        "tilt": True,
    },
    "Beast Mode": {
        "mode": "beast_hype",
        "font_file": "Bangers-Regular.ttf",
        "font_size": 74,
        "uppercase": True,
        "base_text": (255, 255, 255),
        "active_cycle": [(255, 214, 10), (255, 115, 29), (57, 255, 20)],
        "accent_rgb": (255, 196, 0),
        "pill_text": (15, 15, 18),
        "tilt": True,
    },
    "Neon Cyber": {
        "mode": "neon_glow",
        "font_file": "Anton-Regular.ttf",
        "font_size": 66,
        "uppercase": True,
        "base_text": (245, 248, 255),
        "active_cycle": [(0, 245, 255), (255, 56, 215), (57, 255, 20)],
        "accent_rgb": (0, 245, 255),
        "pill_text": (10, 14, 22),
        "tilt": False,
    },
    "Minimal Glass": {
        "mode": "minimal_glass",
        "font_file": "Poppins-ExtraBold.ttf",
        "font_size": 48,
        "uppercase": False,
        "base_text": (240, 244, 248),
        "active_cycle": [(255, 214, 70), (56, 230, 255)],
        "accent_rgb": (255, 214, 70),
        "pill_text": (15, 16, 20),
        "tilt": False,
    },
    "Submagic Pill": {
        "mode": "submagic_pill",
        "font_file": "Montserrat-ExtraBold.ttf",
        "font_size": 56,
        "uppercase": True,
        "base_text": (255, 255, 255),
        "active_cycle": [(255, 226, 20), (34, 255, 102), (147, 51, 234)],
        "accent_rgb": (255, 226, 20),
        "pill_text": (15, 15, 18),
        "tilt": False,
    },
    "Editorial Gold": {
        "mode": "editorial_gold",
        "font_file": "Playfair-BoldItalic.ttf",
        "font_size": 56,
        "uppercase": False,
        "base_text": (252, 250, 245),
        "active_cycle": [(255, 208, 72)],
        "accent_rgb": (255, 208, 72),
        "pill_text": (18, 16, 12),
        "tilt": False,
    },
}

HD_3D_EMOJIS: Dict[str, Tuple[str, str, str]] = {
    "fire":       ("Fire", "fire_3d.png", "1f525"),
    "robot":      ("Robot", "robot_3d.png", "1f916"),
    "brain":      ("Brain", "brain_3d.png", "1f9e0"),
    "mindblown":  ("Exploding head", "exploding_head_3d.png", "1f92f"),
    "rocket":     ("Rocket", "rocket_3d.png", "1f680"),
    "money":      ("Money bag", "money_bag_3d.png", "1f4b0"),
    "trophy":     ("Trophy", "trophy_3d.png", "1f3c6"),
    "bulb":       ("Light bulb", "light_bulb_3d.png", "1f4a1"),
    "bolt":       ("High voltage", "high_voltage_3d.png", "26a1"),
    "target":     ("Direct hit", "direct_hit_3d.png", "1f3af"),
    "shush":      ("Shushing face", "shushing_face_3d.png", "1f92b"),
    "warning":    ("Warning", "warning_3d.png", "26a0"),
    "laugh":      ("Face with tears of joy", "face_with_tears_of_joy_3d.png", "1f602"),
    "think":      ("Thinking face", "thinking_face_3d.png", "1f914"),
    "eyes":       ("Eyes", "eyes_3d.png", "1f440"),
    "laptop":     ("Laptop", "laptop_3d.png", "1f4bb"),
    "chart":      ("Chart increasing", "chart_increasing_3d.png", "1f4c8"),
    "heart":      ("Red heart", "red_heart_3d.png", "2764"),
    "crown":      ("Crown", "crown_3d.png", "1f451"),
    "100":        ("Hundred points", "hundred_points_3d.png", "1f4af"),
    "mic":        ("Studio microphone", "studio_microphone_3d.png", "1f399"),
    "chat":       ("Speech balloon", "speech_balloon_3d.png", "1f4ac"),
    "hourglass":  ("Hourglass not done", "hourglass_not_done_3d.png", "23f3"),
    "globe":      ("Globe showing asia-australia", "globe_showing_asia-australia_3d.png", "1f30f"),
    "car":        ("Automobile", "automobile_3d.png", "1f697"),
    "skull":      ("Skull", "skull_3d.png", "1f480"),
    "game":       ("Video game", "video_game_3d.png", "1f3ae"),
}

KEYWORD_TO_EMOJI: Dict[str, str] = {
    "ai": "robot", "robot": "robot", "machine": "robot", "turing": "robot", "agi": "robot",
    "brain": "brain", "smart": "brain", "think": "brain", "mind": "brain", "genius": "brain", "intelligence": "brain",
    "shock": "mindblown", "shocked": "mindblown", "crazy": "mindblown", "insane": "mindblown", "wild": "mindblown", "wtf": "mindblown", "bro": "mindblown",
    "fire": "fire", "viral": "fire", "hot": "fire", "best": "fire", "amazing": "fire", "epic": "fire", "war": "fire", "lit": "fire",
    "money": "money", "rich": "money", "dollar": "money", "million": "money", "billion": "money", "paisa": "money", "rupees": "money", "crore": "money", "donated": "money",
    "future": "rocket", "fast": "rocket", "speed": "rocket", "rocket": "rocket", "growth": "rocket",
    "human": "globe", "world": "globe", "earth": "globe", "india": "globe", "bharat": "globe", "desh": "globe", "country": "globe",
    "calculator": "laptop", "code": "laptop", "computer": "laptop", "tech": "laptop", "software": "laptop", "data": "laptop", "google": "laptop",
    "secret": "shush", "hidden": "shush", "nobody": "shush", "truth": "shush", "sach": "shush", "raaz": "shush",
    "warning": "warning", "danger": "warning", "stop": "warning", "mistake": "warning", "wrong": "warning", "attack": "warning", "arrest": "warning",
    "car": "car", "gaadi": "car", "gadi": "car", "vehicle": "car", "drive": "car",
    "funny": "laugh", "laugh": "laugh", "joke": "laugh", "lol": "laugh", "lmao": "laugh", "haha": "laugh",
    "dead": "skull", "bruh": "skull", "rip": "skull", "cooked": "skull",
    "game": "game", "gaming": "game", "play": "game", "stream": "game", "gta": "game", "live": "game",
    "win": "trophy", "winner": "trophy", "superior": "crown", "king": "crown", "top": "crown", "goat": "crown", "success": "trophy",
    "idea": "bulb", "learn": "bulb", "tip": "bulb", "lesson": "bulb", "explain": "bulb", "plan": "bulb",
    "time": "hourglass", "years": "hourglass", "saal": "hourglass", "waqt": "hourglass", "wait": "hourglass",
    "medicine": "heart", "health": "heart", "heart": "heart", "love": "heart", "life": "heart",
    "power": "bolt", "energy": "bolt", "instant": "bolt", "impact": "bolt", "vs": "bolt",
    "target": "target", "goal": "target", "real": "100", "fact": "100", "true": "100",
    "why": "think", "kyu": "think", "kyon": "think", "question": "think", "what": "think", "how": "think",
    "eyes": "eyes", "look": "eyes", "watch": "eyes", "dekho": "eyes", "see": "eyes",
    "chart": "chart", "stock": "chart", "market": "chart", "trade": "chart",
    "speak": "mic", "talk": "mic", "podcast": "mic", "voice": "mic",
    "language": "chat", "english": "chat", "hindi": "chat", "baat": "chat",
}

_NVENC_AVAILABLE: Optional[bool] = None
_EMOJI_IMG_CACHE: Dict[Tuple[str, int], Optional[Image.Image]] = {}
_ASSET_LOCK = threading.Lock()


def _smootherstep(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * x * (x * (x * 6.0 - 15.0) + 10.0)


def _ease_out_cubic(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 1.0 - (1.0 - x) ** 3


def _smart_resize(img: np.ndarray, size: Tuple[int, int]) -> np.ndarray:
    tw, th = size
    sh, sw = img.shape[:2]
    if tw == sw and th == sh:
        return img
    interp = cv2.INTER_AREA if (tw < sw or th < sh) else cv2.INTER_CUBIC
    return cv2.resize(img, (tw, th), interpolation=interp)


def check_nvenc_available() -> bool:
    global _NVENC_AVAILABLE
    if _NVENC_AVAILABLE is not None:
        return _NVENC_AVAILABLE
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "color=c=black:s=128x128:d=0.1",
        "-c:v", "h264_nvenc", "-f", "null", "-",
    ]
    res = subprocess.run(cmd, capture_output=True)
    _NVENC_AVAILABLE = (res.returncode == 0)
    return _NVENC_AVAILABLE


def _ensure_template_font(font_filename: str, assets_dir: str = "assets") -> Optional[Path]:
    assets = Path(assets_dir)
    fonts_dir = assets / "fonts"
    fonts_dir.mkdir(parents=True, exist_ok=True)

    for cand in (assets / font_filename, fonts_dir / font_filename):
        if cand.exists() and cand.stat().st_size > 8000:
            return cand

    url = FONT_DOWNLOAD_URLS.get(font_filename)
    if url:
        dst = fonts_dir / font_filename
        with _ASSET_LOCK:
            if not dst.exists():
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=4.0) as resp:
                        data = resp.read()
                        if len(data) > 8000:
                            dst.write_bytes(data)
                except Exception:
                    pass
        if dst.exists() and dst.stat().st_size > 8000:
            return dst

    for fallback_list in [sorted(assets.glob("*.ttf")), sorted(fonts_dir.glob("*.ttf"))]:
        if fallback_list:
            return fallback_list[0]
    for win_font in [
        Path("C:/Windows/Fonts/impact.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("C:/Windows/Fonts/segoeuib.ttf"),
    ]:
        if win_font.exists():
            return win_font
    return None


def _get_unicode_fallback_font_path(assets_dir: str = "assets") -> Optional[Path]:
    for cand in [
        Path(assets_dir) / "fonts" / "Poppins-ExtraBold.ttf",
        Path("assets/fonts/Poppins-ExtraBold.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("C:/Windows/Fonts/NirmalaB.ttf"),
        Path("C:/Windows/Fonts/Nirmala.ttf"),
        Path("C:/Windows/Fonts/mangalb.ttf"),
    ]:
        if cand.exists():
            return cand
    return None


def _load_font_for_text(text: str, primary_font_path: Optional[Path], size: int) -> ImageFont.FreeTypeFont:
    if any(ord(ch) > 255 for ch in text):
        uni_path = _get_unicode_fallback_font_path()
        if uni_path:
            try:
                return ImageFont.truetype(str(uni_path), size)
            except Exception:
                pass
    if primary_font_path and primary_font_path.exists():
        try:
            return ImageFont.truetype(str(primary_font_path), size)
        except Exception:
            pass
    return ImageFont.load_default()


def _get_hd_emoji(emoji_key: str, size: int = 72, assets_dir: str = "assets") -> Optional[Image.Image]:
    if emoji_key not in HD_3D_EMOJIS:
        return None
    cache_key = (emoji_key, size)

    with _ASSET_LOCK:
        if cache_key in _EMOJI_IMG_CACHE:
            return _EMOJI_IMG_CACHE[cache_key]

    folder, filename, apple_hex = HD_3D_EMOJIS[emoji_key]
    cache_dir = Path(assets_dir) / "emojis_3d"
    cache_dir.mkdir(parents=True, exist_ok=True)
    png_path = cache_dir / f"{emoji_key}_3d.png"

    if not png_path.exists():
        folder_enc = urllib.parse.quote(folder)
        urls = [
            f"https://cdn.jsdelivr.net/gh/microsoft/fluentui-emoji@main/assets/{folder_enc}/3D/{filename}",
            f"https://raw.githubusercontent.com/microsoft/fluentui-emoji/main/assets/{folder_enc}/3D/{filename}",
            f"https://cdn.jsdelivr.net/npm/emoji-datasource-apple/img/apple/64/{apple_hex}.png",
        ]
        for url in urls:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=3.5) as resp:
                    data = resp.read()
                    if len(data) > 500:
                        png_path.write_bytes(data)
                        break
            except Exception:
                continue

    if not png_path.exists():
        with _ASSET_LOCK:
            _EMOJI_IMG_CACHE[cache_key] = None
        return None

    try:
        raw = Image.open(png_path).convert("RGBA")
        resized = raw.resize((size, size), Image.Resampling.LANCZOS)

        pad = 12
        canvas = Image.new("RGBA", (size + pad * 2, size + pad * 2), (0, 0, 0, 0))
        alpha_ch = resized.split()[3]
        shadow = Image.new("RGBA", (size, size), (0, 0, 0, 155))
        shadow.putalpha(alpha_ch)
        shadow_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        shadow_layer.paste(shadow, (pad, pad + 5))
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=5))
        canvas.alpha_composite(shadow_layer)
        canvas.alpha_composite(resized, (pad, pad))

        with _ASSET_LOCK:
            _EMOJI_IMG_CACHE[cache_key] = canvas
        return canvas
    except Exception:
        with _ASSET_LOCK:
            _EMOJI_IMG_CACHE[cache_key] = None
        return None


def _pick_emoji_key(text: str, default: Optional[str] = None) -> Optional[str]:
    tokens = re.findall(r"[a-zA-Z]+", text.lower())
    for tok in tokens:
        if tok in KEYWORD_TO_EMOJI:
            return KEYWORD_TO_EMOJI[tok]
        if tok.endswith("s") and tok[:-1] in KEYWORD_TO_EMOJI:
            return KEYWORD_TO_EMOJI[tok[:-1]]
    return default


def _pil_to_overlay_layer(pil_rgba: Image.Image) -> Tuple[np.ndarray, np.ndarray]:
    arr = np.array(pil_rgba, dtype=np.uint8)
    bgr = arr[:, :, [2, 1, 0]].astype(np.float32)
    alpha = arr[:, :, 3:4].astype(np.float32) / 255.0
    return bgr, alpha


def _composite_layer(
    frame: np.ndarray,
    layer: Tuple[np.ndarray, np.ndarray],
    center_x: int,
    center_y: int,
    scale: float = 1.0,
    opacity: float = 1.0,
) -> None:
    if opacity <= 0.01 or scale <= 0.05:
        return

    bgr, alpha = layer
    if abs(scale - 1.0) > 0.012:
        new_w = max(2, int(round(bgr.shape[1] * scale)))
        new_h = max(2, int(round(bgr.shape[0] * scale)))
        bgr = cv2.resize(bgr, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        alpha = cv2.resize(alpha, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        if alpha.ndim == 2:
            alpha = alpha[:, :, None]

    lh, lw = bgr.shape[:2]
    fh, fw = frame.shape[:2]

    x1 = center_x - lw // 2
    y1 = center_y - lh // 2
    x2 = x1 + lw
    y2 = y1 + lh

    sx1 = max(0, -x1)
    sy1 = max(0, -y1)
    dx1 = max(0, x1)
    dy1 = max(0, y1)
    dx2 = min(fw, x2)
    dy2 = min(fh, y2)
    if dx2 <= dx1 or dy2 <= dy1:
        return

    sx2 = sx1 + (dx2 - dx1)
    sy2 = sy1 + (dy2 - dy1)

    a = alpha[sy1:sy2, sx1:sx2] * opacity
    roi = frame[dy1:dy2, dx1:dx2].astype(np.float32)
    blended = bgr[sy1:sy2, sx1:sx2] * a + roi * (1.0 - a)
    frame[dy1:dy2, dx1:dx2] = np.clip(blended, 0, 255).astype(np.uint8)


# =============================================================================
# 2. HOOK CARD, 6 VIRAL CAPTION ENGINES & OUTRO CTA
# =============================================================================
def _render_hook_card_layer(
    title: str,
    reason: str,
    style_name: str,
    font_path: Optional[Path],
    assets_dir: str = "assets",
) -> Tuple[np.ndarray, np.ndarray]:
    preset = STYLE_PRESETS.get(style_name, STYLE_PRESETS["Opus Hormozi"])
    accent = preset["accent_rgb"]
    font = _load_font_for_text(title, font_path, 35)

    words = title.upper().strip().split()
    lines: List[str] = []
    cur = ""
    for w in words:
        test = (cur + " " + w).strip()
        if len(test) > 19 and cur:
            lines.append(cur)
            cur = w
        else:
            cur = test
    if cur:
        lines.append(cur)
    lines = lines[:2] or ["VIRAL MOMENT"]

    emoji_key = _pick_emoji_key(f"{title} {reason}", default="fire")
    emoji_img = _get_hd_emoji(emoji_key, size=56, assets_dir=assets_dir) if emoji_key else None

    dummy = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    line_sizes = []
    max_tw = 0
    total_th = 0
    for ln in lines:
        bb = dummy.textbbox((0, 0), ln, font=font)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        line_sizes.append((ln, tw, th, bb[1]))
        max_tw = max(max_tw, tw)
        total_th += th + 10
    total_th -= 10

    emoji_pad = (emoji_img.width + 6) if emoji_img is not None else 0
    pad_x, pad_y = 26, 20
    box_w = min(656, max_tw + emoji_pad + pad_x * 2)
    box_h = max(88, total_th + pad_y * 2)

    canvas = Image.new("RGBA", (box_w + 16, box_h + 16), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    draw.rounded_rectangle([10, 12, box_w + 10, box_h + 12], radius=24, fill=(0, 0, 0, 140))
    draw.rounded_rectangle(
        [6, 6, box_w + 6, box_h + 6],
        radius=24,
        fill=(12, 14, 22, 222),
        outline=(*accent, 245),
        width=4,
    )

    text_start_x = 6 + pad_x - 4
    if emoji_img is not None:
        ey = 6 + (box_h - emoji_img.height) // 2
        canvas.alpha_composite(emoji_img, (text_start_x, ey))
        text_start_x += emoji_img.width + 4

    curr_y = 6 + (box_h - total_th) // 2
    avail_w = box_w - (text_start_x - 6) - pad_x
    for ln, tw, th, top_off in line_sizes:
        tx = text_start_x + max(0, (avail_w - tw) // 2)
        draw.text((tx, curr_y - top_off), ln, font=font, fill=(255, 255, 255, 255))
        curr_y += th + 10

    return _pil_to_overlay_layer(canvas)


def _render_outro_cta_layer(
    style_name: str,
    font_path: Optional[Path],
    assets_dir: str = "assets",
    cta_text: str = "WATCH FULL VIDEO",
) -> Tuple[np.ndarray, np.ndarray]:
    preset = STYLE_PRESETS.get(style_name, STYLE_PRESETS["Opus Hormozi"])
    accent = preset["accent_rgb"]
    font = _load_font_for_text(cta_text, font_path, 38)
    sub_font = _load_font_for_text("LIKE", font_path, 22)
    emoji_img = _get_hd_emoji("fire", size=50, assets_dir=assets_dir)

    dummy = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    bb = dummy.textbbox((0, 0), cta_text, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    e_pad = (emoji_img.width + 2) if emoji_img is not None else 0

    box_w = tw + e_pad + 66
    box_h = max(86, th + 42)
    sub_text = "LIKE  •  SHARE  •  SAVE"
    sbb = dummy.textbbox((0, 0), sub_text, font=sub_font)
    stw, sth = sbb[2] - sbb[0], sbb[3] - sbb[1]

    canvas_w = max(box_w + 24, stw + 40)
    canvas_h = box_h + sth + 44
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    bx = (canvas_w - box_w) // 2
    draw.rounded_rectangle([bx + 4, 12, bx + box_w + 4, box_h + 12], radius=43, fill=(0, 0, 0, 155))
    draw.rounded_rectangle([bx, 6, bx + box_w, box_h + 6], radius=43, fill=(*accent, 255))

    tx = bx + 36
    ty = 6 + (box_h - th) // 2 - bb[1]
    draw.text((tx, ty), cta_text, font=font, fill=(*preset["pill_text"], 255))

    if emoji_img is not None:
        canvas.alpha_composite(emoji_img, (tx + tw + 6, 6 + (box_h - emoji_img.height) // 2))

    sx = (canvas_w - stw) // 2
    sy = box_h + 22 - sbb[1]
    draw.text((sx, sy), sub_text, font=sub_font, fill=(240, 240, 245, 235))

    return _pil_to_overlay_layer(canvas)


def _build_viral_caption_timeline(
    words: List[Dict[str, Any]],
    clip_duration: float,
    style_name: str,
    font_path: Optional[Path],
    assets_dir: str = "assets",
    enable_emojis: bool = True,
) -> List[Dict[str, Any]]:
    if not words:
        return []

    preset = STYLE_PRESETS.get(style_name, STYLE_PRESETS["Opus Hormozi"])
    mode = preset["mode"]
    base_size = preset["font_size"]
    use_upper = preset["uppercase"]
    base_text = preset["base_text"]
    active_cycle = preset["active_cycle"]
    use_tilt = preset.get("tilt", False)

    chunks: List[List[Dict[str, Any]]] = []
    cur: List[Dict[str, Any]] = []
    char_len = 0
    max_words_chunk = 2 if mode == "beast_hype" else 3

    for w in words:
        raw_tok = re.sub(r"[\{\}\\]", "", str(w["word"])).strip()
        if not raw_tok:
            continue
        is_latin = not any(ord(c) > 255 for c in raw_tok)
        tok = (raw_tok.upper() if use_upper else raw_tok) if is_latin else raw_tok
        st_lead = max(0.0, float(w["start"]) - 0.06)
        item = {"word": tok, "start": st_lead, "end": float(w["end"])}
        gap = (item["start"] - cur[-1]["end"]) if cur else 0.0
        if cur and (len(cur) >= max_words_chunk or char_len + len(tok) > 15 or gap > 0.58):
            chunks.append(cur)
            cur = [item]
            char_len = len(tok)
        else:
            cur.append(item)
            char_len += len(tok) + 1
    if cur:
        chunks.append(cur)

    dummy = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    timeline: List[Dict[str, Any]] = []
    last_emoji_time = -99.0

    for c_idx, chunk in enumerate(chunks):
        chunk_text = " ".join(x["word"] for x in chunk)
        chunk_start = chunk[0]["start"]
        active_col = active_cycle[c_idx % len(active_cycle)]

        emoji_layer = None
        if enable_emojis and chunk_start >= 2.5 and (chunk_start - last_emoji_time >= 2.5):
            key = _pick_emoji_key(chunk_text)
            if key:
                em_img = _get_hd_emoji(key, size=76, assets_dir=assets_dir)
                if em_img is not None:
                    emoji_layer = _pil_to_overlay_layer(em_img)
                    last_emoji_time = chunk_start

        font_size = base_size
        font = _load_font_for_text(chunk_text, font_path, font_size)
        gap_px = 18
        while font_size > 36:
            widths = [
                (dummy.textbbox((0, 0), item["word"], font=font)[2] - dummy.textbbox((0, 0), item["word"], font=font)[0])
                for item in chunk
            ]
            if sum(widths) + gap_px * (len(chunk) - 1) + 72 <= 650:
                break
            font_size -= 4
            font = _load_font_for_text(chunk_text, font_path, font_size)

        pop_font = _load_font_for_text(chunk_text, font_path, int(round(font_size * 1.18)))

        word_boxes = []
        max_h = 0
        for item in chunk:
            bb = dummy.textbbox((0, 0), item["word"], font=font)
            tw, th = bb[2] - bb[0], bb[3] - bb[1]
            word_boxes.append((item["word"], tw, th, bb[0], bb[1]))
            max_h = max(max_h, th)

        total_w = sum(wb[1] for wb in word_boxes) + gap_px * (len(word_boxes) - 1)
        canvas_w = 710
        canvas_h = max_h + 96

        for idx, active_item in enumerate(chunk):
            w_start = max(0.0, active_item["start"])
            if idx + 1 < len(chunk):
                w_end = max(w_start + 0.06, chunk[idx + 1]["start"])
            else:
                w_end = max(w_start + 0.14, active_item["end"] + 0.06)
            w_end = min(clip_duration, w_end)
            if w_end <= w_start:
                continue

            canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(canvas)
            text_y_base = (canvas_h - max_h) // 2
            cursor_x = (canvas_w - total_w) // 2

            if mode == "minimal_glass":
                gx1 = max(18, cursor_x - 28)
                gy1 = max(8, text_y_base - 18)
                gx2 = min(canvas_w - 18, cursor_x + total_w + 28)
                gy2 = min(canvas_h - 8, text_y_base + max_h + 20)
                draw.rounded_rectangle([gx1, gy1 + 4, gx2, gy2 + 4], radius=24, fill=(0, 0, 0, 95))
                draw.rounded_rectangle(
                    [gx1, gy1, gx2, gy2], radius=24,
                    fill=(14, 18, 28, 198),
                    outline=(255, 255, 255, 58), width=2,
                )

            for j, (w_str, tw, th, bx0, by0) in enumerate(word_boxes):
                wy = text_y_base + (max_h - th) // 2
                is_active = (j == idx)

                if mode in ("hormozi_kinetic", "beast_hype"):
                    stroke_w = 7 if mode == "beast_hype" else 6
                    if is_active:
                        pbb = dummy.textbbox((0, 0), w_str, font=pop_font)
                        ptw, pth = pbb[2] - pbb[0], pbb[3] - pbb[1]
                        px = cursor_x + (tw - ptw) // 2 - pbb[0]
                        py = text_y_base + (max_h - pth) // 2 - pbb[1] - 4
                        draw.text((px + 5, py + 7), w_str, font=pop_font, fill=(0, 0, 0, 225),
                                  stroke_width=stroke_w, stroke_fill=(0, 0, 0, 225))
                        draw.text((px, py), w_str, font=pop_font, fill=(*active_col, 255),
                                  stroke_width=stroke_w, stroke_fill=(0, 0, 0, 255))
                    else:
                        draw.text((cursor_x - bx0 + 4, wy - by0 + 6), w_str, font=font,
                                  fill=(0, 0, 0, 200), stroke_width=stroke_w - 1, stroke_fill=(0, 0, 0, 200))
                        draw.text((cursor_x - bx0, wy - by0), w_str, font=font,
                                  fill=(*base_text, 255), stroke_width=stroke_w - 1, stroke_fill=(0, 0, 0, 255))

                elif mode == "neon_glow":
                    if is_active:
                        pbb = dummy.textbbox((0, 0), w_str, font=pop_font)
                        ptw, pth = pbb[2] - pbb[0], pbb[3] - pbb[1]
                        px = cursor_x + (tw - ptw) // 2 - pbb[0]
                        py = text_y_base + (max_h - pth) // 2 - pbb[1] - 2
                        glow_img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
                        gdraw = ImageDraw.Draw(glow_img)
                        gdraw.text((px, py), w_str, font=pop_font, fill=(*active_col, 255),
                                   stroke_width=6, stroke_fill=(*active_col, 255))
                        glow_blur = glow_img.filter(ImageFilter.GaussianBlur(radius=11))
                        canvas.alpha_composite(glow_blur)
                        canvas.alpha_composite(glow_blur)
                        draw = ImageDraw.Draw(canvas)
                        draw.text((px, py), w_str, font=pop_font, fill=(255, 255, 255, 255),
                                  stroke_width=3, stroke_fill=(*active_col, 255))
                    else:
                        draw.text((cursor_x - bx0 + 3, wy - by0 + 4), w_str, font=font,
                                  fill=(0, 0, 0, 195), stroke_width=4, stroke_fill=(0, 0, 0, 195))
                        draw.text((cursor_x - bx0, wy - by0), w_str, font=font,
                                  fill=(*base_text, 240), stroke_width=4, stroke_fill=(0, 0, 0, 255))

                elif mode == "minimal_glass":
                    col = (*active_col, 255) if is_active else (*base_text, 235)
                    draw.text((cursor_x - bx0, wy - by0), w_str, font=font, fill=col)

                elif mode == "editorial_gold":
                    sh = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
                    sdraw = ImageDraw.Draw(sh)
                    sdraw.text((cursor_x - bx0 + 2, wy - by0 + 5), w_str, font=font, fill=(0, 0, 0, 220))
                    canvas.alpha_composite(sh.filter(ImageFilter.GaussianBlur(radius=5)))
                    draw = ImageDraw.Draw(canvas)
                    col = (*active_col, 255) if is_active else (*base_text, 250)
                    draw.text((cursor_x - bx0, wy - by0), w_str, font=font, fill=col,
                              stroke_width=2, stroke_fill=(0, 0, 0, 200))

                else:
                    if is_active:
                        lum = 0.299 * active_col[0] + 0.587 * active_col[1] + 0.114 * active_col[2]
                        t_col = (14, 14, 18) if lum > 150 else (255, 255, 255)
                        px1, py1 = cursor_x - 14, text_y_base - 12
                        px2, py2 = cursor_x + tw + 14, text_y_base + max_h + 14
                        draw.rounded_rectangle([px1 + 3, py1 + 5, px2 + 3, py2 + 5], radius=18, fill=(0, 0, 0, 160))
                        draw.rounded_rectangle([px1, py1, px2, py2], radius=18, fill=(*active_col, 255))
                        draw.text((cursor_x - bx0, wy - by0), w_str, font=font, fill=(*t_col, 255))
                    else:
                        draw.text((cursor_x - bx0 + 3, wy - by0 + 4), w_str, font=font,
                                  fill=(0, 0, 0, 185), stroke_width=5, stroke_fill=(0, 0, 0, 185))
                        draw.text((cursor_x - bx0, wy - by0), w_str, font=font,
                                  fill=(*base_text, 255), stroke_width=5, stroke_fill=(0, 0, 0, 255))

                cursor_x += tw + gap_px

            if use_tilt:
                angle = 2.2 if (c_idx % 2 == 0) else -2.2
                canvas = canvas.rotate(angle, resample=Image.Resampling.BICUBIC, expand=False)

            timeline.append({
                "start": w_start,
                "end": w_end,
                "chunk_start": chunk_start,
                "is_new_chunk": (idx == 0),
                "has_emoji_beat": (idx == 0 and emoji_layer is not None),
                "layer": _pil_to_overlay_layer(canvas),
                "emoji_layer": emoji_layer,
            })

    return timeline


# =============================================================================
# 3. CV ANALYZER (ZERO-CV FULL UNCROPPED + STREAMER SPLIT + PODCAST + FULL-BLEED)
# =============================================================================
class _MultiFaceDetector:
    def __init__(self, assets_dir: str = "assets"):
        self.mode = "haar"
        self.detector = None
        self.haar = None

        try:
            import mediapipe as mp
            if hasattr(mp, "solutions") and hasattr(mp.solutions, "face_detection"):
                self.detector = mp.solutions.face_detection.FaceDetection(
                    model_selection=1, min_detection_confidence=0.42
                )
                self.mode = "mp_solutions"
                return

            if hasattr(mp, "tasks"):
                model_path = Path(assets_dir) / "blaze_face_short_range.tflite"
                if not model_path.exists():
                    url = (
                        "https://storage.googleapis.com/mediapipe-models/"
                        "face_detector/blaze_face_short_range/float16/1/"
                        "blaze_face_short_range.tflite"
                    )
                    try:
                        model_path.parent.mkdir(parents=True, exist_ok=True)
                        urllib.request.urlretrieve(url, str(model_path))
                    except Exception:
                        pass

                if model_path.exists():
                    from mediapipe.tasks import python as mp_python
                    from mediapipe.tasks.python import vision as mp_vision

                    opts = mp_vision.FaceDetectorOptions(
                        base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
                        min_detection_confidence=0.42,
                    )
                    self.detector = mp_vision.FaceDetector.create_from_options(opts)
                    self.mode = "mp_tasks"
                    self._mp = mp
                    return
        except Exception:
            pass

        self.haar = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        self.mode = "haar"

    def detect_faces(self, frame_bgr: np.ndarray) -> List[Tuple[float, float, float, float, float]]:
        h, w = frame_bgr.shape[:2]
        raw: List[Tuple[float, float, float, float, float]] = []

        if self.mode == "mp_solutions":
            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            res = self.detector.process(rgb)
            if res.detections:
                for d in res.detections:
                    bb = d.location_data.relative_bounding_box
                    area = max(0.0, bb.width * bb.height)
                    if area >= 0.0025:
                        cx = float(np.clip(bb.xmin + bb.width / 2.0, 0.0, 1.0))
                        cy = float(np.clip(bb.ymin + bb.height / 2.0, 0.0, 1.0))
                        raw.append((cx, cy, float(bb.width), float(bb.height), area))

        elif self.mode == "mp_tasks":
            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            mp_img = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
            res = self.detector.detect(mp_img)
            if res.detections:
                for d in res.detections:
                    bb = d.bounding_box
                    wn = bb.width / max(1.0, float(w))
                    hn = bb.height / max(1.0, float(h))
                    area = wn * hn
                    if area >= 0.0025:
                        cx = float(np.clip((bb.origin_x + bb.width / 2.0) / max(1, w), 0.0, 1.0))
                        cy = float(np.clip((bb.origin_y + bb.height / 2.0) / max(1, h), 0.0, 1.0))
                        raw.append((cx, cy, wn, hn, area))
        else:
            sw = 360
            sh = max(1, int(sw * h / max(1, w)))
            small = cv2.resize(frame_bgr, (sw, sh))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            faces = self.haar.detectMultiScale(gray, 1.15, 5, minSize=(22, 22))
            for fx, fy, fw, fh in faces:
                wn, hn = fw / float(sw), fh / float(sh)
                area = wn * hn
                if area >= 0.003:
                    raw.append(((fx + fw / 2.0) / sw, (fy + fh / 2.0) / sh, wn, hn, area))

        raw.sort(key=lambda t: t[4], reverse=True)
        unique: List[Tuple[float, float, float, float, float]] = []
        for f in raw:
            if all(abs(f[0] - u[0]) > 0.08 or abs(f[1] - u[1]) > 0.10 for u in unique):
                unique.append(f)
        return unique[:4]

    def close(self):
        if self.detector and hasattr(self.detector, "close"):
            try:
                self.detector.close()
            except Exception:
                pass


def _mouth_patch(frame_bgr: np.ndarray, face: Tuple[float, float, float, float, float]) -> np.ndarray:
    h, w = frame_bgr.shape[:2]
    cx, cy, fw, fh, _ = face
    x1 = max(0, int((cx - fw * 0.35) * w))
    x2 = min(w, int((cx + fw * 0.35) * w))
    y1 = max(0, int((cy + fh * 0.05) * h))
    y2 = min(h, int((cy + fh * 0.50) * h))
    if x2 <= x1 + 2 or y2 <= y1 + 2:
        return np.zeros((28, 28), dtype=np.float32)
    crop = cv2.cvtColor(frame_bgr[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
    return cv2.resize(crop, (28, 28), interpolation=cv2.INTER_AREA).astype(np.float32)


def _visual_saliency_center_x(frame_bgr: np.ndarray) -> float:
    small = cv2.resize(frame_bgr, (160, 90), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.sqrt(gx * gx + gy * gy)
    col_energy = np.mean(mag[10:80, :], axis=0)
    total = float(np.sum(col_energy))
    if total < 1e-3:
        return 0.50
    xs = np.linspace(0.0, 1.0, len(col_energy))
    cx = float(np.sum(xs * col_energy) / total)
    return float(np.clip(0.65 * cx + 0.35 * 0.50, 0.25, 0.75))


def _smooth_1d(arr: np.ndarray, deadzone: float = 0.020) -> np.ndarray:
    if len(arr) <= 1:
        return arr
    out = np.empty_like(arr)
    curr = float(arr[0])
    out[0] = curr
    for i in range(1, len(arr)):
        tgt = float(arr[i])
        if abs(tgt - curr) > deadzone:
            curr = 0.14 * tgt + 0.86 * curr
        out[i] = curr
    return out


def _analyze_shots_and_framing(
    video_path: str,
    framing_mode: str = "full_uncropped",
    video_type: str = "full_video",
    max_frames: Optional[int] = None,
    assets_dir: str = "assets",
) -> Dict[str, Any]:
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_est = max(1, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
    if max_frames is not None:
        total_est = min(total_est, max(1, max_frames))

    # ZERO-CV INSTANT SHORTCUT: Full Uncropped & Wide Cinematic keep 100% of original YouTube frame!
    if framing_mode in ("full_uncropped", "wide_cinematic", "blurred_fill"):
        cap.release()
        mode_tag = "full_uncropped" if framing_mode == "full_uncropped" else (
            "wide_cinematic" if framing_mode == "wide_cinematic" else "broll_blur"
        )
        return {
            "fps": fps, "frames": total_est, "src_w": src_w, "src_h": src_h,
            "shots_detected": 1, "cut_frames": [],
            "frame_modes": [mode_tag] * total_est,
            "single_bounds": ["full"] * total_est,
            "single_x": np.full(total_est, 0.50), "single_y": np.full(total_est, 0.40), "single_fw": np.full(total_est, 0.16),
            "left_x": np.full(total_est, 0.25), "left_y": np.full(total_est, 0.36), "left_fw": np.full(total_est, 0.14),
            "right_x": np.full(total_est, 0.75), "right_y": np.full(total_est, 0.36), "right_fw": np.full(total_est, 0.14),
            "split_mid_x": np.full(total_est, 0.50),
            "cam_box": (0.20, 0.72, 0.38),
            "detector_engine": f"instant ({mode_tag})",
            "face_detection_rate": 100.0, "dual_split_pct": 0.0,
        }

    allow_podcast_split = framing_mode in ("dual_split", "podcast_auto")
    stride = max(1, int(round(fps / 4.0)))
    detector = _MultiFaceDetector(assets_dir=assets_dir)

    samples: List[Dict[str, Any]] = []
    prev_tiny: Optional[np.ndarray] = None
    prev_hist: Optional[np.ndarray] = None
    faces_found = 0
    all_face_clusters: List[Tuple[float, float, float]] = []

    frame_idx = 0
    while True:
        if max_frames is not None and frame_idx >= max_frames:
            break
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % stride == 0:
            tiny = cv2.resize(frame, (64, 36), interpolation=cv2.INTER_AREA)
            hsv = cv2.cvtColor(tiny, cv2.COLOR_BGR2HSV)
            hist = cv2.calcHist([hsv], [0, 1], None, [16, 16], [0, 180, 0, 256])
            cv2.normalize(hist, hist)

            is_cut = False
            if prev_tiny is not None and prev_hist is not None:
                pix_diff = float(np.mean(np.abs(tiny.astype(np.float32) - prev_tiny.astype(np.float32))))
                hist_corr = float(cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CORREL))
                if pix_diff > 23.0 or hist_corr < 0.62:
                    is_cut = True
            prev_tiny, prev_hist = tiny, hist

            faces = detector.detect_faces(frame)
            if faces:
                faces_found += 1
                min_x = min(f[0] - f[2] * 0.5 for f in faces)
                max_x = max(f[0] + f[2] * 0.5 for f in faces)
                mean_y = float(np.mean([f[1] for f in faces]))
                span_w = max(0.18, (max_x - min_x) * 1.65)
                all_face_clusters.append(((min_x + max_x) / 2.0, mean_y, min(0.55, span_w)))

            two_faces = None
            if allow_podcast_split and len(faces) >= 2:
                f1, f2 = sorted(faces[:2], key=lambda t: t[0])
                sep_x = abs(f2[0] - f1[0])
                diff_y = abs(f2[1] - f1[1])
                size_ratio = min(f1[4], f2[4]) / max(1e-6, max(f1[4], f2[4]))
                if f1[0] < 0.46 and f2[0] > 0.54 and sep_x >= 0.26 and diff_y <= 0.18 and size_ratio >= 0.35:
                    two_faces = (f1, f2)

            saliency_x = _visual_saliency_center_x(frame) if not faces else faces[0][0]

            samples.append({
                "frame": frame_idx,
                "is_cut": is_cut,
                "faces": faces,
                "two_faces": two_faces,
                "saliency_x": saliency_x,
                "l_patch": _mouth_patch(frame, two_faces[0]) if two_faces else None,
                "r_patch": _mouth_patch(frame, two_faces[1]) if two_faces else None,
            })
        frame_idx += 1

    cap.release()
    detector.close()
    n_frames = max(1, frame_idx)

    if all_face_clusters:
        cam_cx = float(np.median([c[0] for c in all_face_clusters]))
        cam_cy = float(np.median([c[1] for c in all_face_clusters]))
        cam_w = float(np.clip(np.median([c[2] for c in all_face_clusters]), 0.32, 0.54))
    else:
        cam_cx, cam_cy, cam_w = 0.20, 0.72, 0.40

    shots: List[List[Dict[str, Any]]] = []
    cut_frames: List[int] = []
    for s in samples:
        if not shots or s["is_cut"]:
            shots.append([s])
            if s["is_cut"] and s["frame"] > 10:
                cut_frames.append(s["frame"])
        else:
            shots[-1].append(s)

    frame_modes: List[str] = ["single"] * n_frames
    single_x = np.full(n_frames, 0.50, dtype=np.float64)
    single_y = np.full(n_frames, 0.42, dtype=np.float64)
    single_fw = np.full(n_frames, 0.16, dtype=np.float64)
    single_bounds: List[str] = ["full"] * n_frames

    left_x = np.full(n_frames, 0.25, dtype=np.float64)
    left_y = np.full(n_frames, 0.36, dtype=np.float64)
    left_fw = np.full(n_frames, 0.14, dtype=np.float64)
    right_x = np.full(n_frames, 0.75, dtype=np.float64)
    right_y = np.full(n_frames, 0.36, dtype=np.float64)
    right_fw = np.full(n_frames, 0.14, dtype=np.float64)
    split_mid_x = np.full(n_frames, 0.50, dtype=np.float64)

    intro_end_f = int(n_frames * 0.16)
    outro_start_f = int(n_frames * 0.84)

    def _fill_shot_track(f_s: int, f_e: int, idxs: List[int], vals: List[float], default_v: float) -> np.ndarray:
        length = max(1, f_e - f_s)
        if not idxs:
            return np.full(length, default_v, dtype=np.float64)
        grid = np.arange(f_s, f_e, dtype=np.float64)
        interp = np.interp(grid, np.array(idxs, dtype=np.float64), np.array(vals, dtype=np.float64))
        return _smooth_1d(interp)

    if framing_mode == "streamer_split":
        has_cam = (len(all_face_clusters) >= max(2, int(len(samples) * 0.18)))
        mode_val = "streamer_split" if has_cam else "full_uncropped"
        frame_modes = [mode_val] * n_frames
        all_idx = [s["frame"] for s in samples]
        single_x = _fill_shot_track(0, n_frames, all_idx, [s["saliency_x"] for s in samples], 0.50)
    else:
        for sh_idx, sh in enumerate(shots):
            f_s = sh[0]["frame"]
            f_e = shots[sh_idx + 1][0]["frame"] if sh_idx + 1 < len(shots) else n_frames
            if f_e <= f_s:
                continue

            two_s = [x for x in sh if x["two_faces"] is not None] if allow_podcast_split else []
            any_s = [x for x in sh if len(x["faces"]) > 0]

            if allow_podcast_split and len(two_s) >= max(2, int(len(sh) * 0.45)):
                shot_type = "two_shot"
            elif len(any_s) >= max(1, int(len(sh) * 0.25)):
                shot_type = "one_shot"
            else:
                shot_type = "broll"

            if shot_type == "two_shot":
                # When multiple people/speakers are present, keep the WHOLE video visible
                # so nobody and no reaction or game screen is cut in half!
                if framing_mode != "dual_split":
                    for f in range(f_s, f_e):
                        single_bounds[f] = "full"
                        frame_modes[f] = "broll_blur"
                else:
                    t_idx = [x["frame"] for x in two_s]
                    lx = _fill_shot_track(f_s, f_e, t_idx, [x["two_faces"][0][0] for x in two_s], 0.25)
                    ly = _fill_shot_track(f_s, f_e, t_idx, [x["two_faces"][0][1] for x in two_s], 0.36)
                    lfw = _fill_shot_track(f_s, f_e, t_idx, [x["two_faces"][0][2] for x in two_s], 0.14)

                    rx = _fill_shot_track(f_s, f_e, t_idx, [x["two_faces"][1][0] for x in two_s], 0.75)
                    ry = _fill_shot_track(f_s, f_e, t_idx, [x["two_faces"][1][1] for x in two_s], 0.36)
                    rfw = _fill_shot_track(f_s, f_e, t_idx, [x["two_faces"][1][2] for x in two_s], 0.14)

                    left_x[f_s:f_e], left_y[f_s:f_e], left_fw[f_s:f_e] = lx, ly, lfw
                    right_x[f_s:f_e], right_y[f_s:f_e], right_fw[f_s:f_e] = rx, ry, rfw

                    med_l, med_r = float(np.median(lx)), float(np.median(rx))
                    split_mid_x[f_s:f_e] = 0.50 if (med_l < 0.46 and med_r > 0.54) else float((med_l + med_r) / 2.0)

                    for f in range(f_s, f_e):
                        single_bounds[f] = "full"
                        frame_modes[f] = "dual"

            elif shot_type == "one_shot":
                o_idx = [x["frame"] for x in any_s]
                multi_face_counts = [len(x["faces"]) for x in any_s]
                has_multi_faces = (max(multi_face_counts) >= 2) if multi_face_counts else False
                all_shot_faces = [fc for x in any_s for fc in x["faces"]]
                shot_span_w = (max(fc[0] for fc in all_shot_faces) - min(fc[0] for fc in all_shot_faces)) if all_shot_faces else 0.0

                # If multiple people or wide scene in a landscape video (16:9),
                # preserve the WHOLE VIDEO so nobody and no context is cut in half!
                if (has_multi_faces or shot_span_w >= 0.28) and src_w > src_h * 1.15:
                    for f in range(f_s, f_e):
                        single_bounds[f] = "full"
                        frame_modes[f] = "broll_blur"
                else:
                    sx = _fill_shot_track(f_s, f_e, o_idx, [x["faces"][0][0] for x in any_s], 0.50)
                    sy = _fill_shot_track(f_s, f_e, o_idx, [x["faces"][0][1] for x in any_s], 0.38)
                    sfw = _fill_shot_track(f_s, f_e, o_idx, [x["faces"][0][2] for x in any_s], 0.16)
                    single_x[f_s:f_e], single_y[f_s:f_e], single_fw[f_s:f_e] = sx, sy, sfw
                    for f in range(f_s, f_e):
                        single_bounds[f] = "full"
                        frame_modes[f] = "single"

            else:
                b_idx = [x["frame"] for x in sh]
                bx = _fill_shot_track(f_s, f_e, b_idx, [x["saliency_x"] for x in sh], 0.50)
                single_x[f_s:f_e] = bx
                single_y[f_s:f_e] = 0.50
                for f in range(f_s, f_e):
                    single_bounds[f] = "full"
                    frame_modes[f] = "full_broll"

    return {
        "fps": fps,
        "frames": n_frames,
        "src_w": src_w,
        "src_h": src_h,
        "shots_detected": len(shots),
        "cut_frames": cut_frames,
        "frame_modes": frame_modes,
        "single_bounds": single_bounds,
        "single_x": single_x,
        "single_y": single_y,
        "single_fw": single_fw,
        "left_x": left_x, "left_y": left_y, "left_fw": left_fw,
        "right_x": right_x, "right_y": right_y, "right_fw": right_fw,
        "split_mid_x": split_mid_x,
        "cam_box": (cam_cx, cam_cy, cam_w),
        "detector_engine": detector.mode,
        "face_detection_rate": round((faces_found / max(1, len(samples))) * 100.0, 1),
        "dual_split_pct": round(((frame_modes.count("dual") + frame_modes.count("streamer_split")) / max(1, n_frames)) * 100.0, 1),
    }


# =============================================================================
# 4. SHARP HD FRAMING RENDERERS (100% FULL UNCROPPED STILL FRAME + OTHERS)
# =============================================================================
def _crop_portrait(
    frame: np.ndarray,
    cx_norm: float,
    cy_norm: float,
    fw_norm: float,
    target_w: int,
    target_h: int,
    zoom: float = 1.0,
    x_min_px: int = 0,
    x_max_px: Optional[int] = None,
    tight_portrait: bool = False,
) -> np.ndarray:
    src_h, src_w = frame.shape[:2]
    x_min = max(0, x_min_px)
    x_max = min(src_w, x_max_px if x_max_px is not None else src_w)
    reg_w = max(32, x_max - x_min)
    aspect = target_w / float(target_h)

    if tight_portrait:
        face_px = max(60.0, fw_norm * src_w)
        ideal_w = int(round(max(face_px * 3.6, reg_w * 0.72) / max(1.0, zoom)))
        crop_w = min(reg_w, max(64, ideal_w))
        crop_h = int(round(crop_w / aspect))
        if crop_h > src_h:
            crop_h = src_h
            crop_w = min(reg_w, int(round(crop_h * aspect)))
    else:
        crop_h = int(round(src_h / max(1.0, zoom)))
        crop_w = int(round(crop_h * aspect))
        if crop_w > reg_w:
            crop_w = reg_w
            crop_h = min(src_h, int(round(crop_w / aspect)))

    crop_w = max(16, min(reg_w, crop_w))
    crop_h = max(16, min(src_h, crop_h))

    x1 = int(round(cx_norm * src_w - crop_w / 2.0))
    y1 = int(round(cy_norm * src_h - crop_h * 0.38))
    x1 = max(x_min, min(x_max - crop_w, x1))
    y1 = max(0, min(src_h - crop_h, y1))

    cropped = frame[y1 : y1 + crop_h, x1 : x1 + crop_w]
    return _smart_resize(cropped, (target_w, target_h))


def _render_full_uncropped_frame(
    frame: np.ndarray,
    accent_bgr: Tuple[int, int, int],
    out_w: int = 720,
    out_h: int = 1280,
) -> np.ndarray:
    """
    100% FULL UNCROPPED STILL YOUTUBE FRAME:
    - ZERO pixels cropped left, right, top, or bottom (speaker is NEVER half-cut!).
    - ZERO camera shake, ZERO zoom, ZERO drunk motion.
    - Sharp exact-aspect video centered at y=490px with a sleek ambient studio backdrop:
      * Hook Card sits cleanly ABOVE (y=115..215)
      * Full Video sits cleanly in MIDDLE (y=287..692 for 16:9)
      * Viral Captions + HD 3D Emoji sit cleanly BELOW (y=760..960) — zero overlap!
    """
    src_h, src_w = frame.shape[:2]

    # Soft darkened ambient studio backdrop matching the video's real color palette
    small_bg = cv2.resize(frame, (120, 214), interpolation=cv2.INTER_AREA)
    blurred_bg = cv2.GaussianBlur(small_bg, (35, 35), 0)
    bg = cv2.resize(blurred_bg, (out_w, out_h), interpolation=cv2.INTER_LINEAR)
    bg = (bg.astype(np.float32) * 0.28).astype(np.uint8)

    # Fit 100% of the source video width (or height if vertical source) with ZERO cropping!
    scale = min(out_w / float(max(1, src_w)), (out_h * 0.62) / float(max(1, src_h)))
    fg_w = max(32, min(out_w, int(round(src_w * scale))))
    fg_h = max(32, min(out_h, int(round(src_h * scale))))
    fg = _smart_resize(frame, (fg_w, fg_h))

    x0 = (out_w - fg_w) // 2
    # Center cleanly at y=490 so Hook Card above & Captions below never cover the video
    y0 = max(220, int(round(490 - fg_h / 2.0)))
    y1 = min(out_h - 330, y0 + fg_h)
    if (y1 - y0) != fg_h:
        y0 = max(120, (out_h - fg_h) // 2)
        y1 = y0 + fg_h

    # Subtle studio drop shadow framing the full video
    for dy, d_a in [(-6, 0.22), (-4, 0.42), (-2, 0.68), (fg_h + 1, 0.68), (fg_h + 3, 0.42), (fg_h + 5, 0.22)]:
        yy = y0 + dy
        if 0 <= yy < out_h:
            bg[yy, :] = (bg[yy, :].astype(np.float32) * (1.0 - d_a)).astype(np.uint8)

    bg[y0:y1, x0 : x0 + fg_w] = fg

    # Clean 2px studio accent border lines above & below the full video
    acc = (np.array(accent_bgr, dtype=np.float32) * 0.85).astype(np.uint8)
    if y0 >= 2:
        bg[y0 - 2 : y0, x0 : x0 + fg_w] = acc
    if y1 + 2 <= out_h:
        bg[y1 : y1 + 2, x0 : x0 + fg_w] = acc

    return bg


def _render_wide_cinematic_frame(
    frame: np.ndarray,
    accent_bgr: Tuple[int, int, int],
    zoom: float = 1.0,
    out_w: int = 720,
    out_h: int = 1280,
) -> np.ndarray:
    if abs(zoom - 1.0) <= 0.002:
        return _render_full_uncropped_frame(frame, accent_bgr, out_w, out_h)

    src_h, src_w = frame.shape[:2]
    safe_z = max(1.0, min(1.03, zoom))
    zw = int(round(src_w / safe_z))
    zh = int(round(src_h / safe_z))
    zx = (src_w - zw) // 2
    zy = (src_h - zh) // 2
    return _render_full_uncropped_frame(frame[zy : zy + zh, zx : zx + zw], accent_bgr, out_w, out_h)


def _render_broll_blur_frame(frame: np.ndarray, out_w: int = 720, out_h: int = 1280) -> np.ndarray:
    """
    Aesthetic Opus-style Blurred Canvas:
    1. Background fills the full 9:16 vertical canvas (1280x720) with smooth cinematic blur & soft dimming.
    2. Sharp original uncropped video frame centered with subtle drop shadow and clean borders.
    """
    src_h, src_w = frame.shape[:2]

    # Background: scale to cover full vertical canvas
    bg_scale = max(out_w / float(max(1, src_w)), out_h / float(max(1, src_h)))
    bg_w = max(out_w, int(round(src_w * bg_scale)))
    bg_h = max(out_h, int(round(src_h * bg_scale)))
    bg_full = cv2.resize(frame, (bg_w, bg_h), interpolation=cv2.INTER_LINEAR)

    # Center-crop to 9:16 (out_w x out_h)
    bx0 = max(0, (bg_w - out_w) // 2)
    by0 = max(0, (bg_h - out_h) // 2)
    bg_crop = bg_full[by0 : by0 + out_h, bx0 : bx0 + out_w]
    if bg_crop.shape[0] != out_h or bg_crop.shape[1] != out_w:
        bg_crop = cv2.resize(bg_crop, (out_w, out_h))

    # Downscale-blur-upscale for silky aesthetic Gaussian blur with high FPS
    small_bg = cv2.resize(bg_crop, (120, 214), interpolation=cv2.INTER_AREA)
    blurred_small = cv2.GaussianBlur(small_bg, (25, 25), 0)
    canvas = cv2.resize(blurred_small, (out_w, out_h), interpolation=cv2.INTER_LINEAR)
    # Dim background to 42% luminance so the center video, captions, and title card pop with great contrast
    canvas = (canvas.astype(np.float32) * 0.42).astype(np.uint8)

    # Foreground: 100% full uncropped width
    scale = min(out_w / float(max(1, src_w)), (out_h * 0.65) / float(max(1, src_h)))
    fg_w = max(32, min(out_w, int(round(src_w * scale))))
    fg_h = max(32, min(out_h, int(round(src_h * scale))))
    fg = _smart_resize(frame, (fg_w, fg_h))

    fx0 = (out_w - fg_w) // 2
    fy0 = max(180, int(round(490 - fg_h / 2.0)))
    fy1 = min(out_h - 300, fy0 + fg_h)
    if (fy1 - fy0) != fg_h:
        fy0 = max(100, (out_h - fg_h) // 2)
        fy1 = fy0 + fg_h

    # Soft drop shadow above and below
    for dy, d_a in [(-8, 0.18), (-6, 0.32), (-4, 0.52), (-2, 0.74), (fg_h + 1, 0.74), (fg_h + 3, 0.52), (fg_h + 5, 0.32), (fg_h + 7, 0.18)]:
        yy = fy0 + dy
        if 0 <= yy < out_h:
            canvas[yy, :] = (canvas[yy, :].astype(np.float32) * (1.0 - d_a)).astype(np.uint8)

    canvas[fy0:fy1, fx0 : fx0 + fg_w] = fg

    # Crisp modern 1px studio border
    border_color = (200, 200, 200)
    if fy0 >= 1:
        canvas[fy0 - 1 : fy0, fx0 : fx0 + fg_w] = border_color
    if fy1 + 1 <= out_h:
        canvas[fy1 : fy1 + 1, fx0 : fx0 + fg_w] = border_color

    return canvas


def _render_streamer_split_frame(
    frame: np.ndarray,
    cam_box: Tuple[float, float, float],
    accent_bgr: Tuple[int, int, int],
    zoom: float = 1.0,
    out_w: int = 720, out_h: int = 1280,
) -> np.ndarray:
    src_h, src_w = frame.shape[:2]
    top_h = int(round(out_h * 0.56))
    bot_h = out_h - top_h
    cam_cx, cam_cy, cam_w_norm = cam_box

    top_aspect = out_w / float(top_h)
    sc_h = int(round(src_h * (0.76 if cam_cy > 0.55 else 0.84) / max(1.0, zoom)))
    sc_w = int(round(sc_h * top_aspect))
    if sc_w > src_w:
        sc_w = src_w
        sc_h = min(src_h, int(round(sc_w / top_aspect)))
    sc_cx = 0.56 if cam_cx < 0.42 else (0.44 if cam_cx > 0.58 else 0.50)
    sc_cy = 0.36 if cam_cy > 0.55 else 0.62
    sx1 = max(0, min(src_w - sc_w, int(round(sc_cx * src_w - sc_w / 2.0))))
    sy1 = max(0, min(src_h - sc_h, int(round(sc_cy * src_h - sc_h / 2.0))))
    top_panel = _smart_resize(frame[sy1 : sy1 + sc_h, sx1 : sx1 + sc_w], (out_w, top_h))

    bot_aspect = out_w / float(bot_h)
    fc_w = int(round(src_w * cam_w_norm / max(1.0, zoom * 0.96)))
    fc_w = max(96, min(src_w, fc_w))
    fc_h = int(round(fc_w / bot_aspect))
    if fc_h > src_h:
        fc_h = src_h
        fc_w = min(src_w, int(round(fc_h * bot_aspect)))
    fx1 = max(0, min(src_w - fc_w, int(round(cam_cx * src_w - fc_w / 2.0))))
    fy1 = max(0, min(src_h - fc_h, int(round(cam_cy * src_h - fc_h * 0.44))))
    bot_panel = _smart_resize(frame[fy1 : fy1 + fc_h, fx1 : fx1 + fc_w], (out_w, bot_h))

    canvas = np.empty((out_h, out_w, 3), dtype=np.uint8)
    canvas[0:top_h, :] = top_panel
    canvas[top_h:out_h, :] = bot_panel

    for dy, alpha_d in [(-5, 0.25), (-4, 0.45), (-3, 0.68), (-2, 0.88), (-1, 0.95),
                        (0, 0.95), (1, 0.88), (2, 0.68), (3, 0.45), (4, 0.25)]:
        y = top_h + dy
        canvas[y, :] = (canvas[y, :].astype(np.float32) * (1.0 - alpha_d)).astype(np.uint8)
    canvas[top_h - 1 : top_h + 1, 64 : out_w - 64] = (np.array(accent_bgr, dtype=np.float32) * 0.80).astype(np.uint8)
    return canvas


def _render_horizontal_partition_frame(
    frame: np.ndarray,
    lx: float, ly: float, lfw: float,
    rx: float, ry: float, rfw: float,
    mid_norm: float,
    accent_bgr: Tuple[int, int, int],
    out_w: int = 720, out_h: int = 1280,
) -> np.ndarray:
    src_w = frame.shape[1]
    half_h = out_h // 2
    mid_px = int(round(mid_norm * src_w))
    margin = max(16, int(round(src_w * 0.035)))

    left_max = max(96, mid_px - margin)
    right_min = min(src_w - 96, mid_px + margin)

    top_panel = _crop_portrait(frame, lx, ly, lfw, out_w, half_h, zoom=1.06, x_min_px=0, x_max_px=left_max, tight_portrait=True)
    bot_panel = _crop_portrait(frame, rx, ry, rfw, out_w, half_h, zoom=1.06, x_min_px=right_min, x_max_px=src_w, tight_portrait=True)

    canvas = np.empty((out_h, out_w, 3), dtype=np.uint8)
    canvas[0:half_h, :] = top_panel
    canvas[half_h:out_h, :] = bot_panel

    for dy, alpha_d in [(-5, 0.22), (-4, 0.42), (-3, 0.65), (-2, 0.85), (-1, 0.94),
                        (0, 0.94), (1, 0.85), (2, 0.65), (3, 0.42), (4, 0.22)]:
        y = half_h + dy
        canvas[y, :] = (canvas[y, :].astype(np.float32) * (1.0 - alpha_d)).astype(np.uint8)
    canvas[half_h - 1 : half_h + 1, 72 : out_w - 72] = (np.array(accent_bgr, dtype=np.float32) * 0.72).astype(np.uint8)
    return canvas


def _apply_zoom_and_blur(frame: np.ndarray, zoom: float = 1.0, blur_strength: float = 0.0, flash_add: float = 0.0) -> np.ndarray:
    h, w = frame.shape[:2]
    out = frame
    if zoom > 1.005:
        zw = max(32, int(round(w / zoom)))
        zh = max(32, int(round(h / zoom)))
        zx = (w - zw) // 2
        zy = (h - zh) // 2
        out = _smart_resize(out[zy : zy + zh, zx : zx + zw], (w, h))

    if blur_strength > 0.04:
        small = cv2.resize(out, (180, 320), interpolation=cv2.INTER_AREA)
        k = (int(3 + 22 * min(1.0, blur_strength)) | 1)
        blurred = cv2.resize(cv2.GaussianBlur(small, (k, k), 0), (w, h), interpolation=cv2.INTER_LINEAR)
        out = cv2.addWeighted(out, 1.0 - min(0.92, blur_strength), blurred, min(0.92, blur_strength), 0)

    if flash_add > 1.0:
        out = np.clip(out.astype(np.float32) + flash_add, 0, 255).astype(np.uint8)

    return out


def _render_mode_frame(
    mode: str,
    src_frame: np.ndarray,
    track: Dict[str, Any],
    m_idx: int,
    t_sec: float,
    dynamic_zoom: bool,
    accent_bgr: Tuple[int, int, int],
    out_w: int = 720, out_h: int = 1280,
) -> np.ndarray:
    if mode == "full_uncropped":
        return _render_full_uncropped_frame(src_frame, accent_bgr, out_w=out_w, out_h=out_h)

    if mode == "wide_cinematic":
        z = 1.0 + 0.02 * (0.5 - 0.5 * math.cos(t_sec * 0.75)) if dynamic_zoom else 1.0
        return _render_wide_cinematic_frame(src_frame, accent_bgr, zoom=z, out_w=out_w, out_h=out_h)

    if mode == "streamer_split":
        z = 1.0 + 0.035 * (0.5 - 0.5 * math.cos(t_sec * 0.8)) if dynamic_zoom else 1.0
        return _render_streamer_split_frame(src_frame, track["cam_box"], accent_bgr, zoom=z, out_w=out_w, out_h=out_h)

    if mode == "dual":
        return _render_horizontal_partition_frame(
            src_frame,
            float(track["left_x"][m_idx]), float(track["left_y"][m_idx]), float(track["left_fw"][m_idx]),
            float(track["right_x"][m_idx]), float(track["right_y"][m_idx]), float(track["right_fw"][m_idx]),
            float(track["split_mid_x"][m_idx]),
            accent_bgr, out_w, out_h,
        )

    if mode == "broll_blur":
        return _render_broll_blur_frame(src_frame, out_w, out_h)

    if mode == "full_broll":
        z = 1.04 + 0.05 * (0.5 - 0.5 * math.cos(t_sec * 0.75)) if dynamic_zoom else 1.02
        return _crop_portrait(src_frame, float(track["single_x"][m_idx]), 0.50, 0.16, out_w, out_h, zoom=z)

    src_w = src_frame.shape[1]
    z = 1.0 + 0.045 * (0.5 - 0.5 * math.cos(t_sec * 0.85)) if dynamic_zoom else 1.0
    return _crop_portrait(
        src_frame, float(track["single_x"][m_idx]), float(track["single_y"][m_idx]),
        float(track["single_fw"][m_idx]), out_w, out_h, zoom=z,
    )


def _is_url(source: str) -> bool:
    return source.strip().lower().startswith(("http://", "https://"))


def extract_video_segment(
    source: str,
    start: float,
    end: float,
    out_path: str,
    direct_mp4: Optional[Any] = None,
    http_headers: Optional[Dict[str, str]] = None,
    fast_stream_mode: bool = False,
) -> str:
    import glob as _glob
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    duration = max(1.0, end - start)

    if _is_url(source):
        if isinstance(direct_mp4, dict) and direct_mp4.get("v") and direct_mp4.get("a"):
            try:
                ua = (http_headers or {}).get("User-Agent", "Mozilla/5.0")
                ff_fast = [
                    "ffmpeg", "-y", "-v", "error",
                    "-user_agent", ua,
                    "-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "2",
                    "-ss", f"{start:.3f}", "-i", direct_mp4["v"],
                    "-user_agent", ua,
                    "-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "2",
                    "-ss", f"{start:.3f}", "-i", direct_mp4["a"],
                    "-t", f"{duration:.3f}",
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "libx264", "-preset", "superfast", "-crf", "15", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k",
                    "-avoid_negative_ts", "make_zero",
                    out_path,
                ]
                res = subprocess.run(ff_fast, capture_output=True, timeout=24)
                if res.returncode == 0 and Path(out_path).exists() and Path(out_path).stat().st_size > 25000:
                    return out_path
            except Exception:
                pass

        raw_dl = str(Path(out_path).with_name(Path(out_path).stem + "_dl.mp4"))
        fmt_sel = (
            "bestvideo[height<=720][vcodec^=avc]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]/best"
            if fast_stream_mode
            else "bestvideo[height<=1080][height>=720][vcodec^=avc]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
        )
        cmd = [
            *ytdlp_base_cmd(),
            "--download-sections", f"*{start:.2f}-{end:.2f}",
            "-f", fmt_sel,
            "--concurrent-fragments", "4",
            "--merge-output-format", "mp4",
            "--no-playlist", "--quiet", "--no-warnings",
            "-o", raw_dl,
            source,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=85)
        dl_matches = [
            m for m in _glob.glob(str(Path(out_path).with_name(Path(out_path).stem + "_dl.*")))
            if Path(m).stat().st_size > 20000
        ]
        if res.returncode == 0 and dl_matches:
            raw_file = dl_matches[0]
            subprocess.run(
                [
                    "ffmpeg", "-y", "-v", "error",
                    "-i", raw_file,
                    "-c:v", "libx264", "-preset", "superfast", "-crf", "15", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k",
                    "-avoid_negative_ts", "make_zero",
                    out_path,
                ],
                check=True,
            )
            for m in dl_matches:
                try:
                    Path(m).unlink()
                except OSError:
                    pass
            return out_path

        full_tmpl = str(Path(out_path).with_name(Path(out_path).stem + "_full.%(ext)s"))
        cmd3 = [
            *ytdlp_base_cmd(),
            "-f", "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
            "--max-filesize", "180M",
            "--merge-output-format", "mp4",
            "--no-playlist", "--quiet", "--no-warnings",
            "-o", full_tmpl,
            source,
        ]
        res3 = subprocess.run(cmd3, capture_output=True, text=True, timeout=110)
        full_matches = [
            m for m in _glob.glob(str(Path(out_path).with_name(Path(out_path).stem + "_full.*")))
            if Path(m).stat().st_size > 25000
        ]
        if not full_matches:
            raise RuntimeError(f"YouTube HD clip download failed: {(res3.stderr or res.stderr).strip()}")

        full_file = full_matches[0]
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error",
                "-ss", f"{start:.3f}",
                "-i", full_file,
                "-t", f"{duration:.3f}",
                "-c:v", "libx264", "-preset", "superfast", "-crf", "15", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k",
                "-avoid_negative_ts", "make_zero",
                out_path,
            ],
            check=True,
        )
        for f in full_matches:
            try:
                Path(f).unlink()
            except OSError:
                pass
        return out_path

    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-ss", f"{start:.3f}",
        "-i", source,
        "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "superfast", "-crf", "15", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-avoid_negative_ts", "make_zero",
        out_path,
    ]
    subprocess.run(cmd, check=True)
    return out_path



# =============================================================================
# 5. MAIN STUDIO RENDER PIPELINE (STILL-STATIC FULL FRAME + HQ EXPORT + ETA)
# =============================================================================
def render_viral_reel(
    source: str,
    clip_data: Dict[str, Any],
    output_path: str,
    framing_mode: str = "full_uncropped",
    video_type: str = "full_video",
    caption_lang: str = "hinglish",
    style_name: str = "Opus Hormozi",
    transition_style: str = "still_static",     # "still_static", "blur_whip", "flash_zoom", "cross_dissolve"
    fast_stream_mode: bool = False,
    show_captions: bool = True,
    show_emojis: bool = True,
    show_hook_banner: bool = True,
    show_progress_bar: bool = True,
    smooth_outro: bool = True,
    dynamic_zoom: bool = False,
    color_punch: bool = True,
    audio_polish: bool = True,
    outro_text: str = "WATCH FULL VIDEO",
    bg_music_path: Optional[str] = None,
    direct_mp4: Optional[Any] = None,
    http_headers: Optional[Dict[str, str]] = None,
    video_title: str = "",
    temp_dir: str = "temp",
    assets_dir: str = "assets",
    status_cb: Optional[Callable[[str], None]] = None,
    progress_cb: Optional[Callable[[float, str], None]] = None,
) -> Dict[str, Any]:
    def log(msg: str):
        if status_cb:
            status_cb(msg)

    def prog(frac: float, text: str):
        if progress_cb:
            progress_cb(max(0.0, min(1.0, frac)), text)

    t_start = time.perf_counter()
    timings: Dict[str, float] = {}
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(temp_dir).mkdir(parents=True, exist_ok=True)

    # User framing choice is strictly respected across all camera modes:
    is_still_static = (transition_style == "still_static")
    effective_framing = framing_mode
    effective_zoom = False if (is_still_static or effective_framing in ("full_uncropped", "blurred_fill")) else dynamic_zoom

    seg_path = str(Path(temp_dir) / f"{Path(output_path).stem}_{uuid.uuid4().hex[:6]}_seg.mp4")

    # 1. Pull true HD segment with +3.2s sentence-snap buffer
    target_dur = max(8.0, float(clip_data["end"]) - float(clip_data["start"]))
    buffered_end = float(clip_data["end"]) + 3.2
    log(f"Pulling HD {target_dur:.1f}s clip ({clip_data['start']}s - {clip_data['end']}s)...")
    prog(0.10, "Step 1/4: Pulling HD clip segment...")
    t0 = time.perf_counter()
    extract_video_segment(
        source, clip_data["start"], buffered_end, seg_path,
        direct_mp4=direct_mp4, http_headers=http_headers,
        fast_stream_mode=fast_stream_mode,
    )
    timings["clip_fetch_s"] = round(time.perf_counter() - t0, 2)

    # 2. Fast word-level Whisper sync + exact sentence-end snapping
    clip_words = clip_data.get("words", [])
    snapped_dur = target_dur
    updated_meta: Dict[str, str] = {}

    if show_captions or clip_data.get("needs_word_sync") or clip_data.get("needs_title_from_clip"):
        prog(0.26, f"Step 2/4: Syncing {caption_lang.title()} word captions...")
        t0 = time.perf_counter()
        if clip_data.get("needs_word_sync") or not clip_words:
            log(f"Syncing {caption_lang.title()} captions & snapping to clean sentence end...")
            try:
                sync_res = transcribe_and_snap_clip(
                    seg_path, target_dur=target_dur, caption_lang=caption_lang, temp_dir=temp_dir
                )
                clip_words = sync_res["words"]
                snapped_dur = sync_res["clean_end"]
                clip_data["words"] = clip_words
                clip_data["needs_word_sync"] = False
            except Exception:
                clip_words = clip_words or []
        else:
            # Re-zero timestamps if they reference absolute full-video timestamps
            if clip_words and clip_words[0].get("start", 0) > 4.0 and clip_words[0].get("start", 0) >= float(clip_data.get("start", 0)) - 1.5:
                c_start = float(clip_data.get("start", 0))
                clip_words = [
                    {
                        "word": w["word"],
                        "start": max(0.0, round(float(w["start"]) - c_start, 3)),
                        "end": max(0.05, round(float(w["end"]) - c_start, 3)),
                    }
                    for w in clip_words
                ]
            clip_words = convert_words_language(clip_words, caption_lang=caption_lang)
            clip_data["words"] = clip_words
            if clip_words:
                snapped_dur = max(10.0, min(target_dur + 3.0, clip_words[-1]["end"] + 0.40))

        # Auto-generate real Hook Title & Social Caption for instant Heatmap stream clips (~0.4s!)
        if clip_data.get("needs_title_from_clip") and clip_words:
            log("Writing viral Hook Title & Hashtags from clip transcript (~0.4s)...")
            updated_meta = generate_clip_metadata_from_words(clip_words, video_title=video_title)
            if updated_meta.get("hook_title"):
                clip_data["hook_title"] = updated_meta["hook_title"]
            if updated_meta.get("reason"):
                clip_data["reason"] = updated_meta["reason"]
            if updated_meta.get("social_caption"):
                clip_data["social_caption"] = updated_meta["social_caption"]
            clip_data["needs_title_from_clip"] = False

        timings["word_sync_s"] = round(time.perf_counter() - t0, 2)
    else:
        timings["word_sync_s"] = 0.0

    cap_probe = cv2.VideoCapture(seg_path)
    probe_fps = cap_probe.get(cv2.CAP_PROP_FPS) or 30.0
    probe_frames = int(cap_probe.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    probe_h = int(cap_probe.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap_probe.release()
    stop_frame = min(probe_frames, max(30, int(round(snapped_dur * probe_fps))))

    # 3. Framing analysis (0.0s instant for full_uncropped / wide_cinematic!)
    log(f"Framing {probe_h}p → 9:16 layout ({effective_framing})...")
    prog(0.36, f"Step 3/4: Layout ready ({effective_framing})...")
    t0 = time.perf_counter()
    track = _analyze_shots_and_framing(
        seg_path,
        framing_mode=effective_framing,
        video_type=video_type,
        max_frames=stop_frame,
        assets_dir=assets_dir,
    )
    timings["face_track_s"] = round(time.perf_counter() - t0, 2)

    fps = track["fps"]
    n_frames = min(stop_frame, track["frames"])
    actual_dur = max(1.0, n_frames / fps)
    outro_tail_s = 1.65 if smooth_outro else 0.0
    tail_frames = int(round(fps * outro_tail_s))
    total_out_frames = n_frames + tail_frames

    # 4. Pre-render OpusClip Caption Template + Auto Google Font + HD 3D Emojis
    log(f"Building '{style_name}' captions, Google Font & HD 3D emojis...")
    prog(0.42, f"Building '{style_name}' captions & 3D emojis...")
    t0 = time.perf_counter()
    preset = STYLE_PRESETS.get(style_name, STYLE_PRESETS["Opus Hormozi"])
    font_path = _ensure_template_font(preset["font_file"], assets_dir=assets_dir)
    accent_rgb = preset["accent_rgb"]
    accent_bgr = (accent_rgb[2], accent_rgb[1], accent_rgb[0])

    hook_layer = (
        _render_hook_card_layer(
            clip_data.get("hook_title", "VIRAL MOMENT"),
            clip_data.get("reason", ""),
            style_name, font_path, assets_dir,
        )
        if show_hook_banner
        else None
    )
    outro_layer = (
        _render_outro_cta_layer(style_name, font_path, assets_dir, cta_text=outro_text)
        if smooth_outro
        else None
    )
    cap_timeline = (
        _build_viral_caption_timeline(
            clip_words, actual_dur, style_name, font_path, assets_dir,
            enable_emojis=show_emojis,
        )
        if show_captions
        else []
    )
    timings["overlay_prep_s"] = round(time.perf_counter() - t0, 2)

    # 5. CRISP HQ FFmpeg Export
    use_nvenc = check_nvenc_available()
    v_enc_args = (
        ["-c:v", "h264_nvenc", "-preset", "p5", "-cq", "18", "-b:v", "0", "-pix_fmt", "yuv420p"]
        if use_nvenc
        else ["-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-profile:v", "high", "-level", "4.1", "-pix_fmt", "yuv420p"]
    )

    out_w, out_h = 720, 1280
    v_filter = (
        "eq=contrast=1.05:saturation=1.14:brightness=0.01,unsharp=5:5:0.45:5:5:0.0"
        if color_punch
        else "unsharp=5:5:0.30:5:5:0.0"
    )

    voice_fade_d = min(0.32, actual_dur * 0.10)
    voice_fade_st = max(0.0, actual_dur - voice_fade_d)
    audio_trim = f"atrim=0:{actual_dur:.3f},asetpts=PTS-STARTPTS"
    voice_env = (
        f"{audio_trim},"
        f"afade=t=in:st=0:d=0.18:curve=esin,"
        f"afade=t=out:st={voice_fade_st:.2f}:d={voice_fade_d:.2f}:curve=esin"
    )
    if outro_tail_s > 0:
        voice_env += f",apad=pad_dur={outro_tail_s:.2f}"

    has_music = bool(bg_music_path and Path(bg_music_path).exists())
    music_input_args = ["-stream_loop", "-1", "-i", bg_music_path] if has_music else []

    has_audio = False
    try:
        p_a = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type", "-of", "csv=p=0", seg_path],
            capture_output=True, text=True, timeout=8
        )
        has_audio = bool(p_a.stdout.strip())
    except Exception:
        has_audio = True

    fc_parts = [f"[0:v]{v_filter}[v_out]"]
    if has_audio:
        if has_music:
            va = (
                f"[1:a]{audio_trim},loudnorm=I=-14:TP=-1.5:LRA=11,"
                f"afade=t=in:st=0:d=0.18:curve=esin,"
                f"afade=t=out:st={voice_fade_st:.2f}:d={voice_fade_d:.2f}:curve=esin"
                f"{f',apad=pad_dur={outro_tail_s:.2f}' if outro_tail_s > 0 else ''}[va]"
                if audio_polish
                else f"[1:a]{voice_env}[va]"
            )
            fc_parts.append(va)
            fc_parts.append("[2:a]volume=0.11[ma]")
            mix_fade_st = max(0.0, actual_dur - 0.10)
            mix_fade_d = max(0.60, outro_tail_s)
            fc_parts.append(
                f"[va][ma]amix=inputs=2:duration=first:dropout_transition=2,"
                f"afade=t=out:st={mix_fade_st:.2f}:d={mix_fade_d:.2f}:curve=esin[a_out]"
            )
        else:
            if audio_polish:
                fc_parts.append(
                    f"[1:a]{audio_trim},loudnorm=I=-14:TP=-1.5:LRA=11,"
                    f"afade=t=in:st=0:d=0.18:curve=esin,"
                    f"afade=t=out:st={voice_fade_st:.2f}:d={voice_fade_d:.2f}:curve=esin"
                    f"{f',apad=pad_dur={outro_tail_s:.2f}' if outro_tail_s > 0 else ''}[a_out]"
                )
            else:
                fc_parts.append(f"[1:a]{voice_env}[a_out]")
    else:
        if has_music:
            fc_parts.append(
                f"[2:a]{audio_trim},volume=0.35,afade=t=in:st=0:d=0.25:curve=esin,"
                f"afade=t=out:st={voice_fade_st:.2f}:d={voice_fade_d:.2f}:curve=esin"
                f"{f',apad=pad_dur={outro_tail_s:.2f}' if outro_tail_s > 0 else ''}[a_out]"
            )
        else:
            fc_parts.append(
                f"anullsrc=channel_layout=stereo:sample_rate=44100,atrim=0:{actual_dur + outro_tail_s:.3f}[a_out]"
            )

    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-pix_fmt", "bgr24", "-s", f"{out_w}x{out_h}", "-r", f"{fps:.4f}",
        "-i", "pipe:0",
        "-i", seg_path,
        *music_input_args,
        "-filter_complex", ";".join(fc_parts),
        "-map", "[v_out]", "-map", "[a_out]",
        *v_enc_args,
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        "-shortest",
        output_path,
    ]

    log(f"Encoding HQ 9:16 Reel from {probe_h}p ({'Still Static' if is_still_static else transition_style})...")
    t0 = time.perf_counter()

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    cap = cv2.VideoCapture(seg_path)

    modes = track["frame_modes"]
    cut_set = set(track.get("cut_frames", []))
    trans_len = max(6, int(round(fps * 0.28)))
    prev_mode = modes[0] if modes else "full_uncropped"
    trans_from_mode = prev_mode
    trans_countdown = 0
    cut_fx_countdown = 0
    beat_punch_countdown = 0

    cap_ptr = 0
    idx = 0
    hook_end_t = min(3.2, actual_dur * 0.25)
    last_clean_frame: Optional[np.ndarray] = None

    try:
        while idx < n_frames:
            ret, src_frame = cap.read()
            if not ret:
                break

            t_sec = idx / fps
            m_idx = min(idx, len(modes) - 1)
            cur_mode = modes[m_idx]

            if not is_still_static:
                if cur_mode != prev_mode:
                    trans_from_mode = prev_mode
                    trans_countdown = trans_len
                    cut_fx_countdown = trans_len
                    prev_mode = cur_mode
                elif idx in cut_set and cut_fx_countdown == 0:
                    cut_fx_countdown = max(5, int(round(fps * 0.22)))

            out_frame = _render_mode_frame(
                cur_mode, src_frame, track, m_idx, t_sec, effective_zoom, accent_bgr, out_w, out_h
            )

            if not is_still_static and trans_countdown > 0:
                blend_p = _smootherstep(1.0 - (trans_countdown / float(trans_len)))
                old_frame = _render_mode_frame(
                    trans_from_mode, src_frame, track, m_idx, t_sec, effective_zoom, accent_bgr, out_w, out_h
                )
                out_frame = cv2.addWeighted(old_frame, 1.0 - blend_p, out_frame, blend_p, 0)
                trans_countdown -= 1

            # Advance caption pointer
            while cap_ptr < len(cap_timeline) and cap_timeline[cap_ptr]["end"] < t_sec:
                cap_ptr += 1
            active_ev = None
            if cap_ptr < len(cap_timeline):
                ev = cap_timeline[cap_ptr]
                if ev["start"] <= t_sec <= ev["end"]:
                    active_ev = ev
                    if (
                        not is_still_static
                        and effective_zoom
                        and cur_mode not in ("full_uncropped", "wide_cinematic")
                        and ev.get("has_emoji_beat")
                        and abs(t_sec - ev["start"]) < (1.2 / fps)
                    ):
                        beat_punch_countdown = max(beat_punch_countdown, max(6, int(round(fps * 0.24))))

            # Apply motion FX ONLY when NOT in Still/Static mode!
            if not is_still_static:
                fx_zoom, fx_blur, fx_flash = 1.0, 0.0, 0.0

                if cut_fx_countdown > 0:
                    u = 1.0 - (cut_fx_countdown / float(trans_len))
                    bell = math.sin(math.pi * max(0.0, min(1.0, u)))
                    if transition_style == "blur_whip":
                        fx_zoom = max(fx_zoom, 1.0 + 0.09 * bell)
                        fx_blur = max(fx_blur, 0.58 * bell)
                    elif transition_style == "flash_zoom":
                        fx_zoom = max(fx_zoom, 1.0 + 0.11 * bell)
                        fx_flash = max(fx_flash, 48.0 * bell)
                    cut_fx_countdown -= 1

                if t_sec < 0.42:
                    intro_p = _ease_out_cubic(t_sec / 0.42)
                    fx_zoom = max(fx_zoom, 1.15 - 0.15 * intro_p)
                    fx_blur = max(fx_blur, (1.0 - intro_p) * 0.65)

                if beat_punch_countdown > 0:
                    bp_len = max(6, int(round(fps * 0.24)))
                    u = 1.0 - (beat_punch_countdown / float(bp_len))
                    fx_zoom = max(fx_zoom, 1.0 + 0.06 * math.sin(math.pi * max(0.0, min(1.0, u))))
                    beat_punch_countdown -= 1

                if fx_zoom > 1.005 or fx_blur > 0.04 or fx_flash > 1.0:
                    out_frame = _apply_zoom_and_blur(out_frame, zoom=fx_zoom, blur_strength=fx_blur, flash_add=fx_flash)

            last_clean_frame = out_frame.copy()

            pre_outro_p = 0.0
            if smooth_outro and t_sec > actual_dur - 0.38:
                pre_outro_p = _smootherstep((t_sec - (actual_dur - 0.38)) / 0.38)
                if not is_still_static:
                    out_frame = _apply_zoom_and_blur(out_frame, zoom=1.0, blur_strength=0.32 * pre_outro_p)
                out_frame = (out_frame.astype(np.float32) * (1.0 - 0.18 * pre_outro_p)).astype(np.uint8)

            # Glassmorphic Hook Card cleanly ABOVE the video (y=160)
            if hook_layer is not None and 0.05 <= t_sec <= hook_end_t:
                if t_sec < 0.35:
                    ease = _ease_out_cubic((t_sec - 0.05) / 0.30)
                    h_alpha = ease
                    h_y = 160 if is_still_static else int(115 + 45 * ease)
                elif t_sec > hook_end_t - 0.35:
                    h_alpha, h_y = _smootherstep((hook_end_t - t_sec) / 0.35), 160
                else:
                    h_alpha, h_y = 1.0, 160
                _composite_layer(out_frame, hook_layer, out_w // 2, h_y, scale=1.0, opacity=h_alpha)

            # Viral Captions + HD 3D Emoji cleanly positioned (zero overlap over full video!)
            if active_ev is not None:
                dt = t_sec - active_ev["start"]
                if active_ev["is_new_chunk"] and dt < 0.09:
                    c_scale = 0.86 + 0.18 * (dt / 0.09)
                elif active_ev["is_new_chunk"] and dt < 0.15:
                    c_scale = 1.04 - 0.04 * ((dt - 0.09) / 0.06)
                else:
                    c_scale = 1.0

                cap_opacity = 1.0 - pre_outro_p
                if cur_mode == "streamer_split":
                    cap_y = int(round(out_h * 0.56))
                elif cur_mode == "dual":
                    cap_y = out_h // 2
                elif cur_mode in ("full_uncropped", "wide_cinematic"):
                    # Clean dedicated zone underneath the 16:9 video (y=900px)
                    cap_y = 900
                else:
                    cap_y = int(round(out_h * 0.72))

                _composite_layer(out_frame, active_ev["layer"], out_w // 2, cap_y, scale=c_scale, opacity=cap_opacity)

                if active_ev["emoji_layer"] is not None:
                    e_dt = max(0.0, t_sec - active_ev["chunk_start"])
                    if e_dt < 0.14:
                        e_scale = 0.55 + 0.55 * _ease_out_cubic(e_dt / 0.14)
                    elif e_dt < 0.24:
                        e_scale = 1.10 - 0.10 * ((e_dt - 0.14) / 0.10)
                    else:
                        e_scale = 1.0 + 0.03 * math.sin((e_dt - 0.24) * 5.0)
                    float_y = int(round(math.sin(e_dt * 4.5) * 4.0))
                    _composite_layer(
                        out_frame, active_ev["emoji_layer"],
                        out_w // 2, cap_y - 92 + float_y,
                        scale=e_scale, opacity=cap_opacity,
                    )

            # Silky clean brightness fade-in (first 0.25s)
            if t_sec < 0.25:
                in_a = _smootherstep(t_sec / 0.25)
                out_frame = (out_frame.astype(np.float32) * in_a).astype(np.uint8)

            if show_progress_bar:
                bar_w = int(out_w * min(1.0, t_sec / actual_dur))
                bar_a = 1.0 - pre_outro_p
                if bar_a > 0.02:
                    bg_bar = out_frame[out_h - 10 : out_h, :].astype(np.float32)
                    out_frame[out_h - 10 : out_h, :] = np.clip(bg_bar * (1.0 - 0.8 * bar_a), 0, 255).astype(np.uint8)
                    if bar_w > 0:
                        fg_bar = out_frame[out_h - 10 : out_h, 0:bar_w].astype(np.float32)
                        col = np.array(accent_bgr, dtype=np.float32)
                        out_frame[out_h - 10 : out_h, 0:bar_w] = np.clip(
                            col * bar_a + fg_bar * (1.0 - bar_a), 0, 255
                        ).astype(np.uint8)

            proc.stdin.write(out_frame.tobytes())
            idx += 1

            if progress_cb and idx % 20 == 0:
                elapsed_enc = max(0.1, time.perf_counter() - t0)
                enc_fps = idx / elapsed_enc
                rem_frames = max(0, total_out_frames - idx)
                eta_s = max(1, int(round(rem_frames / max(1.0, enc_fps))))
                frac = 0.45 + 0.50 * (idx / float(max(1, total_out_frames)))
                prog(frac, f"Step 4/4: Encoding HQ Reel ({int(frac * 100)}%) — Est. ~{eta_s}s left")

        # SMOOTH CINEMATIC OUTRO TAIL (100% STILL in still_static mode — zero wobble!)
        if smooth_outro and tail_frames > 0 and last_clean_frame is not None:
            small_end = cv2.resize(last_clean_frame, (180, 320), interpolation=cv2.INTER_AREA)
            deep_blur = cv2.resize(cv2.GaussianBlur(small_end, (29, 29), 0), (out_w, out_h))

            for tf in range(tail_frames):
                p = tf / float(max(1, tail_frames - 1))
                if is_still_static:
                    # Rock-steady frame that smoothly dims & fades out (zero zoom wobble!)
                    dim = 0.82 - 0.62 * _smootherstep(min(1.0, p / 0.48))
                    tail_frame = (last_clean_frame.astype(np.float32) * dim).astype(np.uint8)
                else:
                    s_blur = _smootherstep(min(1.0, p / 0.45))
                    z_out = 1.05 - 0.05 * _smootherstep(p)
                    zw, zh = int(round(out_w / z_out)), int(round(out_h / z_out))
                    zx, zy = (out_w - zw) // 2, (out_h - zh) // 2
                    base_blend = cv2.addWeighted(
                        last_clean_frame, 1.0 - (0.35 + 0.65 * s_blur),
                        deep_blur, 0.35 + 0.65 * s_blur, 0
                    )
                    zoomed = _smart_resize(base_blend[zy : zy + zh, zx : zx + zw], (out_w, out_h))
                    dim = 0.84 - 0.62 * _smootherstep(min(1.0, p / 0.48))
                    tail_frame = (zoomed.astype(np.float32) * dim).astype(np.uint8)

                if outro_layer is not None:
                    cta_in = _smootherstep(min(1.0, p / 0.34))
                    cta_out = 1.0 - _smootherstep(max(0.0, (p - 0.68) / 0.32))
                    cta_alpha = cta_in * cta_out
                    cta_scale = 1.0 if is_still_static else (0.92 + 0.08 * cta_in)
                    cta_y = (out_h // 2) if is_still_static else int((out_h // 2) + 28 * (1.0 - cta_in))
                    _composite_layer(tail_frame, outro_layer, out_w // 2, cta_y, scale=cta_scale, opacity=cta_alpha)

                if p > 0.68:
                    fade_black = 1.0 - _smootherstep((p - 0.68) / 0.32)
                    tail_frame = (tail_frame.astype(np.float32) * fade_black).astype(np.uint8)

                proc.stdin.write(tail_frame.tobytes())

    except (BrokenPipeError, OSError):
        pass
    finally:
        cap.release()
        if proc.stdin:
            try:
                proc.stdin.close()
            except Exception:
                pass

    stderr_out = proc.stderr.read().decode("utf-8", errors="ignore")
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg Studio render failed:\n{stderr_out}")

    prog(1.0, "HQ Reel complete!")
    timings["render_s"] = round(time.perf_counter() - t0, 2)
    timings["phase2_total_s"] = round(time.perf_counter() - t_start, 2)

    try:
        if Path(seg_path).exists():
            Path(seg_path).unlink()
    except OSError:
        pass

    return {
        "output_path": output_path,
        "encoder": f"{probe_h}p src • {'NVENC HQ' if use_nvenc else 'x264 HQ'}",
        "font_used": font_path.name if font_path else "Default",
        "framing_mode": effective_framing,
        "style_name": style_name,
        "transition_style": transition_style,
        "snapped_duration_s": round(actual_dur, 2),
        "updated_meta": updated_meta,
        "cv_meta": {
            "detector_engine": track["detector_engine"],
            "shots_detected": track["shots_detected"],
            "face_detection_rate": track["face_detection_rate"],
            "horizontal_split_pct": track["dual_split_pct"],
        },
        "timings": timings,
    }