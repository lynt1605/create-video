#!/usr/bin/env python3
"""story2video: truyện (Wikisource) -> voice -> ảnh -> video dọc <= 2 phút.

  python main.py run "Sự tích trầu cau"     # làm 1 truyện
  python main.py auto                        # lấy truyện kế tiếp trong queue.yaml
  python main.py auto --all                  # làm hết hàng đợi
  python main.py auto --loop 3600            # chạy nền, kiểm tra hàng đợi mỗi 3600s
"""
import argparse
import json
import sys
import time
import traceback
from pathlib import Path

import yaml

from s2v import config
from s2v.pipeline import run_story

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "state.json"


def load_state() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}


def save_state(st: dict) -> None:
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")


def auto_once(cfg) -> bool:
    """Làm 1 truyện chưa xong. Trả về False nếu hàng đợi đã hết."""
    queue = yaml.safe_load((ROOT / cfg["queue_file"]).read_text(encoding="utf-8"))["stories"]
    st = load_state()
    for item in queue:
        title = item["title"]
        if st.get(title, {}).get("status") == "done":
            continue
        print(f"\n>>> {title}", flush=True)
        t = time.time()
        try:
            metas = run_story(title, cfg, item.get("image_prompt"))
            st[title] = {"status": "done", "parts": len(metas), "seconds": round(time.time() - t),
                         "finished": time.strftime("%Y-%m-%d %H:%M:%S")}
        except Exception as e:
            traceback.print_exc()
            fails = st.get(title, {}).get("fails", 0) + 1
            st[title] = {"status": "failed" if fails >= 3 else "retry", "fails": fails, "error": str(e)[:300]}
        save_state(st)
        return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("title")
    r.add_argument("--image-prompt")
    a = sub.add_parser("auto")
    a.add_argument("--all", action="store_true")
    a.add_argument("--loop", type=int, metavar="SECONDS")
    args = ap.parse_args()
    cfg = config.load()

    if args.cmd == "run":
        t = time.time()
        for m in run_story(args.title, cfg, args.image_prompt):
            print(f"  -> {m['file']} ({m['duration']}s)")
        print(f"Tổng: {time.time() - t:.0f}s")
        return 0

    while True:
        did = auto_once(cfg)
        while did and args.all:
            did = auto_once(cfg)
        if not args.loop:
            return 0
        print(f"(hàng đợi {'còn' if did else 'trống'}) ngủ {args.loop}s", flush=True)
        time.sleep(args.loop)


if __name__ == "__main__":
    sys.exit(main())
