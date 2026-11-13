"""Checks your Razorpay keys. Run:  python check_pay.py   (creates one Rs 1 order; nothing is charged)"""
import requests

import config

print()
if not (config.RAZORPAY_KEY_ID and config.RAZORPAY_KEY_SECRET):
    print("RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET are missing in backend/.env")
    raise SystemExit(1)
mode = "TEST" if config.RAZORPAY_KEY_ID.startswith("rzp_test_") else "LIVE"
print(f"Key id: {config.RAZORPAY_KEY_ID}  ({mode} mode)")
try:
    r = requests.post("https://api.razorpay.com/v1/orders", auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET),
                      json={"amount": 100, "currency": "INR", "receipt": "check_" + mode.lower()}, timeout=20)
except requests.RequestException as e:
    print("Could not reach Razorpay:", type(e).__name__, "- check your internet connection.")
    raise SystemExit(1)
if r.status_code == 200:
    print("OK. Razorpay accepted your keys. Test order:", r.json().get("id"))
    print("Now start the website and click Upgrade plan.")
elif r.status_code == 401:
    print("Razorpay rejected the keys. Re-copy both values into backend/.env with no spaces or quotes.")
else:
    print("Razorpay replied", r.status_code, r.text[:200])
print()