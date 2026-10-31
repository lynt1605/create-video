#!/usr/bin/env bash
# Chạy 1 truyện kế tiếp trong queue.yaml (dùng cho cron). Khoá để không chạy chồng.
cd "$(dirname "$0")"
exec 9>.auto.lock
flock -n 9 || { echo "đang chạy rồi"; exit 0; }
.venv/bin/python main.py auto --all >> output/auto.log 2>&1
