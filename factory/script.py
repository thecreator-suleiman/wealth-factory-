"""Step 1: write the story with Google Gemini (free API key from aistudio.google.com)."""
import json
import re

import requests

from .common import env, log

# Tried in order. If one is busy, retired or out of free quota, the next is used.
MODELS = [
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-2.5-flash-lite",
    "gemini-flash-lite-latest",
]

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

from .stickman import MOODS, POSES, PROPS

CHAR = {
    "type": "OBJECT",
    "properties": {
        "pose": {"type": "STRING", "enum": POSES},
        "mood": {"type": "STRING", "enum": MOODS},
        "label": {"type": "STRING"},
    },
    "required": ["pose", "mood", "label"],
}
BEAT = {
    "type": "OBJECT",
    "properties": {
        "text": {"type": "STRING"},
        "characters": {"type": "ARRAY", "items": CHAR},
        "prop": {"type": "STRING", "enum": PROPS},
        "big_text": {"type": "STRING"},
    },
    "required": ["text", "characters", "prop", "big_text"],
}
SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "topic": {"type": "STRING"},
        "title": {"type": "STRING"},
        "hook_text": {"type": "STRING"},
        "beats": {"type": "ARRAY", "items": BEAT},
        "caption": {"type": "STRING"},
        "hashtags": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["topic", "title", "hook_text", "beats", "caption", "hashtags"],
}

LABELS = re.compile(
    r"\b(scene|beat|narrator|voiceover|voice over|hook|intro|outro|cta)\s*\d*\s*[:\-–]\s*"
    r"|\[[^\]]*\]|\([^)]*(music|sfx|pause|beat)[^)]*\)|\*+|#+",
    re.IGNORECASE,
)


def _prompt(cfg: dict, fmt: dict, style: str, used_topics: list[str], feedback: str) -> str:
    ch, vid = cfg["channel"], cfg["video"]
    words_lo = int(vid["target_seconds"] * 2.25)
    words_hi = int(vid["target_seconds"] * 2.65)
    avoid = "\n".join(f"- {t}" for t in used_topics[-80:]) or "- (none yet)"
    rules = "\n".join(f"- {r}" for r in ch["rules"])
    return f"""You are the head writer of a fast-growing short-video channel called "{ch['name']}".
Videos are animated STICKMAN stories: black stick figures on white with green highlights.

CHANNEL: {ch['niche']}
AUDIENCE: {ch['audience']}
LANGUAGE: {ch['language']}

THIS VIDEO'S FORMAT: "{fmt['name']}" - {fmt['brief']}

PICK ONE specific, real, famous, well-documented story that fits the format. Only use facts you are certain are true and widely reported. It must NOT repeat any of these past topics:
{avoid}

WRITE THE STORY AS "beats" (10-14 beats). Each beat = 1-2 short spoken sentences + the stickman scene shown while they are spoken.
Total spoken words across all beats: {words_lo}-{words_hi} (about {vid['target_seconds']} seconds).
- Beat 1 is the hook: a surprising fact, bold claim or open question that stops the scroll. Max 12 words.
- Build tension like a thriller: short punchy sentences, a mini cliffhanger every few beats ("But that's not the crazy part.").
- Concrete details: names, places, years, what was at stake.
- The last beat gives the lesson in one strong sentence that flows back into the first sentence so the video loops.
- "text" is plain spoken English only. No labels, stage directions, emojis, hashtags or brackets.

FOR EACH BEAT'S SCENE:
- "characters": 0-3 stick figures. Pick the pose and mood that act out the sentence (e.g. losing money = sad, a big win = cheer, a decision = think, a deal = hold + another figure, a reveal = shock, explaining = present).
- "label": the real person's or company's short name (max 12 letters) if that figure IS them, otherwise "". Use names often so viewers follow who is who.
- "prop": the one object that best shows the sentence (money_bag, chart_up, chart_down, rocket, building, etc.), or "none".
- "big_text": a short number, year or word (max 8 characters) taken from that beat's sentence to flash on screen, like "$40M", "1994", "x100", "BROKE". Use it in about half the beats, otherwise "".
- Vary the scenes: never the same pose + prop twice in a row.

RULES:
{rules}

ALSO RETURN:
- "topic": the story subject in under 8 words (used to avoid repeats).
- "title": a YouTube Shorts title under 70 characters. Curiosity-driven but honest. No ALL CAPS words except one.
- "hook_text": 3-6 words shown big on screen in the first 2 seconds.
- "caption": 1-2 short sentences for the post + a question that invites comments.
- "hashtags": 3-5 relevant hashtags without the # sign, lowercase.
{feedback}"""


def _call(model: str, key: str, prompt: str) -> dict:
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.95,
            "topP": 0.95,
            "maxOutputTokens": 4096,
            "responseMimeType": "application/json",
            "responseSchema": SCHEMA,
        },
    }
    r = requests.post(
        API.format(model=model),
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        json=body,
        timeout=120,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Gemini {model} HTTP {r.status_code}: {r.text[:300]}")
    data = r.json()
    parts = data["candidates"][0]["content"]["parts"]
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    text = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text.strip())
    return json.loads(text)


def _clean(story: dict, n_images: int = 0) -> dict:
    beats = []
    for beat in story.get("beats", []):
        t = re.sub(r"\s+", " ", LABELS.sub("", beat.get("text", ""))).strip()
        if not t:
            continue
        chars = []
        for c in beat.get("characters", [])[:3]:
            if c.get("pose") in POSES:
                chars.append({"pose": c["pose"],
                              "mood": c.get("mood") if c.get("mood") in MOODS else "neutral",
                              "label": (c.get("label") or "").strip()[:12]})
        big = (beat.get("big_text") or "").strip()[:9]
        beats.append({"text": t, "characters": chars,
                      "prop": beat.get("prop") if beat.get("prop") in PROPS else "none",
                      "big_text": big})
    story["beats"] = beats
    story["script"] = " ".join(b["text"] for b in beats)
    tags = [re.sub(r"[^a-z0-9]", "", t.lower()) for t in story.get("hashtags", [])]
    story["hashtags"] = [t for t in tags if t][:5]
    story["title"] = story["title"].strip().strip('"')[:95]
    story["hook_text"] = story["hook_text"].strip().strip('"')
    return story


def _problems(story: dict, cfg: dict) -> list[str]:
    words = len(story["script"].split())
    lo = int(cfg["video"]["target_seconds"] * 2.15)
    hi = int(cfg["video"]["target_seconds"] * 2.8)
    issues = []
    if words < lo:
        issues.append(f"The beats have only {words} spoken words in total; they must have at least {lo}.")
    if words > hi:
        issues.append(f"The beats have {words} spoken words in total; they must have at most {hi}. Make it shorter.")
    if len(story["beats"]) < 8:
        issues.append("Write 10-14 beats.")
    return issues


def _fact_check(key: str, story: dict) -> tuple[bool, list[str]]:
    """Second opinion with Google Search. Returns (ok, problems). Never blocks on its own errors."""
    prompt = f"""Fact-check this short video script about "{story['topic']}".
Use Google Search. Check every name, date, number, company and event.

SCRIPT:
{story['script']}

Reply with ONLY a JSON object, no other text:
{{"ok": true or false, "problems": ["each claim that is false or made up, with the correct fact"]}}
Minor rounding or simplification is fine (ok = true). Invented events, wrong people, wrong companies or wrong outcomes are not."""
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "tools": [{"google_search": {}}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1024}}
    for model in MODELS:
        try:
            r = requests.post(API.format(model=model),
                              headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                              json=body, timeout=120)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            parts = r.json()["candidates"][0]["content"]["parts"]
            txt = "".join(p.get("text", "") for p in parts)
            m = re.search(r"\{.*\}", txt, re.S)
            data = json.loads(m.group(0)) if m else {}
            ok = bool(data.get("ok", True))
            probs = [str(x) for x in data.get("problems", [])][:5]
            log(f"Fact check ({model}): {'OK' if ok else 'problems found'} {probs if probs else ''}")
            return ok, probs
        except Exception as e:  # noqa: BLE001
            log(f"Fact check with {model} unavailable: {e}")
    return True, []


def write_story(cfg: dict, fmt: dict, style: str, used_topics: list[str]) -> dict:
    key = env("GEMINI_API_KEY")
    feedback = ""
    errors = []
    best = None
    for attempt in range(1, 5):
        story = None
        for model in MODELS:
            try:
                story = _clean(_call(model, key, _prompt(cfg, fmt, style, used_topics, feedback)))
                story["model"] = model
                break
            except Exception as e:  # noqa: BLE001
                errors.append(str(e))
                log(f"Writer error: {e}")
        if story is None:
            continue
        issues = _problems(story, cfg)
        if issues:
            log(f"Story needs another try: {issues}")
            if len(story["beats"]) >= 8 and best is None:
                best = story
            feedback = "\nFIX THESE PROBLEMS FROM YOUR LAST TRY:\n- " + "\n- ".join(issues)
            continue
        ok, probs = _fact_check(key, story)
        if not ok and attempt < 4:
            feedback = ("\nYOUR LAST STORY HAD FACTUAL ERRORS:\n- " + "\n- ".join(probs) +
                        "\nPick a DIFFERENT, very famous story you are completely sure about.")
            continue
        log(f"Story ready: {story['topic']} ({len(story['script'].split())} words, {len(story['beats'])} beats)")
        return story
    if best:
        log("Using the closest story (length slightly off target).")
        return best
    raise RuntimeError("Could not write a story. Last errors: " + " | ".join(errors[-3:]))
