
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("YOUTUBE_API_KEY")

if not API_KEY:
    print("❌ API key not found in .env")
else:
    url = "https://www.googleapis.com/youtube/v3/search"

    params = {
        "part": "snippet",
        "q": "Arijit Singh songs",
        "type": "video",
        "maxResults": 3,
        "key": API_KEY
    }

    response = requests.get(url, params=params, timeout=20)

    if response.status_code == 200:
        data = response.json()
        print("✅ YouTube API is working!")
        for item in data.get("items", []):
            print("Title:", item["snippet"]["title"])
            print("Video ID:", item["id"]["videoId"])
    else:
        print("❌ API request failed")
        print("Status:", response.status_code)
        print("Error:", response.json())
