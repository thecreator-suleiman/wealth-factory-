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

POSES = ["stand", "walk", "run", "point", "cheer", "sad", "think", "shock", "sit", "hold", "present", "angry"]
MOODS = ["happy", "sad", "neutral", "shocked", "angry", "worried"]
PROPS = ["none", "money_bag", "coins", "cash", "chart_up", "chart_down", "arrow_up", "arrow_down",
         "laptop", "phone", "house", "car", "building", "shop", "piggy_bank", "briefcase",
         "lightbulb", "clock", "trophy", "question", "warning", "globe", "rocket", "document",
         "crown", "lock", "calendar", "scale"]

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


def figure(ctx, x, t, pose="stand", mood="neutral", label="", s=1.0, face_right=True):
    """Draws one stick figure standing on the ground at x. Returns hand positions."""
    d = 1 if face_right else -1
    head_r = 58 * s
    leg, thigh = 150 * s, 150 * s
    body = 250 * s
    arm1, arm2 = 115 * s, 110 * s
    bob = math.sin(t * 3.2) * 4 * s
    sway = 0.0
    hip_y = GROUND - (leg + thigh) * 0.97 + bob
    lean = 0.0
    legs = [(-10, 0), (10, 0)]
    arms = [(-25, -5), (25, 5)]
    head_tilt = 0.0

    if pose == "walk":
        sw = math.sin(t * 7) * 28
        legs = [(sw, sw * 0.3), (-sw, -sw * 0.3)]
        arms = [(-sw * 0.8, -sw * 0.4 - 10), (sw * 0.8, sw * 0.4 + 10)]
        sway = (t % 4) * 8 * d
    elif pose == "run":
        sw = math.sin(t * 12) * 45
        legs = [(sw, sw * 0.9 + 20), (-sw, -sw * 0.9 + 20)]
        arms = [(-sw - 10, -90), (sw + 10, 90)]
        lean = 10 * d
    elif pose == "point":
        arms = [(-15, -5), (95 * d, (95 + math.sin(t * 4) * 6) * d)]
    elif pose == "cheer":
        wv = math.sin(t * 9) * 18
        arms = [(-125 + wv, -145 + wv), (125 - wv, 145 - wv)]
        hip_y -= abs(math.sin(t * 5)) * 18 * s
    elif pose == "sad":
        arms = [(-8, 0), (8, 0)]
        head_tilt = 22 * s
        lean = 6 * d
    elif pose == "think":
        arms = [(-40, 40), (35 * d, 165 * d)]
    elif pose == "shock":
        j = math.sin(t * 30) * 3
        arms = [(-130 + j, -100), (130 - j, 100)]
        legs = [(-22, 0), (22, 0)]
    elif pose == "sit":
        hip_y = GROUND - 30 * s
        legs = [(80 * d, 100 * d), (95 * d, 90 * d)]
        arms = [(-35, -20), (35 * d, 60 * d)]
    elif pose == "hold":
        arms = [(70 * d, 120 * d), (85 * d, 125 * d)]
    elif pose == "present":
        arms = [(-15, -5), (115 * d, (128 + math.sin(t * 4) * 8) * d)]
    elif pose == "angry":
        arms = [(-60, 60), (60, -60)]
        legs = [(-18, 0), (18, 0)]

    x = x + sway
    neck_x = x + math.sin(math.radians(lean)) * body
    neck_y = hip_y - body
    # legs
    for a1, a2 in legs:
        _limb(ctx, x, hip_y, a1, thigh, a2, leg)
    # body
    ctx.move_to(x, hip_y)
    ctx.line_to(neck_x, neck_y)
    stroke(ctx)
    # arms
    sh_x, sh_y = neck_x + (x - neck_x) * 0.15, neck_y + (hip_y - neck_y) * 0.12
    hands = [_limb(ctx, sh_x, sh_y, -a1 if False else a1, arm1, a2, arm2) for a1, a2 in arms]
    # head
    hx = neck_x + head_tilt * 0.4 * d
    hy = neck_y - head_r + head_tilt * 0.6
    ctx.arc(hx, hy, head_r, 0, 2 * math.pi)
    ctx.set_source_rgb(1, 1, 1)
    ctx.fill_preserve()
    stroke(ctx)
    _face(ctx, hx, hy, head_r, mood, d, t)
    if pose == "think":
        k = pop(t, 0.3)
        if k > 0:
            ctx.save()
            ctx.translate(hx + 95 * d * s, hy - 110 * s)
            ctx.scale(k, k)
            for i, rr in enumerate((10, 16)):
                ctx.arc(-50 * d * s + i * 25 * d * s, 70 * s - i * 28 * s, rr * s, 0, 2 * math.pi)
                stroke(ctx, INK, 6)
            text(ctx, "?", 0, 0, 110 * s, DARK_GREEN)
            ctx.restore()
    if pose == "shock":
        for k in range(3):
            ang = math.radians(-60 + k * 60)
            ctx.move_to(hx + math.sin(ang) * (head_r + 18), hy - math.cos(ang) * (head_r + 18))
            ctx.line_to(hx + math.sin(ang) * (head_r + 48), hy - math.cos(ang) * (head_r + 48))
            stroke(ctx, INK, 7)
    if pose == "sad":
        ctx.arc(hx + 30 * d * s, hy + 20 * s + (t * 60 % 50), 7 * s, 0, 2 * math.pi)
        ctx.set_source_rgb(0.35, 0.6, 0.95)
        ctx.fill()
    if label:
        text(ctx, label.upper(), hx, hy - head_r - 55 * s, 54 * s, INK, outline=(1, 1, 1))
        lw = min(len(label), 14) * 15 * s
        ctx.move_to(hx - lw, hy - head_r - 22 * s)
        ctx.line_to(hx + lw, hy - head_r - 22 * s)
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


_PROPS = {
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
    ctx.set_source_rgb(1, 1, 1)
    ctx.paint()
    # gentle camera push-in
    z = 1 + min(t, 6) * 0.006
    ctx.save()
    ctx.translate(W / 2, GROUND - 300)
    ctx.scale(z, z)
    ctx.translate(-W / 2, -(GROUND - 300))
    _ground(ctx)
    chars = [c for c in scene.get("characters", []) if c.get("pose")][:3]
    p = scene.get("prop", "none") or "none"
    has_prop = p != "none"
    n = len(chars)
    if n == 0:
        if has_prop:
            prop(ctx, p, W / 2, GROUND - 330, t, 1.25)
    elif n == 1:
        cx = 320 if has_prop else W / 2
        _enter(ctx, t, lambda: figure(ctx, cx, t, chars[0]["pose"], chars[0].get("mood", "neutral"),
                                      chars[0].get("label", ""), 1.12, True))
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
    _big_text(ctx, scene.get("big_text", ""), t, 2.7 if idx == 0 else 0.3)
    _brand(ctx)


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
    k = pop(t, 0.0, 0.4)
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
