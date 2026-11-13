"""YouTube song lookup for Infinity AI. Playback uses the official embedded player."""
import os
import re
import requests
from fastapi import APIRouter, Depends, HTTPException, Query
from auth import current_user
from database import User

router = APIRouter(prefix="/api/music", tags=["music"])
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")

def youtube_key():
    return os.getenv("YOUTUBE_API_KEY", "").strip()

@router.get("/search")
def search_song(q: str = Query(min_length=2, max_length=180), user: User = Depends(current_user)):
    key = youtube_key()
    if not key:
        raise HTTPException(503, "Song search is not configured. Add YOUTUBE_API_KEY to the backend environment.")
    try:
        response = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={"part": "snippet", "q": q, "type": "video", "videoEmbeddable": "true", "maxResults": 5, "key": key},
            timeout=15,
        )
    except requests.RequestException:
        raise HTTPException(503, "Could not reach YouTube. Please try again.")
    data = response.json() if response.content else {}
    if response.status_code != 200:
        reason = (((data.get("error") or {}).get("errors") or [{}])[0].get("reason"))
        if reason == "quotaExceeded":
            raise HTTPException(429, "YouTube daily search quota reached. Try again tomorrow.")
        raise HTTPException(502, "YouTube song search failed. Check the API key and YouTube Data API v3 restrictions.")
    results = []
    for item in data.get("items", []):
        vid = ((item.get("id") or {}).get("videoId") or "")
        sn = item.get("snippet") or {}
        if not VIDEO_ID.fullmatch(vid):
            continue
        thumbs = sn.get("thumbnails") or {}
        thumb = (thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}).get("url")
        results.append({"video_id": vid, "title": sn.get("title", "YouTube video"), "channel": sn.get("channelTitle", ""), "thumbnail": thumb, "youtube_url": f"https://www.youtube.com/watch?v={vid}", "embed_url": f"https://www.youtube-nocookie.com/embed/{vid}?playsinline=1&rel=0"})
    return {"items": results}
