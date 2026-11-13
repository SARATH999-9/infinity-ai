"""Razorpay payments for the INFINITY AI "Pro" plan.

Flow (all money logic stays on the server):
  1. POST /api/pay/order    -> server creates a Razorpay order (amount is set HERE, never by the browser)
  2. browser opens Razorpay Checkout with that order_id (UPI QR / UPI / cards / netbanking)
  3. POST /api/pay/verify   -> server checks Razorpay's HMAC signature, then activates Pro
  4. POST /api/pay/webhook  -> safety net: Razorpay calls us even if the user closes the tab after paying
"""
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timedelta

import requests
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

import config
from auth import current_user
from database import Payment, SessionLocal, User, get_db, plan_info

log = logging.getLogger("infinity.pay")
router = APIRouter(prefix="/api/pay")
API = "https://api.razorpay.com/v1"


def enabled() -> bool:
    return bool(config.RAZORPAY_KEY_ID and config.RAZORPAY_KEY_SECRET)


def _hmac(secret: str, payload: bytes) -> str:
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def activate(db: Session, order_id: str, payment_id: str) -> bool:
    """Marks the order paid and gives the user Pro time. Safe to call twice (verify + webhook)."""
    row = db.scalar(select(Payment).where(Payment.order_id == order_id))
    if not row:
        return False
    if row.status == "paid":
        return True
    user = db.get(User, row.user_id)
    if not user:
        return False
    now = datetime.utcnow()
    start = user.plan_until if user.plan_until and user.plan_until > now else now  # renewing adds time
    user.plan = "pro"
    user.plan_until = start + timedelta(days=config.PRO_DAYS)
    row.status = "paid"
    row.payment_id = payment_id
    row.paid_at = now
    db.commit()
    log.info("Pro activated for user %s until %s (order %s)", user.id, user.plan_until, order_id)
    return True


@router.get("/status")
def status(user: User = Depends(current_user)):
    return {"enabled": enabled(), **plan_info(user)}


@router.post("/order")
def create_order(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not enabled():
        raise HTTPException(503, "Payments are not set up yet. Add RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET to backend/.env.")
    body = {
        "amount": config.PRO_PRICE_PAISE,  # in paise: 100 = Rs 1
        "currency": "INR",
        "receipt": f"inf{user.id}_{int(time.time())}"[:40],
        "notes": {"user_id": str(user.id), "plan": "pro"},
    }
    try:
        r = requests.post(f"{API}/orders", auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET), json=body, timeout=20)
    except requests.RequestException:
        raise HTTPException(503, "Could not reach Razorpay. Check your internet connection.")
    if r.status_code == 401:
        raise HTTPException(503, "Razorpay rejected the keys. Check RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in backend/.env.")
    if r.status_code >= 400:
        log.error("Razorpay order failed: %s %s", r.status_code, r.text[:300])
        raise HTTPException(502, "Razorpay could not create the order. Try again in a minute.")
    order = r.json()
    db.add(Payment(order_id=order["id"], user_id=user.id, amount=order["amount"], status="created"))
    db.commit()
    return {
        "order_id": order["id"], "amount": order["amount"], "currency": order["currency"],
        "key_id": config.RAZORPAY_KEY_ID, "email": user.email, "name": user.name or "",
    }


class VerifyIn(BaseModel):
    razorpay_order_id: str = Field(min_length=5, max_length=60)
    razorpay_payment_id: str = Field(min_length=5, max_length=60)
    razorpay_signature: str = Field(min_length=10, max_length=200)


@router.post("/verify")
def verify(body: VerifyIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not enabled():
        raise HTTPException(503, "Payments are not set up.")
    row = db.scalar(select(Payment).where(Payment.order_id == body.razorpay_order_id, Payment.user_id == user.id))
    if not row:
        raise HTTPException(404, "Order not found for this account.")
    expected = _hmac(config.RAZORPAY_KEY_SECRET, f"{body.razorpay_order_id}|{body.razorpay_payment_id}".encode())
    if not hmac.compare_digest(expected, body.razorpay_signature):
        log.warning("Bad payment signature for user %s", user.id)
        raise HTTPException(400, "Payment could not be verified. If money was deducted it will be refunded by your bank.")
    activate(db, body.razorpay_order_id, body.razorpay_payment_id)
    db.refresh(user)
    return {"ok": True, **plan_info(user)}


@router.post("/webhook")
async def webhook(request: Request):
    """Razorpay Dashboard -> Webhooks -> URL https://YOUR-DOMAIN/api/pay/webhook, events: payment.captured, order.paid."""
    secret = config.RAZORPAY_WEBHOOK_SECRET
    if not secret:
        raise HTTPException(503, "Webhook secret not set.")
    raw = await request.body()
    sig = request.headers.get("X-Razorpay-Signature", "")
    if not hmac.compare_digest(_hmac(secret, raw), sig):
        raise HTTPException(400, "Bad signature.")
    try:
        event = json.loads(raw)
        ev = event.get("event", "")
        if ev in ("payment.captured", "order.paid"):
            pay = event["payload"]["payment"]["entity"]
            with SessionLocal() as db:
                activate(db, pay["order_id"], pay["id"])
    except (KeyError, ValueError):
        log.warning("Unreadable webhook body")
    return {"ok": True}