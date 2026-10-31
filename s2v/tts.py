"""Text -> mp3 (edge-tts, miễn phí) kèm mốc thời gian từng câu."""
import asyncio
import json
import shutil
import threading
import time
from pathlib import Path

import edge_tts

from .util import FFMPEG, ROOT_CACHE, duration, run, sha

_lock = threading.Lock()  # edge-tts hay từ chối khi gọi dồn dập: tuần tự + giãn cách
_last = [0.0]
MIN_GAP = 2.0


async def _synth(text: str, out: Path, voice: str, rate: str) -> list[dict]:
    com = edge_tts.Communicate(text, voice, rate=rate)
    marks = []
    with open(out, "wb") as f:
        async for ch in com.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] in ("SentenceBoundary", "WordBoundary"):
                marks.append({
                    "start": ch["offset"] / 1e7,
                    "end": (ch["offset"] + ch["duration"]) / 1e7,
                    "text": ch["text"],
                })
    return marks


def _chunk(sents: list[str], limit: int = 500) -> list[list[str]]:
    groups, cur, n = [], [], 0
    for s in sents:
        if cur and n + len(s) > limit:
            groups.append(cur)
            cur, n = [], 0
        cur.append(s)
        n += len(s) + 1
    if cur:
        groups.append(cur)
    return groups


def synthesize(sents: list[str], out: Path, cfg: dict) -> tuple[float, list[dict]]:
    """Đọc từng cụm câu ngắn (ổn định hơn) rồi nối lại. Trả về (độ dài giây, {start,end,text})."""
    order = ["edge", "gtts"] if cfg.get("provider", "edge") == "auto" else [cfg.get("provider", "edge")]
    for k, prov in enumerate(order):
        try:
            return _synthesize_all(sents, out, cfg, prov)
        except RuntimeError as e:
            if k == len(order) - 1:
                raise
            print(f"  [tts] {prov} lỗi ({str(e)[:60]}) -> thử {order[k + 1]}", flush=True)


def _synthesize_all(sents, out: Path, cfg: dict, prov: str) -> tuple[float, list[dict]]:
    tmp = out.parent / (out.stem + "_chunks")
    tmp.mkdir(exist_ok=True)
    files, marks, t = [], [], 0.0
    for i, g in enumerate(_chunk(sents)):
        f = tmp / f"{i:03d}.mp3"
        d, m = _synthesize_one(g, f, cfg, prov)
        marks += [{"start": x["start"] + t, "end": x["end"] + t, "text": x["text"]} for x in m]
        files.append(f)
        t += d
    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{f.resolve()}'\n" for f in files), encoding="utf-8")
    run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)])
    shutil.rmtree(tmp, ignore_errors=True)
    out.with_suffix(".json").write_text(json.dumps(marks, ensure_ascii=False), encoding="utf-8")
    return duration(out), marks


def _gtts(sents: list[str], out: Path) -> list[dict]:
    from gtts import gTTS
    last = None
    for i in range(3):
        try:
            gTTS(" ".join(sents), lang="vi").save(str(out))
            break
        except Exception as e:
            last = repr(e)
            time.sleep(2 * (i + 1))
    else:
        raise RuntimeError(f"gTTS lỗi: {last}")
    dur, total, t, marks = duration(out), sum(len(x) for x in sents), 0.0, []
    for x in sents:  # không có mốc thời gian thật: chia theo số ký tự
        d = dur * len(x) / total
        marks.append({"start": t, "end": t + d, "text": x})
        t += d
    return marks


def _synthesize_one(sents: list[str], out: Path, cfg: dict, prov: str = "edge") -> tuple[float, list[dict]]:
    meta = out.with_suffix(".json")
    text = " ".join(sents)
    key = sha(f"{prov}|{cfg['voice']}|{cfg.get('rate', '+0%')}|{text}")
    c_mp3, c_json = ROOT_CACHE / f"tts_{key}.mp3", ROOT_CACHE / f"tts_{key}.json"
    if c_mp3.exists() and c_json.exists():
        shutil.copy(c_mp3, out)
        shutil.copy(c_json, meta)
        return duration(out), json.loads(meta.read_text(encoding="utf-8"))
    last_err = None
    if prov == "gtts":
        marks = _gtts(sents, out)
        dur = duration(out)
        meta.write_text(json.dumps(marks, ensure_ascii=False), encoding="utf-8")
        shutil.copy(out, c_mp3)
        shutil.copy(meta, c_json)
        return dur, marks
    for i in range(6):
        with _lock:
            time.sleep(max(0.0, MIN_GAP - (time.time() - _last[0])))
            try:
                marks = asyncio.run(asyncio.wait_for(_synth(text, out, cfg["voice"], cfg.get("rate", "+0%")), 60))
                _last[0] = time.time()
                break
            except Exception as e:  # bị chặn tạm / mạng chập chờn: chờ rồi thử lại
                last_err = repr(e)
                _last[0] = time.time()
        time.sleep(min(8 * 2 ** i, 60))  # lỗi theo đợt: chờ dài dần
    else:
        raise RuntimeError(f"edge-tts lỗi: {last_err}")
    dur = duration(out)
    if not marks:  # dự phòng: chia đều theo số ký tự
        total = sum(len(s) for s in sents)
        t = 0.0
        for s in sents:
            d = dur * len(s) / total
            marks.append({"start": t, "end": t + d, "text": s})
            t += d
    meta.write_text(json.dumps(marks, ensure_ascii=False), encoding="utf-8")
    shutil.copy(out, c_mp3)
    shutil.copy(meta, c_json)
    return dur, marks
