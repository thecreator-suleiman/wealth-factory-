"""Step 2: turn the script into a human-sounding voiceover + word timings for captions.

Main engine: Microsoft neural voices through the free `edge-tts` package.
If the voice service is down, the post is skipped (no different voice is ever used).
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
    import re as _re
    import time as _t
    # Plain text only: odd symbols can make the voice service return no audio.
    clean = _re.sub(r"[^A-Za-z0-9 .,!?'$%:;\-]", " ", text.replace("&", " and "))
    clean = _re.sub(r"\s+", " ", clean).strip()
    # Same male voice every time. Keep retrying for up to ~30 minutes;
    # never switch to a different-sounding voice.
    deadline = _t.time() + 30 * 60
    attempt = 0
    while True:
        for voice in (v["main"], v["backup"]):
            try:
                words = asyncio.run(_edge(clean, voice, v["rate"], out, v.get("pitch", "+0Hz")))
                total = audio_seconds(out)
                if len(words) < len(clean.split()) * 0.5:
                    log("Word timings missing - estimating captions instead.")
                    words = _estimate_timings(clean, total)
                log(f"Voice ready: {voice}, {total:.1f}s, {len(words)} timed words")
                return out, _fix_names(words), voice
            except Exception as e:  # noqa: BLE001
                log(f"Voice {voice} failed (try {attempt + 1}): {e}")
        attempt += 1
        if _t.time() > deadline:
            raise RuntimeError("Andrew voice unavailable for 30 minutes - skipping this post to keep the voice consistent.")
        _t.sleep(min(30 * attempt, 180))


def fit_length(voice: Path, words: list, lo: float = 82.0, hi: float = 110.0):
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
