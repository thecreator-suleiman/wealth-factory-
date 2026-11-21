"""Make ONE stickman video inside a Claude chat - no schedules, no posting, no API keys.

Usage (Claude runs this for you):
    python -m factory.studio --story story.json --voice my_voice.mp3 --out video.mp4

story.json = {"hook_text": "...", "beats": [{"text": "...", "characters": [{"pose": "...",
             "mood": "...", "label": "..."}], "prop": "...", "big_text": "...", "headline": ""}]}
The voice file is a recording of the beats' text, read in order (your own voice works best).
"""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

from . import stickman
from .common import WORK, load_config, log
from .main import beat_times
from .script import _clean
from .video import FONT_DIR, _font, finish_video
from .voice import _estimate_timings, audio_seconds


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--story", required=True)
    ap.add_argument("--voice", required=True)
    ap.add_argument("--out", default="video.mp4")
    a = ap.parse_args()

    cfg = load_config()
    story = _clean({"title": "", "hashtags": [], "hook_text": ""} | json.loads(Path(a.story).read_text(encoding="utf-8")))
    folder = WORK / "studio"
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    voice = folder / "voice.mp3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", a.voice, "-ac", "1", "-ar", "44100", str(voice)],
                   check=True)
    total = audio_seconds(voice)
    words = _estimate_timings(story["script"], total)
    stickman.set_font(_font()[0])
    times = beat_times(story["beats"], words, total)
    scenes = stickman.render(story["beats"], times, 3.0, folder / "scenes.mp4",
                             fps=cfg["video"]["fps"], handle=cfg["channel"].get("handle", "@monezic"))
    final = finish_video(cfg, scenes, voice, words, story.get("hook_text", ""), total, total + 3.0, folder)
    shutil.copy(final, a.out)
    log(f"Done: {a.out}")


if __name__ == "__main__":
    main()
