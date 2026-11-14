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


# ---------------------------------------------------------------- WhatsApp (CallMeBot, free)
def send_whatsapp(text: str) -> None:
    """Sends a WhatsApp message to your own phone (CallMeBot or Whatabot, both free).
    Skipped quietly if neither is set up."""
    phone = env("WHATSAPP_PHONE", required=False).replace(" ", "")
    if not phone:
        return
    services = []
    if env("CALLMEBOT_API_KEY", required=False):
        services.append(("CallMeBot", ["https://api.callmebot.com/whatsapp.php"],
                         {"phone": phone, "apikey": env("CALLMEBOT_API_KEY", required=False)}))
    if env("WHATABOT_API_KEY", required=False):
        services.append(("Whatabot", ["https://api.whatabot.net/whatsapp/sendMessage",
                                      "http://api.whatabot.net/whatsapp/sendMessage"],
                         {"phone": phone, "apikey": env("WHATABOT_API_KEY", required=False)}))
    for name, urls, params in services:
        for url in urls:
            try:
                r = requests.get(url, params={**params, "text": text[:1500]}, timeout=60)
                if r.status_code == 200 and "ERROR" not in r.text.upper()[:300]:
                    log(f"WhatsApp message sent ({name}).")
                    return
                log(f"WhatsApp via {name} failed: {r.status_code} {r.text[:200]}")
            except Exception as e:  # noqa: BLE001
                log(f"WhatsApp via {name} failed: {e}")


def whatsapp_report(story: dict, results: dict | None) -> str:
    icons = {"youtube": "▶️ YouTube", "tiktok": "🎵 TikTok", "instagram": "📸 Instagram"}
    lines = [f"*Monezic* - new video", f"_{story['title']}_", ""]
    if results is None:
        lines.append("🧪 Test video (not posted). Check Telegram to watch it.")
    else:
        for platform in ("youtube", "tiktok", "instagram"):
            if platform not in results:
                continue
            r = results[platform]
            name = icons[platform]
            if r["ok"]:
                lines.append(f"✅ {name}: {r.get('link') or 'posted'}")
            elif r["ok"] is None:
                lines.append(f"⏳ {name}: still processing")
            else:
                lines.append(f"❌ {name}: {r['error']}")
    return "\n".join(lines)
