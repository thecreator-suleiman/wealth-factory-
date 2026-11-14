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

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "topic": {"type": "STRING"},
        "title": {"type": "STRING"},
        "hook_text": {"type": "STRING"},
        "script": {"type": "STRING"},
        "image_prompts": {"type": "ARRAY", "items": {"type": "STRING"}},
        "caption": {"type": "STRING"},
        "hashtags": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["topic", "title", "hook_text", "script", "image_prompts", "caption", "hashtags"],
}

LABELS = re.compile(
    r"\b(scene|beat|narrator|voiceover|voice over|hook|intro|outro|cta)\s*\d*\s*[:\-–]\s*"
    r"|\[[^\]]*\]|\([^)]*(music|sfx|pause|beat)[^)]*\)|\*+|#+",
    re.IGNORECASE,
)


def _prompt(cfg: dict, fmt: dict, style: str, used_topics: list[str], feedback: str) -> str:
    ch, vid = cfg["channel"], cfg["video"]
    words_lo = int(vid["target_seconds"] * 2.6)
    words_hi = int(vid["target_seconds"] * 2.9)
    n = vid["images"]
    avoid = "\n".join(f"- {t}" for t in used_topics[-80:]) or "- (none yet)"
    rules = "\n".join(f"- {r}" for r in ch["rules"])
    return f"""You are the head writer of a fast-growing short-video channel called "{ch['name']}".

CHANNEL: {ch['niche']}
AUDIENCE: {ch['audience']}
LANGUAGE: {ch['language']}

THIS VIDEO'S FORMAT: "{fmt['name']}" - {fmt['brief']}

PICK ONE specific, real, well-documented story that fits the format. It must NOT repeat any of these past topics:
{avoid}

WRITE "script" = only the words the narrator speaks:
- {words_lo}-{words_hi} words (about {vid['target_seconds']} seconds).
- Sentence 1 is the hook: a surprising fact, a bold claim or an open question that makes people stop scrolling. Max 12 words.
- Build tension like a thriller: short punchy sentences, one idea per sentence, a mini cliffhanger every 15 seconds ("But that's not the crazy part.").
- Use concrete details: names, places, years, what was at stake.
- End with the lesson in one strong sentence, then a final line that flows naturally back into the first sentence so the video loops.
- Plain spoken English. No labels, no stage directions, no emojis, no hashtags, no lists, no brackets.

RULES:
{rules}

ALSO RETURN:
- "topic": the story subject in under 8 words (used to avoid repeats).
- "title": a YouTube Shorts title under 70 characters. Curiosity-driven but honest. No ALL CAPS words except one.
- "hook_text": 3-6 words shown big on screen in the first 2 seconds.
- "image_prompts": exactly {n} image descriptions, in story order, one per moment of the script. Each is self-contained (repeat who/where), vertical composition, NO text, NO logos, NO real famous faces (show silhouettes, hands, places, objects instead). Style for all of them: {style}.
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


def _clean(story: dict, n_images: int) -> dict:
    script = LABELS.sub("", story["script"])
    script = re.sub(r"\s+", " ", script).strip()
    story["script"] = script
    prompts = [p.strip() for p in story.get("image_prompts", []) if p and p.strip()]
    if prompts:
        while len(prompts) < n_images:
            prompts.append(prompts[len(prompts) % len(prompts)])
    story["image_prompts"] = prompts[:n_images]
    tags = [re.sub(r"[^a-z0-9]", "", t.lower()) for t in story.get("hashtags", [])]
    story["hashtags"] = [t for t in tags if t][:5]
    story["title"] = story["title"].strip().strip('"')[:95]
    story["hook_text"] = story["hook_text"].strip().strip('"')
    return story


def _problems(story: dict, cfg: dict) -> list[str]:
    words = len(story["script"].split())
    lo = int(cfg["video"]["target_seconds"] * 2.5)
    hi = int(cfg["video"]["target_seconds"] * 3.1)
    issues = []
    if words < lo:
        issues.append(f"The script has only {words} words; it must have at least {lo}.")
    if words > hi:
        issues.append(f"The script has {words} words; it must have at most {hi}.")
    if len(story["image_prompts"]) < 8:
        issues.append(f"Give exactly {cfg['video']['images']} image_prompts.")
    return issues


def write_story(cfg: dict, fmt: dict, style: str, used_topics: list[str]) -> dict:
    key = env("GEMINI_API_KEY")
    feedback = ""
    errors = []
    best = None
    for attempt in range(1, 4):
        for model in MODELS:
            try:
                story = _call(model, key, _prompt(cfg, fmt, style, used_topics, feedback))
                story = _clean(story, cfg["video"]["images"])
                issues = _problems(story, cfg)
                if not issues:
                    log(f"Story written by {model}: {story['topic']} ({len(story['script'].split())} words)")
                    story["model"] = model
                    return story
                if len(story["image_prompts"]) >= 8:
                    best = dict(story, model=model)
                feedback = "\nFIX THESE PROBLEMS FROM YOUR LAST TRY:\n- " + "\n- ".join(issues)
                log(f"Story needs another try ({model}): {issues}")
                break  # same model family is fine, retry with feedback
            except Exception as e:  # noqa: BLE001
                errors.append(str(e))
                log(f"Writer error: {e}")
                continue
    if best:
        log("Using the closest story (length slightly off target).")
        return best
    raise RuntimeError("Could not write a story. Last errors: " + " | ".join(errors[-3:]))
