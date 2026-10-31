"""Chia truyện thành các phần ngắn, cắt tại ranh giới câu/đoạn."""
import re

_SENT = re.compile(r"(?<=[.!?…”\"])\s+")


def sentences(paragraphs: list[str]) -> list[str]:
    out = []
    for p in paragraphs:
        out.extend(s.strip() for s in _SENT.split(p) if s.strip())
    return out


def words(s: str) -> int:
    return len(s.split())


def split_parts(paragraphs: list[str], target_words: int) -> list[list[str]]:
    """Gom câu thành các phần ~target_words từ, tránh phần cuối quá ngắn."""
    sents = sentences(paragraphs)
    total = sum(words(s) for s in sents)
    n = max(1, -(-total // target_words))  # làm tròn lên để không phần nào vượt mục tiêu
    per = total / n
    parts, cur, cnt = [], [], 0
    for s in sents:
        w = words(s)
        if cur and cnt + w / 2 > per and len(parts) < n - 1:
            parts.append(cur)
            cur, cnt = [], 0
        cur.append(s)
        cnt += w
    if cur:
        parts.append(cur)
    return parts


def halve(sents: list[str]) -> tuple[list[str], list[str]]:
    half = sum(words(s) for s in sents) / 2
    acc = 0
    for i, s in enumerate(sents):
        acc += words(s)
        if acc >= half and i < len(sents) - 1:
            return sents[: i + 1], sents[i + 1 :]
    return sents[:-1], sents[-1:]
