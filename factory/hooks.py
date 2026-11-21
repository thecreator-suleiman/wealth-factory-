"""Hook formulas, hook scorer and title checker.

Formulas (factory/ytkit/hooks.json) and the scoring/linting rules are adapted from
github.com/Jakeschincariol/youtube-agent-skill (MIT License, (c) 2026 Jake Schincariol - see
factory/ytkit/LICENSE). Ported to plain functions so the pipeline can reject weak hooks and
bad titles automatically, offline, with no extra API calls.
"""
import json
import re
from pathlib import Path

_DATA = json.loads((Path(__file__).parent / "ytkit" / "hooks.json").read_text(encoding="utf-8"))
FORMULAS = {h["id"]: h for h in _DATA["hooks"]}

# Formulas that suit true money stories (no "I tried it", tool stacks or tutorials).
# "the-impossible" = paradox stated as fact - the retention formula's default hook.
MONEY = ["the-impossible", "someone-elses-result", "the-warning", "contrarian-flip", "the-mistake",
         "the-statistic", "the-insider", "the-before-after", "the-origin", "the-comparison",
         "the-deadline", "the-direct-address"]


def formulas_for(n: int, k: int = 3) -> str:
    """Prompt block: the paradox hook + 2 rotating formulas from the library (different every video)."""
    rest = [m for m in MONEY if m != "the-impossible"]
    pick = ["the-impossible"] + [rest[(n * 2 + i) % len(rest)] for i in range(k - 1)]
    lines = []
    for fid in pick:
        f = FORMULAS[fid]
        lines.append(f'- {f["name"]}: {f["shape"]} Example shape: "{f["example"]}" Fails when: {f["fails_when"]}')
    return "\n".join(lines)


# ---------------------------------------------------------------- hook scorer (port of hookscore.py)
FILLER = {"basically", "actually", "literally", "just", "really", "very", "so", "kind", "sort", "like",
          "guys", "hey", "welcome", "today", "video", "subscribe", "channel"}
VAGUE = {"amazing", "incredible", "insane", "crazy", "huge", "massive", "game", "changer", "secret",
         "powerful", "ultimate", "best", "revolutionary", "mind", "blowing", "unbelievable"}
CONCRETE = re.compile(r"\b(\d[\d,.]*\s?(%|k|m|x|s|m|h)?|\$\d|\d+\s?(second|minute|hour|day|week|month|year)s?)\b", re.I)
YOU = re.compile(r"\b(you|your|you're|youre|yourself)\b", re.I)
STAKE = re.compile(r"\b(lose|lost|wasting|waste|quit|fail|broke|cost|risk|before|stop|never|die|dying|dead"
                   r"|bankrupt|billion|million|fired|collapsed?|buried|laughed|sold|bought|rejected|refused|turned down"
                   r"|gave away|worth|paying|charging|owe[ds]?|debt|crash(ed)?|everything|nothing|richest|poorest|biggest)\b", re.I)  # + money stakes
CURIOSITY = re.compile(r"\b(why|how|what|which|until|before|but|nobody|almost|except|reason|actually"
                       r"|yet|still|then|quietly|strange|secretly|instead|only|wait)\b", re.I)                     # + paradox turn words
NUMWORD = re.compile(r"\b(half|twice|double|triple|one|two|three|four|five|six|seven|eight|nine|ten|hundred"
                     r"|thousand|million|billion|trillion)\b", re.I)


def _words(t):
    return re.findall(r"[a-z0-9'%$.]+", t.lower())


def _specificity(t):
    w = _words(t)
    if not w:
        return 0
    nums = len(CONCRETE.findall(t)) + min(2, len(NUMWORD.findall(t)))  # spoken numbers count too
    s = 34 + nums * 22 - sum(x in VAGUE for x in w) * 16 - sum(x in FILLER for x in w) * 5
    s += min(18, 6 * sum(1 for x in t.split()[1:] if x[:1].isupper()))
    if t.split() and t.split()[0][:1].isupper() and t.split()[0].lower() not in ("the", "a", "this", "your", "you"):
        s += 6  # a named subject up front
    return max(0, min(100, s))


def _address(t):
    n = len(YOU.findall(t))
    first = 30 if YOU.search(" ".join(t.split()[:6])) else 0
    return max(0, min(100, 26 + n * 20 + first))


def _stakes(t):
    return max(0, min(100, 22 + len(STAKE.findall(t)) * 26 + (14 if CONCRETE.search(t) else 0)))


def _curiosity(t):
    q = 18 if t.strip().endswith("?") else 0
    closed = -18 if re.search(r"\b(because|so that|which means)\b", t, re.I) else 0
    return max(0, min(100, 24 + len(CURIOSITY.findall(t)) * 17 + q + closed))


def _brevity(t):
    n = len(_words(t))
    if n == 0:
        return 0
    if 9 <= n <= 24:
        return 100
    if n < 9:
        return max(30, 100 - (9 - n) * 11)
    return max(10, 100 - (n - 24) * 7)


FIX = {"specificity": "swap one adjective for a number, a name or a date",
       "address": "say 'you' in the first six words, or name the person",
       "stakes": "name what was lost or won (money, a company, a job)",
       "curiosity": "cut the half of the sentence that answers itself; leave the 'how' open",
       "brevity": "9 to 24 words"}


def score_hook(t: str) -> tuple[int, dict]:
    """0-100 verdict: 60% the mean of five properties + 40% the weakest one.
    Story hooks name a person instead of saying 'you', so ADDRESS counts half as much as the rest."""
    parts = {"specificity": _specificity(t), "address": _address(t), "stakes": _stakes(t),
             "curiosity": _curiosity(t), "brevity": _brevity(t)}
    vals = list(parts.values())
    core = [v for k, v in parts.items() if k != "address"]  # a named person works as well as "you"
    return round(0.7 * sum(vals) / len(vals) + 0.3 * min(core)), parts


def hook_issue(t: str, threshold: int = 46) -> str | None:
    v, parts = score_hook(t)
    if v >= threshold:
        return None
    weak = min(parts, key=parts.get)
    return (f'The hook (beat 1) scored {v}/100 - too weak. Weakest part: {weak} - {FIX[weak]}. '
            f'Rewrite beat 1 as a paradox stated as fact: a named person/company + a number + a twist.')


# ---------------------------------------------------------------- title checker (port of title.py)
T_VAGUE = {"amazing", "incredible", "insane", "crazy", "huge", "massive", "ultimate", "best", "powerful",
           "secret", "revolutionary", "mindblowing", "epic", "perfect", "complete", "everything"}
STOP = {"the", "a", "an", "of", "for", "to", "in", "on", "and", "or", "is", "are", "with", "your", "you", "my",
        "i", "this", "that", "it", "how", "what", "why"}


def title_issues(title: str, screen_text: str = "") -> tuple[list[str], list[str]]:
    """Returns (must_fix, nice_to_fix)."""
    t = title.strip()
    must, nice = [], []
    if len(t) > 60:
        must.append(f"Title is {len(t)} characters - keep it under 60.")
    caps = [w for w in t.split() if len(w) > 2 and w.isupper()]
    if len(caps) > 1:
        must.append(f"Title has {len(caps)} ALL-CAPS words - max one.")
    v = sorted({w for w in _words(t) if w.strip(".'") in T_VAGUE})
    if v:
        must.append(f"Title uses vague hype words ({', '.join(v)}) - use a name, number or date instead.")
    if not re.search(r"\d", t) and not re.search(r"\b[A-Z][a-z]+", " ".join(t.split()[1:])):
        nice.append("Title has no number, date or name.")
    if not [w for w in _words(t)[:3] if w not in STOP]:
        nice.append("First three words of the title are filler - move the subject forward.")
    if screen_text:
        shared = (set(_words(t)) - STOP) & (set(_words(screen_text)) - STOP)
        if shared:
            nice.append(f"Title repeats the on-screen hook text ({', '.join(sorted(shared))}).")
    return must, nice
