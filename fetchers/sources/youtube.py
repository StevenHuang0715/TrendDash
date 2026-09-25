"""YouTube 台灣發燒影片（官方 YouTube Data API v3）。

需要 API Key：放在 fetchers/.env 的 YOUTUBE_API_KEY。
申請方式見 README。
"""

import os

from common import item

ID = "youtube"
NAME = "YouTube 熱門"
SECTION = "video"
API = "https://www.googleapis.com/youtube/v3/videos"


def enabled():
    # 沒有 API Key 就不顯示這個來源；填進 .env 後自動出現
    return bool(os.getenv("YOUTUBE_API_KEY"))


def fetch(session):
    key = os.getenv("YOUTUBE_API_KEY")

    resp = session.get(
        API,
        params={
            "part": "snippet,statistics",
            "chart": "mostPopular",
            "regionCode": "TW",
            "maxResults": 30,
            "key": key,
        },
        timeout=20,
    )
    resp.raise_for_status()

    items = []
    for v in resp.json().get("items", []):
        sn, st = v["snippet"], v.get("statistics", {})
        views = int(st.get("viewCount", 0))
        thumbs = sn.get("thumbnails", {})
        thumb = (thumbs.get("medium") or thumbs.get("default") or {}).get("url")
        items.append(
            item(
                sn["title"],
                f"https://www.youtube.com/watch?v={v['id']}",
                thumbnail=thumb,
                score=views,
                score_label=f"{views:,} 次觀看",
                time=sn.get("publishedAt"),
                meta=sn.get("channelTitle"),
            )
        )
    return items
