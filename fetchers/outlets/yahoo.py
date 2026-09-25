"""Yahoo 奇摩新聞 熱門新聞（tw.news.yahoo.com/most-popular，解析頁面內嵌的 root.App.main JSON）。

fetch_recent 讀 Google News sitemap（news-sitemap-index.xml 底下的 news-sitemap*.xml），只涵蓋約 2 天。
每日 sitemap（sitemap-YYYY-MM-DD.xml）雖然有 7 天以上，但只有網址沒有標題和時間，所以不用。
"""

import html
import json
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

NAME = "Yahoo 奇摩新聞"
URL = "https://tw.news.yahoo.com/most-popular"
LIMIT = 20
TW = timezone(timedelta(hours=8))

SITEMAP_INDEX = "https://tw.news.yahoo.com/news-sitemap-index.xml"
MAX_PAGES = 30
REQUEST_DELAY = 0.3


def _stream_items(html):
    # 頁面把初始資料塞在 `root.App.main = {...};`，用 raw_decode 讀出第一個完整 JSON 物件
    start = html.index("root.App.main")
    data, _ = json.JSONDecoder().raw_decode(html[html.index("{", start):])
    streams = data["context"]["dispatcher"]["stores"]["StreamStore"]["streams"]
    for stream in streams.values():
        rows = (stream.get("data") or {}).get("stream_items")
        if rows:
            return rows
    return []


def _thumbnail(images):
    if not images:
        return None
    if "img:440x246" in images:
        return images["img:440x246"].get("url")
    best = max(images.values(), key=lambda x: x.get("width") or 0)
    return best.get("url")


def fetch(session):
    resp = session.get(URL, timeout=20)
    resp.raise_for_status()

    items = []
    seen = set()
    for row in _stream_items(resp.text):
        # 穿插的 Taboola 廣告 type 是 "ad"
        if row.get("type") != "article" or row.get("isTaboolaAd"):
            continue
        url = urljoin(URL, row.get("url") or row.get("link") or "")
        title = (row.get("title") or "").strip()
        if not title or not url.startswith("http") or url in seen:
            continue
        seen.add(url)

        pubtime = row.get("pubtime")
        items.append({
            "title": title,
            "url": url,
            "time": datetime.fromtimestamp(pubtime / 1000, TW).isoformat() if pubtime else None,
            "thumbnail": _thumbnail(row.get("images")),
        })
        if len(items) >= LIMIT:
            break

    if not items:
        raise RuntimeError("Yahoo 新聞：熱門頁解析不到任何新聞")
    return items


def _xml_text(block, tag):
    m = re.search(rf"<{tag}>(.*?)</{tag}>", block, re.S)
    if not m:
        return ""
    text = m.group(1).strip()
    if text.startswith("<![CDATA["):
        text = text[9:-3]
    return html.unescape(text).strip()


def fetch_recent(session, since):
    """回傳 since 之後發布的文章（依發布日期往回翻頁）。資料來源：tw.news.yahoo.com/news-sitemap-index.xml（約 2 天）。"""
    resp = session.get(SITEMAP_INDEX, timeout=20)
    resp.raise_for_status()
    # 索引裡依序是 news-sitemap.xml（最新）、-p0、-p1……越後面越舊
    sitemaps = re.findall(r"<loc>(.*?)</loc>", resp.text)[:MAX_PAGES]

    items = []
    seen = set()
    for sitemap in sitemaps:
        time.sleep(REQUEST_DELAY)
        try:
            resp = session.get(html.unescape(sitemap.strip()), timeout=20)
            resp.raise_for_status()
        except Exception as exc:
            if not items:
                raise
            print(f"  [yahoo] {sitemap} 失敗，先回傳已抓到的：{exc}")
            break

        any_new = False
        for block in re.findall(r"<url>(.*?)</url>", resp.text, re.S):
            try:
                # 時間是 UTC（結尾 Z），轉成台灣時間
                dt = datetime.fromisoformat(_xml_text(block, "news:publication_date").replace("Z", "+00:00"))
            except ValueError:
                continue
            if dt.tzinfo is None or dt < since:
                continue
            any_new = True
            url = _xml_text(block, "loc")
            title = " ".join(_xml_text(block, "news:title").split())
            if not title or not url.startswith("http") or url in seen:
                continue
            seen.add(url)
            items.append({
                "title": title,
                "url": url,
                "time": dt.astimezone(TW).isoformat(),
                "thumbnail": _xml_text(block, "image:loc") or None,
            })
        if not any_new:  # 這份全都比 since 舊，後面的更舊
            break

    if not items:
        raise RuntimeError("Yahoo 新聞：sitemap 沒有抓到任何新聞")
    items.sort(key=lambda x: x["time"], reverse=True)
    return items
