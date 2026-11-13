# INFINITY AI

A FastAPI-powered AI assistant with a black-and-gold web interface.

## Features
- Email/password and optional Google sign-in
- Streaming AI chat, saved conversations, file/photo input, voice input and read-aloud
- Image generation and AI video generation (subject to configured providers and plan limits)
- Daily Free-plan limits with an automatic Pro upgrade prompt when a limit is reached
- Razorpay checkout for Pro (server-side order amount and signature verification)
- YouTube song search: song/audio requests show an official embedded YouTube player in chat; requests for a video song/music video show a clickable YouTube link

## Run locally (Windows PowerShell)

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
copy .env.example .env
notepad .env
python -m uvicorn main:app --reload
```

Open http://localhost:8000. Add your own provider credentials to `backend/.env`. Never commit `.env` or share it.

## Important environment variables

```env
# At least one AI provider key
GROQ_API_KEY=
GEMINI_API_KEY=

# YouTube Data API v3 (backend only; restrict this key to YouTube Data API v3)
YOUTUBE_API_KEY=

# Daily limits and Pro offer
FREE_DAILY_LIMIT=20
PRO_DAILY_LIMIT=200
FREE_VIDEO_LIMIT=0
PRO_VIDEO_LIMIT=3
PRO_PRICE_PAISE=200
PRO_DAYS=30

# Razorpay credentials (use test keys while testing)
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
RAZORPAY_WEBHOOK_SECRET=
```

`PRO_PRICE_PAISE=200` means **₹2 for 30 days**. The server reads the actual price from the environment, so set the same value in your local `.env` and your hosting provider's environment settings. A working, activated Razorpay merchant account and valid keys are required before real payments can be accepted.

## YouTube music behavior
- Example: `Play Shape of You by Ed Sheeran` -> searches YouTube and displays its embedded player in the chat. The user presses Play in the official player.
- Example: `Show the video song for Shape of You` -> displays a link that opens the YouTube watch page.
- The app does not download or extract audio from YouTube. Playback uses YouTube's embedded player and follows its playback controls, ads, availability and embedding rules.
- The YouTube API key stays on the server. Add `YOUTUBE_API_KEY` to the Render service's Environment page for production.

## Daily limits and Pro
- Free and Pro daily message limits are enforced by the backend.
- Free video generation is disabled when `FREE_VIDEO_LIMIT=0`; Pro video allowance is controlled by `PRO_VIDEO_LIMIT`.
- When a daily message/video limit is reached, the UI opens the Pro plan details and checkout prompt.
- Pro benefits shown in the UI include the higher message allowance, Deep Thinking, the configured daily video allowance, and all Free features.

## Deployment
Deploy the FastAPI backend and serve the `frontend` directory as configured in `main.py`/the included Dockerfile. On Render, add the same environment variables under **Dashboard -> Service -> Environment**. In particular, set `YOUTUBE_API_KEY` and `PRO_PRICE_PAISE=200`. Do not place API keys in `frontend/index.html`.

## Security
- Never upload `.env`, `.jwt_secret`, database files, or API credentials to GitHub.
- If a credential has ever been committed or shared, revoke/rotate it in its provider dashboard before deployment.
- Use YouTube Data API v3 restrictions for the YouTube key; keep the key server-side.
