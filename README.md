# INFINITY AI  (powered by Sarath Chandra)

A ChatGPT-style assistant with a black and gold interface.

**What you get**
- Animated intro: INFINITY AI symbol, name, and "POWERED BY SARATH CHANDRA" in yellow
- Login screen: email and password, **Create account** (with your name), or **Continue with Gmail**
- Welcome greeting with your name after login ("Good evening, <your name>")
- Streaming chat, saved history, image and text/code file input, dictation, hands-free voice conversation, read-aloud, deep-thinking button, regenerate
- **AI fallback chain:** add several free keys (Groq, Gemini, OpenRouter...). If one fails or hits its limit, the next one answers automatically. Retired model names are replaced automatically.

## Run on your computer

### Windows (easiest)
1. Install Python 3.10+ from python.org (tick **Add Python to PATH**).
2. Unzip, then double-click **run.bat**.
3. When Notepad opens, paste your key(s) (see below), press Ctrl+S, close Notepad.
4. The browser opens at http://localhost:8000.

### Windows PowerShell (manual)
```powershell
cd infinity-ai\backend
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
copy .env.example .env
notepad .env
python check_key.py
python -m uvicorn main:app --reload
```
If activation says scripts are disabled: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### macOS / Linux
```bash
cd infinity-ai
./run.sh
```

Open **http://localhost:8000**. Stop the server with Ctrl+C. Next time, repeat only the activate and `python -m uvicorn main:app --reload` lines (or run.bat again).

## Get a free AI key (add one or more to backend/.env)

| Line in .env | Where to get it | Cost |
|---|---|---|
| `GROQ_API_KEY=gsk_...` | https://console.groq.com/keys | free tier (Llama models) |
| `GEMINI_API_KEY=AIza...` | https://aistudio.google.com/app/apikey | free tier, can see images |
| `OPENROUTER_API_KEY=sk-or-...` | https://openrouter.ai/keys | free models available |
| `XAI_API_KEY=xai-...` | https://console.x.ai | paid (Grok) |
| `ANTHROPIC_API_KEY=sk-ant-...` | https://console.anthropic.com | paid (Claude) |

No spaces, no quotes. **Best setup: add both Groq and Gemini.** Then chat keeps working even if one key fails or runs out of free quota.

After editing `.env`, stop the server (Ctrl+C) and start it again. Run `python check_key.py` any time: it tests each provider and prints the exact reason if one fails (bad key, retired model, quota).

## "Continue with Gmail" setup (optional, about 5 minutes)
Without this, the button shows a message and email login still works.
1. Go to https://console.cloud.google.com and create a project.
2. Open **APIs & Services > OAuth consent screen**, choose **External**, fill the app name and your email, and add your Gmail under **Test users**.
3. Open **Credentials > Create credentials > OAuth client ID > Web application**.
4. Under **Authorized JavaScript origins** add `http://localhost:8000` (and your real domain later).
5. Copy the **Client ID** into `backend/.env` as `GOOGLE_CLIENT_ID=...`, then restart the server.
Google's menus change sometimes; the names above are the usual ones.

## Troubleshooting
- **"No module named ..."**: the virtual environment is not active. Run `.venv\Scripts\Activate.ps1` in the `backend` folder, or just use run.bat.
- **Chat error mentioning a provider**: run `python check_key.py` and follow what it says.
- **Microphone**: works on `localhost` or HTTPS only. Use Chrome, Edge or Safari.
- **Upgrading from an older version**: your accounts and chats are kept. The database upgrades itself.

## Project layout
```
run.bat / run.sh        one-click start
backend/main.py         API: accounts, Google login, chats, streaming
backend/providers.py    AI providers + automatic fallback
backend/config.py       settings from .env
backend/check_key.py    tests your keys
backend/database.py     users, conversations, messages
backend/auth.py         password hashing and login tokens
frontend/index.html     the whole interface
```

## Put it online (Render, Railway, Fly.io, any Docker host)
Use the included Dockerfile. Set the same variables as `.env` on the host, use a hosted PostgreSQL `DATABASE_URL` (add `psycopg2-binary` to requirements.txt), serve over HTTPS, and add your domain to the Google client's authorized origins.
