"""Wealth Factory - makes one short video from start to finish.

Run by GitHub Actions twice a day (see .github/workflows/factory.yml).
"""
import html
import os
import shutil
import sys
import traceback
from datetime import datetime, timezone

from .common import DATA, WORK, load_config, log, read_json, write_json
from .notify import report, send_text, send_video, send_whatsapp, whatsapp_report
from .publish import host_video, post_everywhere, posting_enabled
from .script import write_story
from . import stickman
from .video import FONT_DIR, finish_video
from .voice import fit_length, make_voice

HISTORY = DATA / "history.json"


def beat_times(beats: list[dict], words: list, total: float) -> list[tuple[float, float]]:
    """When each scene starts and ends, following the spoken words."""
    counts = [len(b["text"].split()) for b in beats]
    n_script = sum(counts)
    starts, k = [], 0
    for c in counts:
        idx = min(round(k * len(words) / n_script), len(words) - 1)
        starts.append(0.0 if not starts else max(words[idx][0] - 0.15, starts[-1] + 0.5))
        k += c
    ends = starts[1:] + [total]
    return list(zip(starts, ends))


def run() -> int:
    cfg = load_config()
    history = read_json(HISTORY, [])
    now = datetime.now(timezone.utc)
    run_id = now.strftime("%Y%m%d-%H%M")
    run_url = ""
    if os.environ.get("GITHUB_RUN_ID"):
        run_url = (f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/"
                   f"{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}")

    folder = WORK / run_id
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)

    step = "starting"
    try:
        fmt = cfg["formats"][len(history) % len(cfg["formats"])]
        style = ""
        log(f"Format: {fmt['name']}")

        step = "writing the story"
        story = write_story(cfg, fmt, style, [h["topic"] for h in history])
        write_json(folder / "story.json", story)

        step = "recording the voice"
        voice, words, voice_name = make_voice(cfg, story["script"], folder)
        voice, words, total = fit_length(voice, words)

        step = "drawing the stickman scenes"
        stickman.set_font("Anton" if (FONT_DIR / "Anton-Regular.ttf").exists() else "DejaVu Sans")
        times = beat_times(story["beats"], words, total)
        end_card = 3.0
        scenes = stickman.render(story["beats"], times, end_card, folder / "scenes.mp4",
                                 fps=cfg["video"]["fps"], handle=cfg["channel"].get("handle", "@monezic"))

        step = "building the video"
        video = finish_video(cfg, scenes, voice, words, story["hook_text"], total, total + end_card, folder)

        results = None
        video_url = ""
        if posting_enabled():
            step = "putting the video online"
            video_url = host_video(video, f"{run_id}.mp4")
            step = "posting to social media"
            results = post_everywhere(cfg, story, video_url)
        else:
            log("Test run: not posting to social media.")

        step = "sending the Telegram report"
        send_video(cfg, video, f"<b>{html.escape(story['title'])}</b>")
        delivered = send_text(cfg, report(cfg, story, results, run_url))
        send_whatsapp(whatsapp_report(story, results))

        if results is not None:
            history.append({
                "date": now.isoformat(timespec="minutes"),
                "topic": story["topic"],
                "title": story["title"],
                "format": fmt["name"],
                "voice": voice_name,
                "seconds": round(total, 1),
                "video": video_url,
                "results": results,
            })
            write_json(HISTORY, history)

        if results and not any(r.get("ok") for r in results.values()):
            log("Video was made but no platform accepted it.")
            return 1
        if not delivered:
            log("The Telegram report could not be delivered - check TELEGRAM_BOT_TOKEN and that the bot is an admin of the channel.")
            return 1
        log("All done.")
        return 0
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        msg = (f"❌ <b>Wealth Factory problem</b>\nWhile {html.escape(step)}:\n"
               f"<code>{html.escape(str(e))[:700]}</code>")
        if run_url:
            msg += f'\n\n<a href="{html.escape(run_url)}">Details</a>'
        try:
            send_text(cfg, msg)
            send_whatsapp(f"❌ Monezic problem while {step}: {str(e)[:300]}")
        except Exception:  # noqa: BLE001
            pass
        return 1


if __name__ == "__main__":
    sys.exit(run())
