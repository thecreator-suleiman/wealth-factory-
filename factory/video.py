"""Step 4: build the final vertical video - moving images, voice, big captions, progress bar."""
import re
import subprocess
from pathlib import Path

from .common import ROOT, log

FONT_DIR = ROOT / "work" / "fonts"


def _font() -> tuple[str, int]:
    """Anton (downloaded by the workflow) looks best; DejaVu Sans Bold is the safe fallback."""
    if (FONT_DIR / "Anton-Regular.ttf").exists():
        return "Anton", 0
    return "DejaVu Sans", -1


def _ts(t: float) -> str:
    t = max(t, 0)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _esc(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")")


def _chunks(words: list[tuple[float, float, str]]) -> list[tuple[float, float, str]]:
    """Group words into 1-3 word bites, breaking at punctuation - easy to read on a phone."""
    out, cur = [], []
    for w in words:
        cur.append(w)
        text = " ".join(x[2] for x in cur)
        if len(cur) >= 3 or len(text) >= 14 or re.search(r"[.,!?;:]$", w[2]):
            out.append((cur[0][0], cur[-1][1], text))
            cur = []
    if cur:
        out.append((cur[0][0], cur[-1][1], " ".join(x[2] for x in cur)))
    return out


def write_captions(words: list, hook: str, total: float, path: Path, w: int, h: int) -> None:
    font, bold = _font()
    size = 104 if font == "Anton" else 86
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,{bold},0,0,0,100,100,1,0,1,7,3,5,60,60,0,1
Style: Hook,{font},{size + 14},&H0000D4FF,&H00FFFFFF,&H00000000,&HC8000000,{bold},0,0,0,100,100,1,0,3,18,0,5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    if hook:
        lines.append(
            f"Dialogue: 1,{_ts(0)},{_ts(2.4)},Hook,,0,0,0,,"
            f"{{\\pos({w // 2},{int(h * 0.22)})\\fad(120,200)}}{_esc(hook.upper())}"
        )
    chunks = _chunks(words)
    for i, (start, end, text) in enumerate(chunks):
        nxt = chunks[i + 1][0] if i + 1 < len(chunks) else min(end + 0.6, total)
        end = max(end, min(nxt, end + 0.5))
        styled = []
        for word in text.split():
            clean = _esc(word.upper())
            if re.search(r"\d|\$|%", word):  # numbers pop in yellow
                styled.append(f"{{\\c&H0000D4FF&}}{clean}{{\\c&H00FFFFFF&}}")
            else:
                styled.append(clean)
        lines.append(
            f"Dialogue: 0,{_ts(start)},{_ts(end)},Cap,,0,0,0,,"
            f"{{\\pos({w // 2},{int(h * 0.64)})\\fscx82\\fscy82\\t(0,90,\\fscx100\\fscy100)}}"
            + " ".join(styled)
        )
    path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")


MOTIONS = [
    # slow zoom in
    ("min(1+0.0011*on,1.18)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
    # slow zoom out
    ("max(1.18-0.0011*on,1.0)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
    # drift upward
    ("1.14", "iw/2-(iw/zoom/2)", "(ih-ih/zoom)*(1-on/{d})"),
    # drift sideways
    ("1.14", "(iw-iw/zoom)*on/{d}", "ih/2-(ih/zoom/2)"),
]


def _clip(img: Path, out: Path, seconds: float, motion: int, w: int, h: int, fps: int) -> None:
    frames = max(int(seconds * fps), fps)
    z, x, y = MOTIONS[motion % len(MOTIONS)]
    x, y = x.format(d=frames), y.format(d=frames)
    vf = (
        f"scale={w * 2}:{h * 2}:flags=lanczos,"
        f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={w}x{h}:fps={fps},"
        f"eq=contrast=1.06:saturation=1.12,format=yuv420p"
    )
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(img), "-vf", vf,
         "-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
         "-r", str(fps), str(out)],
        check=True,
    )


def build_video(cfg: dict, images: list[Path], voice: Path, words: list, hook: str,
                total: float, folder: Path) -> Path:
    v = cfg["video"]
    w, h, fps = v["width"], v["height"], v["fps"]
    tail = 0.8
    length = total + tail
    per = length / len(images)
    log(f"Rendering {len(images)} scenes, {length:.1f}s total")
    clips = []
    for i, img in enumerate(images):
        out = folder / f"clip_{i:02d}.mp4"
        _clip(img, out, per + (0.2 if i == len(images) - 1 else 0), i, w, h, fps)
        clips.append(out)
    listing = folder / "clips.txt"
    listing.write_text("".join(f"file '{c.name}'\n" for c in clips), encoding="utf-8")
    joined = folder / "joined.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(listing), "-c", "copy", str(joined)],
        check=True, cwd=folder,
    )
    ass = folder / "captions.ass"
    write_captions(words, hook, total, ass, w, h)
    final = folder / "final.mp4"
    fonts = FONT_DIR if FONT_DIR.exists() else folder
    graph = (
        f"[0:v]ass='{ass.name}':fontsdir='{fonts}'[cap];"
        f"color=c=0xFFD400:s={w}x12:r={fps}[bar];"
        f"[cap][bar]overlay=x='-w+w*t/{length:.2f}':y=0:shortest=1[v]"
    )
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-i", str(joined), "-i", str(voice),
         "-filter_complex", graph,
         "-map", "[v]", "-map", "1:a",
         "-af", f"apad=pad_dur={tail},loudnorm=I=-14:TP=-1.5:LRA=11",
         "-t", f"{length:.2f}",
         "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-profile:v", "high",
         "-pix_fmt", "yuv420p", "-r", str(fps),
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
         "-movflags", "+faststart", str(final)],
        check=True, cwd=folder,
    )
    size_mb = final.stat().st_size / 1e6
    log(f"Video ready: {final.name} ({size_mb:.1f} MB)")
    return final
