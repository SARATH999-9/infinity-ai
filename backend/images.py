"""Creates images from a text description with the free Pollinations service (no key needed)."""
import base64
import logging
import random
import time
import urllib.parse

import requests

log = logging.getLogger("infinity")


def generate(prompt: str) -> str:
    """Returns a data: URL (jpeg/png). Raises RuntimeError if every attempt fails."""
    prompt = " ".join(prompt.split())[:500]
    if not prompt:
        raise RuntimeError("Empty image prompt.")
    last = "unknown error"
    for attempt in range(3):
        seed = random.randint(1, 1_000_000)
        url = (f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}"
               f"?width=1024&height=1024&seed={seed}&nologo=true&model=flux")
        try:
            r = requests.get(url, timeout=90, headers={"User-Agent": "INFINITY-AI/1.0"})
            ctype = r.headers.get("content-type", "").split(";")[0]
            if r.status_code == 200 and ctype.startswith("image/") and len(r.content) > 2000:
                return f"data:{ctype};base64,{base64.b64encode(r.content).decode()}"
            last = f"HTTP {r.status_code}"
            if r.status_code == 429:  # free tier allows about one image every 15 seconds
                time.sleep(16)
        except requests.RequestException as e:
            last = type(e).__name__
    log.warning("image generation failed: %s", last)
    raise RuntimeError(last)