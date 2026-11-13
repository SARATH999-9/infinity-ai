
"""
Video generation for INFINITY AI.

Providers are tried in VIDEO_ORDER:
    veo          Google Gemini Omni Flash video generation.
    magichour    Magic Hour video generation.
    pollinations Pollinations video models.

generate() yields:
    {"wait": seconds} while generating
    {"url": "/media/video/xxxx.mp4", "provider": name} when complete.
"""

import base64
import concurrent.futures as cf
import logging
import re
import secrets
import time
import urllib.parse
from pathlib import Path

import requests

import config
import images

log = logging.getLogger("infinity.video")

ROOT = Path(__file__).resolve().parent / "media"
DIR = ROOT / "video"
DIR.mkdir(parents=True, exist_ok=True)

POOL = cf.ThreadPoolExecutor(max_workers=3)
MAX_WAIT = 480

# Current Google video-generation model.
# Veo 3.1 Gemini API was shut down on October 22, 2026.
GEMINI_VIDEO_MODEL = "gemini-omni-1.1-flash"

_cool: dict = {}


class VideoError(Exception):
    def __init__(self, msg, status=0):
        super().__init__(msg)
        self.status = status


def _names(value):
    """Convert comma-separated strings or lists into provider/model names."""
    if isinstance(value, str):
        return [
            x.strip().lower()
            for x in value.split(",")
            if x.strip()
        ]

    return [
        str(x).strip().lower()
        for x in (value or [])
        if str(x).strip()
    ]


def _why(r) -> str:
    try:
        j = r.json()

        error = j.get("error")

        if isinstance(error, dict):
            msg = error.get("message") or error.get("status")
        else:
            msg = error or j.get("message")

        return f"HTTP {r.status_code}: {str(msg or 'Unknown error')[:200]}"

    except (ValueError, AttributeError):
        return f"HTTP {r.status_code}"


_REQ = re.compile(
    r"^\s*(please\s+)?((can|could|would)\s+you\s+)?"
    r"(generate|create|make|produce|animate)\s+(me\s+)?"
    r"(an?\s+|the\s+|some\s+)?"
    r"(?:[\w-]+\s+){0,3}?"
    r"(video|clip|animation)s?\s+"
    r"(of|for|showing|about|where|that|with)\s+",
    re.I | re.S
)


def clean_request(text: str) -> str:
    t = " ".join((text or "").split())
    m = _REQ.match(t)

    if m and len(t) > m.end():
        rest = t[m.end():]

        # Group 7 is the video type: video, clip, or animation.
        if m.group(7).lower() == "animation":
            return "an animated video of " + rest

        return rest

    return t


def pick_aspect(p: str) -> str:
    return (
        "9:16"
        if re.search(
            r"reel|story|stories|vertical|9:16|portrait|tiktok|shorts|phone|mobile",
            p,
            re.I
        )
        else "16:9"
    )


def _snap(sec: int) -> int:
    """Snap duration to a supported Veo-style duration."""
    return min((4, 6, 8), key=lambda x: abs(x - sec))


def _smart(idea: str, history=None) -> str:
    """Expand a short idea into a detailed video prompt."""

    if not config.IMAGE_SMART_PROMPT or not config.ACTIVE:
        return idea

    ctx = ""

    if history and len(idea.split()) <= 8:
        ctx = (
            "Earlier requests in this chat (context only): "
            + " | ".join(h[:200] for h in history[-3:])
            + "\n\n"
        )

    try:
        import providers

        ask = (
            "Rewrite the idea below as ONE detailed English prompt "
            "for an AI video generator (40 to 90 words). "
            "STRICT RULES: keep EVERY subject, object, person, animal, "
            "colour, place and style the user mentioned; never replace "
            "or add a main subject. Describe the main action and motion, "
            "the camera movement, lighting, setting and mood, as one "
            "continuous shot. Make it a realistic cinematic video "
            "unless another style is named. No on-screen text. "
            "Output only the prompt inside [[IMAGE: ]].\n\n"
            + ctx
            + "Idea: "
            + idea
        )

        out = "".join(
            providers.stream_text(
                [{"role": "user", "text": ask, "images": []}],
                False
            )
        )

        m = re.search(r"\[\[IMAGE:\s*(.+?)(\]\]|$)", out, re.S)

        better = " ".join(
            (m.group(1) if m else "").split()
        ).strip(" \"'")

        if (
            len(better) >= max(25, len(idea))
            and images._keeps_subject(idea, better)
        ):
            return better[:900]

    except Exception as e:
        log.info(
            "Video prompt rewrite skipped: %s",
            str(e)[:120]
        )

    return idea


def available() -> list:
    """Return configured video providers."""

    order = _names(config.VIDEO_ORDER)

    return [
        n for n in order
        if n in PROVIDERS and config.VIDEO_KEYS.get(n)
    ]


def _save(data: bytes) -> str:
    """Save generated MP4 and return its public media URL."""

    if not data:
        raise VideoError("The video provider returned an empty file.")

    name = (
        secrets.token_urlsafe(12).replace("-", "a").replace("_", "b")
        + ".mp4"
    )

    path = DIR / name
    path.write_bytes(data)

    cutoff = time.time() - config.VIDEO_KEEP_DAYS * 86400

    for f in DIR.glob("*.mp4"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
        except OSError:
            pass

    return "/media/video/" + name


# --------------------------------------------------
# GOOGLE GEMINI OMNI FLASH
# --------------------------------------------------

def _veo(prompt, aspect):
    """
    Generate an MP4 using Google's Gemini Omni Flash Interactions API.

    The Google GenAI SDK returns base64 video data in:
        interaction.output_video.data
    """

    api_key = config.VIDEO_KEYS.get("veo")

    if not api_key:
        raise VideoError("Google Gemini video API key is missing.")

    # Let the frontend know that generation has started.
    yield {"wait": 0}

    try:
        from google import genai

        client = genai.Client(api_key=api_key)

        interaction = client.interactions.create(
            model=GEMINI_VIDEO_MODEL,
            input=prompt[:3000],
            response_format={
                "type": "video",
                "aspect_ratio": aspect
            }
        )

        output_video = getattr(
            interaction,
            "output_video",
            None
        )

        video_data = getattr(
            output_video,
            "data",
            None
        ) if output_video else None

        if not video_data:
            raise VideoError(
                "Gemini returned no video data. "
                "Check the API response and model access."
            )

        try:
            video_bytes = base64.b64decode(video_data)
        except Exception as e:
            raise VideoError(
                "Gemini returned invalid video data: " + str(e)[:150]
            )

        if not video_bytes:
            raise VideoError("Gemini returned an empty video.")

        return video_bytes

    except VideoError:
        raise

    except Exception as e:
        message = str(e)[:250]
        status = getattr(e, "code", 0)

        try:
            status = int(status)
        except (TypeError, ValueError):
            status = 0

        raise VideoError(
            "Google Gemini video: " + message,
            status
        )


# --------------------------------------------------
# MAGIC HOUR
# --------------------------------------------------

def _magichour(prompt, aspect):
    base = "https://api.magichour.ai"

    api_key = config.VIDEO_KEYS.get("magichour")

    if not api_key:
        raise VideoError("Magic Hour API key is missing.")

    hdr = {
        "Authorization": "Bearer " + api_key,
        "Content-Type": "application/json"
    }

    body = {
        "name": "INFINITY AI video",
        "end_seconds": config.MAGIC_HOUR_SECONDS,
        "aspect_ratio": aspect,
        "resolution": config.MAGIC_HOUR_RESOLUTION,
        "style": {
            "prompt": prompt[:3000]
        }
    }

    if config.MAGIC_HOUR_MODEL != "default":
        body["model"] = config.MAGIC_HOUR_MODEL

    r = requests.post(
        base + "/v1/text-to-video",
        headers=hdr,
        json=body,
        timeout=60
    )

    if r.status_code in (400, 422):
        body = {
            "end_seconds": config.MAGIC_HOUR_SECONDS,
            "aspect_ratio": aspect,
            "style": {
                "prompt": prompt[:3000]
            }
        }

        r = requests.post(
            base + "/v1/text-to-video",
            headers=hdr,
            json=body,
            timeout=60
        )

    if r.status_code == 401:
        raise VideoError(
            "Magic Hour: the key was rejected. "
            "Check MAGIC_HOUR_API_KEY in backend/.env.",
            401
        )

    if r.status_code == 402:
        raise VideoError(
            "Magic Hour: no credits left.",
            429
        )

    if r.status_code != 200:
        raise VideoError(
            "Magic Hour: " + _why(r),
            r.status_code
        )

    job = r.json().get("id")

    if not job:
        raise VideoError("Magic Hour: no job ID returned.")

    t0 = time.time()

    while True:
        yield {"wait": time.time() - t0}

        if time.time() - t0 > MAX_WAIT:
            raise VideoError("Magic Hour: timed out.")

        time.sleep(6)

        p = requests.get(
            f"{base}/v1/video-projects/{job}",
            headers=hdr,
            timeout=30
        )

        if p.status_code != 200:
            raise VideoError(
                "Magic Hour: " + _why(p),
                p.status_code
            )

        j = p.json()
        st = j.get("status")

        if st in ("error", "canceled"):
            e = j.get("error") or {}

            message = (
                e.get("message")
                if isinstance(e, dict)
                else None
            )

            raise VideoError(
                "Magic Hour: " + (message or "the video failed")
            )

        if st == "complete":
            dl = (
                (j.get("downloads") or [{}])[0].get("url")
            )

            if not dl:
                raise VideoError(
                    "Magic Hour: finished but no download link was returned."
                )

            d = requests.get(
                dl,
                timeout=240,
                allow_redirects=True
            )

            if d.status_code != 200 or not d.content:
                raise VideoError(
                    "Magic Hour: could not download the finished video.",
                    d.status_code
                )

            return d.content


# --------------------------------------------------
# POLLINATIONS
# --------------------------------------------------

def _pollinations(prompt, aspect):
    key = config.VIDEO_KEYS.get("pollinations")

    if not key:
        raise VideoError("Pollinations API key is missing.")

    last = "no video model available"

    models = _names(config.POLLINATIONS_VIDEO_MODELS)

    for model in models:
        ck = "pollinations:" + model

        if _cool.get(ck, 0) > time.time():
            continue

        secs = (
            _snap(config.VIDEO_SECONDS)
            if model == "veo"
            else min(max(config.VIDEO_SECONDS, 2), 10)
        )

        url = (
            "https://gen.pollinations.ai/image/"
            + urllib.parse.quote(prompt[:900])
        )

        params = {
            "model": model,
            "duration": secs,
            "aspectRatio": aspect,
            "key": key
        }

        fut = POOL.submit(
            lambda u=url, p=params: requests.get(
                u,
                params=p,
                headers={
                    "Authorization": "Bearer " + key,
                    "User-Agent": "INFINITY-AI/1.0"
                },
                timeout=MAX_WAIT
            )
        )

        t0 = time.time()

        while not fut.done():
            yield {"wait": time.time() - t0}
            time.sleep(5)

        try:
            r = fut.result()

        except requests.RequestException as e:
            last = f"{model}: {type(e).__name__}"
            continue

        ctype = r.headers.get(
            "content-type", ""
        ).split(";")[0]

        if (
            r.status_code == 200
            and ctype.startswith("video/")
            and r.content
        ):
            return r.content

        last = f"{model}: {_why(r)}"

        if r.status_code in (401, 402, 403, 404):
            _cool[ck] = time.time() + 900

    raise VideoError("Pollinations: " + last)


# --------------------------------------------------
# PROVIDER REGISTRY
# --------------------------------------------------

PROVIDERS = {
    "veo": _veo,
    "magichour": _magichour,
    "pollinations": _pollinations
}

LABELS = {
    "veo": "Google Gemini Omni Flash",
    "magichour": "Magic Hour",
    "pollinations": "Pollinations video"
}


# --------------------------------------------------
# MAIN VIDEO GENERATION
# --------------------------------------------------

def generate(prompt: str, history=None, smart: bool = True):
    idea = clean_request(prompt)

    if not idea:
        raise VideoError("Empty video prompt.")

    aspect = pick_aspect(idea)

    final = _smart(idea, history) if smart else idea

    reasons = []

    for name in available():

        if _cool.get(name, 0) > time.time():
            continue

        t0 = time.time()

        try:
            data = yield from PROVIDERS[name](final, aspect)

        except VideoError as e:
            reasons.append(str(e))

            if e.status in (401, 403, 404):
                _cool[name] = time.time() + 900

            elif e.status == 429:
                _cool[name] = time.time() + 120

            continue

        except requests.RequestException as e:
            reasons.append(
                f"{name}: {type(e).__name__}"
            )
            continue

        except Exception as e:
            log.exception("Unexpected video provider error: %s", name)
            reasons.append(
                f"{name}: {str(e)[:180]}"
            )
            continue

        if not data:
            reasons.append(
                f"{name}: generated video is empty"
            )
            continue

        url = _save(data)

        print(
            f"[INFINITY AI] Video by {name} "
            f"in {time.time() - t0:.0f}s "
            f"({len(data) // 1024} KB)"
        )

        yield {
            "url": url,
            "provider": name
        }

        return

    log.warning(
        "Video generation failed: %s",
        " | ".join(reasons)
    )

    raise VideoError(
        " | ".join(reasons)
        or "No video provider is configured."
    )
