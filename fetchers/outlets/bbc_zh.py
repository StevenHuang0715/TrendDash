"""BBC 中文（bbc.com/zhongwen 繁體版「最多閱讀」排行，取自頁面內嵌的 __NEXT_DATA__ JSON）。"""

import json
import re
import time
from datetime import datetime, timezone

import feedparser

NAME = "BBC 中文"
URL = "https://www.bbc.com/zhongwen/popular/read/trad"
IMAGE_BASE = "https://ichef.bbci.co.uk/ace/ws/480"

RSS_URL = "https://feeds.bbci.co.uk/zhongwen/trad/rss.xml"
# 主題頁（國際、中國、香港、台灣、英國、財經、影片），每頁約 24 篇，可用 ?page=N 往回翻
TOPICS = ["c83plve5vmjt", "ckr7mn6r003t", "cezw73jk755t", "cd6qem06z92t", "c1ez1k4emn0t", "cq8nqywy37yt", "cgvl47l38e1t"]
MAX_PAGES = 30  # 所有請求合計上限
REQUEST_DELAY = 0.3


def _find_most_read(obj):
    # 排行資料藏在 pageData 某層的 "mostRead": {"items": [...]}，位置不固定就遞迴找
    if isinstance(obj, dict):
        most_read = obj.get("mostRead")
        if isinstance(most_read, dict) and most_read.get("items"):
            return most_read["items"]
        children = obj.values()
    elif isinstance(obj, list):
        children = obj
    else:
        return None
    for child in children:
        found = _find_most_read(child)
        if found:
            return found
    return None


def _thumbnail(entry):
    blocks = (((entry.get("images") or {}).get("defaultPromoImage") or {}).get("blocks")) or []
    for block in blocks:
        if block.get("type") == "rawImage":
            model = block.get("model") or {}
            if model.get("originCode") and model.get("locator"):
                return f"{IMAGE_BASE}/{model['originCode']}/{model['locator']}"
    return None


def fetch(session):
    resp = session.get(URL, timeout=20)
    resp.raise_for_status()
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', resp.text, re.S)
    if not m:
        raise ValueError("找不到 __NEXT_DATA__")
    entries = _find_most_read(json.loads(m.group(1))) or []
    entries.sort(key=lambda e: e.get("rank") or 999)

    items, seen = [], set()
    for e in entries:
        title = (e.get("title") or "").strip()
        url = e.get("href") or ""
        if url.startswith("/"):
            url = "https://www.bbc.com" + url
        if not title or not url or url in seen:
            continue
        seen.add(url)
        items.append({"title": title, "url": url, "time": e.get("timestamp"), "thumbnail": _thumbnail(e)})
    if not items:
        raise ValueError("BBC 中文排行解析不到任何文章")
    return items[:20]


def _clean_url(url):
    # RSS 網址帶 ?at_medium=RSS 之類的追蹤參數
    return url.split("?", 1)[0]


def _parse_iso(text):
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None


def _next_data(html):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        raise ValueError("找不到 __NEXT_DATA__")
    return json.loads(m.group(1))


def _rss_items(resp):
    items = []
    for e in feedparser.parse(resp.content).entries:
        if not e.get("published_parsed"):
            continue
        thumbs = e.get("media_thumbnail") or []
        items.append(
            {
                "title": e.title.strip(),
                "url": _clean_url(e.link),
                "time": datetime(*e.published_parsed[:6], tzinfo=timezone.utc),
                "thumbnail": thumbs[0].get("url") if thumbs else None,
            }
        )
    return items


def _topic_items(resp):
    page = _next_data(resp.text)["props"]["pageProps"]["pageData"]
    items = []
    for curation in page.get("curations") or []:
        for x in curation.get("summaries") or []:
            published = _parse_iso(x.get("firstPublished"))
            if not published or not x.get("link") or not x.get("title"):
                continue
            image = x.get("imageUrl")
            items.append(
                {
                    "title": x["title"].strip(),
                    "url": _clean_url(x["link"]),
                    "time": published,
                    "thumbnail": image.replace("{width}", "480") if image else None,
                }
            )
    return items, page.get("pageCount") or 1


def fetch_recent(session, since):
    """回傳 since 之後發布的文章。來源：繁體 RSS（feeds.bbci.co.uk/zhongwen/trad/rss.xml，約 40 篇）
    加上 bbc.com/zhongwen/topics/<id>/trad 各主題頁往回翻頁。"""
    found = {}
    requests_left = MAX_PAGES

    def get(url):
        nonlocal requests_left
        requests_left -= 1
        time.sleep(REQUEST_DELAY)
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
        return resp

    def add(items):
        for it in items:
            if it["time"] >= since and it["url"] not in found:
                found[it["url"]] = it

    try:
        add(_rss_items(get(RSS_URL)))
        for topic in TOPICS:
            page = 1
            while requests_left > 0:
                items, page_count = _topic_items(get(f"https://www.bbc.com/zhongwen/topics/{topic}/trad?page={page}"))
                add(items)
                # 主題頁不是嚴格照時間排，整頁都比 since 舊才停
                if not items or all(it["time"] < since for it in items) or page >= page_count:
                    break
                page += 1
    except Exception as exc:  # 中途失敗就回傳目前拿到的
        print(f"  [bbc_zh] fetch_recent 中斷：{exc}")

    if not found:
        raise ValueError("BBC 中文近期文章解析不到任何文章")
    items = sorted(found.values(), key=lambda x: x["time"], reverse=True)
    for it in items:
        it["time"] = it["time"].isoformat()
    return items
