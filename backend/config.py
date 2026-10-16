import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env", override=True)


def _clean(v: str) -> str:
    return (v or "").strip().strip('"').strip("'").strip()


@dataclass
class Prov:
    name: str
    label: str
    base: str
    key: str
    model: str
    deep: str
    vision: bool
    vision_model: str = ""


# env = name of the .env variable that holds the key
PRESETS = {
    "gemini": dict(label="Google Gemini", base="https://generativelanguage.googleapis.com/v1beta/openai/",
                   model="gemini-2.5-flash", deep="gemini-2.5-flash", prefix="AIza", vision=True, env="GEMINI_API_KEY"),
    "groq": dict(label="Groq (Llama)", base="https://api.groq.com/openai/v1",
                 model="llama-3.3-70b-versatile", deep="llama-3.3-70b-versatile", prefix="gsk_", vision=True, vision_model="meta-llama/llama-4-scout-17b-16e-instruct", env="GROQ_API_KEY"),
    "openrouter": dict(label="OpenRouter", base="https://openrouter.ai/api/v1",
                       model="openai/gpt-oss-120b:free", deep="openai/gpt-oss-120b:free", prefix="sk-or-", vision=False, env="OPENROUTER_API_KEY"),
    "grok": dict(label="xAI Grok", base="https://api.x.ai/v1",
                 model="grok-4.3", deep="grok-4.3", prefix="xai-", vision=True, env="XAI_API_KEY"),
    "openai": dict(label="OpenAI (GPT)", base="https://api.openai.com/v1",
                   model="gpt-4.1", deep="gpt-4.1", prefix="sk-", vision=True, env="OPENAI_API_KEY"),
    "anthropic": dict(label="Anthropic Claude", base="",
                      model="claude-sonnet-5-5", deep="claude-opus-5-5", prefix="sk-ant-", vision=True, env="ANTHROPIC_API_KEY"),
    "ollama": dict(label="Ollama (on your PC)", base="http://localhost:11434/v1",
                   model="llama3.2", deep="llama3.2", prefix="", vision=False, env=""),
}
PLACEHOLDERS = ("your-key", "your_key", "paste", "full-key", "here", "xxxx")

# Old single-provider settings still work.
LEGACY = _clean(os.getenv("AI_PROVIDER", "")).lower()
LEGACY_KEY = _clean(os.getenv("AI_API_KEY", ""))
order_env = _clean(os.getenv("AI_PROVIDERS", ""))
if order_env:
    names = [n.strip().lower() for n in order_env.split(",") if n.strip()]
else:
    names = [LEGACY] if LEGACY in PRESETS else []
    names += [n for n in ("anthropic", "openai", "gemini", "grok", "groq", "openrouter") if n not in names]

ACTIVE: list[Prov] = []
PROBLEMS: list[str] = []
for n in names:
    if n not in PRESETS:
        PROBLEMS.append(f"Unknown provider '{n}' in AI_PROVIDERS.")
        continue
    p = PRESETS[n]
    key = _clean(os.getenv(p["env"], "")) if p["env"] else "ollama"
    if not key and n == LEGACY:
        key = LEGACY_KEY
    if not key:
        continue
    if p["env"] and any(w in key.lower() for w in PLACEHOLDERS):
        PROBLEMS.append(f"{p['label']}: the key in .env is still placeholder text.")
        continue
    if p["prefix"] and not key.startswith(p["prefix"]):
        PROBLEMS.append(f"{p['label']}: keys start with {p['prefix']} but yours does not. Copy the full key again.")
        continue
    up = n.upper()
    model = _clean(os.getenv(f"{up}_MODEL", "")) or (_clean(os.getenv("MODEL", "")) if n == LEGACY else "") or p["model"]
    deep = _clean(os.getenv(f"{up}_DEEP_MODEL", "")) or (_clean(os.getenv("DEEP_MODEL", "")) if n == LEGACY else "") or p["deep"]
    vmodel = _clean(os.getenv(f"{up}_VISION_MODEL", "")) or p.get("vision_model", "")
    ACTIVE.append(Prov(n, p["label"], p["base"], key, model, deep, p["vision"], vmodel))

KEY_PROBLEM = ""
if not ACTIVE:
    KEY_PROBLEM = "No AI key found in backend/.env. Add GROQ_API_KEY or GEMINI_API_KEY (see README). " + " ".join(PROBLEMS)

GOOGLE_CLIENT_ID = _clean(os.getenv("GOOGLE_CLIENT_ID", ""))

# Image generation: tried in this order; "pollinations" is the free fallback and needs no key.
IMAGE_KEYS = {
    "openai": _clean(os.getenv("OPENAI_API_KEY", "")),
    "gemini": _clean(os.getenv("GEMINI_API_KEY", "")),
    "together": _clean(os.getenv("TOGETHER_API_KEY", "")),
}
IMAGE_MODELS = {
    "openai": _clean(os.getenv("OPENAI_IMAGE_MODEL", "")) or "gpt-image-1",
    "gemini": _clean(os.getenv("GEMINI_IMAGE_MODEL", "")) or "gemini-2.5-flash-image",
    "together": _clean(os.getenv("TOGETHER_IMAGE_MODEL", "")) or "black-forest-labs/FLUX.1-schnell",
}
OPENAI_IMAGE_QUALITY = _clean(os.getenv("OPENAI_IMAGE_QUALITY", "")) or "medium"
IMAGE_ORDER = [n.strip().lower() for n in (_clean(os.getenv("IMAGE_PROVIDERS", "")) or "openai,gemini,together,pollinations").split(",") if n.strip()]

JWT_SECRET = _clean(os.getenv("JWT_SECRET", ""))
if len(JWT_SECRET) < 24:  # no setup needed: make one and remember it
    f = HERE / ".jwt_secret"
    if f.exists() and len(f.read_text().strip()) >= 24:
        JWT_SECRET = f.read_text().strip()
    else:
        JWT_SECRET = secrets.token_urlsafe(48)
        f.write_text(JWT_SECRET)

JWT_DAYS = int(os.getenv("JWT_DAYS", "14"))
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./infinity.db")
DAILY_LIMIT = int(os.getenv("DAILY_LIMIT", "200"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "2048"))
DEEP_MAX_TOKENS = int(os.getenv("DEEP_MAX_TOKENS", "4096"))

SYSTEM_PROMPT = (
    "You are INFINITY AI, a friendly, expert voice and text assistant created by Sarath Chandra. "
    "Answer any question clearly and accurately. Keep spoken-style answers concise unless asked for detail. "
    "Use Markdown (short lists, fenced code with a language) when useful. "
    "Analyse attached images and files as asked. Reply in the language the user writes or speaks in. "
    "If the user asks you to create, generate, draw or design an image, picture, logo, poster or other visual, "
    "reply with one short friendly sentence, then on a new last line write exactly "
    "[[IMAGE: a detailed English description of the image]] and nothing after it. Never say you cannot make images. "
    "Write image descriptions that are specific and photorealistic unless the user asks for another style: "
    "subject, setting, lighting, camera and lens, mood. "
    "When asked for a document, report, letter, resume or similar, write the complete document in clean Markdown "
    "that starts with a '# Title' line (the app shows a Word download button under every answer). "
    "Never claim to be human. If asked which model or company is behind you, say you are INFINITY AI, "
    "created by Sarath Chandra, and that you cannot share details of the underlying model."
)