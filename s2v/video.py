"""Ảnh tĩnh + voice + phụ đề -> mp4 dọc chuẩn YouTube (H.264/AAC)."""
from pathlib import Path

from .util import FFMPEG, run


def render(image: Path, audio: Path, ass: Path, dur: float, out: Path, v: dict, music: Path | None = None) -> Path:
    W, H, fps = v["width"], v["height"], v["fps"]
    pad = 1.0  # đệm 1s im lặng cuối
    total = dur + pad
    # Ảnh phóng to 15% rồi chạy pan chậm (crop theo thời gian) - rẻ hơn zoompan rất nhiều.
    sw, sh = int(W * 1.15) // 2 * 2, int(H * 1.15) // 2 * 2
    ox, oy = sw - W, sh - H
    vf = (
        f"scale={sw}:{sh}:force_original_aspect_ratio=increase,crop={sw}:{sh},"
        f"crop={W}:{H}:x='{ox}*t/{total:.2f}':y='{oy}*(0.5-0.5*cos(3.14159*t/{total:.2f}))',"
        f"fps={fps},scale=in_range=pc:out_range=tv,format=yuv420p,ass={ass.name},fade=t=in:d=0.6,fade=t=out:st={total-0.6:.2f}:d=0.6"
    )
    cmd = [FFMPEG, "-y", "-loop", "1", "-framerate", str(fps), "-i", str(image), "-i", str(audio)]
    if music:
        cmd += ["-stream_loop", "-1", "-i", str(music)]
        af = "[1:a]apad,volume=1.0[v];[2:a]volume=0.08[m];[v][m]amix=inputs=2:duration=first:normalize=0,afade=t=out:st={:.2f}:d=0.6[a]".format(total - 0.6)
    else:
        af = "[1:a]loudnorm=I=-16:TP=-1.5:LRA=11,apad,afade=t=out:st={:.2f}:d=0.6[a]".format(total - 0.6)
    cmd += [
        "-filter_complex", f"[0:v]{vf}[v];{af}",
        "-map", "[v]", "-map", "[a]", "-t", f"{total:.2f}",
        "-c:v", "libx264", "-preset", v["preset"], "-crf", str(v["crf"]), "-profile:v", "high", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-movflags", "+faststart",
        out.name,
    ]
    # chạy trong thư mục chứa ass/out để filter 'ass=' không dính đường dẫn đặc biệt
    import subprocess
    p = subprocess.run(cmd, cwd=out.parent, capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError("ffmpeg lỗi:\n" + p.stderr[-1500:])
    return out
