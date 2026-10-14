"""Talks to several AI providers and falls back automatically when one fails.
Messages look like {"role": "user"|"assistant", "text": str, "images": [(media_type, base64), ...]}."""
import logging
import time

import anthropic
import openai

import config

log = logging.getLogger("infinity")


class AIError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


_clients: dict = {}
_cool: dict = {}    # provider name -> (skip until, reason)
_model: dict = {}   # provider name -> model found by auto-discovery


def _client(cfg):
    c = _clients.get(cfg.name)
    if c is None:
        if cfg.name == "anthropic":
            c = anthropic.Anthropic(api_key=cfg.key, max_retries=1, timeout=60)
        else:
            c = openai.OpenAI(api_key=cfg.key, base_url=cfg.base, max_retries=1, timeout=60)
        _clients[cfg.name] = c
    return c


def _anthropic_stream(cfg, msgs, model, max_tokens):
    out = []
    for m in msgs:
        if m["role"] == "assistant":
            out.append({"role": "assistant", "content": m["text"]})
            continue
        blocks = [{"type": "image", "source": {"type": "base64", "media_type": mt, "data": d}} for mt, d in m["images"]]
        blocks.append({"type": "text", "text": m["text"]})
        out.append({"role": "user", "content": blocks if len(blocks) > 1 else m["text"]})
    with _client(cfg).messages.stream(model=model, max_tokens=max_tokens, system=config.SYSTEM_PROMPT, messages=out) as s:
        yield from s.text_stream


def _openai_stream(cfg, msgs, model, max_tokens):
    out = [{"role": "system", "content": config.SYSTEM_PROMPT}]
    for m in msgs:
        if m["role"] == "assistant":
            out.append({"role": "assistant", "content": m["text"]})
        elif m["images"] and cfg.vision:
            parts = [{"type": "image_url", "image_url": {"url": f"data:{mt};base64,{d}"}} for mt, d in m["images"]]
            parts.append({"type": "text", "text": m["text"]})
            out.append({"role": "user", "content": parts})
        else:
            note = "[The user attached an image, but you cannot see images. Say so politely.]\n" if m["images"] else ""
            out.append({"role": "user", "content": note + m["text"]})
    stream = _client(cfg).chat.completions.create(model=model, messages=out, max_tokens=max_tokens, stream=True)
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


def _run(cfg, msgs, model, deep):
    mt = config.DEEP_MAX_TOKENS if deep else config.MAX_TOKENS
    fn = _anthropic_stream if cfg.name == "anthropic" else _openai_stream
    yield from fn(cfg, msgs, model, mt)


def _classify(e):
    """-> (kind, short human reason)"""
    if isinstance(e, (openai.AuthenticationError, anthropic.AuthenticationError)):
        return "auth", "API key rejected"
    if isinstance(e, (openai.NotFoundError, anthropic.NotFoundError)):
        return "model", "model not available"
    if isinstance(e, (openai.PermissionDeniedError, anthropic.PermissionDeniedError)):
        return "perm", "key not allowed for this model or region"
    if isinstance(e, (openai.RateLimitError, anthropic.RateLimitError)):
        return "rate", "rate limit or free quota reached"
    if isinstance(e, (openai.APIConnectionError, anthropic.APIConnectionError)):
        return "conn", "could not connect"
    if isinstance(e, (openai.BadRequestError, anthropic.BadRequestError)):
        t = str(e).lower()
        if "decommission" in t or "deprecated" in t or ("model" in t and ("not exist" in t or "not found" in t or "not supported" in t)):
            return "model", "model not available"
        if "credit" in t or "billing" in t:
            return "credit", "no credit on this account"
        return "bad", "request rejected (try without the photo or with a shorter message)"
    if isinstance(e, (openai.APIStatusError, anthropic.APIStatusError)):
        return ("server", "provider service error") if getattr(e, "status_code", 0) >= 500 else ("other", f"error {getattr(e, 'status_code', '')}")
    return "other", type(e).__name__


_SKIP = ("whisper", "guard", "tts", "embed", "moderation", "orpheus", "playai", "image", "imagen", "veo", "audio", "live", "aqa")
_PREFER = ("llama-3.3-70b", "llama-3.1-70b", "llama-3.3", "llama-3.1-8b", "llama", "gpt-oss", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash", "gemini", "grok")


def _discover(cfg):
    """Ask the provider which models exist and pick a good chat model."""
    try:
        ids = [m.id.replace("models/", "") for m in _client(cfg).models.list()]
    except Exception as e:
        log.warning("model discovery failed for %s: %s", cfg.name, e)
        return None
    ids = [i for i in ids if not any(b in i.lower() for b in _SKIP)]
    if cfg.name == "openrouter":
        ids = [i for i in ids if i.endswith(":free")] or ids
    for p in _PREFER:
        for i in ids:
            if p in i.lower():
                return i
    return ids[0] if ids else None


def stream_text(msgs, deep=False):
    has_img = bool(msgs and msgs[-1].get("images"))
    order = sorted(config.ACTIVE, key=lambda c: 0 if (has_img and c.vision) else 1)
    problems = []
    for cfg in order:
        until, why = _cool.get(cfg.name, (0, ""))
        if until > time.time():
            problems.append(f"{cfg.label}: {why}")
            continue
        started = False
        retried = False
        while True:
            model = _model.get(cfg.name) or (cfg.deep if deep else cfg.model)
            try:
                for t in _run(cfg, msgs, model, deep):
                    started = True
                    yield t
                return
            except Exception as e:
                kind, why = _classify(e)
                log.warning("%s failed (%s, model %s): %s", cfg.label, kind, model, str(e)[:300])
                if started:
                    raise AIError(f"The reply was cut off ({cfg.label}: {why}). Send your message again.")
                if kind == "model" and not retried and cfg.name != "anthropic":
                    retried = True
                    found = _discover(cfg)
                    if found and found != model:
                        log.warning("%s: switching model %s -> %s", cfg.label, model, found)
                        _model[cfg.name] = found
                        continue
                secs = {"auth": 900, "model": 900, "perm": 900, "credit": 900, "rate": 60, "conn": 20, "server": 30, "bad": 0}.get(kind, 30)
                if secs:
                    _cool[cfg.name] = (time.time() + secs, why)
                problems.append(f"{cfg.label}: {why}")
                break
    raise AIError("No AI provider could answer. " + " | ".join(problems) + ". Run 'python check_key.py' to see details.")


def test_provider(cfg):
    msgs = [{"role": "user", "text": "Reply with the single word: ready", "images": []}]
    model = _model.get(cfg.name) or cfg.model
    try:
        text = "".join(_run(cfg, msgs, model, False))
        return True, f"OK  model {model} answered: {text.strip()[:40]!r}"
    except Exception as e:
        kind, why = _classify(e)
        extra = ""
        if kind == "model" and cfg.name != "anthropic":
            found = _discover(cfg)
            if found:
                extra = f"  -> Try: {cfg.name.upper()}_MODEL={found}"
        return False, f"FAILED  {why}. Details: {str(e)[:200]}{extra}"
