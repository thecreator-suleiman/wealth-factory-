"""Wealth Factory - makes one short video from start to finish.

Run by GitHub Actions twice a day (see .github/workflows/factory.yml).
"""
import html
import os
import shutil
import sys
import time
import traceback
from datetime import datetime, timezone

from .common import DATA, WORK, load_config, log, read_json, write_json
from .notify import advice, report, send_text, send_video, send_whatsapp, share_messages, whatsapp_report
from .publish import host_video, post_everywhere, posting_enabled
from .script import write_freebie, write_story
from . import stickman
from .video import FONT_DIR, _font, finish_video
from .voice import fit_pace, make_voice

HISTORY = DATA / "history.json"


def publish_freebie(cfg: dict, story: dict, kind: str, run_id: str) -> str:
    """Saves the free plan/guide as a web page in docs/ (GitHub Pages) and updates the index."""
    text = write_freebie(story, kind)
    if not text:
        return ""
    docs = DATA.parent / "docs"
    (docs / "plans").mkdir(parents=True, exist_ok=True)
    title = story["topic"]
    label = "Free business plan" if kind == "business" else "Free guide"
    (docs / "plans" / f"{run_id}.md").write_text(
        f"---\ntitle: \"{label}: {title}\"\n---\n\n# {label}: {title}\n\n{text}\n", encoding="utf-8")
    index = docs / "index.md"
    old = index.read_text(encoding="utf-8").split("<!-- list -->", 1)[-1] if index.exists() else ""
    index.write_text(
        "---\ntitle: Free Plans\n---\n\n# Free business plans & money guides\n\n"
        "Practical, free plans from our videos. New ones every week.\n\n<!-- list -->\n"
        f"- [{label}: {title}](plans/{run_id}.html)\n" + old.lstrip("\n"), encoding="utf-8")
    url = f"{cfg['channel'].get('plans_url', '').rstrip('/')}/plans/{run_id}.html"
    log(f"Free {kind} page: {url}")
    return url


def wait_for_slot(cfg: dict) -> None:
    """Hold a finished video until the next posting time (if it is less than 100 minutes away)."""
    import time as _t
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    best = None
    for hhmm in cfg["posting"].get("times_utc", []):
        h, m = map(int, hhmm.split(":"))
        slot = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if slot < now - timedelta(minutes=5):
            slot += timedelta(days=1)
        if best is None or slot < best:
            best = slot
    if best is None:
        return
    wait = (best - now).total_seconds()
    if 0 < wait <= 100 * 60:
        log(f"Video ready early - waiting {wait / 60:.0f} min to post at {best:%H:%M} UTC")
        _t.sleep(wait)


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
    if os.environ.get("GITHUB_EVENT_NAME") == "schedule" and history:
        last = datetime.fromisoformat(history[-1]["date"])
        if (now - last).total_seconds() < 5 * 3600:
            log("This slot was already posted - backup run skipping.")
            return 0
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
        mix = cfg.get("mix") or ["story"]
        kind = mix[len(history) % len(mix)]
        options = [f for f in cfg["formats"] if f.get("kind", "story") == kind] or cfg["formats"]
        done_same_kind = sum(1 for h in history if h.get("kind", "story") == kind)
        fmt = options[done_same_kind % len(options)]
        n = len(history)
        # Part 1 / Part 2 cliffhanger stories: about one story in seven is split; Part 2 is the very next video.
        prev = history[-1] if history else {}
        part = 0
        if prev.get("part") == 1 and prev.get("script"):
            part = 2
            kind = prev.get("kind", "story")
            fmt = next((f for f in cfg["formats"] if f["name"] == prev.get("format")), fmt)
            cfg["_part1"] = prev["script"]
        elif kind == "story" and n % 7 == 3:
            part = 1
        cfg["_part"] = part
        style = ""
        log(f"Format: {fmt['name']} ({kind})" + (f" - Part {part}" if part else ""))

        step = "writing the story"
        # Opening test ended 21 Nov: hook first, always. Clear pace (~2.95 words/s), 61-70 s, ends on the payoff.
        opening = "hook"  # owner 21 Nov: the hook (paradox stated as fact) is always the very first line
        length = "fast"
        cfg["_opening"] = opening
        from .script import STRUCTURES
        from .hooks import formulas_for
        cfg["_structure"] = STRUCTURES[(n // 4 + n) % len(STRUCTURES)]
        cfg["_hooks"] = formulas_for(n)
        log(f"Test variant: opening={opening}, length={length}")
        for attempt in range(5):  # Google "high demand" spikes pass in minutes - be patient
            try:
                story = write_story(cfg, fmt, style, [h["topic"] for h in history])
                break
            except RuntimeError as e:
                busy = (any(k in str(e) for k in ("503", "429", "UNAVAILABLE", "high demand"))
                        and "exceeded your current quota" not in str(e))  # daily quota won't clear by waiting
                if not busy or attempt == 4:
                    raise
                log(f"Gemini busy - waiting {3 + attempt * 2} min, then trying again")
                time.sleep((3 + attempt * 2) * 60)
        write_json(folder / "story.json", story)

        step = "recording the voice"
        voice, words, voice_name = make_voice(cfg, story["script"], folder)
        voice, words, total = fit_pace(voice, words, cfg["voice"].get("words_per_second", 3.7),
                                       cfg["video"].get("min_seconds", 61), cfg["video"].get("max_seconds", 70))

        step = "drawing the stickman scenes"
        stickman.set_font(_font()[0])
        times = beat_times(story["beats"], words, total)
        tail = 0.35  # no end card: the video ends on the payoff and loops straight back into the hook
        times[-1] = (times[-1][0], total + tail)
        scenes = stickman.render(story["beats"], times, 0.0, folder / "scenes.mp4",
                                 fps=cfg["video"]["fps"], handle=cfg["channel"].get("handle", "@monezic"),
                                 words=words)

        step = "building the video"
        video = finish_video(cfg, scenes, voice, words, story["hook_text"], total, total + tail, folder,
                             beats=story["beats"], times=times)

        plan_url = ""
        if kind in ("business", "tool"):
            step = "writing the free plan"
            plan_url = publish_freebie(cfg, story, kind, run_id)
            story["plan_url"] = plan_url
            if plan_url:
                story["caption"] += f"\n\nFree {'business plan' if kind == 'business' else 'guide'}: {plan_url}"
        src = [x.strip() for x in story.get("sources", []) if x and x.strip() and "http" not in x][:4]
        if src:
            story["caption"] += "\n\nSources: " + ", ".join(src)

        results = None
        video_url = ""
        if posting_enabled():
            if os.environ.get("GITHUB_EVENT_NAME") == "schedule":
                wait_for_slot(cfg)
            step = "putting the video online"
            for attempt in range(3):  # GitHub hiccups pass in a minute
                try:
                    video_url = host_video(video, f"{run_id}.mp4")
                    break
                except Exception as e:  # noqa: BLE001
                    if attempt == 2:
                        raise
                    log(f"Hosting failed ({e}) - retrying in 60 s")
                    time.sleep(60)
            step = "posting to social media"
            # YouTube refuses a 3rd upload within ~24 h, so it gets only the evening-US video (02:00 Kigali).
            hour = datetime.now(timezone.utc).hour
            if 6 <= hour < 18 and "youtube" in cfg["posting"]["platforms"]:
                cfg["posting"]["platforms"] = [p for p in cfg["posting"]["platforms"] if p != "youtube"]
                log("Day slot: posting to TikTok + Instagram only (YouTube gets the 02:00 video).")
            if "youtube" in cfg["posting"]["platforms"]:
                from .trailer_post import youtube_uploads
                recent = youtube_uploads(datetime.now(timezone.utc), hours=24.5)  # history = run start times
                if len(recent) >= 2:
                    cfg["posting"]["platforms"] = [p for p in cfg["posting"]["platforms"] if p != "youtube"]
                    log(f"YouTube already has {len(recent)} uploads in the last 24 h (e.g. the trailer) - skipping it.")
            results = post_everywhere(cfg, story, video_url)
            # Self-repair: retry platforms that failed for a temporary reason (not limits or logins).
            permanent = ("limit", "authoriz", "permission", "reconnect", "login", "token")
            retry = [p for p, r in results.items()
                     if not r.get("ok") and not any(k in (r.get("error") or "").lower() for k in permanent)]
            if retry:
                log(f"Posting failed on {', '.join(retry)} - retrying in 5 min")
                time.sleep(300)
                again = post_everywhere({**cfg, "posting": {**cfg["posting"], "platforms": retry}}, story, video_url)
                results.update({p: r for p, r in again.items() if r.get("ok") or p in retry})
        else:
            log("Test run: not posting to social media.")

        step = "sending the Telegram report"
        send_video(cfg, video, f"<b>{html.escape(story['title'])}</b>")
        delivered = send_text(cfg, report(cfg, story, results, run_url))
        send_whatsapp(whatsapp_report(story, results))
        for msg in share_messages(story, results)[:1]:  # forward-ready YouTube message only (WhatsApp limits)
            send_whatsapp(msg)

        if results is not None:
            history.append({
                "date": now.isoformat(timespec="minutes"),
                "topic": story["topic"],
                "title": story["title"],
                "format": fmt["name"],
                "kind": kind,
                "plan": plan_url,
                "voice": voice_name,
                "variant": f"{opening}/{length}",
                "part": part,
                "script": story["script"] if part == 1 else "",
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
        msg = (f"❌ <b>Monezic problem</b>\nWhile {html.escape(step)}:\n"
               f"<code>{html.escape(str(e))[:700]}</code>\n\n{html.escape(advice(step + ' ' + str(e)))}")
        if run_url:
            msg += f'\n\n<a href="{html.escape(run_url)}">Details</a>'
        try:
            send_text(cfg, msg)
            send_whatsapp(f"❌ Monezic problem while {step}: {str(e)[:300]}\n{advice(step + ' ' + str(e))}")
        except Exception:  # noqa: BLE001
            pass
        return 1


if __name__ == "__main__":
    sys.exit(run())
