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


STYLE_WORDS = re.compile(r"cartoon|anime|logo|icon|illustration|painting|drawing|sketch|3d|vector|pixel|watercolor|oil|comic|minimal|flat|poster|render|clipart|sticker|manga|digital art|diagram|infographic|chart|graph|map|flowchart|mockup|wireframe|banner|sign|typography|isometric|silhouette|pattern|texture|blueprint|schematic", re.I)
REAL_WORDS = re.compile(r"photorealistic|photograph|\blens\b|\bdslr\b|\b8k\b", re.I)
REAL_SUFFIX = ", photorealistic, natural lighting, sharp focus, fine detail"
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


_STOP = set("a an the of in on at with and or to for from by is are this that it its my your into over under near some very make create image picture photo".split())


def _keeps_subject(idea: str, better: str) -> bool:
    """True if the rewritten prompt still mentions (almost) every important word of the user's request."""
    words = [w for w in re.findall(r"[a-z0-9]+", idea.lower()) if len(w) > 2 and w not in _STOP]
    if not words:
        return True
    low = better.lower()
    hit = sum(1 for w in words if w[:max(4, len(w) - 2)] in low)  # crude stemming: cars ~ car
    return hit / len(words) >= 0.6


def _verify(idea: str, url: str):
    """Asks a vision-capable chat AI whether the picture matches the request. True = good, False = bad, None = could not check."""
    if not config.IMAGE_VERIFY or not config.ACTIVE:
        return None
    try:
        import providers
        if not providers.vision_providers():
            return None
        head, b64 = url.split(",", 1)
        mime = head.split(":", 1)[1].split(";")[0]
        ask = ('You are a strict picture checker. The user asked for: "' + idea[:400] + '". Look at the picture. '
               "Reply with exactly one word. PASS if it clearly shows what was asked (right main subject, colours, number of items, setting) "
               "and has no obvious flaws such as deformed faces or hands, extra or missing limbs, melted objects or garbled text. Otherwise FAIL.")
        out = "".join(providers.stream_text([{"role": "user", "text": ask, "images": [(mime, b64)]}], False)).upper()
        if "PASS" in out and "FAIL" not in out:
            return True
        if "FAIL" in out:
            return False
    except Exception as e:
        log.info("picture check skipped: %s", str(e)[:120])
    return None


def _smart(idea: str, history=None) -> str:
    """Asks the chat AI to turn a short idea into a rich image prompt WITHOUT changing what the user asked for."""
    if not config.IMAGE_SMART_PROMPT or not config.ACTIVE:
        return idea
    ctx = ""
    if history and len(idea.split()) <= 8:  # short follow-ups such as "make it blue" need the earlier request
        ctx = "Earlier requests in this chat (context only, the newest idea below is what to draw): " + " | ".join(h[:200] for h in history[-3:]) + "\n\n"
    try:
        import providers  # local import: avoids loading the chat stack unless needed
        ask = ("Rewrite the idea below as ONE detailed English prompt for an AI image generator (50 to 100 words).\n"
               "STRICT RULES: keep EVERY subject, object, person, animal, colour, number, place, text and style the user mentioned exactly; "
               "never replace, remove or add a main subject; only add supporting detail (setting, lighting, camera angle, lens, mood, textures). "
               "If the user named a style (cartoon, anime, logo, painting, 3D, illustration, diagram, poster) keep that style; otherwise make it a realistic photograph. "
               "Put no readable text in the image unless the user asked for specific words, and then quote those words exactly. "
               "Output only the prompt inside [[IMAGE: ]].\n\n" + ctx + "Idea: " + idea)
        out = "".join(providers.stream_text([{"role": "user", "text": ask, "images": []}], False))
        m = re.search(r"\[\[IMAGE:\s*(.+?)(\]\]|$)", out, re.S)
        better = " ".join((m.group(1) if m else "").split()).strip(" \"'")
        if len(better) >= max(25, len(idea)) and _keeps_subject(idea, better):
            return better[:900]
        log.info("smart prompt rejected (it drifted from the request)")
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
    tried, last = [], None
    # the configured model first; if OpenAI has retired it, try the neighbouring GPT Image models
    for model in [config.IMAGE_MODELS["openai"], "gpt-image-2", "gpt-image-1.5", "gpt-image-1"]:
        if model in tried:
            continue
        tried.append(model)
        r = requests.post("https://api.openai.com/v1/images/generations",
                          headers={"Authorization": "Bearer " + config.IMAGE_KEYS["openai"]},
                          json={"model": model, "prompt": prompt, "size": SIZES[shape][0],
                                "quality": config.OPENAI_IMAGE_QUALITY, "n": 1}, timeout=150)
        if r.status_code == 200:
            return "data:image/png;base64," + r.json()["data"][0]["b64_json"]
        last = ImageError("OpenAI: " + _why(r), r.status_code)
        txt = r.text.lower()
        if not (r.status_code == 404 or (r.status_code == 400 and "model" in txt)):
            break
    raise last


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


def _imagen(prompt, shape):
    """Google Imagen 4 through the Gemini API (paid tier). Uses your GEMINI_API_KEY."""
    ratio = {"square": "1:1", "landscape": "4:3", "portrait": "3:4"}[shape]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.IMAGE_MODELS['imagen']}:predict"
    r = requests.post(url, headers={"x-goog-api-key": config.IMAGE_KEYS["imagen"]},
                      json={"instances": [{"prompt": prompt[:2000]}], "parameters": {"sampleCount": 1, "aspectRatio": ratio}}, timeout=150)
    if r.status_code != 200:
        raise ImageError("Imagen: " + _why(r), r.status_code)
    preds = r.json().get("predictions") or []
    if not preds or not preds[0].get("bytesBase64Encoded"):
        raise ImageError("Imagen: no image returned (it may have been blocked by safety filters)", 422)
    return f"data:{preds[0].get('mimeType') or 'image/png'};base64,{preds[0]['bytesBase64Encoded']}"


def _magichour(prompt, shape):
    """Magic Hour image API. FREE key (about 400 credits at sign-up + 100 a day, no card).
    Free-plan models: z-image-turbo, flux-2-klein, flux-schnell (about 5 credits each, realistic photos) and nano-banana (about 50 credits, most accurate)."""
    base = "https://api.magichour.ai"
    hdr = {"Authorization": "Bearer " + config.IMAGE_KEYS["magichour"], "Content-Type": "application/json"}
    ratio = {"square": "1:1", "landscape": "16:9", "portrait": "9:16"}[shape]
    models = [m.strip() for m in config.IMAGE_MODELS["magichour"].split(",") if m.strip()] or ["z-image-turbo"]
    last = ImageError("Magic Hour: no model available")
    for model in models:
        ck = "magichour:" + model
        if _cool.get(ck, 0) > time.time():
            continue
        body = {"name": "INFINITY AI image", "image_count": 1, "aspect_ratio": ratio, "model": model, "resolution": "1k",
                "style": {"prompt": prompt[:3000], "tool": "general"}}
        r = requests.post(base + "/v1/ai-image-generator", headers=hdr, json=body, timeout=60)
        if r.status_code in (400, 422):  # a setting this model does not accept: retry with the bare minimum
            r = requests.post(base + "/v1/ai-image-generator", headers=hdr, json={"image_count": 1, "model": model, "style": {"prompt": prompt[:3000]}}, timeout=60)
        if r.status_code == 401:
            raise ImageError("Magic Hour: the key was rejected. Check MAGIC_HOUR_API_KEY in backend/.env.", 401)
        if r.status_code == 402:  # no credits for this model (or the plan does not include it): try the next model
            _cool[ck] = time.time() + 600
            last = ImageError(f"Magic Hour ({model}): no credits left or not in your plan", 429)
            continue
        if r.status_code != 200 or not r.json().get("id"):
            last = ImageError(f"Magic Hour ({model}): " + _why(r), r.status_code)
            continue
        job = r.json()["id"]
        t0 = time.time()
        while time.time() - t0 < 120:
            time.sleep(3)
            p = requests.get(f"{base}/v1/image-projects/{job}", headers=hdr, timeout=30)
            if p.status_code != 200:
                last = ImageError(f"Magic Hour ({model}): " + _why(p), p.status_code)
                break
            j = p.json()
            if j.get("status") in ("error", "canceled"):
                last = ImageError(f"Magic Hour ({model}): the picture failed (credits are refunded)")
                break
            if j.get("status") == "complete":
                url = ((j.get("downloads") or [{}])[0]).get("url")
                d = requests.get(url, timeout=60) if url else None
                ctype = d.headers.get("content-type", "").split(";")[0] if d is not None else ""
                if d is not None and d.status_code == 200 and len(d.content) > 2000:
                    return f"data:{ctype if ctype.startswith('image/') else 'image/png'};base64,{base64.b64encode(d.content).decode()}"
                last = ImageError(f"Magic Hour ({model}): could not download the picture")
                break
        else:
            last = ImageError(f"Magic Hour ({model}): timed out")
    raise last


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
                      json={"prompt": prompt[:2000], "steps": 8}, timeout=120)
    if r.status_code != 200:
        raise ImageError("Cloudflare: " + _why(r), r.status_code)
    img = ((r.json().get("result") or {}).get("image")) or ""
    if len(img) < 1000:
        raise ImageError("Cloudflare: no image returned", 422)
    return "data:image/jpeg;base64," + img


def _pollinations(prompt, shape):
    """Free. Tries each model of POLLINATIONS_MODEL in order (default gptimage, then flux). A free key from enter.pollinations.ai raises limits."""
    w, h = SIZES[shape][2], SIZES[shape][3]
    key = config.IMAGE_KEYS.get("pollinations", "")
    models = [m.strip() for m in config.IMAGE_MODELS["pollinations"].split(",") if m.strip()] or ["flux"]
    last = "unknown error"
    for model in models:
        ck = "pollinations:" + model
        if _cool.get(ck, 0) > time.time():
            continue
        denied = False
        for attempt in range(2):
            for base in ("https://gen.pollinations.ai/image/", "https://image.pollinations.ai/prompt/"):
                url = (f"{base}{urllib.parse.quote(prompt[:700])}?width={w}&height={h}&seed={random.randint(1, 1_000_000)}"
                       f"&nologo=true&model={model}")
                hdr = {"User-Agent": "INFINITY-AI/1.0"}
                if key:
                    url += "&key=" + urllib.parse.quote(key)
                    hdr["Authorization"] = "Bearer " + key
                try:
                    r = requests.get(url, timeout=120, headers=hdr)
                    ctype = r.headers.get("content-type", "").split(";")[0]
                    if r.status_code == 200 and ctype.startswith("image/") and len(r.content) > 2000:
                        return f"data:{ctype};base64,{base64.b64encode(r.content).decode()}"
                    last = f"{model}: HTTP {r.status_code}"
                    if r.status_code in (401, 402, 403):  # this model needs a key or credits: go to the next model
                        denied = True
                        break
                    if r.status_code == 429 and attempt == 0:  # free tier: about one image every 15 seconds
                        time.sleep(12)
                except requests.RequestException as e:
                    last = f"{model}: {type(e).__name__}"
            if denied:
                _cool[ck] = time.time() + 900
                break
    raise ImageError("Pollinations (free): " + last + ("" if key else " - a free key from enter.pollinations.ai (POLLINATIONS_API_KEY) unlocks better models"))


PROVIDERS = {"openai": _openai, "gemini": _gemini, "imagen": _imagen, "magichour": _magichour, "stability": _stability, "together": _together,
             "cloudflare": _cloudflare, "huggingface": _huggingface, "pollinations": _pollinations}


def available() -> list[str]:
    return [n for n in config.IMAGE_ORDER if n in PROVIDERS and (n == "pollinations" or config.IMAGE_KEYS.get(n))]


def generate_ex(prompt: str, smart: bool = False, history=None):
    """Returns (data: URL, provider name). smart=True lets the chat AI enrich a short request first.
    Every picture is checked by a vision AI (if you have one); a bad picture is regenerated, up to IMAGE_MAX_TRIES times."""
    idea = clean_request(prompt)
    if not idea:
        raise ImageError("Empty image prompt.")
    shape = pick_shape(idea)
    final = _enhance(_smart(idea, history) if smart else idea)
    reasons, tries, rejected = [], 0, None
    for name in available():
        if _cool.get(name, 0) > time.time():
            continue
        for _rep in range(2):  # a second try with the same provider gets a new random seed
            if tries >= config.IMAGE_MAX_TRIES:
                break
            t0 = time.time()
            try:
                url = PROVIDERS[name](final, shape)
                tries += 1
            except ImageError as e:
                reasons.append(str(e))
                if e.status in (401, 403, 404):
                    _cool[name] = time.time() + 900
                elif e.status == 429:
                    _cool[name] = time.time() + (600 if name == "gemini" else 60)  # Gemini free keys have no image quota
                break
            except requests.RequestException as e:
                reasons.append(f"{name}: {type(e).__name__}")
                break
            except (KeyError, IndexError, ValueError):
                reasons.append(f"{name}: unexpected reply")
                break
            ok = _verify(idea, url)
            print(f"[INFINITY AI] Image by {name} in {time.time() - t0:.0f}s - picture check: "
                  f"{'PASSED' if ok else 'REJECTED, trying again' if ok is False else 'not checked'}")
            if ok is not False:
                return url, name
            rejected = rejected or (url, name)
        if tries >= config.IMAGE_MAX_TRIES:
            break
    if rejected:  # nothing passed the check: still return the first picture rather than nothing
        return rejected
    log.warning("image generation failed: %s", " | ".join(reasons))
    raise ImageError(" | ".join(reasons) or "No image provider is available.")


def generate(prompt: str, smart: bool = False, history=None) -> str:
    return generate_ex(prompt, smart, history)[0]


LABELS = {"openai": "OpenAI GPT Image", "gemini": "Google Gemini image model", "imagen": "Google Imagen", "stability": "Stability AI",
          "together": "Together FLUX", "cloudflare": "Cloudflare FLUX (free)", "huggingface": "Hugging Face FLUX",
          "pollinations": "Pollinations (free)", "magichour": "Magic Hour (free credits)"}


def label(name: str) -> str:
    return LABELS.get(name, name)