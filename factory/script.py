"""Step 1: write the story with Google Gemini (free API key from aistudio.google.com)."""
import json
import re

import requests

from .common import env, log
from .hooks import formulas_for, hook_issue, score_hook, title_issues

# Tried in order. If one is busy, retired or out of free quota, the next is used.
MODELS = [
    "gemini-flash-latest",
    "gemini-3.8-flash",
    "gemini-2.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-2.5-flash",
]

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_FOUND: list[str] = []
_SPENT: set[str] = set()


def _models() -> list[str]:
    """MODELS first, then any newer free Flash models Google lists today - so a retired model never stops us."""
    import os
    if os.environ.get("FORCE_BACKUP") == "true":
        return []  # test switch: pretend Gemini is down
    if not _FOUND:
        extra = []
        try:
            r = requests.get("https://generativelanguage.googleapis.com/v1beta/models",
                             params={"key": os.environ.get("GEMINI_API_KEY", ""), "pageSize": 200}, timeout=30)
            for m in r.json().get("models", []):
                name = m.get("name", "").split("/")[-1]
                if ("flash" in name and "generateContent" in m.get("supportedGenerationMethods", [])
                        and not any(b in name for b in ("image", "tts", "audio", "live", "thinking", "exp"))):
                    extra.append(name)
        except Exception:  # noqa: BLE001
            pass
        def ver(n):
            nums = re.findall(r"\d+(?:\.\d+)?", n)
            return float(nums[0]) if nums else 0.0
        extra = sorted(set(extra) - set(MODELS), key=ver, reverse=True)
        _FOUND.extend(MODELS + extra[:6])
        log(f"Gemini models to try: {', '.join(_FOUND)}")
    return _FOUND

from .stickman import MOODS, PLACES, POSES, PROPS

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
        "place": {"type": "STRING", "enum": PLACES},
        "big_text": {"type": "STRING"},
        "headline": {"type": "STRING"},
    },
    "required": ["text", "characters", "place", "prop", "big_text", "headline"],
}
SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "topic": {"type": "STRING"},
        "title": {"type": "STRING"},
        "hook_text": {"type": "STRING"},
        "beats": {"type": "ARRAY", "items": BEAT},
        "caption": {"type": "STRING"},
        "sources": {"type": "ARRAY", "items": {"type": "STRING"}},
        "hashtags": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["topic", "title", "hook_text", "beats", "caption", "hashtags", "sources"],
}

LABELS = re.compile(
    r"\b(scene|beat|narrator|voiceover|voice over|hook|intro|outro|cta)\s*\d*\s*[:\-–]\s*"
    r"|\[[^\]]*\]|\([^)]*(music|sfx|pause|beat)[^)]*\)|\*+|#+",
    re.IGNORECASE,
)


STRUCTURES = [
    "TIMELINE - from the beginning to the twist to where they are now.",
    "MYTH VS TRUTH - open with what everyone believes, then reveal what really happened.",
    "TWO PEOPLE, ONE CHOICE - two people (or companies) faced the same choice; one won, one lost. Show both sides.",
    "3 MISTAKES COUNTDOWN - the story told through the 3 biggest mistakes (or moves), counting down to number 1.",
    "WHAT IF YOU HAD $1,000 - follow what $1,000 at the key moment would be worth now (real numbers only), "
    "then tell the story behind it.",
]


WPS_LO, WPS_HI = 2.75, 3.1          # spoken words per second (owner: clear pace, ~2.95)

LOOP = ("\n   LOOP ENDING: write the payoff so its last words flow straight back into the HOOK when the short "
        "replays\n   (last line + beat 1 read as one sentence), e.g. payoff \"...and that's exactly why\" -> hook "
        "\"Kodak invented\n   the digital camera, then buried it.\" Viewers who loop count as rewatches.")


def _part_text(cfg: dict) -> tuple[str, str]:
    """(part block, ending rule) for Part 1 / Part 2 stories and normal loop-ending videos."""
    if cfg.get("_part") == 1:
        return ("THIS IS PART 1 OF 2. Tell the first half of the story (who, the rise, the big decision) "
                "and stop at the most tense moment.",
                "\n   PART 1 ENDING: the payoff is a CLIFFHANGER instead - stop right before the outcome "
                "(\"...and then the phone rang.\"). The system adds the Part 2 line itself.")
    if cfg.get("_part") == 2:
        return ("THIS IS PART 2 OF 2 - same story, same people. Part 1 script (already posted):\n"
                + cfg.get("_part1", "")[:2500]
                + "\nBeat 1 must be a one-line recap that is still a hook (e.g. \"Part 2: Kodak buried the "
                "future, and now the bill arrives.\"). Then tell what happened next and how it ended. Do not "
                "repeat Part 1's facts except the recap.", LOOP)
    return "", LOOP


def _prompt(cfg: dict, fmt: dict, research: str, used_topics: list[str], feedback: str) -> str:
    ch, vid = cfg["channel"], cfg["video"]
    words_lo = int(vid["target_seconds"] * WPS_LO)
    words_hi = int(vid["target_seconds"] * WPS_HI)
    avoid = "\n".join(f"- {t}" for t in used_topics[-80:]) or "- (none yet)"
    if cfg.get("_part") == 2:
        avoid = "- (Part 2: continue the same topic)"
    rules = "\n".join(f"- {r}" for r in ch["rules"])
    handle = ch.get("handle", "@monezic")
    hooks = cfg.get("_hooks", "")
    part, ending = _part_text(cfg)
    names = cfg.get("_trending") or []
    trending = ("TRENDING THIS WEEK (people/companies in the news - people are searching for them): "
                + "; ".join(names) + ".\nIf one of them has a real, well-documented story that fits this video's "
                "format, PREFER it (say in one line why it matters now). Otherwise ignore this list."
                ) if names and fmt.get("kind") != "news" and not cfg.get("_part") == 2 else ""
    return f"""You are the head writer of "{ch['name']}" ({handle}), a fast-growing money channel in the style of
Casually Finance: casual, witty, skeptical, urgent but analytical. Videos are animated STICKMAN explainers
(black stick figures on white, green highlights).

CHANNEL: {ch['niche']}
AUDIENCE: {ch['audience']}
LANGUAGE: {ch['language']}

THIS VIDEO'S FORMAT: "{fmt['name']}" - {fmt['brief']}

STORY SHAPE FOR THIS VIDEO (tell it this way so every video feels different): {cfg.get('_structure', STRUCTURES[0])}

MONEZIC LESSON (required): the second-to-last beat starts with "The lesson:" and gives Monezic's own short,
original takeaway in one sentence - an insight, not a cliche, and never financial advice.
{part}

{research}

Do NOT repeat any of these past topics (pick a different person or company):
{avoid}

STRUCTURE (12-16 "beats"; each beat = 1-2 short spoken sentences + the scene shown while they are spoken).
Total spoken words: {words_lo}-{words_hi} (about {vid['target_seconds']} seconds at a FAST, steady pace - about
3 words per second - clear, easy to follow). Sentences ~8-12 words, simple words, contractions, no filler.
This is a retention formula measured on viral story shorts - follow it exactly:
1. HOOK (beat 1, 10-16 words): a PARADOX STATED AS FACT. No setup, no greeting, no "stop scrolling".
   A named person or company did something that sounds dumb or impossible, with real stakes and a number,
   e.g. "Kodak invented the digital camera, then buried it to protect film." Use one of these hook formulas:
{hooks}
   Beat 2 must then deliver the first shocking fact.
2. SETTING (1-2 beats): who, where, when - present tense, one concrete detail (a year, a city, a number).
3. ESCALATION (3-5 beats): the decision, risk or mistake. People doubt, laugh or mock (one short in-character
   line of dialogue is great), the stakes climb. One funny casual analogy or exaggeration joke.
4. MYSTERY (1 beat): a question that starts with "Wait," - e.g. "Wait, why would anyone say no to that?"
5. PIVOT (1-2 beats): a beat that starts with "You see," and reveals the real mechanism - the part nobody
   tells you - with an everyday analogy.
6. RESULT (1 beat): how it ended, with a real number.
7. LESSON (second-to-last beat): starts with "The lesson:" + Monezic's own one-sentence takeaway, then ONE
   direct question for the comments (e.g. "Would you have sold?"). Do not say the channel name.
8. PAYOFF (LAST beat, 1-2 short sentences): the ironic twist that lands the story. The video ENDS on this
   line - no goodbye, no "follow", no "thanks for watching".{ending}
Short punchy sentences. Sound like a person telling a friend, not a news anchor.
{trending}
FOR EACH BEAT'S SCENE:
- "characters": 0-3 stick figures. The pose is an ACTION that literally acts out what the voice says in that
  sentence, like a mime: losing everything = fall or kneel or cry, getting rich = fly_money or count_money or lift,
  spending/wasting = throw_money, working hard = dig or carry or type, a deal = handshake or sign (2 figures facing),
  a call = phone, news = read, starting out = walk, escaping/fast growth = run or climb, a mistake = facepalm,
  "nobody knows" = shrug, mocking = laugh, begging banks/investors = beg, pride = confident, a crash = fall or panic,
  giving/paying = give, celebrating = cheer or dance or high_five or clap. Use a different action in every beat;
  use many different actions across the video. Use 2 figures when two sides interact.
- "label": short name (max 12 letters) if the figure IS a real person, company, country or group
  ("FED", "BANKS", "YOU", "CHINA", "INVESTORS"), otherwise "". Use labels often so viewers follow who is who.
- "place": where the sentence happens, drawn as the background so a viewer WITHOUT sound understands it:
  office (desk, chair), home, bank, street (city), stage (speech/announcement), garage (humble start),
  factory, store (shop/selling), market (stock market screen), courtroom (lawsuit/jail), or "auto".
  Keep the same place for beats in the same location; change place when the story moves.
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
- "title": a YouTube Shorts title under 60 characters (best under 40): ominous, declarative, curiosity-driven
  but honest, with the subject's NAME or a NUMBER in it (style: "Kodak Buried The Future", "Nokia Had 50%. Then 0").
  Max one ALL-CAPS word. No hype words (amazing, insane, crazy, secret, ultimate, best).
- "hook_text": 2-5 punchy words shown huge on screen in the first 2 seconds (e.g. "THEY SAID NO", "$0 TO $1B").
  Do not repeat the title's words - it is a second hook.
- "caption": 1-2 short sentences for the post + a question that invites comments.
- "hashtags": 3-5 relevant hashtags without the # sign, lowercase.
- "sources": 2-4 real, well-known sources for the facts used (publication or document names only, e.g.
  "Forbes", "Bloomberg", "Apple 10-K filing", "The Wall Street Journal"). No URLs. Never invent a source.
{feedback}"""


def _research(key: str, fmt: dict, used_topics: list[str], trending: bool) -> str:
    """Finds a real, recent money story with Google Search (or an evergreen one)."""
    if not trending:
        return ("TOPIC: choose one real, famous, well-documented story about a specific PERSON or COMPANY "
                "that fits the format. Only use facts you are certain about.")
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
    for model in _models():
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


_GROQ: list[str] = []


def _groq(prompt: str, as_json: bool, max_tokens: int = 3000) -> str:
    """Backup writer on Groq (free) - used only when every Gemini model fails."""
    import os
    gk = os.environ.get("GROQ_API_KEY", "")
    if not gk:
        raise RuntimeError("Groq backup not set up")
    h = {"Authorization": f"Bearer {gk}"}
    if not _GROQ:
        try:
            ids = [m["id"] for m in requests.get("https://api.groq.com/openai/v1/models", headers=h, timeout=30).json()["data"]]
        except Exception:  # noqa: BLE001
            ids = []
        pref = ["gpt-oss-120b", "llama-4-maverick", "llama-3.3-70b", "kimi-k2", "qwen3", "gpt-oss-20b",
                "llama-4-scout", "llama"]
        # Only text-writing models (skip voice, speech, safety and vision models)
        ids = [i for i in ids if any(k in i for k in pref)
               and not any(b in i for b in ("whisper", "tts", "orpheus", "playai", "guard", "embed", "vision"))]
        ids.sort(key=lambda i: next(n for n, k in enumerate(pref) if k in i))
        _GROQ.extend(ids[:4] or ["llama-3.3-70b-versatile", "openai/gpt-oss-120b"])
        log(f"Groq backup models: {', '.join(_GROQ)}")
    import time as _t
    last = ""
    for rnd in range(2):
        for model in _GROQ:
            body = {"model": model, "temperature": 0.9, "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": prompt}]}
            r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=h, json=body, timeout=180)
            if r.status_code == 200:
                txt = r.json()["choices"][0]["message"]["content"] or ""
                txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.S).strip()
                if as_json:
                    m = re.search(r"\{.*\}", txt, re.S)
                    if not m:
                        last = f"Groq {model}: no JSON in reply"
                        log(last)
                        continue
                    txt = m.group(0)
                log(f"Backup writer used: Groq {model}")
                return txt
            last = f"Groq {model} HTTP {r.status_code}: {r.text[:200]}"
            log(last)
        if "429" in last and rnd == 0:
            log("Groq per-minute limit - waiting 65 s")
            _t.sleep(65)
        else:
            break
    raise RuntimeError(last or "Groq failed")


def _call(model: str, key: str, prompt: str) -> dict:
    if model == "groq":
        txt = _groq(prompt + "\n\nReply with ONLY one JSON object that follows this schema exactly "
                    "(same field names and allowed values):\n" + json.dumps(SCHEMA), True)
        return json.loads(re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", txt.strip()))
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
        if r.status_code == 404:  # Google says which model replaces a retired one - start using it
            for new in re.findall(r"models/(gemini-[\w.\-]+)", r.text):
                if new != model and new not in _FOUND:
                    _FOUND.insert(0, new)
                    log(f"Gemini model {model} retired - switching to {new}")
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
                      "place": beat.get("place") if beat.get("place") in PLACES else "auto",
                      "big_text": big, "headline": (beat.get("headline") or "").strip()[:60]})
    story["beats"] = beats
    story["script"] = " ".join(b["text"] for b in beats)
    tags = [re.sub(r"[^a-z0-9]", "", t.lower()) for t in story.get("hashtags", [])]
    story["hashtags"] = [t for t in tags if t][:5]
    story["title"] = story["title"].split("|")[0].strip().strip('"')[:70]
    story["hook_text"] = " ".join(story["hook_text"].strip().strip('"').split()[:5])
    return story


def _problems(story: dict, cfg: dict) -> list[str]:
    """Hard problems (length, beat count) + soft ones (hook score, title, formula beats) prefixed 'SOFT:'.
    Soft problems are sent back to the writer for the first tries, then accepted."""
    words = len(story["script"].split())
    lo = int(cfg["video"]["target_seconds"] * (WPS_LO - 0.2))
    hi = int(cfg["video"]["target_seconds"] * (WPS_HI + 0.25))
    issues = []
    if words < lo:
        issues.append(f"The beats have only {words} spoken words in total; they must have at least {lo}.")
    if words > hi:
        issues.append(f"The beats have {words} spoken words in total; they must have at most {hi}. Make it shorter.")
    if len(story["beats"]) < 8:
        issues.append("Write 12-16 beats.")
        return issues
    first = story["beats"][0]["text"]
    if re.match(r"\s*(stop|wait|hey|hi|welcome|today)\b", first, re.I):
        issues.append("Beat 1 must be the hook itself (a paradox stated as fact), not a greeting or 'stop scrolling'.")
    else:
        bad = hook_issue(first)
        if bad:
            issues.append("SOFT: " + bad)
    must, _nice = title_issues(story.get("title", ""), story.get("hook_text", ""))
    issues += ["SOFT: " + m for m in must]
    txt = story["script"].lower()
    if "you see," not in txt:
        issues.append('SOFT: Add the pivot beat that starts with "You see," (the real mechanism).')
    if not re.search(r"\bwait\b[^.?!]*\?", txt):
        issues.append('SOFT: Add one mystery beat - a question that starts with "Wait," .')
    if "?" not in " ".join(b["text"] for b in story["beats"][-2:]):
        issues.append("SOFT: The lesson beat (second-to-last) must end with a question for the comments.")
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
    for model in _models():
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


OPENERS = [
    "Stop scrolling. Give me one minute.",
    "Stop scrolling, and give me sixty seconds.",
    "Wait, don't scroll. Give me one minute.",
    "Stop. Give me one minute, this matters.",
]
QUESTIONS = [
    "What do you think? Tell me in the comments.",
    "Would you have seen this coming? Drop it in the comments.",
    "Which side are you on?",
]
FOLLOW = "Comment below, and follow Monezic so you can find us again."
PART2 = ["Part 2 is next. Follow Monezic so you don't miss it.",
         "Follow Monezic - part 2 drops next."]


OFFER = {
    "business": "Want the full free business plan? Follow Monezic on Instagram and comment PLAN.",
    "tool": "Want my free step-by-step guide? Follow Monezic on Instagram and comment GUIDE.",
}


def _guarantee_shape(story: dict, kind: str = "story", opening: str = "stop", part: int = 0) -> dict:
    """Opening line, a comment question + follow line on the LESSON beat, and the video ends on the payoff."""
    import random
    rnd = random.Random(story.get("topic", ""))
    opener = {"text": rnd.choice(OPENERS),
              "characters": [{"pose": "present", "mood": "happy", "label": ""}],
              "prop": "clock", "big_text": "", "headline": ""}
    beats = story["beats"]
    # the payoff must be the last word: strip any goodbye / follow / subscribe sentence the writer added
    last = re.sub(r"[^.?!]*\b(follow|subscribe|thanks for watching|see you)\b[^.?!]*[.?!]?", "",
                  beats[-1]["text"], flags=re.I).strip()
    if last:
        beats[-1]["text"] = last
    if opening == "hook":
        pass  # retention formula: the hook IS the first line - no "stop scrolling" opener
    elif opening == "fact":
        # Shocking fact first (the hook), then "give me one minute".
        if re.match(r"\s*(stop|wait)\b", beats[0]["text"], re.I) and len(beats) > 1:
            beats.pop(0)
        beats.insert(1, dict(opener, text=rnd.choice(["Give me one minute.", "Give me sixty seconds.",
                                                       "Stay with me for one minute."])))
    elif not re.match(r"\s*(stop|wait)\b", beats[0]["text"], re.I):
        beats.insert(0, opener)
    cta = beats[-2] if len(beats) >= 3 else beats[-1]
    cta["text"] = re.sub(r"\s*(Tell (me|us)|Let (me|us) know|Drop it|Comment)[^.?!]*(below|comments?)[.!]?", "",
                         cta["text"], flags=re.I).strip()
    if "?" not in cta["text"]:
        cta["text"] = cta["text"].rstrip() + " " + rnd.choice(QUESTIONS)
    if part == 1:
        beats[-1]["text"] = beats[-1]["text"].rstrip() + " " + rnd.choice(PART2)
    elif kind in OFFER:
        cta["text"] = cta["text"].rstrip() + " " + OFFER[kind]
    elif "follow monezic" not in cta["text"].lower():
        cta["text"] = cta["text"].rstrip() + " " + FOLLOW
    story["script"] = " ".join(b["text"] for b in beats)
    if part:
        story["title"] = re.sub(r"\s*\(?part \d\)?", "", story["title"], flags=re.I).strip()[:58] + f" (Part {part})"
        story["part"] = part
    return story


def trending_names(key: str) -> list[str]:
    """People/companies in money news this week (Gemini + Google Search). [] if unavailable."""
    prompt = ("Use Google Search. List 8 people or companies that are trending in business, money or tech news "
              "THIS WEEK worldwide (include 1-2 African ones if any). Reply with ONLY a JSON array of strings, "
              "each 'Name - why trending (max 8 words)'.")
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "tools": [{"google_search": {}}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 800}}
    for model in _models()[:3]:
        try:
            r = requests.post(API.format(model=model),
                              headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                              json=body, timeout=120)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            txt = "".join(p.get("text", "") for p in r.json()["candidates"][0]["content"]["parts"])
            m = re.search(r"\[.*\]", txt, re.S)
            names = [str(x).strip()[:80] for x in json.loads(m.group(0))][:8] if m else []
            if names:
                log(f"Trending this week ({model}): {'; '.join(names)}")
                return names
        except Exception as e:  # noqa: BLE001
            log(f"Trending search with {model} unavailable: {e}")
    return []


def _better_hook(key: str, story: dict) -> dict:
    """Ask for 6 alternative opening lines, score them with the hook scorer, keep the strongest (incl. the original)."""
    first = story["beats"][0]["text"]
    prompt = (f"This is the first line of a 60-second money story short about: {story['topic']}.\n"
              f"Current first line: \"{first}\"\nStory (for facts only - use ONLY facts from it):\n{story['script'][:1800]}\n\n"
              "Write 6 better first lines. Each: 9-16 words, a PARADOX STATED AS FACT, no setup, no greeting, "
              "names the person or company, includes a real number from the story, and leaves the 'how/why' open "
              "(e.g. \"Kodak invented the digital camera, then buried it to protect film.\"). "
              "Reply with ONLY a JSON array of 6 strings.")
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.8, "maxOutputTokens": 800}}
    cands = []
    for model in [m for m in _models() if m not in _SPENT][:3]:
        try:
            r = requests.post(API.format(model=model), headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                              json=body, timeout=90)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            txt = "".join(p.get("text", "") for p in r.json()["candidates"][0]["content"]["parts"] if not p.get("thought"))
            m = re.search(r"\[.*\]", txt, re.S)
            cands = [str(c).strip() for c in json.loads(m.group(0))] if m else []
            break
        except Exception as e:  # noqa: BLE001
            log(f"Hook rewrite with {model} unavailable: {e}")
    if not cands:
        try:
            m = re.search(r"\[.*\]", _groq(prompt, False, 800), re.S)
            cands = [str(c).strip() for c in json.loads(m.group(0))] if m else []
        except Exception as e:  # noqa: BLE001
            log(f"Hook rewrite backup unavailable: {e}")
    cands = [c for c in cands if 6 <= len(c.split()) <= 20 and not re.match(r"\s*(stop|wait|hey|today)\b", c, re.I)]
    scored = sorted([(score_hook(c)[0], c) for c in cands + [first]], reverse=True)
    best_score, best = scored[0]
    if best != first:
        log(f"Hook upgraded {score_hook(first)[0]} -> {best_score}: {best}")
        story["beats"][0]["text"] = best
        story["script"] = " ".join(b["text"] for b in story["beats"])
    return story


def write_story(cfg: dict, fmt: dict, style: str, used_topics: list[str]) -> dict:
    key = env("GEMINI_API_KEY")
    kind = fmt.get("kind", "story")
    research = _research(key, fmt, used_topics, kind == "news")
    if kind != "news" and cfg.get("_part") != 2 and "_trending" not in cfg:
        cfg["_trending"] = trending_names(key)
    part = cfg.get("_part", 0)

    def shape(s):
        return _guarantee_shape(s, kind, cfg.get("_opening", "stop"), part)

    feedback = ""
    errors = []
    best = None
    backup_best = None
    for attempt in range(1, 7):
        story = None
        for model in [m for m in _models() if m not in _SPENT] + ["groq"]:
            try:
                story = _clean(_call(model, key, _prompt(cfg, fmt, research, used_topics, feedback)))
                story["model"] = model
                break
            except Exception as e:  # noqa: BLE001
                errors.append(str(e))
                log(f"Writer error: {e}")
                if "exceeded your current quota" in str(e):
                    _SPENT.add(model)  # daily free quota used up - don't wait on it, go to the backup
        if story is None:
            continue
        issues = _problems(story, cfg)
        hard = [i for i in issues if not i.startswith("SOFT: ")]
        if attempt >= 3 and not hard:
            if issues:
                log(f"Accepting minor issues after {attempt} tries: {issues}")
            issues = []  # hook/title/formula wishes are not worth losing the video over
        if issues:
            log(f"Story needs another try: {issues}")
            only_length = all("spoken words" in i for i in hard)
            words = len(story["script"].split())
            if only_length and len(story["beats"]) >= 8 and words >= cfg["video"]["target_seconds"] * 2.8:
                best = story
            if story.get("model") == "groq" and len(story["beats"]) >= 6 and words >= 150:
                backup_best = story  # backup writer: slightly short is better than no video
            feedback = "\nFIX THESE PROBLEMS FROM YOUR LAST TRY:\n- " + "\n- ".join(i.replace("SOFT: ", "") for i in issues)
            continue
        ok, probs = _fact_check(key, story)
        if not ok and attempt < 6:
            feedback = ("\nYOUR LAST SCRIPT HAD FACTUAL ERRORS - FIX THEM (or drop those claims):\n- " + "\n- ".join(probs))
            continue
        story = _better_hook(key, story)
        story = shape(story)
        log(f"Story ready: {story['topic']} ({len(story['script'].split())} words, {len(story['beats'])} beats, "
            f"hook score {score_hook(story['beats'][0 if cfg.get('_opening') in ('fact', 'hook') else 1]['text'])[0]})")
        return story
    if best:
        log("Using the closest story (length slightly off target).")
        return shape(_better_hook(key, best))
    if backup_best:
        log("Gemini unavailable - using the backup writer's story.")
        return shape(_better_hook(key, backup_best))
    raise RuntimeError("Could not write a story. Last errors: " + " | ".join(errors[-3:]))


def write_freebie(story: dict, kind: str) -> str:
    """Writes the free business plan / tool guide promised in the video (Markdown)."""
    key = env("GEMINI_API_KEY")
    if kind == "business":
        ask = (f"Write a free, practical starter business plan for this idea: {story['topic']}.\n"
               "Sections: The idea in one line; Who pays and why; Start-up cost (low/realistic, in USD); "
               "Step-by-step: first 30 days; How to get the first 10 customers; Simple pricing example; "
               "Risks and how to avoid them; Free tools to use. Be honest - no income promises.")
    else:
        ask = (f"Write a free step-by-step guide for this free money tool: {story['topic']}.\n"
               "Sections: What it is; Is it really free (and the catch); How to sign up; "
               "5 steps to get value in your first week; Tips; Free alternatives. "
               "Include the official website address only if you are certain of it.")
    prompt = ask + ("\nAudience: young people in Africa and worldwide. Plain English, short sentences, "
                    "Markdown headings and bullet lists, under 700 words. End with: "
                    "'Not financial advice - do your own research.'")
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.5, "maxOutputTokens": 3000}}
    for model in _models():
        try:
            r = requests.post(API.format(model=model),
                              headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                              json=body, timeout=240)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            parts = r.json()["candidates"][0]["content"]["parts"]
            txt = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
            if len(txt) > 400:
                log(f"Free {kind} guide written ({model})")
                return txt
        except Exception as e:  # noqa: BLE001
            log(f"Guide writer {model} unavailable: {e}")
    try:
        txt = _groq(prompt, False, 3000).strip()
        if len(txt) > 400:
            return txt
    except Exception as e:  # noqa: BLE001
        log(f"Guide backup unavailable: {e}")
    return ""
