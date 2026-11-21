"""
ClipPulse Marketing & Thumbnail Suite
-------------------------------------
1. High-CTR Thumbnail Generator (9:16 vertical & 16:9 landscape) with Hormozi, Neon Cyber, Beast, & Editorial styles.
2. AI Social Caption & Hashtag Suite (YouTube Shorts, Instagram Reels, TikTok, LinkedIn) with Groq LPU + smart offline NLP fallback.
"""

from __future__ import annotations
import os
import re
import math
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

try:
    from groq import Groq
except ImportError:
    Groq = None

# =============================================================================
# 1. FONT UTILITIES & STYLES FOR THUMBNAILS
# =============================================================================

def _find_best_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    """Finds best available bold font for thumbnail typography."""
    candidates = [
        Path("assets/Montserrat-ExtraBold.ttf"),
        Path("assets/fonts/Poppins-ExtraBold.ttf"),
        Path("assets/fonts/Anton-Regular.ttf"),
        Path("C:/Windows/Fonts/impact.ttf"),
        Path("C:/Windows/Fonts/ariblk.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("C:/Windows/Fonts/segoeuib.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]
    for p in candidates:
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                continue
    # Fallback to matplotlib fonts in venv if present
    mpl_fonts = list(Path(".venv").glob("**/DejaVuSans-Bold.ttf"))
    if mpl_fonts:
        try:
            return ImageFont.truetype(str(mpl_fonts[0]), size)
        except Exception:
            pass
    return ImageFont.load_default()


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw) -> List[str]:
    """Wraps text into lines that do not exceed max_width."""
    words = text.strip().split()
    if not words:
        return []
    lines: List[str] = []
    cur_line: List[str] = []
    for w in words:
        test = " ".join(cur_line + [w])
        bbox = draw.textbbox((0, 0), test, font=font)
        w_px = bbox[2] - bbox[0]
        if w_px <= max_width:
            cur_line.append(w)
        else:
            if cur_line:
                lines.append(" ".join(cur_line))
                cur_line = [w]
            else:
                lines.append(w)
                cur_line = []
    if cur_line:
        lines.append(" ".join(cur_line))
    return lines[:3]  # Maximum 3 lines for high CTR clarity


# =============================================================================
# 2. FRAME EXTRACTION FOR THUMBNAILS
# =============================================================================

def extract_thumbnail_frame(video_path: str, timestamp_sec: float) -> Optional[Image.Image]:
    """Extracts a single frame from video at timestamp using ffmpeg."""
    try:
        cmd = [
            "ffmpeg", "-v", "error", "-ss", f"{timestamp_sec:.2f}",
            "-i", video_path, "-vframes", "1", "-f", "image2pipe",
            "-vcodec", "png", "-"
        ]
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
        import io
        return Image.open(io.BytesIO(out)).convert("RGBA")
    except Exception:
        # Fallback using OpenCV if ffmpeg pipe fails
        try:
            import cv2
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(timestamp_sec * fps))
            ret, frame = cap.read()
            cap.release()
            if ret and frame is not None:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                return Image.fromarray(rgb).convert("RGBA")
        except Exception:
            pass
    return None


def get_recommended_frame_timestamps(duration_sec: float) -> List[Tuple[str, float]]:
    """Returns top 3 recommended timestamps for thumbnail extraction."""
    dur = max(2.0, float(duration_sec))
    t1 = round(min(dur * 0.18, 3.0), 2)
    t2 = round(dur * 0.45, 2)
    t3 = round(dur * 0.75, 2)
    return [
        (f"Hook Opener ({t1}s)", t1),
        (f"Peak Energy ({t2}s)", t2),
        (f"Climax / Punchline ({t3}s)", t3),
    ]


# =============================================================================
# 3. HIGH-CTR THUMBNAIL RENDERER
# =============================================================================

def generate_viral_thumbnail(
    base_image: Image.Image,
    headline: str,
    subtitle: str = "",
    style_preset: str = "hormozi",
    aspect_ratio: str = "9:16",
    badge_label: str = "MUST WATCH 🔥",
    position: str = "bottom",
) -> Image.Image:
    """
    Renders a production-ready YouTube Shorts / Reels cover thumbnail.
    Styles: 'hormozi', 'neon', 'beast', 'luxury', 'drama'
    Aspect Ratios: '9:16' (1080x1920) or '16:9' (1920x1080)
    """
    target_w, target_h = (1080, 1920) if aspect_ratio == "9:16" else (1920, 1080)
    
    # 1. Fit base image with center crop & subtle pop saturation
    im = base_image.convert("RGB")
    im_w, im_h = im.size
    scale = max(target_w / im_w, target_h / im_h)
    new_w = int(round(im_w * scale))
    new_h = int(round(im_h * scale))
    im_resized = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    # Center crop
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    canvas = im_resized.crop((left, top, left + target_w, top + target_h)).convert("RGBA")

    # 2. Add cinematic ambient gradient overlay for text readability
    gradient = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    g_draw = ImageDraw.Draw(gradient)

    if position == "bottom":
        # Dark vignette fade at bottom
        for y in range(int(target_h * 0.50), target_h):
            alpha = int(220 * ((y - target_h * 0.50) / (target_h * 0.50)) ** 1.3)
            g_draw.line([(0, y), (target_w, y)], fill=(8, 12, 22, min(240, alpha)))
    elif position == "top":
        for y in range(0, int(target_h * 0.50)):
            alpha = int(220 * (1.0 - (y / (target_h * 0.50))) ** 1.3)
            g_draw.line([(0, y), (target_w, y)], fill=(8, 12, 22, min(240, alpha)))
    else:  # center
        for y in range(int(target_h * 0.25), int(target_h * 0.75)):
            dist = 1.0 - abs((y - target_h * 0.5) / (target_h * 0.25))
            alpha = int(190 * dist)
            g_draw.line([(0, y), (target_w, y)], fill=(8, 12, 22, min(220, alpha)))

    # Composite gradient onto canvas
    canvas = Image.alpha_composite(canvas, gradient)

    # 3. Style Configurations
    headline_clean = headline.upper().strip()
    if not headline_clean:
        headline_clean = "VIRAL MOMENT"

    font_size = 90 if aspect_ratio == "9:16" else 115
    title_font = _find_best_font(font_size, bold=True)
    draw = ImageDraw.Draw(canvas)

    lines = _wrap_text(headline_clean, title_font, int(target_w * 0.88), draw)

    # Calculate text block dimensions
    line_height = int(font_size * 1.25)
    total_text_h = len(lines) * line_height

    if position == "bottom":
        start_y = int(target_h * 0.72) - (total_text_h // 2)
    elif position == "top":
        start_y = int(target_h * 0.20)
    else:
        start_y = (target_h - total_text_h) // 2

    # Draw Badge / Tag if provided
    if badge_label:
        b_font = _find_best_font(38, bold=True)
        b_text = badge_label.upper().strip()
        b_bbox = draw.textbbox((0, 0), b_text, font=b_font)
        bw = (b_bbox[2] - b_bbox[0]) + 36
        bh = (b_bbox[3] - b_bbox[1]) + 20
        bx = (target_w - bw) // 2
        by = start_y - bh - 24

        badge_layer = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
        b_draw = ImageDraw.Draw(badge_layer)
        # Glowing badge background
        b_color = (239, 68, 68, 230) if style_preset in ("beast", "drama") else (99, 102, 241, 235)
        b_draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=10, fill=b_color, outline=(255, 255, 255, 180), width=2)
        b_draw.text((bx + 18, by + 8), b_text, font=b_font, fill=(255, 255, 255, 255))
        canvas = Image.alpha_composite(canvas, badge_layer)
        draw = ImageDraw.Draw(canvas)

    # 4. Render styled text lines
    for i, line in enumerate(lines):
        line_bbox = draw.textbbox((0, 0), line, font=title_font)
        lw = line_bbox[2] - line_bbox[0]
        lx = (target_w - lw) // 2
        ly = start_y + (i * line_height)

        # Apply specific styling presets
        if style_preset == "hormozi":
            # High-contrast bold yellow / lime green with heavy black border
            fill_color = (250, 204, 21, 255) if i % 2 == 0 else (34, 197, 94, 255)
            stroke_color = (0, 0, 0, 255)
            stroke_w = 9
            # Draw shadow
            draw.text((lx + 6, ly + 8), line, font=title_font, fill=(0, 0, 0, 180), stroke_width=stroke_w, stroke_fill=(0, 0, 0, 255))
            draw.text((lx, ly), line, font=title_font, fill=fill_color, stroke_width=stroke_w, stroke_fill=stroke_color)

        elif style_preset == "neon":
            # Cyber neon cyan / magenta with soft glow
            glow_layer = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
            g_draw = ImageDraw.Draw(glow_layer)
            glow_color = (6, 182, 212, 160) if i % 2 == 0 else (244, 114, 182, 160)
            g_draw.text((lx, ly), line, font=title_font, fill=glow_color, stroke_width=18, stroke_fill=glow_color)
            glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(12))
            canvas = Image.alpha_composite(canvas, glow_layer)
            draw = ImageDraw.Draw(canvas)
            draw.text((lx, ly), line, font=title_font, fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(15, 23, 42, 255))

        elif style_preset == "beast":
            # MrBeast comic explosive yellow with red stroke
            fill_color = (254, 240, 138, 255)
            stroke_color = (220, 38, 38, 255)
            draw.text((lx + 6, ly + 8), line, font=title_font, fill=(0, 0, 0, 230), stroke_width=10, stroke_fill=(0, 0, 0, 255))
            draw.text((lx, ly), line, font=title_font, fill=fill_color, stroke_width=8, stroke_fill=stroke_color)

        elif style_preset == "luxury":
            # Clean editorial white with subtle gold glow
            draw.text((lx + 3, ly + 4), line, font=title_font, fill=(0, 0, 0, 160), stroke_width=4, stroke_fill=(0, 0, 0, 200))
            draw.text((lx, ly), line, font=title_font, fill=(255, 255, 255, 255), stroke_width=2, stroke_fill=(217, 119, 6, 220))

        else:  # Drama
            fill_color = (239, 68, 68, 255) if i == 0 else (255, 255, 255, 255)
            draw.text((lx + 5, ly + 6), line, font=title_font, fill=(0, 0, 0, 220), stroke_width=8, stroke_fill=(0, 0, 0, 255))
            draw.text((lx, ly), line, font=title_font, fill=fill_color, stroke_width=6, stroke_fill=(0, 0, 0, 255))

    return canvas.convert("RGB")


# =============================================================================
# 4. AI SOCIAL CAPTION & HASHTAG GENERATOR (MULTI-PLATFORM)
# =============================================================================

def _extract_keywords(text: str) -> List[str]:
    """Extracts top semantic tags from transcript."""
    cleaned = re.sub(r"[^\w\s]", "", text.lower())
    words = cleaned.split()
    stops = {
        "the", "and", "is", "in", "to", "of", "a", "it", "this", "that", "for", "on", "with",
        "you", "i", "we", "they", "he", "she", "at", "by", "from", "up", "about", "into",
        "over", "after", "so", "can", "will", "just", "like", "know", "mean", "actually", "really"
    }
    freq: Dict[str, int] = {}
    for w in words:
        if len(w) > 3 and w not in stops:
            freq[w] = freq.get(w, 0) + 1
    sorted_words = sorted(freq.items(), key=lambda kv: kv[1], reverse=True)
    return [k for k, _ in sorted_words[:8]]


def _generate_offline_captions(transcript_text: str, hook_title: str, video_title: str) -> Dict[str, Any]:
    """Deterministic, high-converting rule-based caption generator when LLM is offline."""
    keywords = _extract_keywords(transcript_text + " " + hook_title)
    niche_tags = " ".join([f"#{kw}" for kw in keywords[:5]]) if keywords else "#insights #story"
    
    first_sentence = (transcript_text.strip().split(".")[0] or hook_title).strip()
    if len(first_sentence) > 90:
        first_sentence = first_sentence[:90] + "..."

    yt_title = f"{hook_title} 🤯 #Shorts"
    if len(yt_title) > 95:
        yt_title = yt_title[:90] + "... #Shorts"

    yt_desc = (
        f"{first_sentence}\n\n"
        f"Watch until the end for the real takeaway!\n\n"
        f"🔔 Subscribe for daily high-value clips and breakdowns.\n\n"
        f"#shorts #viral #trending #reels {niche_tags}"
    )

    ig_hook = f"Wait for this... 🤯👇\n\n{hook_title}\n\n"
    ig_body = f"{first_sentence}\n\n💡 Save this reel so you don't forget it later!\n💬 What's your take on this? Drop a comment below.\n\n"
    ig_tags = (
        f"#reels #reelsinstagram #viralreels #explorepage #trendingreels #shorts "
        f"#mindset #growth #creators #dailyinspo {niche_tags} #reelitfeelit #viralvideos"
    )

    tt_caption = f"{hook_title} 😱 Wait till the end! #fyp #foryou #foryoupage #viral #trending {niche_tags}"

    li_post = (
        f"Key insight of the day:\n\n"
        f"\"{first_sentence}\"\n\n"
        f"Here's why this matters:\n"
        f"• The greatest leverage comes from clear, focused execution.\n"
        f"• Attention is the new currency — capture it with authentic value.\n\n"
        f"What are your thoughts on this? Let's discuss in the comments.\n\n"
        f"#Leadership #Strategy #Growth #Productivity {niche_tags}"
    )

    return {
        "youtube": {"title": yt_title, "description": yt_desc, "tags": f"#shorts #viral #trending {niche_tags}"},
        "instagram": {"hook": "Wait for this... 🤯👇", "caption": ig_hook + ig_body + ig_tags, "hashtags": ig_tags},
        "tiktok": {"caption": tt_caption, "hashtags": f"#fyp #viral #trending {niche_tags}"},
        "linkedin": {"post": li_post, "hashtags": f"#Leadership #Strategy #Growth {niche_tags}"},
        "source": "Smart Heuristic Engine (Offline)",
    }


def generate_social_suite(transcript_text: str, hook_title: str, video_title: str = "") -> Dict[str, Any]:
    """
    Generates high-performing titles, captions, and algorithmic hashtags for YouTube Shorts,
    Instagram Reels, TikTok, and LinkedIn. Uses Groq LPU if available, with robust offline fallback.
    """
    api_key = os.getenv("GROQ_API_KEY", "").strip()

    if not api_key or Groq is None:
        return _generate_offline_captions(transcript_text, hook_title, video_title)

    prompt = f"""You are a world-class viral short-form social media manager.
Given this video clip transcript and hook title, generate optimized copy for 4 platforms:

Hook Title: {hook_title}
Video Topic: {video_title}
Clip Spoken Transcript:
\"\"\"{transcript_text[:1200]}\"\"\"

Generate a valid JSON object matching this exact structure:
{{
  "youtube": {{
    "title": "Clicky high-CTR Title under 65 chars with 1 emoji and #Shorts",
    "description": "Engaging 3-paragraph YouTube description with call to action and 8 tags",
    "tags": "#shorts #viral #trending #reels and 5 niche tags"
  }},
  "instagram": {{
    "hook": "1-line scroll stopping hook line for first sentence",
    "caption": "Full Instagram caption formatted with clean line breaks, value takeaway, and call to save/comment",
    "hashtags": "25 high-traffic and niche hashtags starting with #"
  }},
  "tiktok": {{
    "caption": "Snappy, punchy curiosity TikTok caption under 150 chars with hashtags",
    "hashtags": "#fyp #foryou #viral #trending and 4 niche tags"
  }},
  "linkedin": {{
    "post": "Professional thought-leadership post with hook, 3 bullet insights, and discussion prompt",
    "hashtags": "5 professional hashtags starting with #"
  }}
}}
Respond ONLY with the JSON object. Do not include markdown codeblocks or extra text."""

    try:
        client = Groq(api_key=api_key)
        comp = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=900,
        )
        import json
        raw = comp.choices[0].message.content.strip()
        data = json.loads(raw)
        data["source"] = "Groq LPU (AI Active)"
        return data
    except Exception:
        # Fallback to local heuristic engine
        return _generate_offline_captions(transcript_text, hook_title, video_title)
