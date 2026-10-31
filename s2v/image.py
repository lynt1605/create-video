"""Tạo ảnh bằng Pollinations.ai (miễn phí, không cần key).

Gói miễn phí giới hạn ~1 ảnh / 45 giây / IP, nên mọi request đi qua 1 khoá + 1 bộ đếm giờ
lưu trên đĩa (đúng giữa các lần chạy), thay vì đập API rồi nhận lỗi 402.
"""
import re
import threading
import time
import urllib.parse
from pathlib import Path

import requests

from .util import ROOT_CACHE, sha

_lock = threading.Lock()
_LAST = ROOT_CACHE / "img_last.txt"
IMG = "https://image.pollinations.ai/prompt/"
TXT = "https://text.pollinations.ai/"
GAP = 46  # giây giữa 2 ảnh (giới hạn miễn phí 45s)

FACE_HINT = (
    "one clear main character in medium shot, face clearly visible, calm natural expression, "
    "detailed symmetrical face, well-proportioned, centered composition"
)


def make_prompt(title: str, part_text: str, style: str, override: str | None) -> str:
    """Prompt tiếng Anh: ưu tiên prompt tự đặt; sau đó nhờ text.pollinations.ai; cuối cùng dùng tên truyện."""
    if override:
        return f"{override}, {FACE_HINT}, {style}"
    ask = (
        "Write ONE short English image-generation prompt (max 40 words) for a single illustrative "
        "scene from this Vietnamese folk tale excerpt. Show at most two characters, described by "
        "age, clothing and action (traditional Vietnamese clothes, ancient Vietnam). No text, "
        f"no crowds. Story: {title}. Excerpt: {part_text[:900]}\nPrompt:"
    )
    try:
        r = requests.get(TXT + urllib.parse.quote(ask), timeout=45)
        if r.ok and 10 < len(r.text) < 400:
            return f"{r.text.strip()}, {FACE_HINT}, {style}"
    except requests.RequestException:
        pass
    return f"Vietnamese folk tale '{title}', {FACE_HINT}, {style}"


def _wait_slot() -> None:
    try:
        last = float(_LAST.read_text())
    except (OSError, ValueError):
        last = 0.0
    time.sleep(max(0.0, last + GAP - time.time()))


def _clean(path: Path) -> None:
    """Cắt dải logo ở đáy ảnh của gói miễn phí."""
    from PIL import Image

    im = Image.open(path).convert("RGB")
    w, h = im.size
    im.crop((0, 0, w, int(h * 0.93))).save(path, quality=93)


def _pollinations(prompt: str, out: Path, cfg: dict, seed: int = 7) -> Path:
    cache = ROOT_CACHE / f"img_{sha(prompt + str(seed))}.jpg"
    if cache.exists():
        out.write_bytes(cache.read_bytes())
        return out
    url = IMG + urllib.parse.quote(prompt) + (
        f"?width={cfg['width']}&height={cfg['height']}&nologo=true&seed={seed}"
    )
    last = None
    for _ in range(cfg.get("retries", 3) + 3):
        with _lock:
            _wait_slot()
            try:
                r = requests.get(url, timeout=cfg.get("timeout", 120))
                if r.ok and r.headers.get("content-type", "").startswith("image"):
                    _LAST.write_text(str(time.time()))
                    out.write_bytes(r.content)
                    _clean(out)
                    cache.write_bytes(out.read_bytes())
                    return out
                last = f"HTTP {r.status_code} {r.text[:80]}"
                m = re.search(r"Retry after (\d+)s", r.text)
                time.sleep(int(m.group(1)) + 1 if m else 8)
            except requests.RequestException as e:
                last = e
                time.sleep(5)
    raise RuntimeError(f"Không tạo được ảnh: {last}")


def fallback(title: str, out: Path, cfg: dict, siblings: list[Path]) -> Path:
    """Khi dịch vụ ảnh lỗi: dùng lại ảnh phần khác của truyện, hoặc vẽ nền gradient (không làm kẹt pipeline)."""
    for s in siblings:
        if s.exists() and s != out:
            out.write_bytes(s.read_bytes())
            return out
    from PIL import Image, ImageDraw

    w, h = cfg["width"], cfg["height"]
    hue = int(sha(title), 16)
    top = (40 + hue % 60, 30 + (hue >> 8) % 50, 70 + (hue >> 16) % 80)
    bot = (200 - hue % 40, 150 - (hue >> 8) % 40, 90 + (hue >> 4) % 60)
    im = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(im)
    for y in range(h):
        t = y / h
        d.line([(0, y), (w, y)], fill=tuple(int(top[i] * (1 - t) + bot[i] * t) for i in range(3)))
    im.save(out, quality=92)
    return out


def generate(prompt: str, out: Path, cfg: dict, seed: int = 7) -> Path:
    """Thử lần lượt các nguồn trong cfg['providers'] (mặc định: local rồi pollinations)."""
    cache = ROOT_CACHE / f"loc_{sha(prompt + str(seed))}.jpg"
    if cache.exists():
        out.write_bytes(cache.read_bytes())
        return out
    errs = []
    for prov in cfg.get("providers", ["local", "pollinations"]):
        try:
            if prov == "local":
                from . import image_local
                if not image_local.available():
                    errs.append("local: chưa cài model (chạy setup_local_images.sh)")
                    continue
                image_local.generate(prompt, out, cfg, seed)
                cache.write_bytes(out.read_bytes())
                return out
            if prov == "pollinations":
                return _pollinations(prompt, out, cfg, seed)
        except Exception as e:  # noqa: BLE001 - chuyển sang nguồn kế tiếp
            errs.append(f"{prov}: {e}")
    raise RuntimeError(" | ".join(errs))
