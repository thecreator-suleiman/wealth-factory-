"""Draw animated stickman scenes in code - clean, consistent, no AI image mistakes.

Every frame is drawn with Cairo (smooth vector lines): black stick figures on white,
green accents, simple props, pop-in animation and gentle motion.
"""
import math
import subprocess
from pathlib import Path

import cairo

W, H = 1080, 1920
GROUND = 1330
INK = (0.08, 0.08, 0.09)
GREEN = (0.13, 0.77, 0.37)       # #22C55E
DARK_GREEN = (0.09, 0.64, 0.29)  # #16A34A
GREY = (0.55, 0.55, 0.58)
RED = (0.86, 0.15, 0.15)
LINE = 13

POSES = ["stand", "walk", "run", "point", "cheer", "sad", "think", "shock", "sit", "hold", "present", "angry",
         "wave", "clap", "facepalm", "shrug", "count_money", "throw_money", "dig", "carry", "push", "kneel",
         "fall", "jump", "dance", "type", "phone", "sign", "handshake", "high_five", "cry", "laugh", "explain",
         "bow", "salute", "read", "lift", "shake_fist", "panic", "sneak", "tired", "give", "climb", "confident",
         "beg", "lie_down", "fly_money"]
MOODS = ["happy", "sad", "neutral", "shocked", "angry", "worried"]
PROPS = ["none", "money_bag", "coins", "cash", "chart_up", "chart_down", "arrow_up", "arrow_down",
         "laptop", "phone", "house", "car", "building", "shop", "piggy_bank", "briefcase",
         "lightbulb", "clock", "trophy", "question", "warning", "globe", "rocket", "document",
         "crown", "lock", "calendar", "scale", "plane", "factory", "bank", "newspaper"]

FONT = "Anton"


def set_font(name: str) -> None:
    global FONT
    FONT = name


# ---------------------------------------------------------------- easing
def ease_out_back(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def ease_out(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def pop(t: float, start: float, dur: float = 0.35) -> float:
    return ease_out_back((t - start) / dur) if t > start else 0.0


# ---------------------------------------------------------------- primitives
def stroke(ctx, color=INK, width=LINE):
    ctx.set_source_rgb(*color)
    ctx.set_line_width(width)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.stroke()


def fill_stroke(ctx, fill=GREEN, color=INK, width=LINE - 2):
    ctx.set_source_rgb(*fill)
    ctx.fill_preserve()
    stroke(ctx, color, width)


def rrect(ctx, x, y, w, h, r):
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    ctx.close_path()


def text(ctx, s, x, y, size, color=INK, bold=True, align="center", outline=None):
    ctx.select_font_face(FONT, cairo.FONT_SLANT_NORMAL,
                         cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(size)
    ext = ctx.text_extents(s)
    if align == "center":
        tx = x - ext.width / 2 - ext.x_bearing
    elif align == "right":
        tx = x - ext.width - ext.x_bearing
    else:
        tx = x - ext.x_bearing
    ty = y - ext.height / 2 - ext.y_bearing
    ctx.move_to(tx, ty)
    ctx.text_path(s)
    if outline:
        ctx.set_source_rgb(*outline)
        ctx.set_line_width(size * 0.16)
        ctx.set_line_join(cairo.LINE_JOIN_ROUND)
        ctx.stroke_preserve()
    ctx.set_source_rgb(*color)
    ctx.fill()
    return ext.width


# ---------------------------------------------------------------- stick figure
def _limb(ctx, x, y, a1, l1, a2, l2):
    """Two-segment limb from (x, y). Angles in degrees, 0 = straight down, positive = to the right."""
    r1, r2 = math.radians(a1), math.radians(a2)
    ex, ey = x + math.sin(r1) * l1, y + math.cos(r1) * l1
    hx, hy = ex + math.sin(r2) * l2, ey + math.cos(r2) * l2
    ctx.move_to(x, y)
    ctx.line_to(ex, ey)
    ctx.line_to(hx, hy)
    stroke(ctx)
    return hx, hy


PLACES = ["auto", "office", "home", "bank", "street", "stage", "garage", "factory", "store", "market", "courtroom"]
BG = (0.80, 0.81, 0.83)      # light lines: background never fights the characters
BGF = (0.95, 0.96, 0.96)     # light fills
_AUTO = {"type": "office", "sit": "office", "phone": "office", "sign": "office", "read": "home", "tired": "home",
         "lie_down": "home", "dig": "garage", "carry": "garage", "push": "garage", "count_money": "bank",
         "lift": "bank", "fly_money": "bank", "give": "store", "present": "stage", "explain": "stage",
         "bow": "stage", "salute": "stage", "walk": "street", "run": "street", "sneak": "street"}


def _L(ctx, pts, w=6, col=BG):
    ctx.move_to(*pts[0])
    for p in pts[1:]:
        ctx.line_to(*p)
    stroke(ctx, col, w)


def _R(ctx, x, y, w, h, fill=BGF, col=BG, lw=6, r=6):
    rrect(ctx, x, y, w, h, r)
    fill_stroke(ctx, fill, col, lw)


def _window(ctx, x, y, w=220, h=260):
    _R(ctx, x, y, w, h, (0.93, 0.97, 1.0))
    _L(ctx, [(x + w / 2, y), (x + w / 2, y + h)], 5)
    _L(ctx, [(x, y + h / 2), (x + w, y + h / 2)], 5)


def draw_place(ctx, place, t):
    G = GROUND
    if place == "office":
        _window(ctx, 90, 520); _window(ctx, 770, 520)
        _R(ctx, 420, 560, 240, 170, (1, 1, 1)); _L(ctx, [(440, 700), (500, 650), (560, 670), (640, 590)], 7, GREEN)
        _L(ctx, [(540, 730), (540, 790)], 5)
    elif place == "home":
        _window(ctx, 120, 500, 260, 300)
        _R(ctx, 640, G - 230, 380, 140, (0.93, 0.95, 0.94), BG, 6, 30)       # sofa
        _R(ctx, 620, G - 300, 60, 210, (0.93, 0.95, 0.94), BG, 6, 20)
        _R(ctx, 980, G - 300, 60, 210, (0.93, 0.95, 0.94), BG, 6, 20)
        _L(ctx, [(560, G), (560, G - 380)], 6); _R(ctx, 500, G - 470, 120, 90, (1, 0.97, 0.85), BG, 6, 20)
        _R(ctx, 760, 520, 180, 130, (1, 1, 1)); text(ctx, "HOME", 850, 585, 40, BG)
    elif place == "bank":
        _L(ctx, [(60, 620), (540, 430), (1020, 620), (60, 620)], 8)
        text(ctx, "BANK", 540, 560, 70, BG)
        for cx in (130, 330, 750, 950):
            _R(ctx, cx - 30, 640, 60, G - 640 - 10, BGF, BG, 6, 4)
        _R(ctx, 40, G - 20, 1000, 20, BGF, BG, 5, 2)
    elif place == "street":
        for i, (bx, bw, bh) in enumerate([(0, 200, 620), (210, 160, 460), (380, 240, 720), (640, 180, 520), (830, 250, 650)]):
            _R(ctx, bx, G - bh, bw, bh, BGF, BG, 5, 2)
            for wy in range(int(G - bh + 40), int(G - 80), 90):
                for wx in range(int(bx + 25), int(bx + bw - 40), 60):
                    _R(ctx, wx, wy, 30, 40, (0.9, 0.94, 0.98), BG, 3, 2)
        _L(ctx, [(0, G + 40), (1080, G + 40)], 5)
    elif place == "stage":
        ctx.move_to(540, 300); ctx.line_to(230, G); ctx.line_to(850, G); ctx.close_path()
        ctx.set_source_rgba(1, 0.85, 0.3, 0.13); ctx.fill()
        _R(ctx, -20, 380, 170, G - 380, (0.93, 0.85, 0.85), BG, 6, 0); _R(ctx, 930, 380, 170, G - 380, (0.93, 0.85, 0.85), BG, 6, 0)
        _R(ctx, 0, 360, 1080, 50, (0.93, 0.85, 0.85), BG, 6, 0)
        _R(ctx, 0, G - 10, 1080, 40, (0.95, 0.92, 0.88), BG, 5, 0)
    elif place == "garage":
        _R(ctx, 120, 480, 840, 420, (0.96, 0.96, 0.95)); 
        for yy in range(530, 900, 60):
            _L(ctx, [(120, yy), (960, yy)], 4)
        for bx, by in ((80, G - 120), (190, G - 120), (130, G - 230)):
            _R(ctx, bx, by, 105, 105, (0.95, 0.9, 0.82), BG, 5, 4)
        text(ctx, "GARAGE", 540, 450, 44, BG)
    elif place == "factory":
        for fx in (60, 380, 700):
            _L(ctx, [(fx, G), (fx, 700), (fx + 110, 620), (fx + 110, 700), (fx + 220, 620), (fx + 220, 700), (fx + 320, 700), (fx + 320, G)], 6)
        _R(ctx, 860, 380, 70, 320, BGF, BG, 6, 2)
        for k in range(3):
            o = (t * 40 + k * 60) % 180
            ctx.arc(895 + k * 12, 360 - o, 26 + o * 0.15, 0, 2 * math.pi); stroke(ctx, BG, 5)
    elif place == "store":
        _R(ctx, 60, 470, 960, 90, (0.88, 0.96, 0.9), BG, 6, 6); text(ctx, "SHOP", 540, 515, 52, BG)
        for sy in (650, 800, 950):
            _L(ctx, [(80, sy), (440, sy)], 6)
            for k in range(5):
                _R(ctx, 95 + k * 68, sy - 70, 50, 66, BGF, BG, 4, 4)
        _R(ctx, 640, G - 260, 380, 260, BGF, BG, 6, 4)
    elif place == "market":
        _R(ctx, 120, 420, 840, 480, (0.97, 0.98, 0.97))
        pts = [(160 + i * 50, 700 + math.sin(i * 0.9 + t * 1.5) * 60 - i * 9) for i in range(16)]
        _L(ctx, pts, 8, GREEN)
        text(ctx, "STOCKS", 540, 470, 44, BG)
        _L(ctx, [(540, 900), (540, 980)], 6)
    elif place == "courtroom":
        _R(ctx, 330, 560, 420, 300, (0.93, 0.9, 0.85))
        text(ctx, "COURT", 540, 620, 46, BG)
        _L(ctx, [(540, 680), (540, 820)], 6); _L(ctx, [(460, 700), (620, 700)], 6)
        for cx in (100, 980):
            _R(ctx, cx - 30, 500, 60, G - 500, BGF, BG, 6, 4)


def _furniture(ctx, pose, x, hip_y, d, s):
    """Chair under a sitting figure; a desk in front when typing."""
    if pose in ("sit", "type"):
        sx = x - 30 * d * s
        _R(ctx, sx - 90 * s, hip_y + 5, 180 * s, 26 * s, (0.92, 0.86, 0.78), INK, 7, 6)          # seat
        _L(ctx, [(sx - 80 * d * s, hip_y + 5), (sx - 80 * d * s, hip_y - 230 * s)], 9, INK)    # back
        _L(ctx, [(sx - 70 * s, hip_y + 30 * s), (sx - 70 * s, GROUND)], 8, INK)
        _L(ctx, [(sx + 70 * s, hip_y + 30 * s), (sx + 70 * s, GROUND)], 8, INK)
    if pose == "type":
        dx = x + 250 * d * s
        top = hip_y - 40 * s
        _R(ctx, dx - 150 * s, top, 300 * s, 24 * s, (0.92, 0.86, 0.78), INK, 7, 4)
        _L(ctx, [(dx - 125 * s, top + 24 * s), (dx - 125 * s, GROUND)], 8, INK)
        _L(ctx, [(dx + 125 * s, top + 24 * s), (dx + 125 * s, GROUND)], 8, INK)
        lx = dx - 20 * d * s
        _R(ctx, lx - 90 * s, top - 6 * s, 180 * s, 12 * s, (0.85, 0.85, 0.85), INK, 6, 3)        # keyboard
        ctx.save(); ctx.translate(lx + 70 * d * s, top - 6 * s); ctx.rotate(-0.25 * d)
        _R(ctx, -10 * s if d > 0 else -110 * s, -120 * s, 120 * s, 120 * s, (0.9, 0.97, 0.92), INK, 7, 6)
        ctx.restore()


def _A(**k):
    a = dict(legs=[(-10, 0), (10, 0)], arms=[(-25, -5), (25, 5)], dy=0.0, lean=0.0, tilt=0.0,
             dx=0.0, rot=0.0, fx=(), mood=None)
    a.update(k)
    return a


def _ease(t, dur):
    return ease_out(min(max(t / dur, 0.0), 1.0))


def action(name: str, t: float, d: int, s: float) -> dict:
    """~45 base actions. Angles: 0 = straight down, + = toward facing side (front arm uses d)."""
    S = math.sin
    if name == "walk":
        sw = S(t * 7) * 28
        return _A(legs=[(sw, sw * 0.3), (-sw, -sw * 0.3)],
                  arms=[(-sw * 0.8, -sw * 0.4 - 10), (sw * 0.8, sw * 0.4 + 10)],
                  dx=(-160 + _ease(t, 2.2) * 160) * d * s)
    if name == "run":
        sw = S(t * 12) * 45
        return _A(legs=[(sw, sw * 0.9 + 20), (-sw, -sw * 0.9 + 20)], arms=[(-sw - 10, -90), (sw + 10, 90)],
                  lean=10 * d, dx=(-260 + _ease(t, 1.4) * 260) * d * s, fx=("speed",))
    if name == "point":
        return _A(arms=[(-15, -5), (95 * d, (95 + S(t * 4) * 6) * d)])
    if name == "cheer":
        wv = S(t * 9) * 18
        return _A(arms=[(-125 + wv, -145 + wv), (125 - wv, 145 - wv)], dy=-abs(S(t * 5)) * 18 * s, fx=("sparkle",))
    if name == "sad":
        return _A(arms=[(-8, 0), (8, 0)], tilt=22 * s, lean=6 * d, fx=("tear",))
    if name == "think":
        return _A(arms=[(-40, 40), (35 * d, 165 * d)], fx=("question",))
    if name == "shock":
        j = S(t * 30) * 3
        return _A(arms=[(-130 + j, -100), (130 - j, 100)], legs=[(-22, 0), (22, 0)], fx=("shock",))
    if name == "sit":
        return _A(dy=140 * s, legs=[(88 * d, 0), (92 * d, 6 * d)], arms=[(-35, -20), (35 * d, 60 * d)])
    if name == "hold":
        return _A(arms=[(70 * d, 120 * d), (85 * d, 125 * d)])
    if name == "present":
        return _A(arms=[(-15, -5), (115 * d, (128 + S(t * 4) * 8) * d)])
    if name == "angry":
        return _A(arms=[(-60, 60), (60, -60)], legs=[(-18, 0), (18, 0)], fx=("steam",))
    if name == "wave":
        w = S(t * 10) * 25
        return _A(arms=[(-15, -5), (150 * d, (170 + w) * d)])
    if name == "clap":
        k = abs(S(t * 9))
        return _A(arms=[(-(60 + 25 * k), -100), ((60 + 25 * k) * d, 100 * d)], fx=("sparkle",))
    if name == "facepalm":
        return _A(arms=[(-10, 0), (40 * d, 175 * d)], tilt=10 * s)
    if name == "shrug":
        k = abs(S(t * 3))
        return _A(arms=[(-45 - 10 * k, -140), (45 + 10 * k, 140)], tilt=-6 * s * k, dy=-k * 8)
    if name == "count_money":
        f = S(t * 14) * 10
        return _A(arms=[(55 * d, (110 + f) * d), (70 * d, 125 * d)], tilt=8 * s, fx=("cash_hand",))
    if name == "throw_money":
        k = (t * 1.6) % 1
        return _A(arms=[(-30, -10), ((40 + 140 * k) * d, (60 + 120 * k) * d)], fx=("bills",))
    if name == "dig":
        k = S(t * 4)
        return _A(arms=[((60 + 30 * k) * d, (100 + 40 * k) * d), ((50 + 30 * k) * d, (80 + 40 * k) * d)],
                  lean=(12 + 8 * k) * d, fx=("shovel",))
    if name == "carry":
        return _A(arms=[(-150, -175), (150, 175)], dy=S(t * 7) * 6, fx=("box_up",),
                  legs=[(S(t * 7) * 15, 0), (-S(t * 7) * 15, 0)])
    if name == "push":
        return _A(arms=[(80 * d, 95 * d), (85 * d, 100 * d)], lean=22 * d,
                  legs=[(-30 * d, -10 * d), (5 * d, 0)], fx=("box_front",))
    if name == "kneel":
        return _A(dy=120 * s, legs=[(70 * d, 0), (-20 * d, -85 * d)], arms=[(-10, 0), (15 * d, 0)], tilt=18 * s)
    if name == "fall":
        return _A(rot=88 * _ease(t, 0.7) * d, arms=[(-160, -175), (160, 175)], legs=[(-12, -5), (12, 5)],
                  fx=("sweat",) if t > 0.6 else ())
    if name == "jump":
        k = abs(S(t * 4.5))
        return _A(dy=-k * 120 * s, legs=[(-20 - 20 * k, 30 * k), (20 + 20 * k, -30 * k)],
                  arms=[(-140, -150), (140, 150)])
    if name == "dance":
        k = S(t * 8)
        return _A(arms=[(-100 + 40 * k, -150), (60 + 40 * k, 20)], legs=[(-15 + 20 * k, 0), (25 + 10 * k, 30 * k)],
                  lean=8 * k, dy=-abs(k) * 15, fx=("notes",))
    if name == "type":
        k = abs(S(t * 16)) * 8
        return _A(dy=140 * s, legs=[(88 * d, 0), (92 * d, 6 * d)],
                  arms=[(70 * d, (95 + k) * d), (75 * d, (90 - k) * d)])
    if name == "phone":
        return _A(arms=[(-15, -5), (30 * d, 170 * d)], tilt=6 * s * S(t * 2), fx=("phone",))
    if name == "sign":
        return _A(arms=[(60 * d, 100 * d), (55 * d, (95 + S(t * 12) * 12) * d)], tilt=14 * s, fx=("paper",))
    if name == "handshake":
        k = S(t * 9) * 10
        return _A(arms=[(-15, -5), (70 * d, (95 + k) * d)], fx=("deal",))
    if name == "high_five":
        return _A(arms=[(-15, -5), (150 * d, 160 * d)], dy=-abs(S(t * 3)) * 10, fx=("sparkle",))
    if name == "cry":
        return _A(arms=[(35 * d, 165 * d), (-35 * d, -165 * d)], tilt=16 * s, dy=S(t * 9) * 3, fx=("tear", "tear2"))
    if name == "laugh":
        k = S(t * 14)
        return _A(arms=[(-20, 70), (20, -70)], lean=-10 * d + k * 2, tilt=-10 * s, fx=("haha",), mood="happy")
    if name == "explain":
        k = S(t * 5)
        return _A(arms=[(-(80 + 20 * k), -120), ((80 - 20 * k) * d, (120 + 15 * k) * d)])
    if name == "bow":
        k = _ease(t, 0.6)
        return _A(lean=40 * k * d, arms=[(10 * d, 0), (20 * d, 10 * d)])
    if name == "salute":
        return _A(arms=[(-10, 0), (110 * d, 200 * d)], legs=[(-4, 0), (4, 0)])
    if name == "read":
        return _A(arms=[(75 * d, 140 * d), (85 * d, 150 * d)], tilt=8 * s, fx=("newspaper",))
    if name == "lift":
        k = abs(S(t * 3))
        return _A(arms=[(-150 + 30 * k, -180), (150 - 30 * k, 180)], legs=[(-24, 0), (24, 0)], fx=("bag_up",))
    if name == "shake_fist":
        k = S(t * 14) * 10
        return _A(arms=[(-20, -10), (140 * d, (150 + k) * d)], fx=("steam",))
    if name == "panic":
        j = S(t * 25) * 4
        return _A(arms=[(-150 + j, 150), (150 - j, -150)], dx=S(t * 6) * 40, fx=("sweat",), mood="worried")
    if name == "sneak":
        k = S(t * 5) * 18
        return _A(dy=60 * s, lean=18 * d, legs=[(k, 40), (-k, 40)], arms=[(60 * d, 140 * d), (30 * d, 110 * d)],
                  dx=(-120 + _ease(t, 2.5) * 120) * d * s)
    if name == "tired":
        return _A(lean=10 * d, tilt=26 * s, arms=[(-4, 0), (4, 0)], dy=S(t * 1.5) * 4, fx=("zzz",))
    if name == "give":
        k = _ease(t, 0.6)
        return _A(arms=[(-15, -5), ((20 + 60 * k) * d, (30 + 70 * k) * d)], fx=("coin_hand",))
    if name == "climb":
        k = S(t * 5)
        return _A(arms=[(-150 + 20 * k, -170), (150 + 20 * k, 170)], legs=[(-25 + 25 * k, 30), (25 + 25 * k, -30)],
                  dy=-(t * 40 % 120) * s, fx=("ladder",))
    if name == "confident":
        return _A(arms=[(70 * d, -60 * d), (-70 * d, 60 * d)], legs=[(-16, 0), (16, 0)], tilt=-6 * s,
                  mood="happy", fx=("shine",))
    if name == "beg":
        return _A(dy=120 * s, legs=[(70 * d, 0), (-20 * d, -85 * d)], arms=[(130 * d, 150 * d), (120 * d, 160 * d)],
                  mood="worried")
    if name == "lie_down":
        return _A(rot=90 * d, arms=[(-20, -5), (20, 5)], fx=("zzz",))
    if name == "fly_money":  # rich and happy, money raining
        return _A(arms=[(-125, -145), (125, 145)], dy=-abs(S(t * 4)) * 10, fx=("rain_money",), mood="happy")
    return _A(arms=[(-25 + S(t * 2) * 3, -5), (25 - S(t * 2) * 3, 5)])  # stand / unknown


def _fx(ctx, name, hx, hy, hands, t, d, s, x):
    k = pop(t, 0.15)
    if k <= 0:
        return
    if name == "question":
        ctx.save(); ctx.translate(hx + 95 * d * s, hy - 110 * s); ctx.scale(k, k)
        text(ctx, "?", 0, 0, 110 * s, DARK_GREEN); ctx.restore()
    elif name == "shock":
        for i in range(3):
            a = math.radians(-60 + i * 60)
            ctx.move_to(hx + math.sin(a) * 76 * s, hy - math.cos(a) * 76 * s)
            ctx.line_to(hx + math.sin(a) * 110 * s, hy - math.cos(a) * 110 * s)
            stroke(ctx, INK, 7)
    elif name in ("tear", "tear2"):
        side = 1 if name == "tear" else -1
        ctx.arc(hx + 30 * d * s * side, hy + 20 * s + (t * 60 % 50), 7 * s, 0, 2 * math.pi)
        ctx.set_source_rgb(0.35, 0.6, 0.95); ctx.fill()
    elif name == "sweat":
        for i in range(2):
            yy = hy - 30 * s + ((t * 80 + i * 30) % 60)
            ctx.arc(hx + (62 + i * 14) * s * (1 if i else -1), yy, 8 * s, 0, 2 * math.pi)
            ctx.set_source_rgb(0.35, 0.6, 0.95); ctx.fill()
    elif name == "steam":
        for i in (-1, 1):
            o = (t * 50) % 30
            ctx.arc(hx + i * 50 * s, hy - 80 * s - o, 12 * s, 0, 2 * math.pi)
            stroke(ctx, GREY, 5)
    elif name == "sparkle":
        for i in range(4):
            a = t * 2 + i * 1.57
            px, py = hx + math.cos(a) * 120 * s, hy + math.sin(a) * 90 * s
            r = 14 * s * (0.6 + 0.4 * abs(math.sin(t * 6 + i)))
            ctx.move_to(px - r, py); ctx.line_to(px + r, py); ctx.move_to(px, py - r); ctx.line_to(px, py + r)
            stroke(ctx, GREEN, 5)
    elif name == "shine":
        for i in range(5):
            a = math.radians(-150 + i * 30)
            ctx.move_to(hx + math.cos(a) * 80 * s, hy + math.sin(a) * 80 * s)
            ctx.line_to(hx + math.cos(a) * (100 + 8 * math.sin(t * 6)) * s, hy + math.sin(a) * (100 + 8 * math.sin(t * 6)) * s)
            stroke(ctx, (1, 0.78, 0.15), 6)
    elif name == "speed":
        for i in range(3):
            yy = hy + (120 + i * 70) * s
            ctx.move_to(x - (90 + i * 20) * d * s, yy); ctx.line_to(x - (190 + i * 20) * d * s, yy)
            stroke(ctx, GREY, 6)
    elif name == "zzz":
        o = (t * 30) % 60
        text(ctx, "z", hx + 70 * d * s, hy - 60 * s - o, 50 * s, GREY)
        text(ctx, "Z", hx + 110 * d * s, hy - 110 * s - o, 70 * s, GREY)
    elif name == "haha":
        text(ctx, "HA HA", hx + 170 * d * s, hy + 10 * s + math.sin(t * 14) * 6, 56 * s, DARK_GREEN)
    elif name == "notes":
        for i in range(2):
            o = (t * 60 + i * 40) % 80
            nx, ny = hx + (90 + i * 50) * d * s, hy - 40 * s - o
            ctx.arc(nx, ny, 12 * s, 0, 2 * math.pi); ctx.set_source_rgb(*DARK_GREEN); ctx.fill()
            ctx.move_to(nx + 11 * s, ny); ctx.line_to(nx + 11 * s, ny - 45 * s); ctx.line_to(nx + 30 * s, ny - 35 * s)
            stroke(ctx, DARK_GREEN, 5)
    elif name == "deal":
        hx2, hy2 = hands[1]
        ctx.arc(hx2, hy2, 16 * s, 0, 2 * math.pi); fill_stroke(ctx, (1, 1, 1), INK, 6)
    elif name == "impact":
        for i in range(6):
            a = math.radians(i * 30 + 180)
            gx = x + 230 * d * s
            ctx.move_to(gx + math.cos(a) * 40, GROUND - 10 + math.sin(a) * 40)
            ctx.line_to(gx + math.cos(a) * 80, GROUND - 10 + math.sin(a) * 80)
            stroke(ctx, INK, 6)
    else:  # hand-held props drawn at the front hand
        px, py = hands[1]
        ctx.save(); ctx.translate(px, py); ctx.scale(k * s, k * s)
        if name in ("cash_hand", "bills", "coin_hand"):
            n = 1 if name != "bills" else 4
            for i in range(n):
                fly = ((t * 1.6 + i * 0.25) % 1) * 260 if name == "bills" else 0
                ctx.save(); ctx.translate(fly * d, -fly * 0.8 + fly * fly / 500); ctx.rotate(0.3 * i + fly / 200)
                if name == "coin_hand":
                    ctx.arc(0, -30, 26, 0, 2 * math.pi); fill_stroke(ctx, (1, 0.82, 0.2), INK, 6)
                else:
                    rrect(ctx, -45, -25, 90, 50, 6); fill_stroke(ctx, GREEN, INK, 6)
                    text(ctx, "$", 0, 0, 34, INK)
                ctx.restore()
        elif name == "shovel":
            ctx.move_to(0, 0); ctx.line_to(60 * d, 140); stroke(ctx, INK, 9)
            ctx.move_to(40 * d, 140); ctx.line_to(80 * d, 140); ctx.line_to(60 * d, 185); ctx.close_path()
            fill_stroke(ctx, GREY, INK, 6)
        elif name in ("box_up", "box_front"):
            rrect(ctx, -70, -110 if name == "box_up" else -60, 140, 110, 8); fill_stroke(ctx, (0.85, 0.7, 0.5), INK, 7)
            text(ctx, "$", 0, -55 if name == "box_up" else -5, 60, INK)
        elif name == "laptop":
            rrect(ctx, -10 * d - 60, -70, 120, 75, 8); fill_stroke(ctx, (0.9, 0.95, 0.92), INK, 7)
        elif name == "phone":
            rrect(ctx, -18, -45, 36, 70, 8); fill_stroke(ctx, INK, INK, 4)
        elif name == "paper":
            rrect(ctx, -10, -10, 110 * d, 80, 4); fill_stroke(ctx, (1, 1, 1), INK, 5)
            for i in range(3):
                ctx.move_to(10 * d, 10 + i * 20); ctx.line_to(80 * d, 10 + i * 20); stroke(ctx, GREY, 4)
        elif name == "newspaper":
            rrect(ctx, -80, -100, 160, 120, 4); fill_stroke(ctx, (1, 1, 1), INK, 6)
            text(ctx, "NEWS", 0, -70, 34, INK)
            for i in range(3):
                ctx.move_to(-60, -40 + i * 18); ctx.line_to(60, -40 + i * 18); stroke(ctx, GREY, 4)
        elif name == "bag_up":
            ctx.translate(-px + (hands[0][0] + px) / 2, -40)
            ctx.arc(0, 0, 55, 0, 2 * math.pi); fill_stroke(ctx, (0.85, 0.7, 0.4), INK, 7); text(ctx, "$", 0, 0, 56, INK)
        elif name == "ladder":
            for sx in (-60, 60):
                ctx.move_to(sx, -400); ctx.line_to(sx, 600); stroke(ctx, (0.6, 0.45, 0.3), 9)
            for i in range(-6, 10):
                ctx.move_to(-60, i * 70); ctx.line_to(60, i * 70); stroke(ctx, (0.6, 0.45, 0.3), 7)
        elif name == "rain_money":
            ctx.restore(); ctx.save()
            for i in range(9):
                bx = x - 400 + (i * 97) % 800
                by = ((t * 260 + i * 140) % 1300) - 100
                ctx.save(); ctx.translate(bx, by); ctx.rotate(math.sin(t * 3 + i))
                rrect(ctx, -40, -22, 80, 44, 6); fill_stroke(ctx, GREEN, INK, 5); ctx.restore()
        ctx.restore()


def figure(ctx, x, t, pose="stand", mood="neutral", label="", s=1.0, face_right=True):
    """Draws one stick figure acting out `pose` on the ground at x. Returns hand positions."""
    d = 1 if face_right else -1
    if pose in ("fall", "lie_down"):
        s *= 0.8  # a lying body is long - keep it inside the frame
    a = action(pose, t, d, s)
    mood = a["mood"] or mood
    head_r = 58 * s
    leg, thigh = 150 * s, 150 * s
    body = 250 * s
    arm1, arm2 = 115 * s, 110 * s
    bob = math.sin(t * 3.2) * 4 * s
    x = x + a["dx"]
    hip_y = GROUND - (leg + thigh) * 0.97 + bob + a["dy"]
    lean, head_tilt = a["lean"], a["tilt"]
    # soft shadow keeps the figure grounded
    ctx.save(); ctx.translate(x, GROUND + 4); ctx.scale(1, 0.18)
    ctx.arc(0, 0, 85 * s, 0, 2 * math.pi); ctx.restore()
    ctx.set_source_rgba(0, 0, 0, 0.08); ctx.fill()
    ctx.save()
    if a["rot"]:
        k = abs(a["rot"]) / 90
        piv = GROUND - 330 * s  # rotate around the middle of the body, then drop it onto the ground
        ctx.translate(x, piv + k * 255 * s); ctx.rotate(math.radians(a["rot"])); ctx.translate(-x, -piv)
    _furniture(ctx, pose, x, hip_y, d, s)
    neck_x = x + math.sin(math.radians(lean)) * body
    neck_y = hip_y - math.cos(math.radians(lean)) * body
    for a1, a2 in a["legs"]:
        _limb(ctx, x, hip_y, a1, thigh, a2, leg)
    ctx.move_to(x, hip_y); ctx.line_to(neck_x, neck_y); stroke(ctx)
    sh_x, sh_y = neck_x + (x - neck_x) * 0.15, neck_y + (hip_y - neck_y) * 0.12
    hands = [_limb(ctx, sh_x, sh_y, a1, arm1, a2, arm2) for a1, a2 in a["arms"]]
    hx = neck_x + math.sin(math.radians(lean)) * head_r + head_tilt * 0.4 * d
    hy = neck_y - math.cos(math.radians(lean)) * head_r + head_tilt * 0.6
    ctx.arc(hx, hy, head_r, 0, 2 * math.pi)
    ctx.set_source_rgb(1, 1, 1); ctx.fill_preserve(); stroke(ctx)
    _face(ctx, hx, hy, head_r, mood, d, t)
    for f in a["fx"]:
        _fx(ctx, f, hx, hy, hands, t, d, s, x)
    ctx.restore()
    if label:
        text(ctx, label.upper(), hx, hy - head_r - 55 * s, 54 * s, INK, outline=(1, 1, 1))
        lw = min(len(label), 14) * 15 * s
        ctx.move_to(hx - lw, hy - head_r - 22 * s); ctx.line_to(hx + lw, hy - head_r - 22 * s)
        stroke(ctx, GREEN, 8)
    return hands


def _face(ctx, x, y, r, mood, d, t):
    ex = r * 0.32
    blink = (t % 3.3) < 0.12
    for sx in (-1, 1):
        if blink:
            ctx.move_to(x + sx * ex - 7 + d * 6, y - r * 0.1)
            ctx.line_to(x + sx * ex + 7 + d * 6, y - r * 0.1)
            stroke(ctx, INK, 5)
        else:
            ctx.arc(x + sx * ex + d * 6, y - r * 0.1, 7 if mood != "shocked" else 9, 0, 2 * math.pi)
            ctx.set_source_rgb(*INK)
            ctx.fill()
    my = y + r * 0.35
    if mood == "happy":
        ctx.arc(x + d * 6, my - 12, r * 0.35, math.radians(25), math.radians(155))
        stroke(ctx, INK, 6)
    elif mood in ("sad", "worried"):
        ctx.arc(x + d * 6, my + 16, r * 0.3, math.radians(205), math.radians(335))
        stroke(ctx, INK, 6)
    elif mood == "shocked":
        ctx.arc(x + d * 6, my, r * 0.16, 0, 2 * math.pi)
        stroke(ctx, INK, 6)
    else:
        ctx.move_to(x - r * 0.2 + d * 6, my)
        ctx.line_to(x + r * 0.2 + d * 6, my)
        stroke(ctx, INK, 6)
    if mood in ("angry", "worried"):
        tilt = 1 if mood == "angry" else -1
        for sx in (-1, 1):
            ctx.move_to(x + sx * ex - 12 + d * 6, y - r * 0.38 - tilt * sx * 6)
            ctx.line_to(x + sx * ex + 12 + d * 6, y - r * 0.38 + tilt * sx * 6)
            stroke(ctx, INK, 5)


# ---------------------------------------------------------------- props
def prop(ctx, name, cx, cy, t, size=1.0):
    k = pop(t, 0.15)
    if k <= 0 or name == "none":
        return
    ctx.save()
    ctx.translate(cx, cy + math.sin(t * 2.5) * 6)
    ctx.scale(k * size, k * size)
    grow = ease_out((t - 0.3) / 0.9)
    f = _PROPS.get(name)
    if f:
        f(ctx, t, grow)
    ctx.restore()


def _dollar(ctx, x, y, s, color=INK):
    text(ctx, "$", x, y, s, color)


def _money_bag(ctx, t, g):
    ctx.move_to(-35, -120)
    ctx.curve_to(-150, -40, -160, 130, 0, 135)
    ctx.curve_to(160, 130, 150, -40, 35, -120)
    ctx.close_path()
    fill_stroke(ctx)
    ctx.move_to(-45, -140)
    ctx.line_to(45, -140)
    ctx.line_to(30, -118)
    ctx.line_to(-30, -118)
    ctx.close_path()
    fill_stroke(ctx)
    _dollar(ctx, 0, 30, 130)


def _coins(ctx, t, g):
    n = 1 + int(g * 5)
    for i in range(n):
        ctx.save()
        ctx.scale(1, 0.35)
        ctx.arc(0, (100 - i * 34) / 0.35, 90, 0, 2 * math.pi)
        ctx.restore()
        fill_stroke(ctx)
    for i in range(3):  # falling coins
        y = ((t * 380 + i * 160) % 480) - 380
        ctx.arc(-120 + i * 120, y, 32, 0, 2 * math.pi)
        fill_stroke(ctx, width=6)


def _cash(ctx, t, g):
    for i in range(4):
        ctx.save()
        ctx.rotate(math.radians(-18 + i * 12 * g))
        rrect(ctx, -120, -70, 240, 130, 14)
        fill_stroke(ctx)
        _dollar(ctx, 0, -5, 80)
        ctx.restore()


def _chart(ctx, t, g, up=True):
    ctx.move_to(-170, -170)
    ctx.line_to(-170, 150)
    ctx.line_to(190, 150)
    stroke(ctx)
    hs = [70, 130, 190, 270] if up else [270, 190, 120, 50]
    for i, h in enumerate(hs):
        hh = h * min(max(g * 1.4 - i * 0.12, 0), 1)
        rrect(ctx, -140 + i * 80, 150 - hh, 56, max(hh, 2), 6)
        fill_stroke(ctx, GREEN if up else (0.94, 0.33, 0.31))
    if g > 0.6:
        ctx.move_to(-150, 60 if up else -110)
        ctx.line_to(170, -170 if up else 110)
        stroke(ctx, INK, 10)
        ang = math.atan2(-230 if up else 220, 320)
        hx, hy = 170, -170 if up else 110
        for s in (-1, 1):
            ctx.move_to(hx, hy)
            ctx.line_to(hx - 45 * math.cos(ang + s * 0.5), hy - 45 * math.sin(ang + s * 0.5))
            stroke(ctx, INK, 10)


def _arrow(ctx, t, g, up=True):
    L = 320 * max(g, 0.05)
    s = -1 if up else 1
    ctx.save()
    ctx.translate(0, 160 * -s)
    ctx.move_to(-45, 0)
    ctx.line_to(-45, s * L)
    ctx.line_to(-100, s * L)
    ctx.line_to(0, s * (L + 110))
    ctx.line_to(100, s * L)
    ctx.line_to(45, s * L)
    ctx.line_to(45, 0)
    ctx.close_path()
    fill_stroke(ctx, GREEN if up else (0.94, 0.33, 0.31))
    ctx.restore()


def _laptop(ctx, t, g):
    rrect(ctx, -150, -150, 300, 190, 12)
    fill_stroke(ctx, (1, 1, 1))
    rrect(ctx, -125, -128, 250, 145, 6)
    fill_stroke(ctx, GREEN, INK, 5)
    ctx.move_to(-200, 60)
    ctx.line_to(200, 60)
    ctx.line_to(170, 40)
    ctx.line_to(-170, 40)
    ctx.close_path()
    fill_stroke(ctx, (1, 1, 1))


def _phone(ctx, t, g):
    rrect(ctx, -75, -150, 150, 300, 22)
    fill_stroke(ctx, (1, 1, 1))
    rrect(ctx, -58, -120, 116, 220, 8)
    fill_stroke(ctx, GREEN, INK, 5)
    if (t * 2) % 1 < 0.5:
        ctx.arc(55, -150, 22, 0, 2 * math.pi)
        fill_stroke(ctx, RED, INK, 4)


def _house(ctx, t, g):
    rrect(ctx, -140, -40, 280, 190, 6)
    fill_stroke(ctx, (1, 1, 1))
    ctx.move_to(-175, -30)
    ctx.line_to(0, -180)
    ctx.line_to(175, -30)
    ctx.close_path()
    fill_stroke(ctx)
    rrect(ctx, -30, 50, 60, 100, 4)
    fill_stroke(ctx)


def _car(ctx, t, g):
    ctx.move_to(-200, 40)
    ctx.line_to(-180, -20)
    ctx.line_to(-90, -30)
    ctx.line_to(-40, -100)
    ctx.line_to(80, -100)
    ctx.line_to(140, -30)
    ctx.line_to(200, -15)
    ctx.line_to(205, 40)
    ctx.close_path()
    fill_stroke(ctx)
    for wx in (-110, 120):
        ctx.arc(wx, 45, 42, 0, 2 * math.pi)
        fill_stroke(ctx, (1, 1, 1))
        ctx.arc(wx, 45, 14, 0, 2 * math.pi)
        ctx.set_source_rgb(*INK)
        ctx.fill()


def _building(ctx, t, g):
    h = 380 * max(g, 0.1)
    rrect(ctx, -110, 160 - h, 220, h, 6)
    fill_stroke(ctx, (1, 1, 1))
    rows = int(h // 70)
    for r in range(rows):
        for c in range(3):
            rrect(ctx, -80 + c * 60, 160 - h + 25 + r * 70, 38, 40, 4)
            fill_stroke(ctx, GREEN, INK, 4)


def _shop(ctx, t, g):
    rrect(ctx, -160, -40, 320, 200, 6)
    fill_stroke(ctx, (1, 1, 1))
    for i in range(5):
        ctx.move_to(-170 + i * 68, -40)
        ctx.line_to(-136 + i * 68, -120)
        ctx.line_to(-102 + i * 68, -40)
        ctx.close_path()
        fill_stroke(ctx, GREEN if i % 2 == 0 else (1, 1, 1), INK, 6)
    rrect(ctx, -40, 40, 80, 120, 4)
    fill_stroke(ctx)


def _piggy(ctx, t, g):
    ctx.save()
    ctx.scale(1.25, 1)
    ctx.arc(0, 0, 120, 0, 2 * math.pi)
    ctx.restore()
    fill_stroke(ctx)
    ctx.arc(150, -10, 35, 0, 2 * math.pi)
    fill_stroke(ctx)
    for lx in (-80, 70):
        rrect(ctx, lx - 18, 95, 36, 60, 8)
        fill_stroke(ctx)
    ctx.move_to(-60, -100)
    ctx.line_to(-30, -150)
    ctx.line_to(0, -110)
    fill_stroke(ctx)
    rrect(ctx, -30, -125, 60, 12, 4)
    ctx.set_source_rgb(*INK)
    ctx.fill()
    y = -260 + ease_out((t % 1.5) / 0.8) * 140
    ctx.arc(0, y, 30, 0, 2 * math.pi)
    fill_stroke(ctx, (1, 0.82, 0.2), INK, 6)


def _briefcase(ctx, t, g):
    rrect(ctx, -170, -90, 340, 230, 18)
    fill_stroke(ctx)
    rrect(ctx, -60, -140, 120, 60, 14)
    stroke(ctx)
    ctx.move_to(-170, 0)
    ctx.line_to(170, 0)
    stroke(ctx, INK, 8)


def _bulb(ctx, t, g):
    a = (math.sin(t * 6) + 1) / 2
    for i in range(8):
        ang = i * math.pi / 4
        ctx.move_to(math.cos(ang) * 150, -40 + math.sin(ang) * 150)
        ctx.line_to(math.cos(ang) * (175 + a * 25), -40 + math.sin(ang) * (175 + a * 25))
        stroke(ctx, DARK_GREEN, 10)
    ctx.arc(0, -40, 110, 0, 2 * math.pi)
    fill_stroke(ctx, (1, 0.9, 0.3))
    rrect(ctx, -50, 70, 100, 70, 10)
    fill_stroke(ctx, (1, 1, 1))


def _clock(ctx, t, g):
    ctx.arc(0, 0, 150, 0, 2 * math.pi)
    fill_stroke(ctx, (1, 1, 1))
    ctx.arc(0, 0, 150, 0, 2 * math.pi)
    stroke(ctx, GREEN, 18)
    for ang, ln, w in ((t * 3, 110, 10), (t * 0.4, 70, 14)):
        ctx.move_to(0, 0)
        ctx.line_to(math.sin(ang) * ln, -math.cos(ang) * ln)
        stroke(ctx, INK, w)


def _trophy(ctx, t, g):
    ctx.move_to(-110, -150)
    ctx.line_to(110, -150)
    ctx.curve_to(110, 20, -110, 20, -110, -150)
    fill_stroke(ctx, (1, 0.82, 0.2))
    rrect(ctx, -20, 0, 40, 80, 4)
    fill_stroke(ctx, (1, 0.82, 0.2))
    rrect(ctx, -90, 80, 180, 50, 8)
    fill_stroke(ctx)


def _question(ctx, t, g):
    text(ctx, "?", 0, 0, 380, DARK_GREEN, outline=INK)


def _warning(ctx, t, g):
    ctx.move_to(0, -170)
    ctx.line_to(185, 150)
    ctx.line_to(-185, 150)
    ctx.close_path()
    fill_stroke(ctx, (1, 0.82, 0.2))
    text(ctx, "!", 0, 30, 220, INK)


def _globe(ctx, t, g):
    ctx.arc(0, 0, 160, 0, 2 * math.pi)
    fill_stroke(ctx, (0.85, 0.95, 0.88))
    for k in range(3):
        w = 160 * abs(math.cos(t * 0.8 + k * 1.05))
        ctx.save()
        ctx.scale(max(w, 1) / 160, 1)
        ctx.arc(0, 0, 160, 0, 2 * math.pi)
        ctx.restore()
        stroke(ctx, DARK_GREEN, 6)
    ctx.move_to(-160, 0)
    ctx.line_to(160, 0)
    stroke(ctx, DARK_GREEN, 6)


def _rocket(ctx, t, g):
    ctx.save()
    ctx.translate(0, -g * 120)
    ctx.move_to(0, -200)
    ctx.curve_to(80, -120, 70, 60, 55, 110)
    ctx.line_to(-55, 110)
    ctx.curve_to(-70, 60, -80, -120, 0, -200)
    fill_stroke(ctx, (1, 1, 1))
    ctx.arc(0, -60, 30, 0, 2 * math.pi)
    fill_stroke(ctx, GREEN, INK, 6)
    for s in (-1, 1):
        ctx.move_to(s * 55, 40)
        ctx.line_to(s * 110, 130)
        ctx.line_to(s * 50, 110)
        fill_stroke(ctx)
    fl = 60 + math.sin(t * 20) * 20
    ctx.move_to(-35, 115)
    ctx.line_to(0, 115 + fl + 40)
    ctx.line_to(35, 115)
    fill_stroke(ctx, (1, 0.6, 0.15), INK, 5)
    ctx.restore()


def _document(ctx, t, g):
    rrect(ctx, -130, -170, 260, 340, 10)
    fill_stroke(ctx, (1, 1, 1))
    for i in range(int(1 + g * 5)):
        ctx.move_to(-90, -110 + i * 50)
        ctx.line_to(90 - (i % 2) * 40, -110 + i * 50)
        stroke(ctx, GREY, 10)
    if g > 0.8:
        ctx.move_to(-40, 120)
        ctx.curve_to(-10, 80, 20, 150, 70, 100)
        stroke(ctx, DARK_GREEN, 8)


def _crown(ctx, t, g):
    ctx.move_to(-170, 90)
    ctx.line_to(-170, -80)
    ctx.line_to(-85, 0)
    ctx.line_to(0, -130)
    ctx.line_to(85, 0)
    ctx.line_to(170, -80)
    ctx.line_to(170, 90)
    ctx.close_path()
    fill_stroke(ctx, (1, 0.82, 0.2))
    for x in (-170, 0, 170):
        ctx.arc(x, -100 if x else -150, 22, 0, 2 * math.pi)
        fill_stroke(ctx, GREEN, INK, 6)


def _lock(ctx, t, g):
    ctx.arc(0, -60, 85, math.pi, 2 * math.pi)
    stroke(ctx, INK, 26)
    rrect(ctx, -130, -60, 260, 210, 20)
    fill_stroke(ctx)
    ctx.arc(0, 30, 24, 0, 2 * math.pi)
    ctx.set_source_rgb(*INK)
    ctx.fill()


def _calendar(ctx, t, g):
    rrect(ctx, -160, -150, 320, 300, 18)
    fill_stroke(ctx, (1, 1, 1))
    rrect(ctx, -160, -150, 320, 80, 18)
    fill_stroke(ctx)
    for r in range(3):
        for c in range(4):
            rrect(ctx, -125 + c * 65, -45 + r * 62, 40, 40, 6)
            fill_stroke(ctx, GREEN if (r * 4 + c) < g * 12 else (1, 1, 1), INK, 4)


def _scale(ctx, t, g):
    tilt = math.sin(t * 2) * 0.18
    ctx.move_to(0, -120)
    ctx.line_to(0, 150)
    stroke(ctx, INK, 14)
    rrect(ctx, -80, 140, 160, 25, 8)
    fill_stroke(ctx, INK)
    ctx.save()
    ctx.translate(0, -120)
    ctx.rotate(tilt)
    ctx.move_to(-170, 0)
    ctx.line_to(170, 0)
    stroke(ctx, INK, 12)
    for s in (-1, 1):
        ctx.save()
        ctx.translate(s * 170, 0)
        ctx.rotate(-tilt)
        ctx.move_to(-60, 90)
        ctx.line_to(0, 0)
        ctx.line_to(60, 90)
        stroke(ctx, INK, 6)
        ctx.arc(0, 90, 65, 0, math.pi)
        fill_stroke(ctx, GREEN if s < 0 else (1, 1, 1))
        ctx.restore()
    ctx.restore()


def _plane(ctx, t, g):
    ctx.save()
    ctx.translate(-60 + g * 60, -g * 40)
    ctx.rotate(-0.12)
    ctx.move_to(-210, 0)
    ctx.curve_to(-210, -45, 150, -45, 210, 0)
    ctx.curve_to(150, 40, -210, 40, -210, 0)
    fill_stroke(ctx, (1, 1, 1))
    for poly in ([(-20, -10), (60, -160), (100, -160), (60, -10)], [(-20, 10), (60, 150), (100, 150), (60, 10)],
                 [(-190, -10), (-160, -90), (-130, -90), (-140, -10)]):
        ctx.move_to(*poly[0])
        for pt in poly[1:]:
            ctx.line_to(*pt)
        ctx.close_path()
        fill_stroke(ctx)
    for i in range(5):
        ctx.arc(-110 + i * 50, -5, 9, 0, 2 * math.pi)
        ctx.set_source_rgb(*INK)
        ctx.fill()
    ctx.restore()


def _factory(ctx, t, g):
    ctx.move_to(-180, 150)
    ctx.line_to(-180, -20)
    for i in range(3):
        ctx.line_to(-180 + i * 100 + 100, -80)
        ctx.line_to(-180 + i * 100 + 100, -20)
    ctx.line_to(180, 150)
    ctx.close_path()
    fill_stroke(ctx, (1, 1, 1))
    rrect(ctx, 120, -200, 50, 190, 6)
    fill_stroke(ctx)
    for i in range(3):
        r = 25 + ((t * 40 + i * 30) % 90) * 0.4
        ctx.arc(150 + i * 25, -230 - ((t * 60 + i * 40) % 120), r, 0, 2 * math.pi)
        ctx.set_source_rgba(0.6, 0.6, 0.62, 0.5)
        ctx.fill()
    for i in range(3):
        rrect(ctx, -140 + i * 90, 40, 50, 50, 4)
        fill_stroke(ctx, GREEN, INK, 5)


def _bank(ctx, t, g):
    ctx.move_to(-200, -60)
    ctx.line_to(0, -170)
    ctx.line_to(200, -60)
    ctx.close_path()
    fill_stroke(ctx)
    _dollar(ctx, 0, -95, 70)
    for i in range(4):
        rrect(ctx, -165 + i * 100, -45, 30, 170, 4)
        fill_stroke(ctx, (1, 1, 1), INK, 7)
    rrect(ctx, -210, 125, 420, 40, 6)
    fill_stroke(ctx, (1, 1, 1))
    if math.sin(t * 3) > 0.6:  # a crack appears now and then
        ctx.move_to(-20, -40)
        ctx.line_to(10, 10)
        ctx.line_to(-15, 60)
        ctx.line_to(15, 120)
        stroke(ctx, RED, 7)


def _newspaper(ctx, t, g):
    rrect(ctx, -180, -150, 360, 300, 10)
    fill_stroke(ctx, (1, 1, 1))
    rrect(ctx, -150, -125, 300, 50, 6)
    fill_stroke(ctx, INK, INK, 4)
    text(ctx, "NEWS", 0, -100, 40, (1, 1, 1))
    rrect(ctx, -150, -55, 130, 110, 6)
    fill_stroke(ctx, GREEN, INK, 5)
    for i in range(5):
        ctx.move_to(0, -45 + i * 25)
        ctx.line_to(150, -45 + i * 25)
        stroke(ctx, GREY, 8)
    for i in range(3):
        ctx.move_to(-150, 80 + i * 25)
        ctx.line_to(150 - i * 60, 80 + i * 25)
        stroke(ctx, GREY, 8)


_PROPS = {
    "bank": _bank, "newspaper": _newspaper,
    "plane": _plane, "factory": _factory,
    "money_bag": _money_bag, "coins": _coins, "cash": _cash,
    "chart_up": lambda c, t, g: _chart(c, t, g, True), "chart_down": lambda c, t, g: _chart(c, t, g, False),
    "arrow_up": lambda c, t, g: _arrow(c, t, g, True), "arrow_down": lambda c, t, g: _arrow(c, t, g, False),
    "laptop": _laptop, "phone": _phone, "house": _house, "car": _car, "building": _building,
    "shop": _shop, "piggy_bank": _piggy, "briefcase": _briefcase, "lightbulb": _bulb,
    "clock": _clock, "trophy": _trophy, "question": _question, "warning": _warning,
    "globe": _globe, "rocket": _rocket, "document": _document, "crown": _crown,
    "lock": _lock, "calendar": _calendar, "scale": _scale,
}


# ---------------------------------------------------------------- scenes
def _big_text(ctx, s, t, start=0.3):
    if not s:
        return
    s = s.upper()
    k = pop(t, start, 0.4)
    if k <= 0:
        return
    ctx.save()
    ctx.translate(W / 2, 345)
    ctx.scale(k, k)
    ctx.rotate(math.radians(-3))
    size = 170 if len(s) <= 6 else 135 if len(s) <= 9 else 105
    ctx.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(size)
    ew = ctx.text_extents(s).width
    rrect(ctx, -ew / 2 - 40, -size * 0.62, ew + 80, size * 1.24, 24)
    fill_stroke(ctx, GREEN, INK, 10)
    text(ctx, s, 0, 0, size, (1, 1, 1), outline=INK)
    ctx.restore()


def _wrap(ctx, s, size, max_w):
    ctx.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(size)
    lines, cur = [], ""
    for word in s.split():
        test = f"{cur} {word}".strip()
        if ctx.text_extents(test).width > max_w and cur:
            lines.append(cur)
            cur = word
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines[:3]


def _headline(ctx, s, t, start=0.2):
    """A news card: 'BREAKING' tag + the headline, like a news ticker screenshot."""
    k = pop(t, start, 0.4)
    if k <= 0:
        return
    s = s.upper()
    size = 56
    lines = _wrap(ctx, s, size, 820)
    h = 120 + len(lines) * size * 1.15
    ctx.save()
    ctx.translate(W / 2, 330)
    ctx.scale(k, k)
    ctx.rotate(math.radians(-1.5))
    rrect(ctx, -460, -h / 2, 920, h, 22)
    fill_stroke(ctx, (1, 1, 1), INK, 10)
    rrect(ctx, -430, -h / 2 - 34, 290, 68, 12)
    fill_stroke(ctx, RED, INK, 8)
    text(ctx, "BREAKING", -285, -h / 2, 40, (1, 1, 1))
    y = -h / 2 + 95
    for line in lines:
        text(ctx, line, -415, y, size, INK, align="left")
        y += size * 1.15
    ctx.move_to(-415, h / 2 - 28)
    ctx.line_to(-415 + 830 * ease_out((t - start - 0.3) / 1.2), h / 2 - 28)
    stroke(ctx, GREEN, 10)
    ctx.restore()


def _ground(ctx):
    ctx.move_to(70, GROUND + 4)
    ctx.line_to(W - 70, GROUND + 4)
    stroke(ctx, (0.85, 0.85, 0.87), 6)


def _brand(ctx):
    ctx.arc(70, 78, 30, 0, 2 * math.pi)
    fill_stroke(ctx, (1, 0.82, 0.2), INK, 5)
    text(ctx, "M", 70, 79, 34, INK)
    text(ctx, "MONEZIC", 115, 80, 40, (0.25, 0.25, 0.28), align="left")


def draw_scene(ctx, scene: dict, t: float, idx: int):
    if idx == 0:
        t += 0.6  # first frame already full and moving - no empty pop-in (the swipe decision happens here)
    ctx.set_source_rgb(1, 1, 1)
    ctx.paint()
    ctx.save()
    _camera(ctx, scene.get("_cam", "push"), t, scene.get("_seed", 0))
    draw_place(ctx, scene.get("_place", "none"), t)
    _ground(ctx)
    chars = [c for c in scene.get("characters", []) if c.get("pose")][:3]
    p = scene.get("prop", "none") or "none"
    has_prop = p != "none"
    n = len(chars)
    if n == 0:
        if has_prop:
            prop(ctx, p, W / 2, GROUND - 330, t, 1.25)
    elif n == 1:
        jx = (scene.get("_seed", 0) % 101 - 50)
        cx = (320 if has_prop else W / 2) + jx
        sc1 = 1.08 + (scene.get("_seed", 0) % 7) * 0.012
        fr = True if has_prop else bool(scene.get("_seed", 0) % 2)
        _enter(ctx, t, lambda: figure(ctx, cx, t, chars[0]["pose"], chars[0].get("mood", "neutral"),
                                      chars[0].get("label", ""), sc1, fr))
        if has_prop:
            prop(ctx, p, 785, GROUND - 300, t, 1.0)
    else:
        xs = [290, 790] if n == 2 else [200, 540, 880]
        sc = 1.0 if n == 2 else 0.82
        for i, c in enumerate(chars):
            face_right = xs[i] < W / 2
            _enter(ctx, t - i * 0.08, lambda c=c, x=xs[i], fr=face_right: figure(
                ctx, x, t, c["pose"], c.get("mood", "neutral"), c.get("label", ""), sc, fr))
        if has_prop:
            if n == 2:
                prop(ctx, p, W / 2, GROUND - 230, t, 0.62)
            elif not scene.get("big_text"):
                prop(ctx, p, W / 2, 470, t, 0.55)
    ctx.restore()
    if scene.get("headline"):
        _headline(ctx, scene["headline"], t, 2.7 if idx == 0 else 0.2)
    else:
        _big_text(ctx, scene.get("big_text", ""), t, 2.7 if idx == 0 else 0.3)
    _brand(ctx)


CAMS = ["push", "pull", "pan_l", "pan_r", "face", "tilt", "low", "drift"]
_SHAKY = {"shock", "fall", "panic", "angry", "shake_fist", "jump"}


def _camera(ctx, cam, t, seed):
    """Camera move for a scene. Anchored near the figures' chests."""
    e = ease_out(min(t / 3.5, 1.0))
    ax, ay = W / 2, GROUND - 330
    z, dx, dy, rot = 1.0, 0.0, 0.0, 0.0
    if cam == "push":
        z = 1.0 + 0.10 * e
    elif cam == "pull":
        z = 1.14 - 0.12 * e
    elif cam in ("pan_l", "pan_r"):
        z, dx = 1.08, (e - 0.5) * 90 * (1 if cam == "pan_l" else -1)
    elif cam == "face":
        z, ay = 1.0 + 0.32 * e, GROUND - 560
    elif cam == "tilt":
        z, rot = 1.06, (0.025 if seed % 2 else -0.025) * e
    elif cam == "low":
        z, ay, dy = 1.1, GROUND - 120, -40 * e
    elif cam == "drift":
        z, dx, dy = 1.05, math.sin(t * 0.8) * 25, math.cos(t * 0.6) * 15
    elif cam == "shake":
        k = max(0.0, 1 - t / 0.8)
        z, dx, dy = 1.06, math.sin(t * 60) * 14 * k, math.cos(t * 53) * 10 * k
    ctx.translate(ax + dx, ay + dy)
    ctx.rotate(rot)
    ctx.scale(z, z)
    ctx.translate(-ax, -ay)


_ALT = {"stand": ["explain", "point"], "present": ["explain", "point"], "point": ["present", "explain"],
        "cheer": ["jump", "clap", "fly_money"], "sad": ["cry", "kneel", "facepalm"], "think": ["shrug", "read"],
        "shock": ["panic", "facepalm"], "hold": ["count_money", "give"], "walk": ["sneak", "run"],
        "run": ["walk", "panic"], "angry": ["shake_fist", "push"], "sit": ["type", "tired"]}


def _prepare(scenes: list[dict]) -> list[dict]:
    """No two scenes in a row share the same action or camera; shaky camera on dramatic actions."""
    import zlib
    prev_pose, prev_cam, prev_place = None, None, "none"
    for i, sc in enumerate(scenes):
        seed = zlib.crc32((sc.get("text", "") + str(i)).encode())
        sc["_seed"] = seed
        chars = [c for c in sc.get("characters", []) if c.get("pose")]
        if chars and chars[0]["pose"] == prev_pose:
            alts = _ALT.get(prev_pose, ["explain", "point", "present"])
            chars[0]["pose"] = alts[seed % len(alts)]
        pose = chars[0]["pose"] if chars else None
        if pose in _SHAKY:
            cam = "shake"
        else:
            opts = [c for c in CAMS if c != prev_cam]
            cam = opts[seed % len(opts)]
        sc["_cam"] = cam
        pl = sc.get("place", "auto")
        if pl not in PLACES or pl == "auto":
            pl = _AUTO.get(pose, prev_place if i else "none")
        sc["_place"] = pl
        prev_place = pl
        prev_pose, prev_cam = pose, cam
    return scenes


def _enter(ctx, t, draw):
    k = pop(t, 0.0, 0.3)
    ctx.save()
    ctx.translate(W / 2, GROUND)
    ctx.scale(0.85 + 0.15 * k, 0.85 + 0.15 * k)
    ctx.translate(-W / 2, -GROUND)
    draw()
    ctx.restore()


def draw_end_card(ctx, t: float, handle: str):
    ctx.set_source_rgb(1, 1, 1)
    ctx.paint()
    k = max(pop(t, 0.0, 0.4), 0.01)
    ctx.save()
    ctx.translate(W / 2, 640)
    ctx.scale(k, k)
    ctx.arc(0, 0, 170, 0, 2 * math.pi)
    fill_stroke(ctx, (1, 0.82, 0.2), INK, 12)
    ctx.arc(0, 0, 140, 0, 2 * math.pi)
    stroke(ctx, INK, 6)
    text(ctx, "M", 0, -6, 190, INK)
    ctx.restore()
    if t > 0.2:
        text(ctx, "MONEZIC", W / 2, 920, 150, INK)
        text(ctx, "REAL MONEY STORIES", W / 2, 1030, 60, DARK_GREEN)
    # subscribe button gets "tapped"
    tapped = t > 1.6
    k2 = pop(t, 0.5, 0.35)
    if k2 > 0:
        ctx.save()
        ctx.translate(W / 2, 1250)
        press = 0.92 if 1.45 < t < 1.6 else 1.0
        ctx.scale(k2 * press, k2 * press)
        rrect(ctx, -300, -80, 600, 160, 80)
        fill_stroke(ctx, GREY if tapped else RED, INK, 8)
        text(ctx, "SUBSCRIBED" if tapped else "SUBSCRIBE", 45, 0, 60, (1, 1, 1))
        # bell
        ctx.save()
        ctx.translate(-215, 0)
        ctx.rotate(math.sin(t * 18) * 0.3 if tapped else 0)
        ctx.move_to(-30, 25)
        ctx.curve_to(-30, -45, 30, -45, 30, 25)
        ctx.close_path()
        ctx.set_source_rgb(1, 1, 1)
        ctx.fill()
        ctx.arc(0, 32, 9, 0, 2 * math.pi)
        ctx.fill()
        ctx.restore()
        ctx.restore()
    if 0.9 < t < 1.75:  # hand cursor
        hx = W / 2 + 140 + (1 - ease_out((t - 0.9) / 0.55)) * 260
        hy = 1300 + (1 - ease_out((t - 0.9) / 0.55)) * 260
        ctx.save()
        ctx.translate(hx, hy)
        ctx.rotate(-0.4)
        rrect(ctx, -26, -90, 52, 150, 26)
        fill_stroke(ctx, (1, 1, 1), INK, 8)
        ctx.restore()
    if t > 1.0:
        text(ctx, f"FOLLOW {handle.upper()}", W / 2, 1480, 66, INK)
        text(ctx, "NEW STORIES EVERY DAY", W / 2, 1570, 44, GREY)


# ---------------------------------------------------------------- render
def render(scenes: list[dict], times: list[tuple[float, float]], end_card: float, out: Path,
           fps: int = 30, handle: str = "@monezic") -> Path:
    """scenes[i] is shown from times[i][0] to times[i][1]; then an end card for end_card seconds."""
    scenes = _prepare([dict(sc) for sc in scenes])
    total = times[-1][1] + end_card
    frames = int(total * fps)
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra",
         "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", str(out)],
        stdin=subprocess.PIPE,
    )
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    ctx.set_antialias(cairo.ANTIALIAS_BEST)
    i = 0
    for f in range(frames):
        t = f / fps
        if t >= times[-1][1]:
            draw_end_card(ctx, t - times[-1][1], handle)
        else:
            while i < len(times) - 1 and t >= times[i][1]:
                i += 1
            draw_scene(ctx, scenes[i], t - times[i][0], i)
        surf.flush()
        proc.stdin.write(surf.get_data())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("stickman video encoding failed")
    return out
