"""Schedule the channel trailer on YouTube ONLY, through Buffer, at a given UTC time.

Run by .github/workflows/trailer.yml (manual). Refuses if YouTube already has 2+ uploads in the
24 h before the slot, or a 02:00-Kigali (00:00 UTC) upload less than 12 h before it.
"""
import os
import sys
from datetime import datetime, timedelta

import requests

from .common import DATA, load_config, log, read_json, write_json
from .publish import CREATE, _channels, _gql, _metadata

VIDEO = "https://raw.githubusercontent.com/{repo}/media/trailer/monezic_trailer.mp4"
TITLE = "Monezic: Real Money Stories (Channel Trailer)"
TEXT = ("One decision. That's what it takes.\n\nMonezic tells the real stories of people and companies who won big "
        "or lost it all, and the one decision that made the difference. No hype, no get-rich-quick, just real "
        "money stories and the lesson inside them.\n\nNew stories every day. Subscribe so you don't miss the next one.\n\n"
        "#money #business #monezic")


def youtube_uploads(before: datetime, hours: float = 24) -> list[datetime]:
    """YouTube uploads (from history + extra uploads like this trailer) in the `hours` before `before`."""
    out = []
    for h in read_json(DATA / "history.json", []):
        if (h.get("results") or {}).get("youtube", {}).get("ok"):
            out.append(datetime.fromisoformat(h["date"]))
    for x in read_json(DATA / "youtube_extra.json", []):
        out.append(datetime.fromisoformat(x["date"]))
    return sorted(t for t in out if before - timedelta(hours=hours) < t < before)


def main() -> int:
    due = datetime.fromisoformat(os.environ["DUE_AT"].replace("Z", "+00:00"))
    # Next 02:00 Kigali slot before `due` is planned as a YouTube upload too (it hasn't happened yet).
    planned = due.replace(hour=0, minute=0, second=0, microsecond=0)
    if planned >= due:
        planned -= timedelta(days=1)
    ups = youtube_uploads(due)
    if planned > datetime.now(planned.tzinfo) and all(abs((u - planned).total_seconds()) > 3 * 3600 for u in ups):
        ups.append(planned)
    log(f"YouTube uploads in the 24 h before {due:%Y-%m-%d %H:%M} UTC: {[f'{u:%d %H:%M}' for u in ups]}")
    if len(ups) > 1:
        log("Refusing: more than 1 YouTube upload in the 24 h before the trailer slot.")
        return 1
    if any(timedelta(0) <= due - u < timedelta(hours=12) for u in ups):
        log("Refusing: a YouTube upload is less than 12 h before the trailer slot.")
        return 1
    url = VIDEO.format(repo=os.environ["GITHUB_REPOSITORY"])
    if requests.head(url, timeout=30).status_code != 200:
        log(f"Trailer file not reachable: {url}")
        return 1
    cfg = load_config()
    ch = _channels().get("youtube")
    if not ch or ch.get("isDisconnected"):
        log("YouTube is not connected in Buffer.")
        return 1
    meta = _metadata("youtube", {"title": TITLE}, cfg)
    res = _gql(CREATE, {"input": {
        "channelId": ch["id"], "text": TEXT, "mode": "customScheduled", "schedulingType": "automatic",
        "dueAt": due.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "assets": [{"video": {"url": url, "metadata": {"thumbnailOffset": 500}}}],
        "metadata": meta}})["createPost"]
    if res.get("__typename") != "PostActionSuccess":
        log(f"Buffer refused: {res.get('message', res)}")
        return 1
    log(f"Trailer scheduled on YouTube for {due:%Y-%m-%d %H:%M} UTC (Buffer post {res['post']['id']}, "
        f"status {res['post']['status']})")
    extra = read_json(DATA / "youtube_extra.json", [])
    extra.append({"date": due.isoformat(timespec="minutes"), "what": "channel trailer", "buffer_id": res["post"]["id"]})
    write_json(DATA / "youtube_extra.json", extra)
    return 0


if __name__ == "__main__":
    sys.exit(main())
