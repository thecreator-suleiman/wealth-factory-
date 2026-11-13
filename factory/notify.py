"""Step 6: report to your Telegram channel - the only thing you need to look at."""
import html
from pathlib import Path

import requests

from .common import env, log

NAMES = {"tiktok": "TikTok", "instagram": "Instagram", "youtube": "YouTube"}


def _api(method: str) -> str:
    return f"https://api.telegram.org/bot{env('TELEGRAM_BOT_TOKEN')}/{method}"


def send_text(cfg: dict, text: str) -> bool:
    try:
        r = requests.post(
            _api("sendMessage"),
            data={"chat_id": cfg["telegram"]["chat_id"], "text": text,
                  "parse_mode": "HTML", "disable_web_page_preview": "true"},
            timeout=60,
        )
        if r.status_code != 200:
            log(f"Telegram message failed: {r.text[:200]}")
            return False
        return True
    except Exception as e:  # noqa: BLE001
        log(f"Telegram message failed: {e}")
        return False


def send_video(cfg: dict, video: Path, caption: str) -> None:
    if video.stat().st_size > 49_000_000:
        log("Video too big for Telegram preview - skipping the upload.")
        return
    try:
        with open(video, "rb") as f:
            r = requests.post(
                _api("sendVideo"),
                data={"chat_id": cfg["telegram"]["chat_id"], "caption": caption[:1000],
                      "parse_mode": "HTML", "supports_streaming": "true"},
                files={"video": (video.name, f, "video/mp4")},
                timeout=300,
            )
        if r.status_code != 200:
            log(f"Telegram video failed: {r.text[:200]}")
    except Exception as e:  # noqa: BLE001
        log(f"Telegram video failed: {e}")


def report(cfg: dict, story: dict, results: dict | None, run_url: str) -> str:
    e = html.escape
    lines = [f"<b>{e(story['title'])}</b>", f"<i>{e(story['topic'])}</i>", ""]
    if results is None:
        lines.append("🧪 Test run - not posted to social media.")
    else:
        for platform in cfg["posting"]["platforms"]:
            r = results.get(platform, {"ok": False, "error": "not attempted"})
            name = NAMES.get(platform, platform)
            if r["ok"]:
                link = f' - <a href="{e(r["link"])}">open</a>' if r.get("link") else ""
                lines.append(f"✅ {name}{link}")
            elif r["ok"] is None:
                lines.append(f"⏳ {name}: {e(r['error'])}")
            else:
                lines.append(f"❌ {name}: {e(r['error'])}")
    if run_url:
        lines += ["", f'<a href="{e(run_url)}">Details</a>']
    return "\n".join(lines)
