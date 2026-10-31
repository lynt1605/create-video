# story2video

Truyện cổ tích Việt (vi.wikisource.org, phạm vi công cộng) → voice → ảnh → video dọc 1080x1920, mỗi video ≤ 2 phút. Toàn bộ miễn phí.

```
python3 -m venv --without-pip .venv   # máy này thiếu ensurepip: cài pip bằng get-pip.py
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py run "Sự tích trầu cau"   # 1 truyện
.venv/bin/python main.py auto --all                # cả hàng đợi queue.yaml
```

- Cấu hình: `config.yaml`. Hàng đợi: `queue.yaml`. Trạng thái: `state.json` (truyện lỗi tự thử lại, tối đa 3 lần).
- Kết quả: `output/<truyen>/part_NN/*.mp4`, `description.txt`, `story.json` (title/description để đăng).
- Chạy tự động: `crontab -e` rồi thêm `*/30 * * * * /home/ly/create-video/run_auto.sh`
- Mỗi video dùng 1 ảnh. Nếu Pollinations lỗi sẽ dùng ảnh dự phòng (`image_fallback: true` trong meta.json).
