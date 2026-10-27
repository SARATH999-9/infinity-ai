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


STYLE_WORDS = re.compile(r"cartoon|anime|logo|icon|illustration|painting|drawing|sketch|3d|vector|pixel|watercolor|oil|comic|minimal|flat|poster|render|clipart|sticker|manga|digital art", re.I)
REAL_WORDS = re.compile(r"photorealistic|photograph|\blens\b|\bdslr\b|\b8k\b", re.I)
REAL_SUFFIX = (", ultra realistic photograph, shot on a full-frame camera with an 85mm lens, natural soft lighting, "
               "true-to-life colours, realistic textures and skin detail, sharp focus, high dynamic range, 8k")
NEGATIVE = "blurry, low quality, distorted, deformed, extra fingers, bad anatomy, watermark, text, cartoon, painting"
_cool: dict = {}

# "create an image of a red car" -> "a red car"
_REQ = re.compile(
    r"^\s*(please\s+)?((can|could|would)\s+you\s+)?(generate|create|make|draw|design|paint|render|give\s+me|show\s+me)\s+(me\s+)?"
    r"(an?\s+|the\s+|some\s+)?(?:[\w-]+\s+){0,2}?(image|picture|photo)s?\s+(of|for|showing|with|about|that)\s+", re.I | re.S)


def clean_request(text: str) -> str:
    t = " ".join((text or "").split())
    m = _REQ.match(t)
    if m and len(t) > m.end():
        rest = t[m.end():]
        return ("a photo of " + rest) if m.group(7).lower() == "photo" else rest
    return t


def pick_shape(p: str) -> str:
    """square | landscape | portrait, guessed from the words of the request."""
    if re.search(r"wallpaper|banner|landscape|desktop|youtube|thumbnail|panorama|cover photo|16:9|widescreen|cinematic", p, re.I):
        return "landscape"
    if re.search(r"portrait|poster|flyer|invitation|phone|mobile|story|reel|9:16|full[- ]body|book cover|vertical|standing", p, re.I):
        return "portrait"
    return "square"


SIZES = {  # shape -> (OpenAI size, aspect ratio, width, height)
    "square": ("1024x1024", "1:1", 1024, 1024),
    "landscape": ("1536x1024", "3:2", 1344, 896),
    "portrait": ("1024x1536", "2:3", 896, 1344),
}


def _enhance(p: str) -> str:
    """Rule-based boost: adds camera/lighting words unless the user asked for another style or the prompt is already detailed."""
    p = " ".join(p.split())[:900]
    if not p or STYLE_WORDS.search(p) or REAL_WORDS.search(p):
        return p
    return p + REAL_SUFFIX


def _smart(idea: str) -> str:
    """Asks the chat AI to turn a short idea into a rich, realistic image prompt. Falls back to the idea itself."""
    if not config.IMAGE_SMART_PROMPT or not config.ACTIVE:
        return idea
    try:
        import providers  # local import: avoids loading the chat stack unless needed
        ask = ("Rewrite the idea below as ONE detailed English prompt for an AI image generator (60 to 110 words). "
               "Make it look like a real photograph unless a style such as cartoon, anime, logo, painting, 3D or illustration is named, "
               "in which case keep that style. Describe subject, setting, lighting, camera and lens, colours and mood. "
               "Do not put readable text in the image. Output only the prompt inside [[IMAGE: ]].\n\nIdea: " + idea)
        out = "".join(providers.stream_text([{"role": "user", "text": ask, "images": []}], False))
        m = re.search(r"\[\[IMAGE:\s*(.+?)(\]\]|$)", out, re.S)
        better = " ".join((m.group(1) if m else "").split()).strip(" \"'")
        if len(better) >= max(25, len(idea)):
            return better[:900]
    except Exception as e:  # any failure -> just use the original idea
        log.info("smart prompt skipped: %s", str(e)[:120])
    return idea


def _why(r) -> str:
    try:
        e = r.json().get("error", r.text)
        e = e.get("message", e) if isinstance(e, dict) else e
    except Exception:
        e = r.text
    return f"HTTP {r.status_code} {str(e)[:140]}".strip()


def _openai(prompt, shape):
    r = requests.post("https://api.openai.com/v1/images/generations",
                      headers={"Authorization": "Bearer " + config.IMAGE_KEYS["openai"]},
                      json={"model": config.IMAGE_MODELS["openai"], "prompt": prompt, "size": SIZES[shape][0],
                            "quality": config.OPENAI_IMAGE_QUALITY, "n": 1}, timeout=150)
    if r.status_code != 200:
        raise ImageError("OpenAI: " + _why(r), r.status_code)
    return "data:image/png;base64," + r.json()["data"][0]["b64_json"]


def _gemini(prompt, shape):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.IMAGE_MODELS['gemini']}:generateContent"
    gen = {"responseModalities": ["IMAGE"]}
    if shape != "square":
        gen["imageConfig"] = {"aspectRatio": SIZES[shape][1]}
    body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": gen}
    hdr = {"x-goog-api-key": config.IMAGE_KEYS["gemini"]}
    r = requests.post(url, headers=hdr, json=body, timeout=150)
    if r.status_code == 400 and "imageConfig" in gen:  # older models: retry without the aspect ratio
        gen.pop("imageConfig")
        r = requests.post(url, headers=hdr, json=body, timeout=150)
    if r.status_code != 200:
        raise ImageError("Gemini: " + _why(r), r.status_code)
    for cand in r.json().get("candidates", []):
        for part in (cand.get("content") or {}).get("parts", []):
            blob = part.get("inlineData") or part.get("inline_data")
            if blob and blob.get("data"):
                return f"data:{blob.get('mimeType') or blob.get('mime_type') or 'image/png'};base64,{blob['data']}"
    raise ImageError("Gemini: no image returned (it may have been blocked by safety filters)", 422)


def _stability(prompt, shape):
    model = config.IMAGE_MODELS["stability"]
    r = requests.post(f"https://api.stability.ai/v2beta/stable-image/generate/{model}",
                      headers={"Authorization": "Bearer " + config.IMAGE_KEYS["stability"], "Accept": "image/*"},
                      files={"none": ""},
                      data={"prompt": prompt, "negative_prompt": NEGATIVE, "aspect_ratio": SIZES[shape][1], "output_format": "png"},
                      timeout=150)
    ctype = r.headers.get("content-type", "").split(";")[0]
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise ImageError("Stability: " + _why(r), r.status_code)
    return f"data:{ctype};base64,{base64.b64encode(r.content).decode()}"


def _together(prompt, shape):
    w, h = SIZES[shape][2], SIZES[shape][3]
    body = {"model": config.IMAGE_MODELS["together"], "prompt": prompt, "width": w, "height": h, "n": 1, "response_format": "b64_json"}
    name = body["model"].lower()
    if "schnell" in name:
        body["steps"] = 4
    elif "flux" in name and "pro" not in name:
        body["steps"] = 28
    r = requests.post("https://api.together.xyz/v1/images/generations",
                      headers={"Authorization": "Bearer " + config.IMAGE_KEYS["together"]}, json=body, timeout=150)
    if r.status_code != 200:
        raise ImageError("Together: " + _why(r), r.status_code)
    return "data:image/png;base64," + r.json()["data"][0]["b64_json"]


def _huggingface(prompt, shape):
    model = config.IMAGE_MODELS["huggingface"]
    w, h = SIZES[shape][2], SIZES[shape][3]
    r = requests.post(f"https://router.huggingface.co/hf-inference/models/{model}",
                      headers={"Authorization": "Bearer " + config.IMAGE_KEYS["huggingface"], "Accept": "image/png"},
                      json={"inputs": prompt, "parameters": {"width": w, "height": h}}, timeout=150)
    ctype = r.headers.get("content-type", "").split(";")[0]
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise ImageError("Hugging Face: " + _why(r), r.status_code)
    return f"data:{ctype};base64,{base64.b64encode(r.content).decode()}"


def _cloudflare(prompt, shape):
    """Cloudflare Workers AI (FLUX.1 schnell): has a free daily allowance. Image size is fixed by the model."""
    url = f"https://api.cloudflare.com/client/v4/accounts/{config.CLOUDFLARE_ACCOUNT_ID}/ai/run/{config.IMAGE_MODELS['cloudflare']}"
    r = requests.post(url, headers={"Authorization": "Bearer " + config.IMAGE_KEYS["cloudflare"]},
                      json={"prompt": prompt[:2000], "steps": 6}, timeout=120)
    if r.status_code != 200:
        raise ImageError("Cloudflare: " + _why(r), r.status_code)
    img = ((r.json().get("result") or {}).get("image")) or ""
    if len(img) < 1000:
        raise ImageError("Cloudflare: no image returned", 422)
    return "data:image/jpeg;base64," + img


def _pollinations(prompt, shape):
    """Free. Uses the new gen.pollinations.ai address first (an optional POLLINATIONS_API_KEY raises limits), then the old one."""
    w, h = SIZES[shape][2], SIZES[shape][3]
    key = config.IMAGE_KEYS.get("pollinations", "")
    last = "unknown error"
    for attempt in range(2):
        for base in ("https://gen.pollinations.ai/image/", "https://image.pollinations.ai/prompt/"):
            url = (f"{base}{urllib.parse.quote(prompt[:700])}?width={w}&height={h}&seed={random.randint(1, 1_000_000)}"
                   f"&nologo=true&model={config.IMAGE_MODELS['pollinations']}")
            hdr = {"User-Agent": "INFINITY-AI/1.0"}
            if key:
                url += "&key=" + urllib.parse.quote(key)
                hdr["Authorization"] = "Bearer " + key
            try:
                r = requests.get(url, timeout=90, headers=hdr)
                ctype = r.headers.get("content-type", "").split(";")[0]
                if r.status_code == 200 and ctype.startswith("image/") and len(r.content) > 2000:
                    return f"data:{ctype};base64,{base64.b64encode(r.content).decode()}"
                last = f"HTTP {r.status_code}"
                if r.status_code == 429 and attempt == 0:  # free tier: about one image every 15 seconds
                    time.sleep(12)
            except requests.RequestException as e:
                last = type(e).__name__
    raise ImageError("Pollinations (free): " + last + (" - get a free key at enter.pollinations.ai and set POLLINATIONS_API_KEY" if not key else ""))


PROVIDERS = {"openai": _openai, "gemini": _gemini, "stability": _stability, "together": _together,
             "cloudflare": _cloudflare, "huggingface": _huggingface, "pollinations": _pollinations}


def available() -> list[str]:
    return [n for n in config.IMAGE_ORDER if n in PROVIDERS and (n == "pollinations" or config.IMAGE_KEYS.get(n))]


def generate(prompt: str, smart: bool = False) -> str:
    """Returns a data: URL. smart=True lets the chat AI enrich a short request first. Raises ImageError if every provider fails."""
    idea = clean_request(prompt)
    if not idea:
        raise ImageError("Empty image prompt.")
    shape = pick_shape(idea)
    final = _enhance(_smart(idea) if smart else idea)
    reasons = []
    for name in available():
        if _cool.get(name, 0) > time.time():
            continue
        try:
            return PROVIDERS[name](final, shape)
        except ImageError as e:
            reasons.append(str(e))
            if e.status in (401, 403, 404):
                _cool[name] = time.time() + 900
            elif e.status == 429:
                _cool[name] = time.time() + (600 if name == "gemini" else 60)  # Gemini free keys have no image quota
        except requests.RequestException as e:
            reasons.append(f"{name}: {type(e).__name__}")
        except (KeyError, IndexError, ValueError):
            reasons.append(f"{name}: unexpected reply")
    log.warning("image generation failed: %s", " | ".join(reasons))
    raise ImageError(" | ".join(reasons) or "No image provider is available.")