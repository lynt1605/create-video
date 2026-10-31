"""Điều phối: truyện -> các phần <= max_seconds -> mp4 + metadata."""
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import image as img
from . import splitter, subtitle, tts, video
from .source import fetch_story
from .util import sha, slugify, timed

ROOT = Path(__file__).resolve().parent.parent


def _tts_fit(sents, out_dir: Path, idx: int, cfg: dict):
    """Tổng hợp voice; nếu vượt max_seconds thì cắt đôi phần đó. Trả về list (sents, dur, marks, mp3)."""
    mp3 = out_dir / f"tmp_{idx}.mp3"
    dur, marks = tts.synthesize(sents, mp3, cfg["tts"])
    limit = cfg["video"]["max_seconds"]
    if dur <= limit or len(sents) < 2:
        return [(sents, dur, marks, mp3)]
    a, b = splitter.halve(sents)
    mp3.unlink(missing_ok=True)
    mp3.with_suffix(".json").unlink(missing_ok=True)
    return _tts_fit(a, out_dir, idx * 10 + 1, cfg) + _tts_fit(b, out_dir, idx * 10 + 2, cfg)


def _build_part(n: int, total: int, sents, dur, marks, mp3, story: dict, slug: str,
                out_dir: Path, cfg: dict, img_fut) -> dict:
    log: list = []
    tag = f"part_{n:02d}"
    pdir = out_dir / tag
    pdir.mkdir(exist_ok=True)
    final = pdir / f"{slug}_{tag}.mp4"
    if final.exists():
        print(f"  {tag}: đã có, bỏ qua")
        return json.loads((pdir / "meta.json").read_text(encoding="utf-8"))
    audio = pdir / "voice.mp3"
    mp3.replace(audio)
    mp3.with_suffix(".json").replace(pdir / "voice.json")

    label = f"{story['title']} – Phần {n}/{total}" if total > 1 else story["title"]
    with timed(f"{tag} chờ ảnh", log):
        prompt, src = img_fut.result()
    image = pdir / "image.jpg"
    fallback = src is None
    if fallback:
        print(f"  [{tag}] ảnh lỗi; dùng ảnh dự phòng", flush=True)
        sibs = sorted(out_dir.glob("part_*/image.jpg"))
        img.fallback(story["title"], image, cfg["image"], sibs)
    else:
        image.write_bytes(src.read_bytes())
    with timed(f"{tag} phụ đề", log):
        ass = subtitle.write_ass(marks, label, dur + 1, pdir / "subs.ass", cfg["video"])
    with timed(f"{tag} encode", log):
        video.render(image.resolve(), audio.resolve(), ass.resolve(), dur, final.resolve(), cfg["video"])
    meta = {
        "part": n, "total_parts": total, "file": str(final.relative_to(ROOT)),
        "duration": round(dur + 1, 1), "title": f"{label} | Truyện cổ tích Việt Nam #shorts",
        "image_prompt": prompt, "image_fallback": fallback, "timings": log,
    }
    (pdir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def run_story(title: str, cfg: dict, image_prompt: str | None = None) -> list[dict]:
    story = fetch_story(title)
    slug = slugify(story["title"])
    out_dir = ROOT / "output" / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "raw.txt").write_text("\n\n".join(story["paragraphs"]), encoding="utf-8")
    words = sum(len(p.split()) for p in story["paragraphs"])
    print(f"== {story['title']}: {words} từ ==", flush=True)

    parts = splitter.split_parts(story["paragraphs"], cfg["split"]["target_words"])

    # Ảnh: 1 luồng riêng (giới hạn 45s/ảnh của gói miễn phí), chạy nền ngay từ đầu cùng lúc với voice.
    img_pool = ThreadPoolExecutor(1)
    img_futs: dict[str, object] = {}
    per_story = cfg["image"].get("mode", "per_part") == "per_story"

    def image_for(sents):
        text = " ".join(sents)
        key = "story" if per_story else sha(text[:300])  # nửa đầu của phần bị cắt đôi vẫn trúng cache
        if key not in img_futs:
            def job(text=text, key=key):
                seed = 1 if per_story else int(key, 16) % 1000
                prompt = img.make_prompt(story["title"], text, cfg["image"]["style"], image_prompt)
                try:
                    return prompt, img.generate(prompt, out_dir / f"img_{key}.jpg", cfg["image"], seed=seed)
                except RuntimeError as e:
                    print(f"  [ảnh] {e}", flush=True)
                    return prompt, None
            img_futs[key] = img_pool.submit(job)
        return img_futs[key]

    for p in parts:
        image_for(p)
    with timed("voice (tất cả phần)"):
        fitted = []
        with ThreadPoolExecutor(cfg["pipeline"]["part_workers"]) as ex:
            for r in ex.map(lambda ip: _tts_fit(ip[1], out_dir, ip[0] + 1, cfg), enumerate(parts)):
                fitted += r
    total = len(fitted)
    print(f"  chia thành {total} phần: " + ", ".join(f"{d:.0f}s" for _, d, _, _ in fitted), flush=True)

    with ThreadPoolExecutor(cfg["pipeline"]["part_workers"]) as ex:
        futs = [
            ex.submit(_build_part, i + 1, total, s, d, m, mp3, story, slug, out_dir, cfg, image_for(s))
            for i, (s, d, m, mp3) in enumerate(fitted)
        ]
        metas = [f.result() for f in futs]

    desc = (
        f"{story['title']} – truyện cổ tích Việt Nam.\n\n"
        f"Nguồn văn bản: {story['url']} (Wikisource, tác phẩm thuộc phạm vi công cộng).\n"
        "Giọng đọc: Microsoft Edge TTS (tổng hợp bằng AI). Hình ảnh: tạo bằng AI.\n"
        "#truyencotich #shorts #truyenviet"
    )
    (out_dir / "description.txt").write_text(desc, encoding="utf-8")
    (out_dir / "story.json").write_text(json.dumps(
        {"title": story["title"], "url": story["url"], "parts": metas}, ensure_ascii=False, indent=2), encoding="utf-8")
    return metas
