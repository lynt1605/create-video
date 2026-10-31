import hashlib
import re
import shutil
import subprocess
import time
import unicodedata
from contextlib import contextmanager

import static_ffmpeg
from pathlib import Path

static_ffmpeg.add_paths()
ROOT_CACHE = Path(__file__).resolve().parent.parent / "cache"
ROOT_CACHE.mkdir(exist_ok=True)
FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")


def slugify(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def sha(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def duration(path) -> float:
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


def run(cmd: list[str]) -> None:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(f"{cmd[0]} failed:\n{p.stderr[-1500:]}")


@contextmanager
def timed(label: str, log: list | None = None):
    t = time.time()
    yield
    dt = time.time() - t
    print(f"  [{label}] {dt:.1f}s", flush=True)
    if log is not None:
        log.append((label, round(dt, 1)))
