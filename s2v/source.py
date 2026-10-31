"""Lấy truyện từ vi.wikisource.org (tác phẩm phạm vi công cộng)."""
import re

import requests
from bs4 import BeautifulSoup

API = "https://vi.wikisource.org/w/api.php"
HEADERS = {"User-Agent": "story2video/0.1 (personal non-commercial project)"}


def fetch_story(title: str) -> dict:
    r = requests.get(
        API,
        params={"action": "parse", "page": title, "prop": "text", "format": "json",
                "formatversion": 2, "redirects": 1},
        headers=HEADERS, timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if "parse" not in data:
        raise ValueError(f"Không tìm thấy trang Wikisource: {title}")
    soup = BeautifulSoup(data["parse"]["text"], "lxml")
    for bad in soup.select("table, .noprint, .mw-editsection, sup.reference, style, script, .ws-noexport"):
        bad.decompose()
    paras = []
    for p in soup.select("p"):
        t = re.sub(r"\s+", " ", p.get_text(" ", strip=True)).strip()
        t = re.sub(r"\s+([,.;:!?…])", r"\1", t)
        if len(t) < 2:
            continue
        paras.append(t)
    return {
        "title": data["parse"]["title"],
        "paragraphs": paras,
        "url": "https://vi.wikisource.org/wiki/" + data["parse"]["title"].replace(" ", "_"),
    }
