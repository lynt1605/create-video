"""Mốc thời gian câu -> file phụ đề ASS (đốt vào video)."""
import re
from pathlib import Path


def _ts(t: float) -> str:
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _chunks(text: str, max_words: int = 6) -> list[str]:
    w = text.split()
    n = max(1, -(-len(w) // max_words))
    size = -(-len(w) // n)
    return [" ".join(w[i : i + size]) for i in range(0, len(w), size)]


def _esc(s: str) -> str:
    return s.replace("\\", "").replace("{", "(").replace("}", ")")


def write_ass(marks: list[dict], title: str, total: float, out: Path, v: dict) -> Path:
    W, H = v["width"], v["height"]
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Sub,{v['font']},{v['sub_font_size']},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,5,2,2,70,70,330,1
Style: Title,{v['font']},{int(v['sub_font_size']*0.8)},&H0000E5FF,&H0000E5FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,2,8,60,60,150,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    lines = [f"Dialogue: 0,{_ts(0)},{_ts(total)},Title,,0,0,0,,{_esc(title)}"]
    for m in marks:
        text = re.sub(r"\s+", " ", m["text"]).strip()
        if not text:
            continue
        chunks = _chunks(text)
        weights = [len(c) for c in chunks]
        dur = max(m["end"] - m["start"], 0.2)
        t = m["start"]
        for c, w in zip(chunks, weights):
            d = dur * w / sum(weights)
            lines.append(f"Dialogue: 0,{_ts(t)},{_ts(t + d)},Sub,,0,0,0,,{_esc(c)}")
            t += d
    out.write_text(head + "\n".join(lines) + "\n", encoding="utf-8")
    return out
