"""Run:  python check_key.py   -> tests every AI provider you configured, and Google sign-in setup."""
import config
import providers

print("\nINFINITY AI - setup check\n" + "-" * 40)
if config.PROBLEMS:
    for p in config.PROBLEMS:
        print("WARNING:", p)
if not config.ACTIVE:
    raise SystemExit("PROBLEM: " + config.KEY_PROBLEM)
good = 0
for cfg in config.ACTIVE:
    ok, msg = providers.test_provider(cfg)
    good += ok
    print(f"[{cfg.label}] {msg}")
print("-" * 40)
print("Google sign-in:", "configured" if config.GOOGLE_CLIENT_ID else "not set up (optional: add GOOGLE_CLIENT_ID)")
print("RESULT:", f"{good} of {len(config.ACTIVE)} provider(s) working." + ("" if good else " Chat will not work until one works."))
