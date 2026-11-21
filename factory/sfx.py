"""Original sound effects made with numpy (no samples, no licences) + the per-video SFX track.

whoosh = scene change, pop = big text, cash = money, impact = fall/shock, riser = into the hook / the
"You see," reveal, ding = the lesson. Everything is mixed quietly under the voice in finish_video.
"""
import re
import wave
from pathlib import Path

import numpy as np

SR = 48000
_rng = np.random.default_rng(7)


def _t(sec):
    return np.arange(int(SR * sec)) / SR


def _env(n, a=0.005, r=0.2):
    """Attack / exponential release envelope."""
    t = np.arange(n) / SR
    e = np.minimum(t / max(a, 1e-4), 1.0) * np.exp(-t / max(r, 1e-4))
    return e


def _lowpass(x, k):
    """Cheap one-pole low-pass; k in (0, 1], smaller = darker. k may be an array (sweeps)."""
    y = np.empty_like(x)
    k = np.broadcast_to(k, x.shape)
    acc = 0.0
    for i in range(len(x)):
        acc += k[i] * (x[i] - acc)
        y[i] = acc
    return y


def whoosh(sec=0.45):
    n = int(SR * sec)
    t = np.linspace(0, 1, n)
    noise = _rng.standard_normal(n)
    sweep = 0.02 + 0.35 * np.sin(np.pi * t) ** 2          # filter opens then closes = air moving past
    x = _lowpass(noise, sweep) - _lowpass(noise, sweep * 0.15)
    x *= np.sin(np.pi * t) ** 1.5
    return 0.55 * x / (np.abs(x).max() + 1e-9)


def pop(sec=0.12):
    t = _t(sec)
    f = 900 * np.exp(-t * 28) + 380                       # quick downward chirp
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(len(t), 0.001, 0.035)
    return 0.6 * x


def cash():
    """'Ka-ching': drawer click + two bright bell partials."""
    click = _rng.standard_normal(int(SR * 0.03)) * _env(int(SR * 0.03), 0.0005, 0.006)
    t = _t(0.9)
    bell = sum(a * np.sin(2 * np.pi * f * t) for f, a in ((2093, 1.0), (2637, 0.6), (4186, 0.25), (5274, 0.15)))
    bell *= _env(len(t), 0.002, 0.25)
    out = np.zeros(int(SR * 1.0))
    out[:len(click)] += 0.9 * click
    s = int(SR * 0.07)
    out[s:s + len(bell)] += 0.35 * bell[:len(out) - s]
    return 0.7 * out / np.abs(out).max()


def impact():
    t = _t(0.7)
    f = 95 * np.exp(-t * 6) + 38
    thump = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(len(t), 0.002, 0.18)
    n = int(SR * 0.25)
    crack = _lowpass(_rng.standard_normal(n), 0.25) * _env(n, 0.0005, 0.05)
    thump[:n] += 0.5 * crack
    return 0.9 * thump / np.abs(thump).max()


def riser(sec=1.3):
    n = int(SR * sec)
    t = np.linspace(0, 1, n)
    noise = _lowpass(_rng.standard_normal(n), 0.02 + 0.5 * t ** 2)
    tone = np.sin(2 * np.pi * np.cumsum(220 + 660 * t ** 2) / SR) * 0.25
    x = (noise / (np.abs(noise).max() + 1e-9) * 0.6 + tone) * t ** 2.2
    x[-int(SR * 0.02):] *= np.linspace(1, 0, int(SR * 0.02))
    return 0.5 * x / np.abs(x).max()


def ding():
    t = _t(1.4)
    x = sum(a * np.sin(2 * np.pi * f * t) for f, a in ((1318.5, 1.0), (2637, 0.35), (3951, 0.12)))
    return 0.45 * x * _env(len(t), 0.002, 0.45) / 1.47


_BANK = {}


def _get(name):
    if name not in _BANK:
        _BANK[name] = {"whoosh": whoosh, "pop": pop, "cash": cash, "impact": impact,
                       "riser": riser, "ding": ding}[name]()
    return _BANK[name]


MONEY_PROPS = {"money_bag", "coins", "cash", "piggy_bank", "bank"}
MONEY_POSES = {"count_money", "fly_money", "throw_money", "give"}
HIT_POSES = {"fall", "shock", "panic"}
# loudness of each effect (linear) - all well under the voice
GAIN = {"whoosh": 0.22, "pop": 0.35, "cash": 0.30, "impact": 0.45, "riser": 0.30, "ding": 0.32}


def events(beats: list[dict], times: list[tuple[float, float]]) -> list[tuple[float, str]]:
    """(time, effect) list for a video."""
    ev = []
    hook_i = next((i for i, b in enumerate(beats) if not re.match(r"\s*(stop|wait,? don't|give me|stay with)",
                                                                   b["text"], re.I)), 0)
    last_money = -9.0
    for i, (b, (a, _e)) in enumerate(zip(beats, times)):
        poses = {c["pose"] for c in b.get("characters", [])}
        txt = b["text"].strip().lower()
        if i == hook_i and a > 1.0:
            ev.append((a - 1.3, "riser"))                         # riser into the hook
        if txt.startswith("you see"):
            ev.append((a - 1.3, "riser"))                         # and into the reveal
        if i > 0:
            ev.append((a - 0.18, "whoosh"))
        if b.get("big_text") or b.get("headline"):
            ev.append((a + (2.1 if i == 0 else 0.3), "pop"))
        if (poses & MONEY_POSES or b.get("prop") in MONEY_PROPS) and a - last_money > 6:
            ev.append((a + 0.25, "cash"))
            last_money = a
        if poses & HIT_POSES:
            ev.append((a + (0.65 if "fall" in poses else 0.1), "impact"))
        if txt.startswith("the lesson"):
            ev.append((a + 0.05, "ding"))
    return [(max(t, 0.0), n) for t, n in ev]


def build_track(beats: list[dict], times: list[tuple[float, float]], length: float, out: Path) -> Path:
    track = np.zeros(int(SR * (length + 2)))
    for t, name in events(beats, times):
        x = _get(name) * GAIN[name]
        s = int(t * SR)
        e = min(s + len(x), len(track))
        if e > s:
            track[s:e] += x[:e - s]
    track = track[:int(SR * length)]
    peak = np.abs(track).max()
    if peak > 0.95:
        track *= 0.95 / peak
    pcm = (track * 32767).astype("<i2")
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return out
