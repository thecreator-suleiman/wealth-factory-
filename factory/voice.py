"""Step 2: turn the script into a human-sounding voiceover + word timings for captions.

Main engine: Microsoft neural voices through the free `edge-tts` package.
Emergency backup: Google's free `gTTS` voice (less natural) so a video still goes out.
"""
import asyncio
import re
import subprocess
from pathlib import Path

from .common import log


def audio_seconds(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


async def _edge(text: str, voice: str, rate: str, out: Path, pitch: str = "+0Hz") -> list[tuple[float, float, str]]:
    import edge_tts

    try:
        com = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, boundary="WordBoundary")
    except TypeError:  # older edge-tts sends word boundaries by default
        com = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    words = []
    with open(out, "wb") as f:
        async for chunk in com.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 1e7
                end = start + chunk["duration"] / 1e7
                words.append((start, end, chunk["text"]))
    if out.stat().st_size < 10_000:
        raise RuntimeError("voice file came back empty")
    return words


def _estimate_timings(text: str, total: float) -> list[tuple[float, float, str]]:
    """When the engine gives no word timings, spread words by their length."""
    words = text.split()
    weights = [len(re.sub(r"\W", "", w)) + 2 + (4 if re.search(r"[.!?]$", w) else 0) for w in words]
    scale = total / sum(weights)
    t, out = 0.0, []
    for w, k in zip(words, weights):
        d = k * scale
        out.append((t, t + d * 0.9, w))
        t += d
    return out


SAY = {"Monezic": "Money-zick", "monezic": "Money-zick", "MONEZIC": "Money-zick"}


def _fix_names(words: list) -> list:
    """Show the real spelling in captions even though the voice reads a phonetic version."""
    out = []
    for a, b, w in words:
        if out and w.lower().strip(".,!?") in ("zick", "-zick") and out[-1][2].lower().startswith("money"):
            out[-1] = (out[-1][0], b, "MONEZIC" + w[len(w.rstrip(".,!?")):])
            continue
        if w.lower().startswith("money-zick"):
            w = "MONEZIC" + w[len("money-zick"):]
        out.append((a, b, w))
    return out


def make_voice(cfg: dict, text: str, folder: Path) -> tuple[Path, list, str]:
    folder.mkdir(parents=True, exist_ok=True)
    for k, v in SAY.items():
        text = text.replace(k, v)
    out = folder / "voice.mp3"
    v = cfg["voice"]
    import time as _t
    for voice in (v["main"], v["backup"]):
        tries = 6 if voice == v["main"] else 3
        for attempt in range(tries):
            if attempt:
                _t.sleep(15 * attempt)
            try:
                words = asyncio.run(_edge(text, voice, v["rate"], out, v.get("pitch", "+0Hz")))
                total = audio_seconds(out)
                if len(words) < len(text.split()) * 0.5:
                    log("Word timings missing - estimating captions instead.")
                    words = _estimate_timings(text, total)
                log(f"Voice ready: {voice}, {total:.1f}s, {len(words)} timed words")
                return out, _fix_names(words), voice
            except Exception as e:  # noqa: BLE001
                log(f"Voice {voice} failed (try {attempt + 1}): {e}")
    # Emergency backup
    log("Neural voice unavailable - using backup voice (gTTS).")
    from gtts import gTTS

    raw = folder / "voice_raw.mp3"
    gTTS(text=text, lang="en", tld="com").save(str(raw))
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw),
         "-filter:a", "atempo=1.15", str(out)],
        check=True,
    )
    total = audio_seconds(out)
    return out, _estimate_timings(text, total), "gTTS backup"


def fit_length(voice: Path, words: list, lo: float = 72.0, hi: float = 95.0):
    """Gently speed up / slow down the voice so the video lands between lo and hi seconds.
    (TikTok pays only for 60s+, and shorter keeps viewers watching.)"""
    total = audio_seconds(voice)
    if lo <= total <= hi:
        return voice, words, total
    target = hi - 4 if total > hi else lo + 2
    factor = min(max(total / target, 0.85), 1.25)
    out = voice.with_name("voice_fit.mp3")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(voice),
                    "-filter:a", f"atempo={factor:.4f}", str(out)], check=True)
    new_total = audio_seconds(out)
    log(f"Voice adjusted from {total:.1f}s to {new_total:.1f}s (x{factor:.2f})")
    return out, [(a / factor, b / factor, w) for a, b, w in words], new_total
