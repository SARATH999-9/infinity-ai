import json
import logging
import re
import secrets
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import config
import providers
from auth import current_user, hash_password, make_token, verify_password
from database import Conversation, Message, SessionLocal, User, get_db, init_db

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("infinity")
app = FastAPI(title="INFINITY AI", docs_url="/api/docs", openapi_url="/api/openapi.json")
init_db()

print("\n[INFINITY AI] AI providers (tried in this order):")
for _p in config.ACTIVE:
    print(f"   - {_p.label}: model {_p.model}")
for _w in config.PROBLEMS:
    print("   ! " + _w)
if config.KEY_PROBLEM:
    print("   ! " + config.KEY_PROBLEM)
print("[INFINITY AI] Google sign-in:", "on" if config.GOOGLE_CLIENT_ID else "off (add GOOGLE_CLIENT_ID to enable)", "\n")

EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
DATA_URL = re.compile(r"^data:(image/(?:jpeg|png|webp|gif));base64,([A-Za-z0-9+/=]+)$")


class LoginIn(BaseModel):
    email: str = Field(pattern=EMAIL, max_length=255)
    password: str = Field(min_length=1, max_length=72)


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    email: str = Field(pattern=EMAIL, max_length=255)
    password: str = Field(min_length=8, max_length=72)


class GoogleIn(BaseModel):
    credential: str = Field(min_length=10, max_length=4000)


class FileIn(BaseModel):
    name: str = Field(max_length=120)
    text: str = Field(max_length=40000)


class ChatIn(BaseModel):
    conversation_id: str = Field(pattern=r"^[A-Za-z0-9_-]{4,40}$")
    title: str | None = Field(default=None, max_length=80)
    message: str = Field(default="", max_length=20000)
    images: list[str] = Field(default_factory=list, max_length=6)
    files: list[FileIn] = Field(default_factory=list, max_length=6)
    deep: bool = False
    regenerate: bool = False


def shown_name(u: User) -> str:
    return u.name or u.email.split("@")[0].replace(".", " ").title()


def session_for(u: User) -> dict:
    return {"token": make_token(u.id), "name": shown_name(u), "email": u.email}


# ---------- public config + auth ----------
@app.get("/api/config")
def public_config():
    return {"google_client_id": config.GOOGLE_CLIENT_ID or None}


@app.post("/api/auth/register")
def register(c: RegisterIn, db: Session = Depends(get_db)):
    email = c.email.lower()
    if len(c.password.encode()) > 72:
        raise HTTPException(400, "Password is too long.")
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "That email already has an account. Log in instead.")
    db.add(User(email=email, name=c.name.strip(), password_hash=hash_password(c.password)))
    db.commit()
    return {"ok": True, "email": email}  # no token: the user logs in next


@app.post("/api/auth/login")
def login(c: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == c.email.lower()))
    if not user or not verify_password(c.password, user.password_hash):
        raise HTTPException(401, "Wrong email or password.")
    return session_for(user)


@app.post("/api/auth/google")
def google_login(body: GoogleIn, db: Session = Depends(get_db)):
    if not config.GOOGLE_CLIENT_ID:
        raise HTTPException(503, "Google sign-in is not set up. Add GOOGLE_CLIENT_ID to backend/.env.")
    try:
        from google.auth.transport import requests as grequests
        from google.oauth2 import id_token
        info = id_token.verify_oauth2_token(body.credential, grequests.Request(), config.GOOGLE_CLIENT_ID, clock_skew_in_seconds=10)
    except ValueError:
        raise HTTPException(401, "Google sign-in failed. Try again.")
    except Exception:
        log.exception("google verification error")
        raise HTTPException(503, "Could not verify Google sign-in. Check your internet connection.")
    if not info.get("email") or not info.get("email_verified"):
        raise HTTPException(401, "Your Google email is not verified.")
    email = info["email"].lower()
    name = (info.get("name") or email.split("@")[0])[:40]
    user = db.scalar(select(User).where(User.email == email))
    if not user:
        user = User(email=email, name=name, password_hash=hash_password(secrets.token_urlsafe(24)))
        db.add(user)
        db.commit()
    elif not user.name:
        user.name = name
        db.commit()
    return session_for(user)


@app.get("/api/me")
def me(user: User = Depends(current_user)):
    return {"email": user.email, "name": shown_name(user)}


# ---------- conversations ----------
@app.get("/api/conversations")
def list_conversations(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.updated_at.desc())
    ).all()
    return [{"id": c.id, "title": c.title, "messages": [m.to_dict() for m in c.messages]} for c in rows]


@app.delete("/api/conversations/{cid}")
def delete_conversation(cid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    conv = db.get(Conversation, cid)
    if conv and conv.user_id == user.id:
        db.delete(conv)
        db.commit()
    return {"ok": True}


@app.delete("/api/conversations")
def delete_all(user: User = Depends(current_user), db: Session = Depends(get_db)):
    for conv in db.scalars(select(Conversation).where(Conversation.user_id == user.id)).all():
        db.delete(conv)
    db.commit()
    return {"ok": True}


# ---------- chat (streaming) ----------
def sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"


def to_api_messages(rows: list[Message]) -> list[dict]:
    while rows and rows[0].role != "user":
        rows = rows[1:]
    out = []
    recent = len(rows) - 6  # only re-send images from the last few turns
    for i, m in enumerate(rows):
        if m.role == "assistant":
            out.append({"role": "assistant", "text": m.content})
            continue
        images = []
        if i >= recent:
            for url in json.loads(m.images or "[]"):
                hit = DATA_URL.match(url)
                if hit:
                    images.append((hit.group(1), hit.group(2)))
        out.append({"role": "user", "text": ((m.ctx or "") + m.content) or "(empty)", "images": images})
    return out


@app.post("/api/chat")
def chat(body: ChatIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if config.KEY_PROBLEM:
        raise HTTPException(503, config.KEY_PROBLEM)
    since = datetime.utcnow() - timedelta(days=1)
    used = db.scalar(
        select(func.count(Message.id)).join(Conversation, Conversation.id == Message.conversation_id)
        .where(Conversation.user_id == user.id, Message.role == "user", Message.created_at > since)
    )
    if used >= config.DAILY_LIMIT:
        raise HTTPException(429, "Daily message limit reached. Try again tomorrow.")

    conv = db.get(Conversation, body.conversation_id)
    if conv and conv.user_id != user.id:
        raise HTTPException(404, "Conversation not found.")
    if not conv:
        conv = Conversation(id=body.conversation_id, user_id=user.id, title=(body.title or "New chat")[:60])
        db.add(conv)
        db.flush()

    if body.regenerate:
        last = db.scalars(select(Message).where(Message.conversation_id == conv.id).order_by(Message.id.desc())).first()
        if last and last.role == "assistant":
            db.delete(last)
            db.flush()
    else:
        if not body.message.strip() and not body.images and not body.files:
            raise HTTPException(400, "Message is empty.")
        for img in body.images:
            if not DATA_URL.match(img) or len(img) > 4_000_000:
                raise HTTPException(400, "One of the images is invalid or too large.")
        ctx = "".join(f"[Attached file: {f.name}]\n```\n{f.text}\n```\n\n" for f in body.files)
        db.add(Message(
            conversation_id=conv.id, role="user", content=body.message,
            images=json.dumps(body.images), files=json.dumps([f.name for f in body.files]), ctx=ctx,
        ))
    conv.updated_at = datetime.utcnow()
    db.commit()

    rows = db.scalars(
        select(Message).where(Message.conversation_id == conv.id).order_by(Message.id.desc()).limit(30)
    ).all()[::-1]
    msgs = to_api_messages(rows)
    if not msgs or msgs[-1]["role"] != "user":
        raise HTTPException(400, "Nothing to answer.")
    cid = conv.id

    def stream():
        parts: list[str] = []
        try:
            for t in providers.stream_text(msgs, body.deep):
                parts.append(t)
                yield sse({"type": "delta", "text": t})
            yield sse({"type": "done"})
        except providers.AIError as e:
            log.error("AI error: %s", e.message)
            yield sse({"type": "error", "message": e.message})
        except Exception:
            log.exception("chat failed")
            yield sse({"type": "error", "message": "Something went wrong. Check the server window for details."})
        finally:  # also runs if the user presses stop, so partial answers are kept
            text = "".join(parts)
            if text:
                with SessionLocal() as s2:
                    s2.add(Message(conversation_id=cid, role="assistant", content=text))
                    c2 = s2.get(Conversation, cid)
                    if c2:
                        c2.updated_at = datetime.utcnow()
                    s2.commit()

    return StreamingResponse(
        stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/health")
def health():
    return {"ok": True, "providers": [p.name for p in config.ACTIVE], "problem": config.KEY_PROBLEM or None}


FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="web")
