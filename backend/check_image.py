"""Compares your image providers on the same prompts.   Run:  python check_image.py
Saves test_<provider>_<n>.png so YOU can look at them and see which provider makes good pictures.
PASS / FAIL = the verdict of the vision AI that checks pictures inside the app."""
import base64
import time

import config
import images

PROMPTS = ["a red apple on a wooden table", "a golden retriever puppy running on a beach", "a happy Indian family eating dinner at home"]
print()
names = images.available()
print("Image providers found:", ", ".join(names) or "none")
if "cloudflare" not in names:
    print("(Cloudflare is not active: it needs BOTH CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN in backend/.env)")
for name in names:
    print(f"\\n== {name} ==")
    for i, idea in enumerate(PROMPTS, 1):
        t = time.time()
        try:
            url = images.PROVIDERS[name](images._enhance(idea), "square")
        except Exception as e:
            print(f"  FAILED  {idea!r}: {e}")
            break
        ok = images._verify(idea, url)
        verdict = {True: "PASS", False: "FAIL", None: "not checked"}[ok]
        mime, data = url.split(",", 1)
        ext = "jpg" if "jpeg" in mime else "png"
        open(f"test_{name}_{i}.{ext}", "wb").write(base64.b64decode(data))
        print(f"  {verdict:11} {idea!r}  ({time.time() - t:.0f}s)  -> test_{name}_{i}.{ext}")
print("\\nOpen the saved pictures. If one provider looks bad, remove it from IMAGE_PROVIDERS in backend/.env.\\n")