"""Creates images. Tries the providers in config.IMAGE_ORDER; each one needs its own key except the free Pollinations fallback."""
import base64
import logging
import random
import re
import time
import urllib.parse

import requests

import config

log = logging.getLogger("infinity")


class ImageError(RuntimeError):
    def __init__(self, message, status=0):
        super().__init__(message)
        self.status = status


STYLE_WORDS = re.compile(r"cartoon|anime|logo|icon|illustration|painting|drawing|sketch|3d|vector|pixel|watercolor|oil|comic|minimal|flat|poster|render", re.I)
_cool: dict = {}


def _enhance(p: str) -> str:
    p = " ".join(p.split())[:700]
    return p if STYLE_WORDS.search(p) else p + ", photorealistic, natural lighting, highly detailed, sharp focus"


def _why(r) -> str:
    try:
        e = r.json().get("error", r.text)
        e = e.get("message", e) if isinstance(e, dict) else e
    except Exception:
        e = r.text
    return f"HTTP {r.status_code} {str(e)[:140]}".strip()


def _openai(prompt):
    r = requests.post("https://api.openai.com/v1/images/generations",
                      headers={"Authorization": "Bearer " + config.IMAGE_KEYS["openai"]},
                      json={"model": config.IMAGE_MODELS["openai"], "prompt": prompt, "size": "1024x1024",
                            "quality": config.OPENAI_IMAGE_QUALITY, "n": 1}, timeout=150)
    if r.status_code != 200:
        raise ImageError("OpenAI: " + _why(r), r.status_code)
    return "data:image/png;base64," + r.json()["data"][0]["b64_json"]


def _gemini(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.IMAGE_MODELS['gemini']}:generateContent"
    r = requests.post(url, headers={"x-goog-api-key": config.IMAGE_KEYS["gemini"]},
                      json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseModalities": ["IMAGE"]}},
                      timeout=150)
    if r.status_code != 200:
        raise ImageError("Gemini: " + _why(r), r.status_code)
    for cand in r.json().get("candidates", []):
        for part in (cand.get("content") or {}).get("parts", []):
            blob = part.get("inlineData") or part.get("inline_data")
            if blob and blob.get("data"):
                return f"data:{blob.get('mimeType') or blob.get('mime_type') or 'image/png'};base64,{blob['data']}"
    raise ImageError("Gemini: no image returned (it may have been blocked by safety filters)", 422)


def _together(prompt):
    body = {"model": config.IMAGE_MODELS["together"], "prompt": prompt, "width": 1024, "height": 1024, "n": 1, "response_format": "b64_json"}
    if "schnell" in body["model"].lower():
        body["steps"] = 4
    r = requests.post("https://api.together.xyz/v1/images/generations",
                      headers={"Authorization": "Bearer " + config.IMAGE_KEYS["together"]}, json=body, timeout=150)
    if r.status_code != 200:
        raise ImageError("Together: " + _why(r), r.status_code)
    return "data:image/png;base64," + r.json()["data"][0]["b64_json"]


def _pollinations(prompt):
    last = "unknown error"
    for _ in range(3):
        url = (f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}"
               f"?width=1024&height=1024&seed={random.randint(1, 1_000_000)}&nologo=true&model=flux")
        try:
            r = requests.get(url, timeout=90, headers={"User-Agent": "INFINITY-AI/1.0"})
            ctype = r.headers.get("content-type", "").split(";")[0]
            if r.status_code == 200 and ctype.startswith("image/") and len(r.content) > 2000:
                return f"data:{ctype};base64,{base64.b64encode(r.content).decode()}"
            last = f"HTTP {r.status_code}"
            if r.status_code == 429:  # free tier: about one image every 15 seconds
                time.sleep(16)
        except requests.RequestException as e:
            last = type(e).__name__
    raise ImageError("Pollinations (free): " + last)


PROVIDERS = {"openai": _openai, "gemini": _gemini, "together": _together, "pollinations": _pollinations}


def available() -> list[str]:
    return [n for n in config.IMAGE_ORDER if n in PROVIDERS and (n == "pollinations" or config.IMAGE_KEYS.get(n))]


def generate(prompt: str) -> str:
    """Returns a data: URL. Raises ImageError (with every provider's reason) if all fail."""
    prompt = _enhance(prompt)
    if not prompt:
        raise ImageError("Empty image prompt.")
    reasons = []
    for name in available():
        if _cool.get(name, 0) > time.time():
            continue
        try:
            return PROVIDERS[name](prompt)
        except ImageError as e:
            reasons.append(str(e))
            if e.status in (401, 403, 404):
                _cool[name] = time.time() + 900
            elif e.status == 429:
                _cool[name] = time.time() + 60
        except requests.RequestException as e:
            reasons.append(f"{name}: {type(e).__name__}")
        except (KeyError, IndexError, ValueError):
            reasons.append(f"{name}: unexpected reply")
    log.warning("image generation failed: %s", " | ".join(reasons))
    raise ImageError(" | ".join(reasons) or "No image provider is available.")