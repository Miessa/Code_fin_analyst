"""Resilient downloader with bounded retries; never changes approved data."""

import random
import time
from pathlib import Path

import requests


TEMPORARY_STATUS = {408, 429, 500, 502, 503, 504}


def download(url, destination, attempts=4, timeout=45):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    last_error = None
    for attempt in range(attempts):
        try:
            response = requests.get(url, timeout=timeout, headers={"User-Agent": "ARSEL-benchmark-research/1.0"})
            if response.status_code in TEMPORARY_STATUS:
                raise RuntimeError(f"temporary HTTP {response.status_code}")
            response.raise_for_status()
            destination.write_bytes(response.content)
            return destination
        except Exception as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(min(20, 2 ** attempt + random.random()))
    raise RuntimeError(f"download failed after {attempts} attempts: {last_error}")
