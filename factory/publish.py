"""Step 5: put the video online and post it to TikTok, Instagram and YouTube through Buffer."""
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import requests

from .common import env, log

BUFFER = "https://api.buffer.com"
KEEP_VIDEOS = 6  # older videos are removed from the public media branch


# ---------------------------------------------------------------- media hosting
def host_video(video: Path, name: str) -> str:
    """Publish the MP4 on a 'media' branch of this repo and return a direct public link.

    The branch is rewritten each time (only the last few videos are kept), so the
    repository never grows big.
    """
    repo = env("GITHUB_REPOSITORY")
    token = env("GITHUB_TOKEN")
    remote = f"https://x-access-token:{token}@github.com/{repo}.git"
    tmp = Path(tempfile.mkdtemp())

    def git(*args, check=True):
        return subprocess.run(["git", *args], cwd=tmp, check=check, capture_output=True, text=True)

    got = subprocess.run(
        ["git", "clone", "--quiet", "--depth", "1", "--branch", "media", remote, str(tmp)],
        capture_output=True, text=True,
    )
    if got.returncode != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True)
        git("init", "-q")
        git("remote", "add", "origin", remote)
    folder = tmp / "videos"
    folder.mkdir(exist_ok=True)
    shutil.copy(video, folder / name)
    old = sorted(folder.glob("*.mp4"), key=lambda p: p.name)
    for p in old[:-KEEP_VIDEOS]:
        p.unlink()
    (tmp / "README.md").write_text("Public video files used for posting. Managed automatically.\n")
    git("config", "user.name", "wealth-factory-bot")
    git("config", "user.email", "bot@users.noreply.github.com")
    git("checkout", "-q", "--orphan", "fresh")
    git("add", "-A")
    git("commit", "-q", "-m", f"media: {name}")
    git("push", "-q", "-f", "origin", "fresh:media")
    shutil.rmtree(tmp, ignore_errors=True)

    url = f"https://raw.githubusercontent.com/{repo}/media/videos/{name}"
    for _ in range(20):  # wait until the link really works
        try:
            r = requests.head(url, timeout=30)
            if r.status_code == 200:
                log(f"Video online: {url}")
                return url
        except requests.RequestException:
            pass
        time.sleep(6)
    raise RuntimeError(f"Video link did not become reachable: {url}")


# ---------------------------------------------------------------- Buffer
def _gql(query: str, variables: dict | None = None) -> dict:
    key = env("BUFFER_API_KEY")
    r = requests.post(
        BUFFER,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"query": query, "variables": variables or {}},
        timeout=60,
    )
    if r.status_code == 429:
        raise RuntimeError("Buffer rate limit reached")
    r.raise_for_status()
    data = r.json()
    if data.get("errors"):
        raise RuntimeError("Buffer: " + "; ".join(e.get("message", "?") for e in data["errors"]))
    return data["data"]


def _channels() -> dict:
    orgs = _gql("query { account { organizations { id name } } }")["account"]["organizations"]
    found = {}
    for org in orgs:
        chans = _gql(
            """query($o: OrganizationId!) { channels(input: {organizationId: $o}) {
                 id name service isDisconnected isLocked } }""",
            {"o": org["id"]},
        )["channels"]
        for c in chans:
            if c["service"] not in found and not c["isLocked"]:
                found[c["service"]] = c
    return found


CREATE = """mutation($input: CreatePostInput!) {
  createPost(input: $input) {
    __typename
    ... on PostActionSuccess { post { id status } }
    ... on MutationError { message }
  }
}"""

STATUS = """query($id: PostId!) {
  post(input: {id: $id}) { id status externalLink error { message } }
}"""


def _ai(cfg: dict, service: str) -> bool:
    return bool(cfg["posting"].get("ai_label", {}).get(service, True))


def _metadata(service: str, story: dict, cfg: dict) -> dict:
    if service == "youtube":
        return {"youtube": {
            "title": story["title"][:100],
            "categoryId": str(cfg["posting"]["youtube_category"]),
            "privacy": "public",
            "madeForKids": False,
            "notifySubscribers": True,
            "isAiGenerated": _ai(cfg, "youtube"),
        }}
    if service == "instagram":
        return {"instagram": {"type": "reel", "shouldShareToFeed": True, "isAiGenerated": _ai(cfg, "instagram")}}
    if service == "tiktok":
        return {"tiktok": {"isAiGenerated": _ai(cfg, "tiktok")}}
    return {}


def post_everywhere(cfg: dict, story: dict, video_url: str) -> dict:
    """Returns {platform: {"ok": bool, "link": str, "error": str}}."""
    results = {}
    tags = " ".join(f"#{t}" for t in story["hashtags"][: cfg["posting"]["hashtags_max"]])
    text = f"{story['caption']}\n\n{tags}".strip()
    try:
        channels = _channels()
    except Exception as e:  # noqa: BLE001
        return {p: {"ok": False, "link": "", "error": f"Buffer login failed: {e}"}
                for p in cfg["posting"]["platforms"]}

    pending = {}
    for service in cfg["posting"]["platforms"]:
        ch = channels.get(service)
        if not ch:
            results[service] = {"ok": False, "link": "", "error": "not connected in Buffer"}
            continue
        if ch.get("isDisconnected"):
            results[service] = {"ok": False, "link": "", "error": "disconnected in Buffer - reconnect it"}
            continue
        post_input = {
            "channelId": ch["id"],
            "text": text,
            "mode": "shareNow",
            "schedulingType": "automatic",
            "assets": [{"video": {"url": video_url, "metadata": {"thumbnailOffset": 500}}}],
            "metadata": _metadata(service, story, cfg),
        }
        try:
            res = _gql(CREATE, {"input": post_input})["createPost"]
            if res.get("__typename") == "PostActionSuccess":
                pending[service] = res["post"]["id"]
                log(f"Sent to Buffer: {service}")
            else:
                results[service] = {"ok": False, "link": "", "error": res.get("message", res.get("__typename"))}
        except Exception as e:  # noqa: BLE001
            results[service] = {"ok": False, "link": "", "error": str(e)}

    # Wait for the platforms to confirm (videos take a few minutes to process).
    deadline = time.time() + 15 * 60
    while pending and time.time() < deadline:
        time.sleep(30)
        for service, pid in list(pending.items()):
            try:
                p = _gql(STATUS, {"id": pid})["post"]
            except Exception as e:  # noqa: BLE001
                log(f"Status check failed for {service}: {e}")
                continue
            if p["status"] == "sent":
                results[service] = {"ok": True, "link": p.get("externalLink") or "", "error": ""}
                pending.pop(service)
                log(f"Published on {service}: {p.get('externalLink')}")
            elif p["status"] == "error":
                msg = (p.get("error") or {}).get("message", "unknown error")
                results[service] = {"ok": False, "link": "", "error": msg}
                pending.pop(service)
                log(f"{service} failed: {msg}")
    for service in pending:
        results[service] = {"ok": None, "link": "", "error": "still processing in Buffer - check the app"}
    return results


def posting_enabled() -> bool:
    return os.environ.get("POST_TO_SOCIALS", "true").lower() in ("1", "true", "yes")
