import os
import re
import sys
import json
import time
import uuid
import html
import urllib.request
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Callable, Optional, Tuple

import numpy as np
from dotenv import load_dotenv
from groq import Groq

load_dotenv()


def ytdlp_base_cmd() -> List[str]:
    """Always auto-use cookies.txt if present (keeps YouTube bot-bypass working!)."""
    try:
        from yt_auth import ytdlp_base_cmd as _auth_cmd
        return _auth_cmd()
    except Exception:
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "--force-ipv4", "--socket-timeout", "30", "--retries", "5",
            "--sleep-requests", "0.4",
            "--extractor-args", "youtube:player_client=android,web;player_skip=configs",
        ]
        for cand in (Path("cookies.txt"), Path("assets/cookies.txt")):
            if cand.exists() and cand.stat().st_size > 100:
                cmd += ["--cookies", str(cand.resolve())]
                break
        return cmd


HOOK_KEYWORDS = {
    "secret", "mistake", "never", "actually", "truth", "problem", "why",
    "reason", "shocking", "crazy", "million", "billion", "future", "danger",
    "warning", "stop", "best", "worst", "biggest", "nobody", "how", "real",
    "important", "money", "india", "world", "ai", "brain", "science", "fact",
    "attack", "plan", "story", "history", "shock", "war", "killed", "died",
    "ban", "banned", "exposed", "scam", "arrested", "mystery",
}

HANGING_END_WORDS = {
    "aur", "ki", "ke", "ka", "ko", "se", "me", "mein", "par", "pe", "jo", "jab",
    "lekin", "magar", "kyunki", "isliye", "toh", "to", "hi", "bhi", "ya", "taki",
    "jaise", "jisme", "jiski", "jiska", "iske", "uske", "apne", "wala", "wali",
    "and", "but", "or", "so", "because", "that", "which", "who", "where", "when",
    "if", "the", "a", "an", "of", "in", "on", "at", "with", "for", "from", "by",
    "और", "कि", "के", "का", "को", "से", "में", "पर", "जो", "जब", "लेकिन",
    "क्योंकि", "इसलिए", "तो", "ही", "भी", "या", "जैसे", "जिसमें", "जिसकी",
}

_DEV_VOWELS = {
    "अ": "a", "आ": "aa", "इ": "i", "ई": "ee", "उ": "u", "ऊ": "oo", "ऋ": "ri",
    "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au", "अं": "an", "अः": "ah",
}
_DEV_MATRAS = {
    "ा": "a", "ि": "i", "ी": "ee", "ु": "u", "ू": "oo", "ृ": "ri",
    "े": "e", "ै": "ai", "ो": "o", "ौ": "au", "ं": "n", "ँ": "n", "ः": "h", "्": "",
}
_DEV_CONS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "ng",
    "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ञ": "ny",
    "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n",
    "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m",
    "य": "y", "र": "r", "ल": "l", "व": "v", "श": "sh", "ष": "sh",
    "स": "s", "ह": "h", "ळ": "l", "क्ष": "ksh", "त्र": "tr", "ज्ञ": "gy",
    "क़": "q", "ख़": "kh", "ग़": "gh", "ज़": "z", "ड़": "r", "ढ़": "rh", "फ़": "f",
}
_DEV_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def _has_non_latin(text: str) -> bool:
    return any(ord(ch) > 255 for ch in text)


def _clean_token(tok: str) -> str:
    return re.sub(r"[^\w\u0900-\u097F]", "", tok.lower()).strip()


def _devanagari_to_hinglish_fallback(word: str) -> str:
    word = word.translate(_DEV_DIGITS)
    if not _has_non_latin(word):
        return word
    out = []
    i = 0
    n = len(word)
    while i < n:
        ch = word[i]
        if ch == "़":
            i += 1
            continue
        if ch in _DEV_VOWELS:
            out.append(_DEV_VOWELS[ch])
        elif ch in _DEV_CONS:
            base = _DEV_CONS[ch]
            nxt = word[i + 1] if i + 1 < n else ""
            if nxt == "़" and (ch + nxt) in _DEV_CONS:
                base = _DEV_CONS[ch + nxt]
                i += 1
                nxt = word[i + 1] if i + 1 < n else ""
            if nxt in _DEV_MATRAS:
                out.append(base + _DEV_MATRAS[nxt])
                i += 1
            elif i + 1 < n and word[i + 1] in _DEV_CONS:
                out.append(base + "a")
            else:
                out.append(base)
        elif ch in _DEV_MATRAS:
            out.append(_DEV_MATRAS[ch])
        elif ord(ch) <= 127:
            out.append(ch)
        i += 1
    return "".join(out).strip() or word


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _is_url(source: str) -> bool:
    return source.strip().lower().startswith(("http://", "https://"))


def _get_media_duration(media_path: str) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        media_path,
    ]
    return float(subprocess.check_output(cmd, text=True).strip())


# =============================================================================
# 1. FAST YOUTUBE METADATA + HEATMAP + HD STREAM URLS (~2-3 SECONDS!)
# =============================================================================
def _parse_vtt_ts(ts: str) -> float:
    parts = ts.strip().replace(",", ".").split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return 0.0


def _parse_json3_bytes(raw_bytes: bytes) -> List[Dict[str, Any]]:
    data = json.loads(raw_bytes.decode("utf-8", errors="ignore"))
    raw_items: List[Tuple[float, float, str]] = []
    for ev in data.get("events", []):
        segs = ev.get("segs")
        if not segs:
            continue
        text = "".join(str(s.get("utf8", "")) for s in segs)
        text = re.sub(r"\s+", " ", html.unescape(text)).strip()
        if not text or text in ("[Music]", "[Applause]", "[Laughter]"):
            continue
        start = float(ev.get("tStartMs", 0)) / 1000.0
        dur = float(ev.get("dDurationMs", 2500)) / 1000.0
        raw_items.append((start, start + max(0.5, dur), text))

    merged: List[Dict[str, Any]] = []
    for st, en, txt in raw_items:
        if (
            merged
            and (en - merged[-1]["start"] <= 6.5)
            and (st - merged[-1]["end"] <= 1.1)
            and (len(merged[-1]["text"]) + len(txt) < 150)
        ):
            merged[-1]["end"] = round(max(merged[-1]["end"], en), 2)
            merged[-1]["text"] = f"{merged[-1]['text']} {txt}".strip()
        else:
            merged.append({"start": round(st, 2), "end": round(en, 2), "text": txt})
    return merged


def _parse_vtt_bytes(raw_bytes: bytes) -> List[Dict[str, Any]]:
    raw = raw_bytes.decode("utf-8", errors="ignore")
    blocks = re.split(r"\r?\n\r?\n", raw)
    raw_items: List[Tuple[float, float, str]] = []
    last_text = ""

    for blk in blocks:
        lines = [ln.strip() for ln in blk.splitlines() if ln.strip()]
        ts_line = next((ln for ln in lines if "-->" in ln), None)
        if not ts_line:
            continue
        m = re.search(r"([\d:\.]+)\s*-->\s*([\d:\.]+)", ts_line)
        if not m:
            continue
        st, en = _parse_vtt_ts(m.group(1)), _parse_vtt_ts(m.group(2))
        idx_ts = lines.index(ts_line)
        txt = " ".join(lines[idx_ts + 1 :])
        txt = re.sub(r"<[^>]+>", "", txt)
        txt = re.sub(r"\s+", " ", html.unescape(txt)).strip()
        if not txt or txt == last_text:
            continue
        if last_text and txt.startswith(last_text):
            txt = txt[len(last_text) :].strip()
        if not txt:
            continue
        last_text = txt
        raw_items.append((st, max(st + 0.5, en), txt))

    merged: List[Dict[str, Any]] = []
    for st, en, txt in raw_items:
        if (
            merged
            and (en - merged[-1]["start"] <= 6.5)
            and (st - merged[-1]["end"] <= 1.1)
            and (len(merged[-1]["text"]) + len(txt) < 150)
        ):
            merged[-1]["end"] = round(max(merged[-1]["end"], en), 2)
            merged[-1]["text"] = f"{merged[-1]['text']} {txt}".strip()
        else:
            merged.append({"start": round(st, 2), "end": round(en, 2), "text": txt})
    return merged


def _pick_best_subtitle_entry(info_dict: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    for bucket_name in ("subtitles", "automatic_captions"):
        bucket = info_dict.get(bucket_name) or {}
        if not isinstance(bucket, dict) or not bucket:
            continue

        def _lang_rank(lang_code: str) -> Tuple[int, int]:
            lc = lang_code.lower()
            if lc in ("en", "en-orig", "en-in", "en-us", "en-gb"):
                return (0, len(lc))
            if lc.startswith("en"):
                return (1, len(lc))
            if lc in ("hi", "hi-orig", "hi-in"):
                return (2, len(lc))
            if lc.startswith("hi"):
                return (3, len(lc))
            return (4, len(lc))

        for lang in sorted(bucket.keys(), key=_lang_rank):
            entries = bucket.get(lang) or []
            for preferred_ext in ("json3", "vtt"):
                for ent in entries:
                    if ent.get("ext") == preferred_ext and ent.get("url"):
                        return (ent["url"], preferred_ext)
    return None


def _build_heatmap_or_pace_curve(
    duration: float,
    heatmap: Optional[List[Dict[str, Any]]],
    segments: List[Dict[str, Any]],
) -> List[float]:
    num_secs = max(1, int(np.ceil(duration)))
    curve = np.zeros(num_secs, dtype=np.float64)

    if heatmap and len(heatmap) >= 5:
        for h_item in heatmap:
            s_i = max(0, int(float(h_item.get("start_time", 0))))
            e_i = min(num_secs, max(s_i + 1, int(np.ceil(float(h_item.get("end_time", s_i + 1))))))
            val = float(h_item.get("value", 0.0)) * 100.0
            curve[s_i:e_i] = np.maximum(curve[s_i:e_i], val)
        if np.max(curve) > 0:
            return [round(float(v), 1) for v in np.clip(curve, 0.0, 100.0)]

    for seg in segments:
        s_i = max(0, int(seg["start"]))
        e_i = min(num_secs, max(s_i + 1, int(np.ceil(seg["end"]))))
        dur_s = max(0.5, seg["end"] - seg["start"])
        words = seg["text"].split()
        wps = len(words) / dur_s
        punct_bonus = 1.25 if ("?" in seg["text"] or "!" in seg["text"]) else 1.0
        kw_hits = sum(1 for w in words if re.sub(r"[^a-z]", "", w.lower()) in HOOK_KEYWORDS)
        val = (wps * 24.0 + kw_hits * 7.5) * punct_bonus
        curve[s_i:e_i] = np.maximum(curve[s_i:e_i], val)

    if num_secs > 5:
        curve = np.convolve(curve, np.ones(5) / 5.0, mode="same")
    ref = float(np.percentile(curve, 96)) if np.max(curve) > 0 else 1.0
    if ref <= 1e-6:
        ref = 1.0
    return [round(float(v), 1) for v in np.clip((curve / ref) * 100.0, 0.0, 100.0)]


def _fetch_youtube_fast_metadata(
    url: str,
    prefer_720p: bool = False,
    skip_subtitles: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Single ~2.5s yt-dlp metadata call returning duration, title, Most-Replayed Heatmap,
    HD stream URLs, and optional direct captions (skips slow huge subtitle downloads if requested).
    """
    cmd = [
        *ytdlp_base_cmd(),
        "--dump-single-json",
        "--no-playlist",
        "--skip-download",
        "--no-warnings",
        url,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if res.returncode != 0 or not res.stdout.strip():
        return None

    try:
        info = json.loads(res.stdout)
    except json.JSONDecodeError:
        return None

    duration = float(info.get("duration") or 0.0)
    title = str(info.get("title") or "").strip()
    heatmap = info.get("heatmap") or []
    is_live = bool(info.get("is_live", False))
    was_live = bool(info.get("was_live", False))

    http_headers = info.get("http_headers") or {}
    formats = info.get("formats") or []

    # True HD streams (720p-1080p, NEVER 360p format 18!)
    hd_videos = [
        f for f in formats
        if f.get("url")
        and f.get("vcodec") not in (None, "none")
        and (f.get("height") or 0) >= 720
        and (f.get("height") or 0) <= 1080
        and f.get("protocol") in ("https", "http")
    ]
    if prefer_720p:
        # 720p H.264 is 2.5x faster to download on 3-hour streams & still sharper than 720px wide output!
        hd_videos.sort(
            key=lambda f: (
                1 if 700 <= (f.get("height") or 0) <= 760 else 0,
                1 if str(f.get("vcodec", "")).startswith("avc") else 0,
                f.get("tbr") or 0,
            ),
            reverse=True,
        )
    else:
        hd_videos.sort(
            key=lambda f: (
                1 if (f.get("height") or 0) >= 1000 else 0,
                1 if str(f.get("vcodec", "")).startswith("avc") else 0,
                f.get("height") or 0,
                f.get("tbr") or 0,
            ),
            reverse=True,
        )

    audios = [
        f for f in formats
        if f.get("url")
        and f.get("acodec") not in (None, "none")
        and f.get("vcodec") in (None, "none")
        and f.get("protocol") in ("https", "http")
    ]
    audios.sort(
        key=lambda f: (1 if f.get("ext") == "m4a" else 0, f.get("abr") or f.get("tbr") or 0),
        reverse=True,
    )

    direct_hd = None
    if hd_videos and audios:
        direct_hd = {
            "v": hd_videos[0]["url"],
            "a": audios[0]["url"],
            "height": int(hd_videos[0].get("height") or 720),
        }

    segments: List[Dict[str, Any]] = []
    # In Fast Heatmap Mode on videos with a real heatmap, skip downloading giant 4-hour subtitle files!
    should_pull_subs = (not skip_subtitles) or (len(heatmap) < 5)
    if should_pull_subs:
        sub_pick = _pick_best_subtitle_entry(info)
        if sub_pick:
            sub_url, sub_ext = sub_pick
            try:
                req = urllib.request.Request(
                    sub_url,
                    headers={"User-Agent": http_headers.get("User-Agent", "Mozilla/5.0")},
                )
                with urllib.request.urlopen(req, timeout=25.0) as resp:
                    raw_bytes = resp.read()
                segments = _parse_json3_bytes(raw_bytes) if sub_ext == "json3" else _parse_vtt_bytes(raw_bytes)
            except Exception:
                segments = []

    if duration <= 0.0 and segments:
        duration = float(segments[-1]["end"])
    if duration <= 0.0 and heatmap:
        duration = float(heatmap[-1].get("end_time", 60.0))

    return {
        "duration": round(duration, 2),
        "title": title,
        "heatmap": heatmap,
        "is_live": is_live,
        "was_live": was_live,
        "segments": segments,
        "direct_mp4": direct_hd,
        "http_headers": http_headers,
    }


def _extract_heatmap_peak_clips(
    heatmap: List[Dict[str, Any]],
    duration: float,
    video_type: str,
    video_title: str = "",
    num_clips: int = 5,
    min_dur: int = 30,
    max_dur: int = 48,
) -> List[Dict[str, Any]]:
    """
    INSTANT (~0.01s) Most-Watched Peak Extractor for Livestreams, Ended Streams & Long Videos!
    Picks the top non-overlapping peaks directly from YouTube's viewer Most-Replayed Heatmap
    without downloading or scanning the entire stream.
    """
    if not heatmap:
        return []

    target_dur = round((min_dur + max_dur) / 2.0, 1)
    min_spacing = max(target_dur + 18.0, 65.0)

    # Rank all heatmap buckets by viewer replay intensity (highest first)
    ranked = sorted(
        heatmap,
        key=lambda h: float(h.get("value", 0.0)),
        reverse=True,
    )

    picked: List[Dict[str, Any]] = []
    for item in ranked:
        if len(picked) >= num_clips:
            break
        p_start = float(item.get("start_time", 0.0))
        p_end = float(item.get("end_time", p_start + 15.0))
        p_val = float(item.get("value", 0.5))
        p_mid = (p_start + p_end) / 2.0

        # Skip tiny opening intro noise (first 10s) on long streams unless needed
        if duration > 300 and p_start < 12.0 and p_val < 0.95:
            continue

        # Ensure clips are cleanly spaced apart across the stream
        if any(abs(p_mid - prev["_mid"]) < min_spacing for prev in picked):
            continue

        # Start ~5.3s BEFORE the replay spike so viewers catch the buildup + peak reaction!
        clip_start = max(0.0, round(p_start - 5.3, 2))
        clip_end = min(duration, round(clip_start + target_dur + 0.45, 2))
        if clip_end - clip_start < 12.0:
            clip_start = max(0.0, round(clip_end - target_dur, 2))

        heat_score = round(min(100.0, max(60.0, p_val * 100.0)), 1)
        virality = round(min(99.0, 74.0 + p_val * 24.0), 1)

        picked.append({
            "_mid": p_mid,
            "start": clip_start,
            "end": clip_end,
            "duration": round(clip_end - clip_start, 2),
            "hook_title": "MOST REPLAYED MOMENT",
            "category": "🔥 Most-Watched Peak",
            "opening_hook": f"Top viewer-replayed moment ({int(heat_score)}% peak replay intensity on stream heatmap).",
            "ending_payoff": "Auto-snapped cleanly to the end of the spoken sentence.",
            "reason": f"Detected directly from YouTube's Most-Replayed Heatmap peak ({int(heat_score)}/100 viewer replay surge).",
            "social_caption": f"Most replayed moment from the stream 🔥🤯 #viral #reels #shorts #stream",
            "virality_score": virality,
            "hook_score": round(min(98.0, 78.0 + p_val * 20.0), 1),
            "coherence_score": 88.0,
            "audio_energy_score": heat_score,
            "video_type": video_type,
            "needs_word_sync": True,
            "needs_title_from_clip": True,  # Will auto-generate real Hook Title after 1.5s clip Whisper sync!
            "words": [],
        })

    for idx, c in enumerate(picked, 1):
        c.pop("_mid", None)
        c["rank"] = idx
    return picked


def generate_clip_metadata_from_words(
    words: List[Dict[str, Any]],
    video_title: str = "",
) -> Dict[str, str]:
    """
    0.4s fast LLM call on JUST the 35-second clip transcript to generate a punchy
    Hook Title, Reason, and Social Caption for instant Heatmap clips!
    """
    text = " ".join(str(w.get("word", "")).strip() for w in words).strip()
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not text or not api_key:
        return {}

    try:
        client = Groq(api_key=api_key)
        prompt = f"""Video Title: {video_title}
Clip Spoken Transcript: {text[:900]}

Generate viral metadata for this exact Instagram Reel / TikTok clip. Return ONLY valid JSON:
{{
  "hook_title": "3 TO 5 WORDS ALL CAPS ENGLISH HOOK",
  "reason": "One concise sentence explaining what happens in this viral moment.",
  "social_caption": "Punchy 1-line Instagram/TikTok caption with 4 viral hashtags"
}}"""
        comp = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3,
            reasoning_effort="low",
        )
        parsed = json.loads(comp.choices[0].message.content)
        return {
            "hook_title": str(parsed.get("hook_title", "MOST REPLAYED MOMENT")).strip().upper()[:46],
            "reason": str(parsed.get("reason", "")).strip(),
            "social_caption": str(parsed.get("social_caption", "")).strip(),
        }
    except Exception:
        return {}


# =============================================================================
# 2. AUDIO EXTRACTION, WHISPER SYNC & CLEAN SENTENCE-END SNAPPING
# =============================================================================
def extract_compressed_audio(
    source: str,
    temp_dir: str = "temp",
    max_scan_seconds: Optional[float] = None,
    job_id: Optional[str] = None,
) -> Dict[str, Any]:
    import glob as _glob
    Path(temp_dir).mkdir(parents=True, exist_ok=True)
    job_id = job_id or uuid.uuid4().hex[:8]
    mp3_path = str(Path(temp_dir) / f"{job_id}_16k.mp3")

    if _is_url(source):
        cap_s = int(max_scan_seconds or 180)
        raw_tmpl = str(Path(temp_dir) / f"{job_id}_raw.%(ext)s")

        cmd1 = [
            *ytdlp_base_cmd(),
            "--download-sections", f"*0-{cap_s}",
            "-f", "bestaudio/best",
            "--no-playlist", "--quiet", "--no-warnings",
            "-o", raw_tmpl,
            source,
        ]
        res = subprocess.run(cmd1, capture_output=True, text=True)
        matches = [m for m in _glob.glob(str(Path(temp_dir) / f"{job_id}_raw.*")) if Path(m).stat().st_size > 2000]

        if res.returncode != 0 or not matches:
            for old_f in _glob.glob(str(Path(temp_dir) / f"{job_id}_raw.*")):
                try:
                    Path(old_f).unlink()
                except OSError:
                    pass
            cmd2 = [
                *ytdlp_base_cmd(),
                "-f", "worstaudio[ext=m4a]/bestaudio[abr<=64]/bestaudio/best",
                "--no-playlist", "--quiet", "--no-warnings",
                "-o", raw_tmpl,
                source,
            ]
            res = subprocess.run(cmd2, capture_output=True, text=True)
            matches = [m for m in _glob.glob(str(Path(temp_dir) / f"{job_id}_raw.*")) if Path(m).stat().st_size > 2000]

        if not matches:
            raise RuntimeError(f"yt-dlp audio fetch failed: {res.stderr.strip()}")
        input_media = matches[0]
        source_type = "youtube_window"
    else:
        if not Path(source).exists():
            raise FileNotFoundError(f"Local file not found: {source}")
        input_media = source
        source_type = "local"

    ff_cmd = ["ffmpeg", "-y", "-v", "error", "-i", input_media]
    if max_scan_seconds:
        ff_cmd += ["-t", f"{max_scan_seconds:.1f}"]
    ff_cmd += ["-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k", mp3_path]
    ff_res = subprocess.run(ff_cmd, capture_output=True)
    if ff_res.returncode != 0 or not Path(mp3_path).exists() or Path(mp3_path).stat().st_size < 1000:
        dur_raw = _get_media_duration(input_media) or (max_scan_seconds or 30.0)
        dur = min(dur_raw, max_scan_seconds or 180.0)
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error",
                "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
                "-t", f"{dur:.2f}",
                "-ac", "1", "-ar", "16000", "-b:a", "32k",
                mp3_path,
            ],
            check=True,
        )

    size_mb = Path(mp3_path).stat().st_size / (1024 * 1024)
    if source_type != "local" and Path(input_media).exists():
        try:
            Path(input_media).unlink()
        except OSError:
            pass

    duration = _get_media_duration(mp3_path)
    return {
        "job_id": job_id,
        "source": source,
        "source_type": source_type,
        "title": Path(source).stem if source_type == "local" else "",
        "mp3_path": mp3_path,
        "size_mb": round(size_mb, 2),
        "duration": round(duration, 2),
    }



def compute_audio_energy(mp3_path: str) -> List[float]:
    sr = 16000
    cmd = [
        "ffmpeg", "-v", "error",
        "-i", mp3_path,
        "-f", "s16le", "-ac", "1", "-ar", str(sr), "-",
    ]
    raw_bytes = subprocess.check_output(cmd)
    samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float64)
    if samples.size == 0:
        return [0.0]

    num_secs = max(1, int(np.ceil(samples.size / sr)))
    rms_values = [
        float(np.sqrt(np.mean(samples[s * sr : (s + 1) * sr] ** 2)))
        for s in range(num_secs)
    ]
    arr = np.array(rms_values, dtype=np.float64)
    ref = float(np.percentile(arr, 95)) if np.max(arr) > 0 else 1.0
    if ref <= 1e-6:
        ref = 1.0
    return [round(float(v), 1) for v in np.clip((arr / ref) * 100.0, 0.0, 100.0)]


def transcribe_audio(mp3_path: str) -> Dict[str, Any]:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GROQ_API_KEY is missing in .env")

    client = Groq(api_key=api_key)
    with open(mp3_path, "rb") as audio_file:
        resp = client.audio.transcriptions.create(
            file=(Path(mp3_path).name, audio_file.read()),
            model="whisper-large-v3-turbo",
            response_format="verbose_json",
            timestamp_granularities=["word", "segment"],
            temperature=0.0,
        )

    raw_words = _get(resp, "words", []) or []
    raw_segments = _get(resp, "segments", []) or []

    words = [
        {
            "word": str(_get(w, "word", "")).strip(),
            "start": round(float(_get(w, "start", 0.0)), 3),
            "end": round(float(_get(w, "end", 0.0)), 3),
        }
        for w in raw_words
        if str(_get(w, "word", "")).strip()
    ]

    segments = [
        {
            "start": round(float(_get(s, "start", 0.0)), 2),
            "end": round(float(_get(s, "end", 0.0)), 2),
            "text": str(_get(s, "text", "")).strip(),
        }
        for s in raw_segments
        if str(_get(s, "text", "")).strip()
    ]

    if not words and segments:
        for seg in segments:
            tokens = seg["text"].split()
            if not tokens:
                continue
            step = max(0.05, (seg["end"] - seg["start"]) / len(tokens))
            for i, tok in enumerate(tokens):
                words.append({
                    "word": tok,
                    "start": round(seg["start"] + i * step, 3),
                    "end": round(seg["start"] + (i + 1) * step, 3),
                })

    return {
        "language": _get(resp, "language", "en"),
        "text": _get(resp, "text", ""),
        "words": words,
        "segments": segments,
    }


def _find_clean_sentence_end(
    segments: List[Dict[str, Any]],
    words: List[Dict[str, Any]],
    target_dur: float,
    max_file_dur: float,
) -> float:
    low_bound = max(14.0, target_dur - 6.0)
    high_bound = min(max_file_dur, target_dur + 3.2)

    punct_candidates: List[float] = []
    for seg in segments:
        s_end = float(seg["end"])
        txt = seg["text"].strip()
        if low_bound <= s_end <= high_bound and txt:
            last_word = _clean_token(txt.split()[-1])
            if txt[-1] in ".?!।…" and last_word not in HANGING_END_WORDS:
                punct_candidates.append(s_end)

    if punct_candidates:
        best = min(punct_candidates, key=lambda t: abs(t - target_dur))
        return round(min(max_file_dur, best + 0.45), 2)

    pause_candidates: List[float] = []
    for i, w in enumerate(words):
        w_end = float(w["end"])
        if not (low_bound <= w_end <= high_bound):
            continue
        tok = w["word"].strip()
        clean = _clean_token(tok)
        if clean in HANGING_END_WORDS:
            continue
        gap = (words[i + 1]["start"] - w_end) if (i + 1 < len(words)) else 0.60
        if (tok and tok[-1] in ".?!।") or gap >= 0.32:
            pause_candidates.append(w_end)

    if pause_candidates:
        best = min(pause_candidates, key=lambda t: abs(t - target_dur))
        return round(min(max_file_dur, best + 0.40), 2)

    return round(min(max_file_dur, target_dur), 2)


def convert_words_language(
    words: List[Dict[str, Any]],
    caption_lang: str = "hinglish",
) -> List[Dict[str, Any]]:
    if not words or caption_lang == "native":
        return words

    api_key = os.getenv("GROQ_API_KEY", "").strip()

    if caption_lang == "hinglish":
        non_latin_count = sum(1 for w in words if _has_non_latin(w.get("word", "")))
        if non_latin_count == 0:
            return words
        if not api_key:
            return [
                {
                    "word": _devanagari_to_hinglish_fallback(w["word"]),
                    "start": w["start"],
                    "end": w["end"],
                }
                for w in words
            ]

        # Chunk words in groups of up to 28 for guaranteed 1-to-1 indexed LLM translation
        client = Groq(api_key=api_key)
        chunk_size = 28
        result_words: List[Dict[str, Any]] = []

        for c_idx in range(0, len(words), chunk_size):
            chunk = words[c_idx : c_idx + chunk_size]
            input_dict = {str(i): str(w["word"]).strip() for i, w in enumerate(chunk)}

            prompt = (
                "Convert this numbered JSON dictionary of spoken Hindi/Devanagari words into natural "
                "Indian Hinglish (clean Latin letters A-Z) for viral Instagram Reels / YouTube Shorts captions.\n"
                "Rules:\n"
                f"1. Return a JSON object with the EXACT same keys '0' through '{len(chunk) - 1}'.\n"
                "2. Keep all English words in standard English spelling (e.g., 'college', 'technology', 'startup').\n"
                "3. Convert Hindi/Devanagari words to popular colloquial Hinglish (e.g. 'yeh', 'hai', 'karega', 'nahi', 'toh', 'apna', 'dosto', 'kaise').\n"
                "4. Fix obvious speech-to-text typos.\n\n"
                f"INPUT:\n{json.dumps(input_dict, ensure_ascii=False)}"
            )
            converted_map: Dict[str, str] = {}
            try:
                comp = client.chat.completions.create(
                    model="openai/gpt-oss-20b",
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                    reasoning_effort="low",
                )
                parsed = json.loads(comp.choices[0].message.content)
                if isinstance(parsed, dict):
                    converted_map = {str(k): str(v).strip() for k, v in parsed.items()}
            except Exception:
                converted_map = {}

            for i, w in enumerate(chunk):
                hw = converted_map.get(str(i), "").strip()
                if not hw or _has_non_latin(hw):
                    hw = _devanagari_to_hinglish_fallback(w["word"])
                result_words.append({
                    "word": hw,
                    "start": w["start"],
                    "end": w["end"],
                })

        return result_words

    if caption_lang == "english" and api_key:
        try:
            client = Groq(api_key=api_key)
            # Group into natural phrases based on punctuation or silence gaps > 0.40s
            phrases: List[List[Dict[str, Any]]] = []
            curr_phrase: List[Dict[str, Any]] = []

            for i, w in enumerate(words):
                curr_phrase.append(w)
                txt = str(w.get("word", "")).strip()
                has_punct = bool(txt and txt[-1] in ".?!।")
                is_gap = (i + 1 < len(words) and (words[i + 1]["start"] - w["end"]) >= 0.40)
                is_long = len(curr_phrase) >= 12
                if has_punct or is_gap or is_long or (i + 1 == len(words)):
                    phrases.append(curr_phrase)
                    curr_phrase = []

            phrase_texts = {str(k): " ".join(str(w["word"]).strip() for w in p) for k, p in enumerate(phrases)}
            prompt = (
                "Translate each numbered spoken phrase into punchy, natural conversational English "
                "for short-form Instagram Reels / YouTube Shorts captions.\n"
                f"Return a JSON object with the EXACT same keys '0' through '{len(phrases) - 1}': {{\"0\": \"...\", ...}}\n\n"
                f"INPUT PHRASES:\n{json.dumps(phrase_texts, ensure_ascii=False)}"
            )
            comp = client.chat.completions.create(
                model="openai/gpt-oss-20b",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.2,
                reasoning_effort="low",
            )
            trans_map = json.loads(comp.choices[0].message.content)

            en_words: List[Dict[str, Any]] = []
            for k, p in enumerate(phrases):
                en_sentence = str(trans_map.get(str(k), "")).strip()
                tokens = en_sentence.split() if en_sentence else [w["word"] for w in p]
                t_start = p[0]["start"]
                t_end = p[-1]["end"]
                dur = max(0.12, t_end - t_start)
                step = dur / max(1, len(tokens))
                for j, tok in enumerate(tokens):
                    en_words.append({
                        "word": tok,
                        "start": round(t_start + j * step, 3),
                        "end": round(t_start + (j + 1) * step, 3),
                    })
            if en_words:
                return en_words
        except Exception:
            pass

    return [
        {"word": _devanagari_to_hinglish_fallback(w["word"]), "start": w["start"], "end": w["end"]}
        for w in words
    ]


def transcribe_and_snap_clip(
    video_clip_path: str,
    target_dur: float,
    caption_lang: str = "hinglish",
    temp_dir: str = "temp",
) -> Dict[str, Any]:
    Path(temp_dir).mkdir(parents=True, exist_ok=True)
    tmp_mp3 = str(Path(temp_dir) / f"clip_sync_{uuid.uuid4().hex[:8]}.mp3")
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error",
                "-i", video_clip_path,
                "-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k",
                tmp_mp3,
            ],
            check=True,
        )
        file_dur = _get_media_duration(tmp_mp3)
        res = transcribe_audio(tmp_mp3)
        raw_words = res.get("words", [])
        raw_segs = res.get("segments", [])

        clean_end = _find_clean_sentence_end(raw_segs, raw_words, target_dur, file_dur)
        snapped_words = [w for w in raw_words if w["start"] < clean_end - 0.08]
        final_words = convert_words_language(snapped_words, caption_lang=caption_lang)
        return {"words": final_words, "clean_end": clean_end}
    finally:
        try:
            if Path(tmp_mp3).exists():
                Path(tmp_mp3).unlink()
        except OSError:
            pass


def transcribe_clip_words(
    video_clip_path: str,
    caption_lang: str = "hinglish",
    temp_dir: str = "temp",
) -> List[Dict[str, Any]]:
    dur = _get_media_duration(video_clip_path)
    return transcribe_and_snap_clip(video_clip_path, dur, caption_lang=caption_lang, temp_dir=temp_dir)["words"]


# =============================================================================
# 3. STORY-ARC VIRAL DIRECTOR (GPT-OSS-120B + SEGMENT-ID ANCHORING)
# =============================================================================
def _energy_stats(energy_curve: List[float], start: float, end: float) -> float:
    if not energy_curve:
        return 50.0
    s_idx = max(0, int(start))
    e_idx = min(len(energy_curve), max(s_idx + 1, int(np.ceil(end))))
    window = energy_curve[s_idx:e_idx]
    if not window:
        return 50.0
    score = 0.6 * float(np.mean(window)) + 0.4 * float(np.max(window))
    return round(min(100.0, max(0.0, score)), 1)


def _build_story_safe_transcript(
    segments: List[Dict[str, Any]],
    energy_curve: List[float],
    max_chars: int = 18500,
) -> str:
    lines = []
    for idx, seg in enumerate(segments):
        e_score = int(round(_energy_stats(energy_curve, seg["start"], seg["end"])))
        lines.append((
            idx,
            seg["start"],
            e_score,
            f"[#{idx} | {seg['start']:.1f}s-{seg['end']:.1f}s | E:{e_score}] {seg['text']}",
        ))

    full_text = "\n".join(item[3] for item in lines)
    if len(full_text) <= max_chars:
        return full_text

    total_dur = segments[-1]["end"] if segments else 1.0
    windows = []
    w_start = 0.0
    while w_start < total_dur:
        w_end = w_start + 180.0
        w_items = [x for x in lines if w_start <= x[1] < w_end]
        if len(w_items) >= 4:
            score = float(np.mean([x[2] for x in w_items])) + 0.45 * float(np.max([x[2] for x in w_items]))
            windows.append((w_start, score, w_items))
        w_start += 150.0

    windows.sort(key=lambda t: t[1], reverse=True)
    chosen = []
    used_ids = set()
    char_count = 0

    for ws, sc, w_items in windows:
        if any(abs(ws - prev_ws) < 120.0 for prev_ws, _ in chosen):
            continue
        fresh = [x for x in w_items if x[0] not in used_ids]
        block = "\n".join(x[3] for x in fresh)
        if char_count + len(block) > max_chars and chosen:
            break
        chosen.append((ws, block))
        used_ids.update(x[0] for x in fresh)
        char_count += len(block)

    chosen.sort(key=lambda t: t[0])
    return "\n--- [NEXT VIDEO SECTION] ---\n".join(b for _, b in chosen)


def _extend_past_hanging_ending(
    segments: List[Dict[str, Any]],
    start_id: int,
    end_id: int,
    max_dur: int,
) -> int:
    start_t = segments[start_id]["start"]
    while end_id + 1 < len(segments):
        txt = segments[end_id]["text"].strip()
        if not txt:
            break
        last_tok = _clean_token(txt.split()[-1])
        next_dur = segments[end_id + 1]["end"] - start_t
        if (last_tok in HANGING_END_WORDS or len(txt.split()) < 3) and next_dur <= max_dur + 12:
            end_id += 1
        else:
            break
    return end_id


def find_viral_highlights(
    transcript: Dict[str, Any],
    energy_curve: List[float],
    duration: float,
    video_type: str = "informational",
    clip_goal: str = "viral_hook",
    custom_prompt: str = "",
    video_title: str = "",
    num_clips: int = 5,
    min_dur: int = 35,
    max_dur: int = 58,
    needs_word_sync: bool = False,
    fast_llm: bool = False,
) -> List[Dict[str, Any]]:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    client = Groq(api_key=api_key)
    segments = transcript["segments"]

    if duration < min_dur + 5:
        min_dur = max(12, int(duration * 0.45))
        max_dur = max(min_dur + 5, int(duration))

    annotated = _build_story_safe_transcript(segments, energy_curve)
    title_hint = f"VIDEO TITLE: {video_title}\n" if video_title else ""

    goal_hints = {
        "viral_hook": "Prioritize shocking reveals, dramatic turning points, bold mysteries, and irresistible curiosity cliffhangers.",
        "educational": "Prioritize complete mind-blowing facts, counter-intuitive explanations, and crystal-clear lessons with a strong conclusion.",
        "funny_hype": "Prioritize funniest reactions, peak banter, unexpected punchlines, and chaotic hype moments.",
        "motivational": "Prioritize powerful life realizations, intense emotional highs, and memorable takeaways.",
    }
    goal_instruction = goal_hints.get(clip_goal, goal_hints["viral_hook"])

    system_prompt = (
        "You are an elite viral Instagram Reels / TikTok / YouTube Shorts director. "
        "Every clip MUST deliver a COMPLETE high-retention arc: "
        "(1) Scroll-stopping Hook -> (2) Rising tension / emotion -> (3) Clear Payoff or Cliffhanger. "
        "Never cut mid-sentence. Return ONLY valid JSON."
    )

    user_prompt = f"""{title_hint}VIDEO TYPE: {video_type}
TARGET CLIP STYLE: {goal_instruction}
TOTAL LENGTH: {duration:.1f}s

Read the numbered transcript segments ([#ID | start-end | E:score]) carefully and select the TOP {num_clips} non-overlapping viral clips.

STRICT QUALITY RULES:
1. Pick exact integer "start_id" and "end_id" from [#ID] tags so each clip is {min_dur} to {max_dur} seconds long.
2. NEVER pick random setup exposition without a twist, reaction, or payoff inside the clip.
3. NEVER end mid-sentence. End RIGHT AFTER a punchline, reveal, or complete dramatic statement.
4. "hook_title" MUST be punchy ENGLISH, 3 to 5 words MAX, ALL CAPS.
5. Write "social_caption": a punchy 1-line Instagram/TikTok caption with 4 viral hashtags.

Return strictly this JSON:
{{
  "clips": [
    {{
      "start_id": 42,
      "end_id": 51,
      "hook_title": "HOW ONE MOMENT CHANGED EVERYTHING",
      "category": "Shocking Story / Reaction / Fact / Insight",
      "opening_hook": "What grabs attention in the first 3 seconds.",
      "ending_payoff": "The twist, punchline, or cliffhanger that completes the clip.",
      "reason": "One concise sentence explaining why viewers will watch till the end.",
      "social_caption": "You won't believe how this ended 🤯🔥 #viral #reels #shorts #trending",
      "hook_score": 94,
      "coherence_score": 92
    }}
  ]
}}

NUMBERED TRANSCRIPT:
{annotated}
"""

    raw_json = None
    last_err = None
    models = (
        [("openai/gpt-oss-20b", "low"), ("openai/gpt-oss-120b", "low")]
        if fast_llm
        else [("openai/gpt-oss-120b", "medium"), ("openai/gpt-oss-20b", "low")]
    )
    for model_id, effort in models:
        try:
            completion = client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.25,
                reasoning_effort=effort,
            )
            raw_json = completion.choices[0].message.content
            break
        except Exception as e:
            last_err = e

    if not raw_json:
        raise RuntimeError(f"Groq highlight scoring failed: {last_err}")

    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw_json, re.DOTALL)
        if not match:
            raise RuntimeError("LLM returned non-JSON output.")
        parsed = json.loads(match.group(0))

    raw_clips = parsed.get("clips", [])
    words = transcript.get("words", [])
    results = []

    for c in raw_clips:
        s_id = c.get("start_id")
        e_id = c.get("end_id")
        if isinstance(s_id, (int, float)) and isinstance(e_id, (int, float)) and segments:
            s_i = max(0, min(len(segments) - 1, int(s_id)))
            e_i = max(s_i, min(len(segments) - 1, int(e_id)))
            e_i = _extend_past_hanging_ending(segments, s_i, e_i, max_dur=max_dur)
            raw_start = float(segments[s_i]["start"])
            raw_end = float(segments[e_i]["end"])
            while (raw_end - raw_start) < min_dur and e_i + 1 < len(segments):
                e_i += 1
                raw_end = float(segments[e_i]["end"])
            while (raw_end - raw_start) > max_dur + 18 and e_i > s_i:
                e_i -= 1
                raw_end = float(segments[e_i]["end"])
            start = max(0.0, round(raw_start - 0.28, 2))
            end = min(duration, round(raw_end + 0.45, 2))
        else:
            raw_s = max(0.0, float(c.get("start", 0.0)))
            raw_e = min(duration, float(c.get("end", raw_s + min_dur)))
            if raw_e - raw_s < min_dur:
                raw_e = min(duration, raw_s + min_dur)
            if raw_e - raw_s > max_dur + 15:
                raw_e = min(duration, raw_s + max_dur)
            start = max(0.0, round(raw_s - 0.28, 2))
            end = min(duration, round(raw_e + 0.45, 2))

        hook_score = float(np.clip(float(c.get("hook_score", 82)), 0, 100))
        coherence_score = float(np.clip(float(c.get("coherence_score", 82)), 0, 100))
        audio_score = _energy_stats(energy_curve, start, end)
        virality_score = round(0.45 * hook_score + 0.35 * coherence_score + 0.20 * audio_score, 1)

        clip_words = []
        if not needs_word_sync and words:
            clip_words = [
                {
                    "word": w["word"],
                    "start": round(max(0.0, w["start"] - start), 3),
                    "end": round(max(0.05, w["end"] - start), 3),
                }
                for w in words
                if w["end"] > start and w["start"] < end
            ]

        results.append({
            "start": round(start, 2),
            "end": round(end, 2),
            "duration": round(end - start, 2),
            "hook_title": str(c.get("hook_title", "VIRAL MOMENT")).strip()[:46],
            "category": str(c.get("category", "Highlight")).strip(),
            "opening_hook": str(c.get("opening_hook", "")).strip(),
            "ending_payoff": str(c.get("ending_payoff", "")).strip(),
            "reason": str(c.get("reason", "")).strip(),
            "social_caption": str(c.get("social_caption", "")).strip(),
            "virality_score": virality_score,
            "hook_score": round(hook_score, 1),
            "coherence_score": round(coherence_score, 1),
            "audio_energy_score": audio_score,
            "video_type": video_type,
            "needs_word_sync": needs_word_sync or (len(clip_words) == 0),
            "needs_title_from_clip": False,
            "words": clip_words,
        })

    results.sort(key=lambda x: x["virality_score"], reverse=True)
    for idx, clip in enumerate(results, 1):
        clip["rank"] = idx
    return results


def analyze_video(
    source: str,
    video_type: str = "full_video",
    clip_goal: str = "viral_hook",
    fast_heatmap_mode: bool = False,
    custom_prompt: str = "",
    num_clips: int = 5,
    min_dur: int = 35,
    max_dur: int = 55,
    temp_dir: str = "temp",
    status_cb: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """
    Two high-speed Phase 1 pathways:
    1. FAST HEATMAP MODE (Best for Livestreams / Ended Streams / Long VODs):
       Pulls YouTube's Most-Replayed Heatmap in ~2.5s and instantly jumps to the top
       most-watched peaks (ZERO full-stream scan!).
    2. STORY-ARC MODE (Default for Explainers / Podcasts):
       Pulls YouTube captions + heatmap in ~3s and runs 120B Story-Arc Director.
    """
    def log(msg: str):
        if status_cb:
            status_cb(msg)

    timings: Dict[str, float] = {}
    t_total = time.perf_counter()

    yt_meta = None
    if _is_url(source):
        log(
            "⚡ Fast-fetching YouTube Stream Heatmap & HD info (~2.5s)..."
            if fast_heatmap_mode
            else "Fast-fetching YouTube transcript, heatmap & HD stream info (~3s)..."
        )
        t0 = time.perf_counter()
        yt_meta = _fetch_youtube_fast_metadata(
            source,
            prefer_720p=fast_heatmap_mode,
            skip_subtitles=fast_heatmap_mode,
        )
        timings["meta_subs_s"] = round(time.perf_counter() - t0, 2)

    # FAST PATH: Instant YouTube Heatmap Peak Extraction (finishes Phase 1 in ~2.5-3.5s!)
    if fast_heatmap_mode and yt_meta and len(yt_meta.get("heatmap", [])) >= 5:
        log("🔥 Stream Heatmap detected! Jumping straight to Top Most-Watched Peaks (0s scan)...")
        duration = yt_meta["duration"]
        energy_curve = _build_heatmap_or_pace_curve(duration, yt_meta["heatmap"], [])
        clips = _extract_heatmap_peak_clips(
            heatmap=yt_meta["heatmap"],
            duration=duration,
            video_type=video_type,
            video_title=yt_meta["title"],
            num_clips=num_clips,
            min_dur=min_dur,
            max_dur=max_dur,
        )
        timings["scoring_s"] = 0.02
        timings["phase1_total_s"] = round(time.perf_counter() - t_total, 2)
        return {
            "audio_info": {
                "job_id": uuid.uuid4().hex[:8],
                "source": source,
                "source_type": "youtube_heatmap_instant",
                "title": yt_meta["title"],
                "direct_mp4": yt_meta["direct_mp4"],
                "http_headers": yt_meta["http_headers"],
                "mp3_path": None,
                "size_mb": 0.02,
                "duration": duration,
            },
            "energy_curve": energy_curve,
            "transcript": {"language": "auto", "text": "", "words": [], "segments": []},
            "video_type": video_type,
            "clip_goal": clip_goal,
            "discovery_mode": "Instant Most-Replayed Heatmap",
            "clips": clips,
            "timings": timings,
        }

    # FAST CAPTION PATH (if YouTube captions exist)
    if yt_meta and len(yt_meta.get("segments", [])) >= 4:
        duration = yt_meta["duration"]
        energy_curve = _build_heatmap_or_pace_curve(duration, yt_meta["heatmap"], yt_meta["segments"])
        audio_info = {
            "job_id": uuid.uuid4().hex[:8],
            "source": source,
            "source_type": "youtube_fast_subs",
            "title": yt_meta["title"],
            "direct_mp4": yt_meta["direct_mp4"],
            "http_headers": yt_meta["http_headers"],
            "mp3_path": None,
            "size_mb": 0.05,
            "duration": duration,
        }
        transcript = {
            "language": "auto",
            "text": " ".join(s["text"] for s in yt_meta["segments"]),
            "words": [],
            "segments": yt_meta["segments"],
        }
        needs_word_sync = True
    else:
        # Local file OR brand-new stream with neither heatmap nor subtitles yet
        scan_cap = 90 if (fast_heatmap_mode and _is_url(source)) else (180 if _is_url(source) else None)
        log(f"No heatmap/captions yet — scanning fast {scan_cap or 'local'}s audio sample...")
        t0 = time.perf_counter()
        audio_info = extract_compressed_audio(source, temp_dir=temp_dir, max_scan_seconds=scan_cap)
        if yt_meta:
            audio_info["direct_mp4"] = yt_meta.get("direct_mp4")
            audio_info["http_headers"] = yt_meta.get("http_headers", {})
            audio_info["title"] = yt_meta.get("title", "")
        timings["audio_extract_s"] = round(time.perf_counter() - t0, 2)

        log("Computing Audio RMS Excitement curve...")
        t0 = time.perf_counter()
        energy_curve = compute_audio_energy(audio_info["mp3_path"])
        timings["audio_energy_s"] = round(time.perf_counter() - t0, 2)

        log("Transcribing via Groq Whisper-v3-Turbo...")
        t0 = time.perf_counter()
        transcript = transcribe_audio(audio_info["mp3_path"])
        timings["transcribe_s"] = round(time.perf_counter() - t0, 2)
        needs_word_sync = False

    log(f"Selecting top {num_clips} viral arcs ({'Fast 20B' if fast_heatmap_mode else '120B Story Director'})...")
    t0 = time.perf_counter()
    clips = find_viral_highlights(
        transcript=transcript,
        energy_curve=energy_curve,
        duration=audio_info["duration"],
        video_type=video_type,
        clip_goal=clip_goal,
        custom_prompt=custom_prompt,
        video_title=audio_info.get("title", ""),
        num_clips=num_clips,
        min_dur=min_dur,
        max_dur=max_dur,
        needs_word_sync=needs_word_sync,
        fast_llm=fast_heatmap_mode,
    )
    timings["scoring_s"] = round(time.perf_counter() - t0, 2)
    timings["phase1_total_s"] = round(time.perf_counter() - t_total, 2)

    return {
        "audio_info": audio_info,
        "energy_curve": energy_curve,
        "transcript": transcript,
        "video_type": video_type,
        "clip_goal": clip_goal,
        "discovery_mode": "Fast Stream Fallback" if fast_heatmap_mode else "120B Story-Arc Director",
        "clips": clips,
        "timings": timings,
    }