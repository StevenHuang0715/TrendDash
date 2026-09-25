"""紐約時報中文網（cn.nytimes.com 繁體版文章頁側欄的「最受歡迎」排行；抓不到時退回繁體 RSS 最新文章）。

做法：先讀 RSS 拿一篇最新文章的網址，再打開那篇文章，解析側欄 div.hot_article 的前 10 名。
"""

import re
import time
from datetime import datetime, timedelta, timezone
from time import mktime

import feedparser
from bs4 import BeautifulSoup

NAME = "紐約時報中文網"
BASE = "https://cn.nytimes.com"
RSS_URL = "https://cn.nytimes.com/rss/zh-hant/"

# 近期文章：各頻道列表頁，第 N 頁網址是 /world/N/zh-hant/，每頁約 20 篇
SECTIONS = ["world", "china", "usa", "asia-pacific", "business", "technology", "opinion", "culture", "science", "health", "style"]
MAX_PAGES = 40  # 所有請求合計上限
REQUEST_DELAY = 0.3
CST = timezone(timedelta(hours=8))


def _clean_url(url):
    # 去掉 ?utm_source=... 追蹤參數，才能跟 RSS 的網址對上
    return url.split("?", 1)[0]


def _date_from_url(url):
    # 網址形如 /china/20260924/xxx/zh-hant/，只有日期
    m = re.search(r"/(\d{4})(\d{2})(\d{2})/", url)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def _rss_entries(session):
    resp = session.get(RSS_URL, timeout=20)
    resp.raise_for_status()
    entries = []
    for e in feedparser.parse(resp.content).entries:
        published = None
        if e.get("published_parsed"):
            published = datetime.fromtimestamp(mktime(e.published_parsed), timezone.utc).isoformat()
        img = re.search(r"<img[^>]+src='([^']+)'", e.get("description", ""))
        entries.append(
            {
                "title": e.title.strip(),
                "url": _clean_url(e.link),
                "time": published or _date_from_url(e.link),
                "thumbnail": img.group(1) if img else None,
            }
        )
    return entries


def _most_popular(session, article_url, rss_by_url):
    resp = session.get(article_url, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    for a in soup.select("div.hot_article ol li a"):
        h4 = a.find("h4")
        if not h4 or not a.get("href"):
            continue
        url = _clean_url(a["href"])
        if url.startswith("/"):
            url = BASE + url
        img = a.find("img")
        rss = rss_by_url.get(url, {})
        results.append(
            {
                "title": h4.get_text(strip=True),
                "url": url,
                "time": rss.get("time") or _date_from_url(url),
                "thumbnail": (img.get("src") if img else None) or rss.get("thumbnail"),
            }
        )
    return results


def fetch(session):
    rss = _rss_entries(session)
    rss_by_url = {e["url"]: e for e in rss}

    ranked = []
    if rss:
        try:
            ranked = _most_popular(session, rss[0]["url"], rss_by_url)
        except Exception as exc:  # 排行抓不到就用 RSS
            print(f"  [nyt_zh] 最受歡迎排行失敗，改用 RSS：{exc}")

    items, seen = [], set()
    for it in ranked or rss:
        if it["title"] and it["url"] not in seen:
            seen.add(it["url"])
            items.append(it)
    if not items:
        raise ValueError("紐約時報中文網解析不到任何文章")
    return items[:20]


def _section_items(html):
    soup = BeautifulSoup(html, "html.parser")
    results = []
    # 第一頁頂端的頭條在 sectionLeadHeader，其餘在 li.autoListStory
    for box in soup.select("li.autoListStory, div.collection-item"):
        a = box.select_one("h3 a, .sectionLeadHeader a")
        if not a or not a.get("href"):
            continue
        url = _clean_url(a["href"])
        if url.startswith("//"):
            url = "https:" + url
        elif url.startswith("/"):
            url = BASE + url
        day = _date_from_url(url)
        if not day:
            continue
        img = box.find("img")
        thumb = img and (img.get("data-url") or img.get("src"))
        results.append(
            {
                "title": (a.get("title") or a.get_text()).strip(),
                "url": url,
                "day": day,
                "thumbnail": thumb if thumb and thumb.startswith("http") else None,
            }
        )
    return results


def fetch_recent(session, since):
    """回傳 since 之後發布的文章。來源：繁體 RSS（cn.nytimes.com/rss/zh-hant/，最近約 20 篇，有精確時間）
    加上各頻道列表頁（cn.nytimes.com/<頻道>/<頁>/zh-hant/）往回翻頁。

    列表頁只有網址裡的日期，不在 RSS 裡的文章時間一律記為當天 12:00（北京時間 +08:00）。
    """
    found = {}
    requests_left = MAX_PAGES
    since_day = since.astimezone(CST).strftime("%Y-%m-%d")

    def get(url):
        nonlocal requests_left
        requests_left -= 1
        time.sleep(REQUEST_DELAY)
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
        return resp

    try:
        requests_left -= 1
        for e in _rss_entries(session):
            t = e["time"]
            # RSS 時間有時區；少數只剩日期的就跳過，等列表頁補
            if t and "T" in t and datetime.fromisoformat(t) >= since:
                found[e["url"]] = e
        for section in SECTIONS:
            page = 1
            while requests_left > 0:
                url = f"{BASE}/{section}/zh-hant/" if page == 1 else f"{BASE}/{section}/{page}/zh-hant/"
                items = _section_items(get(url).text)
                for it in items:
                    if it["day"] >= since_day and it["url"] not in found:
                        noon = datetime.fromisoformat(it["day"] + "T12:00:00").replace(tzinfo=CST)
                        if noon >= since:
                            found[it["url"]] = {
                                "title": it["title"],
                                "url": it["url"],
                                "time": noon.isoformat(),
                                "thumbnail": it["thumbnail"],
                            }
                # 列表有置頂舊文，整頁都比 since 舊才停
                if not items or all(it["day"] < since_day for it in items):
                    break
                page += 1
    except Exception as exc:  # 中途失敗就回傳目前拿到的
        print(f"  [nyt_zh] fetch_recent 中斷：{exc}")

    if not found:
        raise ValueError("紐約時報中文網近期文章解析不到任何文章")
    return sorted(found.values(), key=lambda x: datetime.fromisoformat(x["time"]), reverse=True)
