"""Weekly health report to Telegram + WhatsApp: posts in the last 7 days, failures, and upcoming expiries."""
import datetime as dt
import html
import json
from pathlib import Path

import yaml

from .notify import send_text, send_whatsapp

BUFFER_KEY_EXPIRES = dt.date(2027, 11, 14)


def main() -> None:
    cfg = yaml.safe_load(Path("config.yaml").read_text())
    hist = json.loads(Path("data/history.json").read_text())
    now = dt.datetime.now(dt.timezone.utc)
    week = [h for h in hist if now - dt.datetime.fromisoformat(h["date"]) < dt.timedelta(days=7)]
    ok = {p: 0 for p in cfg["posting"]["platforms"]}
    for h in week:
        for p, r in (h.get("results") or {}).items():
            if r.get("ok") and p in ok:
                ok[p] += 1
    first = dt.datetime.fromisoformat(hist[0]["date"]) if hist else now
    expected = max(1, min(14, round((now - first).total_seconds() / 43200)))  # 2 a day since the first post
    lines = ["🩺 <b>Monezic weekly check</b>", f"Videos made: {len(week)} / {expected}"]
    need = {p: (len(week) // 2 if p == "youtube" else len(week)) for p in ok}  # YouTube = 1/day
    lines += [f"{'✅' if n >= need[p] and n else '⚠️'} {p.title()}: {n} posted" for p, n in ok.items()]
    if len(week) < expected - 2:
        lines.append("⚠️ Fewer videos than planned - check the ❌ messages this week.")
    days = (BUFFER_KEY_EXPIRES - now.date()).days
    if days < 45:
        lines.append(f"🔑 Buffer API key expires in {days} days: buffer.com → Settings → API → new key, "
                     "then update BUFFER_API_KEY in GitHub Secrets.")
    if all(n >= need[p] for p, n in ok.items()) and len(week) >= expected - 2:
        lines.append("All good - nothing to do. 👍")
    msg = "\n".join(lines)
    send_text(cfg, msg)
    send_whatsapp(html.unescape(msg.replace("<b>", "").replace("</b>", "")))


if __name__ == "__main__":
    main()
