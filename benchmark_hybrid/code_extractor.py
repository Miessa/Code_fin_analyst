"""Deterministic text and numeric-candidate extraction."""

import re
from pathlib import Path

from bs4 import BeautifulSoup


NUMBER = re.compile(r"(?<!\w)[+-]?\d[\d ,.]*(?:%|x|X|\s*(?:USD|EUR|FCFA|XOF)?\s*/?\s*(?:kW|MW|kWh|MWh)?)")


def extract_text(path):
    path = Path(path)
    if path.suffix.lower() in {".html", ".htm"}:
        return BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), "html.parser").get_text(" ", strip=True)
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("PDF extraction requires: pip install pypdf") from exc
        pages = []
        for number, page in enumerate(PdfReader(str(path)).pages, 1):
            pages.append(f"\n--- PAGE {number} ---\n{page.extract_text() or ''}")
        return "".join(pages)
    return path.read_text(encoding="utf-8", errors="ignore")


def candidate_windows(text, keywords, radius=240):
    lowered = text.lower()
    windows, seen = [], set()
    for keyword in keywords:
        start = 0
        while True:
            pos = lowered.find(keyword.lower(), start)
            if pos < 0:
                break
            window = text[max(0, pos-radius):min(len(text), pos+len(keyword)+radius)]
            key = window.strip()
            if key and key not in seen:
                windows.append({"keyword": keyword, "text": key, "numbers": NUMBER.findall(key)})
                seen.add(key)
            start = pos + len(keyword)
    return windows
