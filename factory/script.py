"""Step 1: write the story with Google Gemini (free API key from aistudio.google.com)."""
import json
import re

import requests

from .common import env, log

# Tried in order. If one is busy, retired or out of free quota, the next is used.
MODELS = [
    "gemini-flash-latest",
    "gemini-2.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-2.5-flash",
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
        "headline": {"type": "STRING"},
    },
    "required": ["text", "characters", "prop", "big_text", "headline"],
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


def _prompt(cfg: dict, fmt: dict, research: str, used_topics: list[str], feedback: str) -> str:
    ch, vid = cfg["channel"], cfg["video"]
    words_lo = int(vid["target_seconds"] * 2.25)
    words_hi = int(vid["target_seconds"] * 2.65)
    avoid = "\n".join(f"- {t}" for t in used_topics[-80:]) or "- (none yet)"
    rules = "\n".join(f"- {r}" for r in ch["rules"])
    handle = ch.get("handle", "@monezic")
    return f"""You are the head writer of "{ch['name']}" ({handle}), a fast-growing money channel in the style of
Casually Finance: casual, witty, skeptical, urgent but analytical. Videos are animated STICKMAN explainers
(black stick figures on white, green highlights).

CHANNEL: {ch['niche']}
AUDIENCE: {ch['audience']}
LANGUAGE: {ch['language']}

THIS VIDEO'S FORMAT: "{fmt['name']}" - {fmt['brief']}

{research}

Do NOT repeat any of these past topics:
{avoid}

STRUCTURE (10-14 "beats"; each beat = 1-2 short spoken sentences + the scene shown while they are spoken).
Total spoken words: {words_lo}-{words_hi} (about {vid['target_seconds']} seconds).
1. COLD OPEN (beat 1): rush straight in with a bold, specific claim about what is happening - a number, a
   name, a contradiction. No greeting, no "stop scrolling", no "did you know", no "in this video". Max 14 words.
2. THE SETUP (1-2 beats): what is happening, in plain words, with one concrete fact.
3. HOW IT WORKS (3-4 beats): explain the mechanism like you are talking to a smart friend. Use one funny,
   casual analogy or label (like "hot potato", "dine and dash", "musical chairs").
4. THE TWIST (1-2 beats): "But here's the part nobody's talking about..." - the hidden angle.
5. HISTORY RHYMES (1-2 beats): a real past event that looks similar, and how it played out.
6. SO WHAT (1 beat): what this means for normal people - no advice, just what to watch.
7. CLOSE (last beat): one sharp line, then a casual call to action, e.g. "Hit subscribe so you're not the last
   one to find out." or "Follow {handle} - the next one's even crazier." Vary it every time.
Short punchy sentences. Sound like a person, not a news anchor.

FOR EACH BEAT'S SCENE:
- "characters": 0-3 stick figures. Pose + mood act out the sentence (losing money = sad, a big win = cheer,
  a decision = think, a deal = hold + another figure, a reveal = shock, explaining = present, panic = run).
- "label": short name (max 12 letters) if the figure IS a real person, company, country or group
  ("FED", "BANKS", "YOU", "CHINA", "INVESTORS"), otherwise "". Use labels often so viewers follow who is who.
- "prop": the one object that best shows the sentence, or "none".
- "big_text": a short number, year or word (max 8 characters) from that beat's sentence, like "$40M", "2008",
  "x100", "BROKE". About half the beats; otherwise "".
- "headline": ONLY in 1-2 beats (usually beat 2): a short news-style headline (max 40 characters) summarising
  the real news, shown as a news card. Otherwise "". If "headline" is used, leave "big_text" empty.
- Vary the scenes: never the same pose + prop twice in a row.

RULES:
{rules}

ALSO RETURN:
- "topic": the subject in under 8 words (used to avoid repeats).
- "title": a YouTube Shorts title under 60 characters: ominous, declarative, curiosity-driven but honest
  (style: "X Is Breaking", "It's Worse Than You Think", "The Smart Money Is Leaving"). Max one ALL-CAPS word.
- "hook_text": 3-6 words shown big on screen in the first 2 seconds.
- "caption": 1-2 short sentences for the post + a question that invites comments.
- "hashtags": 3-5 relevant hashtags without the # sign, lowercase.
{feedback}"""


def _research(key: str, fmt: dict, used_topics: list[str], trending: bool) -> str:
    """Finds a real, recent money story with Google Search (or an evergreen one)."""
    if not trending:
        return ("TOPIC: choose an evergreen story (how money really works, or a famous money event from history) "
                "that fits the format and still matters today. Only use facts you are certain about.")
    avoid = "; ".join(used_topics[-40:]) or "none"
    prompt = f"""Use Google Search to find ONE real money/economy/markets news story from the last 7 days
that fits this video format: "{fmt['name']}" - {fmt['brief']}
It must interest ordinary young people worldwide. Avoid these topics: {avoid}.
Reply with ONLY a JSON object:
{{"story": "one-line summary", "date": "when it happened", "facts": ["5-8 short verified facts with numbers, names and dates"],
  "history": "one real past event that looks similar, in one line"}}"""
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "tools": [{"google_search": {}}],
            "generationConfig": {"temperature": 0.4, "maxOutputTokens": 1500}}
    for model in MODELS:
        try:
            r = requests.post(API.format(model=model),
                              headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                              json=body, timeout=180)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            parts = r.json()["candidates"][0]["content"]["parts"]
            txt = "".join(p.get("text", "") for p in parts)
            m = re.search(r"\{.*\}", txt, re.S)
            data = json.loads(m.group(0))
            facts = "\n".join(f"- {f}" for f in data.get("facts", []))
            log(f"Researched ({model}): {data.get('story')}")
            return (f"TODAY'S TOPIC (real news, researched with Google Search):\n{data.get('story')} ({data.get('date')})\n"
                    f"VERIFIED FACTS - use only these facts for the news part:\n{facts}\n"
                    f"SIMILAR PAST EVENT: {data.get('history')}")
        except Exception as e:  # noqa: BLE001
            log(f"News research with {model} unavailable: {e}")
    return ("TOPIC: choose an evergreen story (how money really works, or a famous money event from history) "
            "that fits the format. Only use facts you are certain about.")


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
        timeout=240,
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
                      "big_text": big, "headline": (beat.get("headline") or "").strip()[:60]})
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
    trending = len(used_topics) % 10 < 7  # about 70% news, 30% evergreen
    research = _research(key, fmt, used_topics, trending)
    feedback = ""
    errors = []
    best = None
    for attempt in range(1, 5):
        story = None
        for model in MODELS:
            try:
                story = _clean(_call(model, key, _prompt(cfg, fmt, research, used_topics, feedback)))
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
            feedback = ("\nYOUR LAST SCRIPT HAD FACTUAL ERRORS - FIX THEM (or drop those claims):\n- " + "\n- ".join(probs))
            continue
        log(f"Story ready: {story['topic']} ({len(story['script'].split())} words, {len(story['beats'])} beats)")
        return story
    if best:
        log("Using the closest story (length slightly off target).")
        return best
    raise RuntimeError("Could not write a story. Last errors: " + " | ".join(errors[-3:]))
