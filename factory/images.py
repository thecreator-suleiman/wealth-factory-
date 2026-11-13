"""Step 3: create one vertical image per story moment with Pollinations (free)."""
import random
import time
import urllib.parse
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image, ImageDraw

from .common import env, log

NEW_API = "https://gen.pollinations.ai/image/{p}"
OLD_API = "https://image.pollinations.ai/prompt/{p}"


def _fit(img: Image.Image, w: int, h: int) -> Image.Image:
    """Crop/resize to exactly w x h without stretching."""
    img = img.convert("RGB")
    scale = max(w / img.width, h / img.height)
    img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    left = (img.width - w) // 2
    top = (img.height - h) // 2
    return img.crop((left, top, left + w, top + h))


def _fetch(prompt: str, seed: int, w: int, h: int, key: str) -> Image.Image:
    p = urllib.parse.quote(prompt[:900], safe="")
    params = {"width": w, "height": h, "seed": seed, "nologo": "true", "model": "flux", "safe": "true"}
    if key:
        url = NEW_API.format(p=p)
        headers = {"Authorization": f"Bearer {key}"}
    else:
        url = OLD_API.format(p=p)
        headers = {}
    r = requests.get(url, params=params, headers=headers, timeout=180)
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image"):
        raise RuntimeError(f"HTTP {r.status_code} {r.headers.get('content-type')} {r.text[:120] if r.status_code != 200 else ''}")
    if len(r.content) < 15_000:
        raise RuntimeError("image too small")
    return Image.open(BytesIO(r.content))


def _placeholder(w: int, h: int, seed: int) -> Image.Image:
    rnd = random.Random(seed)
    top = tuple(rnd.randint(10, 60) for _ in range(3))
    bottom = tuple(rnd.randint(60, 140) for _ in range(3))
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        k = y / h
        d.line([(0, y), (w, y)], fill=tuple(int(a + (b - a) * k) for a, b in zip(top, bottom)))
    return img


def make_images(cfg: dict, prompts: list[str], folder: Path, base_seed: int) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    w, h = cfg["video"]["width"], cfg["video"]["height"]
    key = env("POLLINATIONS_API_KEY", required=False)
    gap = 3 if key else 16  # the free no-key service allows about 1 image per 15 s
    log(f"Making {len(prompts)} images ({'with' if key else 'without'} Pollinations key)")
    paths, good = [], []
    last = 0.0
    for i, prompt in enumerate(prompts):
        path = folder / f"img_{i:02d}.jpg"
        img = None
        for attempt in range(3):
            wait = gap - (time.time() - last)
            if wait > 0:
                time.sleep(wait)
            last = time.time()
            try:
                img = _fit(_fetch(prompt, base_seed + i * 7 + attempt, w, h, key), w, h)
                break
            except Exception as e:  # noqa: BLE001
                log(f"  image {i + 1} try {attempt + 1} failed: {e}")
                time.sleep(5 * (attempt + 1))
        if img is None:
            if good:
                img = Image.open(good[-1]).copy()  # reuse the previous good image
                log(f"  image {i + 1}: reusing previous image")
            else:
                img = _placeholder(w, h, base_seed + i)
                log(f"  image {i + 1}: using plain background")
        else:
            good.append(path)
        img.save(path, quality=92)
        paths.append(path)
    if len(good) < len(prompts) // 2:
        raise RuntimeError(f"Only {len(good)} of {len(prompts)} images could be generated.")
    log(f"Images ready: {len(good)}/{len(prompts)} generated")
    return paths
