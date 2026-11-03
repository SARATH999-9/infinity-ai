"""Checks backend/.env and adds the settings it is missing.

   python check_env.py          -> only reports (changes nothing)
   python check_env.py --recommended -> applies the safe settings for a FREE setup (backup first) and removes duplicate lines
   python check_env.py --fix    -> also adds missing lines at the end of .env (a backup .env.bak is saved first;
                                   your existing lines and keys are never changed or deleted)
Secret values are never printed in full."""
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENV = HERE / ".env"
FIX = "--fix" in sys.argv
REC = "--recommended" in sys.argv
BACKED_UP = False


def backup():
    global BACKED_UP
    if not BACKED_UP:
        shutil.copy(ENV, ENV.with_name(".env.bak"))
        BACKED_UP = True

# name, line to add when missing, group, note.   "# NAME=..." lines are optional settings added commented-out.
CATALOG = [
    ("GROQ_API_KEY", "GROQ_API_KEY=", "AI text", "free key: console.groq.com/keys"),
    ("GEMINI_API_KEY", "GEMINI_API_KEY=", "AI text", "free key: aistudio.google.com/app/apikey (also lets the app check pictures)"),
    ("OPENAI_API_KEY", "OPENAI_API_KEY=", "AI text", "optional, paid: better answers and gpt-image-2 pictures"),
    ("ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY=", "AI text", "optional, paid"),
    ("OPENROUTER_API_KEY", "OPENROUTER_API_KEY=", "AI text", "optional, free models available"),
    ("XAI_API_KEY", "XAI_API_KEY=", "AI text", "optional, paid"),
    ("AI_PROVIDERS", "# AI_PROVIDERS=openai,gemini,groq", "AI text", "optional: which AI to try first"),
    ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_ID=", "Google sign-in", "ends with .apps.googleusercontent.com"),
    ("JWT_SECRET", "# JWT_SECRET=type-a-long-random-text-of-40-characters-or-more", "Security", "set this on the server so logins survive restarts"),
    ("DATABASE_URL", "# DATABASE_URL=postgresql://user:password@host/dbname", "Database", "server only (Render Postgres); leave commented on your PC"),
    ("DAILY_LIMIT", "DAILY_LIMIT=200", "Plans", ""),
    ("FREE_DAILY_LIMIT", "FREE_DAILY_LIMIT=25", "Plans", "messages per day on the Free plan"),
    ("PRO_DAILY_LIMIT", "PRO_DAILY_LIMIT=200", "Plans", "messages per day on Pro"),
    ("PRO_PRICE_PAISE", "PRO_PRICE_PAISE=100", "Plans", "100 paise = Rs 1"),
    ("PRO_DAYS", "PRO_DAYS=30", "Plans", "days of Pro per payment"),
    ("RAZORPAY_KEY_ID", "RAZORPAY_KEY_ID=", "Razorpay", "starts with rzp_test_ (test) or rzp_live_"),
    ("RAZORPAY_KEY_SECRET", "RAZORPAY_KEY_SECRET=", "Razorpay", "the secret that goes with the key id"),
    ("RAZORPAY_WEBHOOK_SECRET", "RAZORPAY_WEBHOOK_SECRET=", "Razorpay", "only needed on the server (Dashboard > Webhooks)"),
    ("CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_ACCOUNT_ID=", "Images", "32 letters/numbers from the Cloudflare dashboard URL (NOT your email)"),
    ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_API_TOKEN=", "Images", "token with the Workers AI permission"),
    ("STABILITY_API_KEY", "# STABILITY_API_KEY=", "Images", "optional, paid"),
    ("TOGETHER_API_KEY", "# TOGETHER_API_KEY=", "Images", "optional, cheap FLUX images"),
    ("HF_TOKEN", "# HF_TOKEN=", "Images", "optional, Hugging Face"),
    ("POLLINATIONS_API_KEY", "# POLLINATIONS_API_KEY=", "Images", "optional, free key from enter.pollinations.ai"),
    ("IMAGE_PROVIDERS", "# IMAGE_PROVIDERS=openai,gemini,imagen,stability,together,magichour,cloudflare,huggingface,pollinations", "Images", "optional: order of image providers"),
    ("OPENAI_IMAGE_MODEL", "# OPENAI_IMAGE_MODEL=gpt-image-2", "Images", "optional"),
    ("OPENAI_IMAGE_QUALITY", "# OPENAI_IMAGE_QUALITY=medium", "Images", "low | medium | high"),
    ("POLLINATIONS_MODEL", "# POLLINATIONS_MODEL=gptimage,flux", "Images", "optional: Pollinations image models in order (nanobanana, seedream, gptimage, flux)"),
    ("IMAGEN_MODEL", "# IMAGEN_MODEL=imagen-4.0-fast-generate-001", "Images", "optional: Google Imagen (paid Gemini key)"),
    ("IMAGE_SHOW_PROVIDER", "IMAGE_SHOW_PROVIDER=1", "Images", "1 = show 'Made with ...' under each picture"),
    ("MAGIC_HOUR_API_KEY", "MAGIC_HOUR_API_KEY=", "Video", "FREE key from magichour.ai/developer (about 400 credits + 100 a day, no card): images AND videos"),
    ("MAGIC_HOUR_IMAGE_MODELS", "# MAGIC_HOUR_IMAGE_MODELS=z-image-turbo,flux-2-klein", "Images", "free-plan image models in order (nano-banana is the most accurate)"),
    ("MAGIC_HOUR_SECONDS", "MAGIC_HOUR_SECONDS=4", "Video", "length of each Magic Hour clip"),
    ("VIDEO_PROVIDERS", "# VIDEO_PROVIDERS=veo,magichour,pollinations", "Video", "optional: order of video providers"),
    ("VEO_MODEL", "# VEO_MODEL=veo-3.1-lite-generate-preview", "Video", "Google Veo model (uses GEMINI_API_KEY with billing); cheapest is the lite model"),
    ("POLLINATIONS_VIDEO_MODEL", "# POLLINATIONS_VIDEO_MODEL=seedance,veo", "Video", "optional: Pollinations video models (needs POLLINATIONS_API_KEY)"),
    ("VIDEO_SECONDS", "VIDEO_SECONDS=6", "Video", "length of each clip in seconds (Veo: 4, 6 or 8)"),
    ("FREE_VIDEO_LIMIT", "FREE_VIDEO_LIMIT=0", "Video", "videos per day on Free (0 = Pro only)"),
    ("PRO_VIDEO_LIMIT", "PRO_VIDEO_LIMIT=3", "Video", "videos per day on Pro (each one costs real money)"),
    ("IMAGE_VERIFY", "IMAGE_VERIFY=1", "Images", "1 = a vision AI checks every picture and redraws wrong ones"),
    ("IMAGE_MAX_TRIES", "IMAGE_MAX_TRIES=3", "Images", "most pictures made per request"),
    ("IMAGE_SMART_PROMPT", "IMAGE_SMART_PROMPT=1", "Images", "1 = the AI expands short image requests"),
]
NUMERIC = {"MAGIC_HOUR_SECONDS", "VIDEO_SECONDS", "FREE_VIDEO_LIMIT", "PRO_VIDEO_LIMIT", "VIDEO_KEEP_DAYS", "DAILY_LIMIT", "FREE_DAILY_LIMIT", "PRO_DAILY_LIMIT", "PRO_PRICE_PAISE", "PRO_DAYS", "IMAGE_MAX_TRIES", "JWT_DAYS", "MAX_TOKENS", "DEEP_MAX_TOKENS"}
PREFIX = {"GROQ_API_KEY": "gsk_", "GEMINI_API_KEY": "AIza", "OPENAI_API_KEY": "sk-", "ANTHROPIC_API_KEY": "sk-ant-",
          "OPENROUTER_API_KEY": "sk-or-", "XAI_API_KEY": "xai-"}
AI_KEYS = ["GROQ_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY", "XAI_API_KEY"]


def mask(v):
    return "(empty)" if not v else (v[:4] + "..." + v[-2:] if len(v) > 10 else v[:2] + "***")


def parse(text):
    vals, dups = {}, []
    for line in text.splitlines():
        m = re.match(r"^\s*([A-Z][A-Z0-9_]*)\s*=(.*)$", line)
        if m:
            k, v = m.group(1), m.group(2)
            if "#" in v and not v.strip().startswith(('"', "'")):
                v = v.split("#", 1)[0]
            if k in vals:
                dups.append(k)
            vals[k] = v
    return vals, dups


print()
if not ENV.exists():
    print(f"No .env file found at {ENV}")
    if FIX:
        shutil.copy(HERE / ".env.example", ENV) if (HERE / ".env.example").exists() else ENV.write_text("")
        print("Created a new .env from .env.example. Open it, fill in your keys, then run this check again.")
    else:
        print("Run  python check_env.py --fix  to create one, or copy .env.example to .env.")
    raise SystemExit(1)

text = ENV.read_text(encoding="utf-8-sig", errors="replace")
if REC:
    SET = {"IMAGE_PROVIDERS": "magichour,cloudflare,pollinations", "MAGIC_HOUR_SECONDS": "4", "IMAGE_MAX_TRIES": "2",
           "FREE_VIDEO_LIMIT": "1", "PRO_VIDEO_LIMIT": "2"}
    lines, done = text.splitlines(), []
    pat = lambda k: re.compile(r"^\s*" + k + r"\s*=")
    keys = {m.group(1) for ln in lines for m in [re.match(r"^\s*([A-Z][A-Z0-9_]*)\s*=", ln)] if m}
    for k in sorted(keys):  # duplicates: keep the LAST line, comment out the earlier ones
        idx = [i for i, ln in enumerate(lines) if pat(k).match(ln)]
        for i in idx[:-1]:
            lines[i] = "# (duplicate, disabled by check_env.py) " + lines[i].lstrip()
            done.append(f"{k}: disabled an extra earlier line")
    for k, v in SET.items():  # recommended values
        idx = [i for i, ln in enumerate(lines) if pat(k).match(ln)]
        if idx:
            old = lines[idx[-1]].split("=", 1)[1].split("#", 1)[0].strip()
            if old != v:
                lines[idx[-1]] = f"{k}={v}"
                done.append(f"{k}: {old or '(empty)'} -> {v}")
        else:
            lines.append(f"{k}={v}")
            done.append(f"{k}: added {v}")
    for k, bad in (("XAI_API_KEY", lambda v: v and not v.startswith("xai-")), ("STABILITY_API_KEY", lambda v: v.startswith("sk-or-"))):
        for i, ln in enumerate(lines):
            m = pat(k).match(ln)
            if m and bad(ln.split("=", 1)[1].split("#", 1)[0].strip().strip('"').strip("'")):
                lines[i] = "# (does not look like a " + k.split("_")[0].title() + " key, disabled by check_env.py) " + ln.lstrip()
                done.append(f"{k}: disabled (the value is not a valid key for this service)")
    if done:
        backup()
        ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")
        text = "\n".join(lines) + "\n"
        print("Applied recommended settings (your original is saved as .env.bak):")
        for d in done:
            print("  -", d)
        print()
    else:
        print("Nothing to change: your .env already has the recommended settings.\n")
vals, dups = parse(text)
clean = {k: v.strip().strip('"').strip("'").strip() for k, v in vals.items()}
problems, warns = [], []
print(f"Checking {ENV}\n")

# --- AI text
have_ai = [k for k in AI_KEYS if clean.get(k)]
if not have_ai:
    problems.append("No AI key found. Add at least one: GROQ_API_KEY or GEMINI_API_KEY (both are free).")
for k in have_ai:
    if k != "XAI_API_KEY" and clean[k][: len(PREFIX[k])] != PREFIX[k]:
        warns.append(f"{k} should start with {PREFIX[k]} - copy the whole key again.")
if "GEMINI_API_KEY" not in have_ai and "GROQ_API_KEY" not in have_ai:
    warns.append("No Gemini or Groq key: the app cannot check generated pictures or read photos and PDFs.")

# --- Google
g = clean.get("GOOGLE_CLIENT_ID", "")
if not g:
    warns.append("GOOGLE_CLIENT_ID is empty: the Google sign-in button will not work.")
elif not g.endswith(".apps.googleusercontent.com"):
    warns.append("GOOGLE_CLIENT_ID should end with .apps.googleusercontent.com")

# --- Razorpay
rid, rsec = clean.get("RAZORPAY_KEY_ID", ""), clean.get("RAZORPAY_KEY_SECRET", "")
if rid or rsec:
    if not (rid and rsec):
        problems.append("Razorpay needs BOTH RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET.")
    elif not rid.startswith(("rzp_test_", "rzp_live_")):
        warns.append("RAZORPAY_KEY_ID should start with rzp_test_ or rzp_live_.")
else:
    warns.append("Razorpay keys are empty: the Upgrade plan payment will say 'not set up'.")
if rid.startswith("rzp_live_") and not clean.get("RAZORPAY_WEBHOOK_SECRET"):
    warns.append("Live Razorpay mode: also set RAZORPAY_WEBHOOK_SECRET and add the webhook in the Razorpay dashboard.")

# --- Cloudflare
cid, ctok = clean.get("CLOUDFLARE_ACCOUNT_ID", ""), clean.get("CLOUDFLARE_API_TOKEN", "")
if cid or ctok:
    if not (cid and ctok):
        problems.append("Cloudflare images need BOTH CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN.")
    elif "@" in cid or not re.fullmatch(r"[0-9a-fA-F]{32}", cid):
        problems.append("CLOUDFLARE_ACCOUNT_ID must be the 32-character code from the Cloudflare dashboard URL, not an email address.")

# --- keys pasted into the wrong place
if clean.get("STABILITY_API_KEY", "").startswith("sk-or-"):
    warns.append("STABILITY_API_KEY looks like an OPENROUTER key (it starts with sk-or-). Get the Stability key at platform.stability.ai, or delete this line.")
if clean.get("XAI_API_KEY") and not clean["XAI_API_KEY"].startswith("xai-"):
    warns.append("XAI_API_KEY does not look like an xAI key (they start with xai-). Get one at console.x.ai, or delete this line.")
if clean.get("POLLINATIONS_API_KEY", "").startswith("pk_"):
    warns.append("POLLINATIONS_API_KEY starts with pk_ (a publishable key). A server should use a secret key (sk_...) from enter.pollinations.ai. Try that if images or video are refused or rate-limited.")

# --- provider order lists
def order(name):
    v = clean.get(name, "")
    return [x.strip().lower() for x in v.split(",") if x.strip()]
ip, vp = order("IMAGE_PROVIDERS"), order("VIDEO_PROVIDERS")
if ip:
    if len(ip) > 1 and ip[0] == "pollinations":
        warns.append("IMAGE_PROVIDERS puts pollinations FIRST. It is the weakest image engine and is the likely reason for poor pictures. Put it last, for example: IMAGE_PROVIDERS=magichour,cloudflare,pollinations")
    if clean.get("MAGIC_HOUR_API_KEY") and "magichour" not in ip:
        warns.append("You set MAGIC_HOUR_API_KEY but IMAGE_PROVIDERS does not include magichour, so it is never used for images.")
    if clean.get("CLOUDFLARE_API_TOKEN") and "cloudflare" not in ip:
        warns.append("IMAGE_PROVIDERS does not include cloudflare, so your Cloudflare key is never used.")
if vp and clean.get("MAGIC_HOUR_API_KEY") and "magichour" not in vp:
    warns.append("VIDEO_PROVIDERS does not include magichour, so your free Magic Hour key is never used for video.")

# --- free-credit reality checks
if clean.get("MAGIC_HOUR_API_KEY"):
    if clean.get("MAGIC_HOUR_SECONDS", "4").isdigit() and int(clean.get("MAGIC_HOUR_SECONDS", "4")) > 5:
        warns.append("MAGIC_HOUR_SECONDS is above 5. Free Magic Hour credits (about 100 a day) cover roughly one 4-second clip, so use MAGIC_HOUR_SECONDS=4.")
    if clean.get("IMAGE_MAX_TRIES", "3").isdigit() and int(clean.get("IMAGE_MAX_TRIES", "3")) > 2:
        warns.append("IMAGE_MAX_TRIES is above 2: every redraw also uses free credits. IMAGE_MAX_TRIES=2 is safer.")
    if clean.get("PRO_VIDEO_LIMIT", "3").isdigit() and int(clean.get("PRO_VIDEO_LIMIT", "3")) > 3:
        warns.append("PRO_VIDEO_LIMIT is above 3. Each video costs real money on paid providers; 1 or 2 is safer.")

# --- video needs a key
if not clean.get("MAGIC_HOUR_API_KEY") and not clean.get("POLLINATIONS_API_KEY") and not clean.get("GEMINI_API_KEY"):
    warns.append("Video creation is off: add MAGIC_HOUR_API_KEY (free), or GEMINI_API_KEY with billing on, or POLLINATIONS_API_KEY.")

# --- values that would crash the server
for k in NUMERIC:
    if k in clean:
        if clean[k] == "" or not re.fullmatch(r"\d+", clean[k]):
            problems.append(f"{k} must be a number (it is '{clean[k]}'). Example: {dict((c[0], c[1]) for c in CATALOG).get(k, k + '=30')}")
if "DATABASE_URL" in clean and not clean["DATABASE_URL"]:
    problems.append("DATABASE_URL is present but empty: delete that line (or put your database address).")
if clean.get("JWT_SECRET") and len(clean["JWT_SECRET"]) < 24:
    warns.append("JWT_SECRET is shorter than 24 characters, so it is ignored. Use 40 or more.")
for k, v in vals.items():
    if re.search(r"\s", v.strip().strip('"').strip("'")) and k not in ("AI_PROVIDERS", "IMAGE_PROVIDERS", "VIDEO_PROVIDERS"):
        warns.append(f"{k} has a space INSIDE the value. Copy the key again without any space.")
    if v.strip()[:1] in ('"', "'"):
        warns.append(f"{k} is inside quotes. It works, but plain text without quotes is safer.")
for k in sorted(set(dups)):
    warns.append(f"{k} appears more than once in .env. Only the LAST one is used: delete the extra line so you know which one counts.")

# --- report
print(f"{'VARIABLE':26} {'STATUS':8} VALUE")
missing = []
for name, line, group, note in CATALOG:
    if name in clean:
        print(f"{name:26} {'set' if clean[name] else 'empty':8} {mask(clean[name])}")
    else:
        print(f"{name:26} {'MISSING':8} {note}")
        missing.append((name, line, group, note))
print()
for p in problems:
    print("PROBLEM:", p)
for w in warns:
    print("WARNING:", w)
if not problems and not warns:
    print("Everything looks right.")

if FIX:
    defaults = {c[0]: c[1].split("=", 1)[1] for c in CATALOG if c[0] in NUMERIC}
    lines, repaired = text.splitlines(), []
    for i, ln in enumerate(lines):
        m = re.match(r"^\s*([A-Z][A-Z0-9_]*)\s*=\s*$", ln)
        if m and m.group(1) in defaults:
            lines[i] = f"{m.group(1)}={defaults[m.group(1)]}"
            repaired.append(f"{m.group(1)} was empty -> now {defaults[m.group(1)]}")
        elif m and m.group(1) == "DATABASE_URL":
            lines[i] = "# DATABASE_URL="
            repaired.append("DATABASE_URL was empty -> commented out")
    if repaired:
        backup()
        ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")
        text = "\n".join(lines) + "\n"
        print("\nRepaired lines that would have crashed the server:")
        for r in repaired:
            print("  -", r)
if missing and FIX:
    backup()
    out = ["", f"# ---- added by check_env.py on {datetime.now():%Y-%m-%d %H:%M} (fill in what you need) ----"]
    last = None
    for name, line, group, note in missing:
        if group != last:
            out.append(f"# {group}")
            last = group
        if note:
            out.append(f"# {note}")
        out.append(line)
    with ENV.open("a", encoding="utf-8") as f:
        f.write(("\n" if not text.endswith("\n") else "") + "\n".join(out) + "\n")
    print(f"\nAdded {len(missing)} missing settings to .env (backup saved as .env.bak). Now fill in the empty ones and restart the server.")
elif missing:
    print(f"\n{len(missing)} settings are missing. Run  python check_env.py --fix  to add them.")
print()