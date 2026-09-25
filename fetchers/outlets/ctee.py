"""工商時報 熱門新聞（首頁側欄「熱門新聞」＋文章頁側欄「熱門日報新聞」）。

/hotnews 完整排行頁被 Cloudflare 擋（403 challenge），只有首頁與文章頁抓得到，
所以合併兩個側欄排行，數量只有 8～10 則左右。
"""

import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import feedparser
from bs4 import BeautifulSoup

NAME = "工商時報"
BASE = "https://www.ctee.com.tw/"
# 沒被 Cloudflare 擋的 RSS：ctee＝全部「工商時報」署名稿，其餘為各分類；每個只有最新 15～30 則
RSS_URL = "https://www.ctee.com.tw/rss_web/livenews/{}"
RSS_FEEDS = ["ctee", "stock", "industry", "tech", "finance", "policy", "world", "china", "house", "life"]
REQUEST_DELAY = 0.3
TW = timezone(timedelta(hours=8))


def _get_soup(session, url):
    resp = session.get(url, timeout=20)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def _hot_links(soup):
    links = []
    for box in soup.select("div.list-box.hotnews"):
        for a in box.select("li.hotnews__item a[href]"):
            links.append((a.get_text(strip=True), urljoin(BASE, a["href"])))
    return links


def _date_from_url(url):
    # 文章編號開頭是日期，例如 /news/20260924700175-430501
    m = re.search(r"/news/(\d{4})(\d{2})(\d{2})\d+", url)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def fetch(session):
    links = _hot_links(_get_soup(session, BASE))
    if links:
        try:
            links += _hot_links(_get_soup(session, links[0][1]))
        except Exception as exc:  # 文章頁失敗就只用首頁那幾則
            print(f"  [ctee] 文章頁側欄失敗：{exc}")

    results, seen = [], set()
    for title, url in links:
        if not title or "/news/" not in url or url in seen:
            continue
        seen.add(url)
        results.append({"title": title, "url": url, "time": _date_from_url(url), "thumbnail": None})

    if not results:
        raise RuntimeError("工商時報首頁找不到熱門新聞，版面可能改了或被 Cloudflare 擋")
    return results[:20]


def fetch_recent(session, since):
    """回傳 since 之後發布的文章。來源：ctee.com.tw/rss_web/livenews/<分類> 多個 RSS 合併。

    限制：RSS 不能翻頁、列表頁又被 Cloudflare 擋，所以只能回溯約 1～2 天，無法補滿 7 天。
    """
    results, seen = [], set()
    for i, feed in enumerate(RSS_FEEDS):
        if i:
            time.sleep(REQUEST_DELAY)
        try:
            resp = session.get(RSS_URL.format(feed), timeout=20)
            resp.raise_for_status()
        except Exception as exc:  # 單一分類失敗不影響其他分類
            print(f"  [ctee] RSS {feed} 失敗：{exc}")
            continue
        for entry in feedparser.parse(resp.content).entries:
            title = (entry.get("title") or "").strip()
            url = (entry.get("link") or "").split("?")[0]
            try:
                # pubDate 是沒帶時區的台灣時間 "2026-09-25T15:58:43"
                when = datetime.fromisoformat(entry.get("published", ""))
            except ValueError:
                continue
            if when.tzinfo is None:
                when = when.replace(tzinfo=TW)
            if not title or "/news/" not in url or when < since or url in seen:
                continue
            seen.add(url)
            results.append({"title": title, "url": url, "time": when.isoformat(), "thumbnail": None})

    if not results:
        raise RuntimeError("工商時報 RSS 沒有抓到任何文章（可能被 Cloudflare 擋）")
    results.sort(key=lambda x: x["time"], reverse=True)
    return results
