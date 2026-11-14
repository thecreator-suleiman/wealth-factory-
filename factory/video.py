"""Step 4: build the final vertical video - stickman scenes, voice, piano, big captions."""
import random
import re
import subprocess
from pathlib import Path

from .common import ROOT, log

FONT_DIR = ROOT / "work" / "fonts"

# ASS colours are &HAABBGGRR
BLACK = "&H00141414"
WHITE = "&H00FFFFFF"
GREEN = "&H004AA316"   # #16A34A
GREEN_HEX = "0x16A34A"


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
    size = 128 if font == "Anton" else 96
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font},{size},{BLACK},{BLACK},{WHITE},&H00000000,{bold},0,0,0,100,100,2,0,1,10,0,5,60,60,0,1
Style: Hook,{font},{size + 6},{WHITE},{WHITE},{GREEN},&H00000000,{bold},0,0,0,100,100,2,0,3,22,0,5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    if hook:
        lines.append(
            f"Dialogue: 1,{_ts(0)},{_ts(2.6)},Hook,,0,0,0,,"
            f"{{\\pos({w // 2},{int(h * 0.14)})\\fad(100,200)\\fscx85\\fscy85\\t(0,120,\\fscx100\\fscy100)}}"
            f"{_esc(hook.upper())}"
        )
    chunks = _chunks(words)
    for i, (start, end, text) in enumerate(chunks):
        nxt = chunks[i + 1][0] if i + 1 < len(chunks) else min(end + 0.6, total)
        end = max(end, min(nxt, end + 0.5))
        styled = []
        for word in text.split():
            clean = _esc(word.upper())
            if re.search(r"\d|\$|%", word):  # numbers pop in green
                styled.append(f"{{\\c{GREEN}}}{clean}{{\\c{BLACK}}}")
            else:
                styled.append(clean)
        lines.append(
            f"Dialogue: 0,{_ts(start)},{_ts(end)},Cap,,0,0,0,,"
            f"{{\\pos({w // 2},{int(h * 0.80)})\\fscx80\\fscy80\\t(0,90,\\fscx100\\fscy100)}}"
            + " ".join(styled)
        )
    path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")


MOTIONS = [
    ("min(1+0.0007*on,1.10)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),   # gentle zoom in
    ("max(1.10-0.0007*on,1.0)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),  # gentle zoom out
    ("1.08", "(iw-iw/zoom)*on/{d}", "ih/2-(ih/zoom/2)"),                 # slow slide
]


def _clip(img: Path, out: Path, seconds: float, motion: int, w: int, h: int, fps: int) -> None:
    """One scene: the drawing is 'revealed' left-to-right like a whiteboard, then drifts gently."""
    frames = max(int(seconds * fps), fps)
    z, x, y = MOTIONS[motion % len(MOTIONS)]
    x, y = x.format(d=frames), y.format(d=frames)
    graph = (
        f"[0:v]scale={w * 2}:{h * 2}:flags=lanczos,"
        f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={w}x{h}:fps={fps},setsar=1[base];"
        f"color=c=white:s={w}x{h}:r={fps}:d={seconds:.3f}[cover];"
        f"[base][cover]overlay=x='w*min(t/0.45\\,1)':y=0:shortest=1,format=yuv420p[v]"
    )
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(img), "-filter_complex", graph,
         "-map", "[v]", "-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "18", "-r", str(fps), str(out)],
        check=True,
    )


def _pick_music(cfg: dict, seed: str) -> Path | None:
    folder = ROOT / cfg.get("music", {}).get("folder", "assets/music")
    tracks = sorted(folder.glob("*.mp3"))
    if not tracks:
        return None
    return random.Random(seed).choice(tracks)


def build_video(cfg: dict, images: list[Path], voice: Path, words: list, hook: str,
                total: float, folder: Path) -> Path:
    v = cfg["video"]
    w, h, fps = v["width"], v["height"], v["fps"]
    tail = 1.2
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

    music = _pick_music(cfg, folder.name)
    inputs = ["-i", str(joined), "-i", str(voice)]
    video_graph = (
        f"[0:v]ass='{ass.name}':fontsdir='{fonts}'[cap];"
        f"color=c={GREEN_HEX}:s={w}x14:r={fps}[bar];"
        f"[cap][bar]overlay=x='-w+w*t/{length:.2f}':y=0:shortest=1[v]"
    )
    if music:
        log(f"Music: {music.stem}")
        inputs += ["-stream_loop", "-1", "-i", str(music)]
        vol = cfg.get("music", {}).get("volume_db", -17)
        audio_graph = (
            f";[1:a]apad=pad_dur={tail},asplit=2[vo][sc];"
            f"[2:a]volume={vol}dB,atrim=0:{length:.2f},afade=t=in:d=1.5,"
            f"afade=t=out:st={max(length - 2.5, 0):.2f}:d=2.5[mu];"
            f"[mu][sc]sidechaincompress=threshold=0.05:ratio=4:attack=20:release=400[duck];"
            f"[vo][duck]amix=inputs=2:duration=first:normalize=0,"
            f"loudnorm=I=-14:TP=-1.5:LRA=11[a]"
        )
    else:
        audio_graph = f";[1:a]apad=pad_dur={tail},loudnorm=I=-14:TP=-1.5:LRA=11[a]"

    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", *inputs,
         "-filter_complex", video_graph + audio_graph,
         "-map", "[v]", "-map", "[a]",
         "-t", f"{length:.2f}",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-profile:v", "high",
         "-pix_fmt", "yuv420p", "-r", str(fps),
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
         "-movflags", "+faststart", str(final)],
        check=True, cwd=folder,
    )
    size_mb = final.stat().st_size / 1e6
    log(f"Video ready: {final.name} ({size_mb:.1f} MB)")
    return final
