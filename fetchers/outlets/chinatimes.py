"""中時新聞網 熱門新聞（www.chinatimes.com/hotnews/ 熱門即時新聞排行，解析 HTML）。

fetch_recent 讀 Google News sitemap（sitemap_todaynews.xml、_d2.xml，各 1000 則），只涵蓋約 3 天。
即時列表 /realtimenews/PageList 與各分類列表都只給到第 10 頁，沒辦法翻得更早。
"""

import html
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

NAME = "中時新聞網"
URL = "https://www.chinatimes.com/hotnews/"
LIMIT = 20

SITEMAPS = [
    "https://www.chinatimes.com/sitemaps/sitemap_todaynews.xml",
    "https://www.chinatimes.com/sitemaps/sitemap_todaynews_d2.xml",
]
REQUEST_DELAY = 0.3
TW = timezone(timedelta(hours=8))


def _iso(text):
    # <time datetime="2026/09/25 12:33">（台灣時間）
    text = (text or "").strip()
    if len(text) == 16:
        return text.replace("/", "-").replace(" ", "T") + ":00+08:00"
    return None


def fetch(session):
    resp = session.get(URL, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    items = []
    seen = set()
    for li in soup.select("ol.article-list > li"):
        link = li.select_one("h3.title a[href]")
        if not link:  # 廣告格沒有標題連結
            continue
        url = urljoin(URL, link["href"])
        title = link.get_text(strip=True)
        if not title or "chinatimes.com" not in url or url in seen:
            continue
        seen.add(url)

        time_el = li.select_one("time[datetime]")
        img = li.select_one("img.photo")
        thumb = img.get("data-src") or img.get("src") if img else None
        items.append({
            "title": title,
            "url": url,
            "time": _iso(time_el["datetime"]) if time_el else None,
            "thumbnail": urljoin(URL, thumb) if thumb else None,
        })
        if len(items) >= LIMIT:
            break

    if not items:
        raise RuntimeError("中時新聞網：熱門頁解析不到任何新聞")
    return items


def _strip_query(url):
    # sitemap 的網址有時帶 ?chdtv 之類的參數
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _xml_text(block, tag):
    m = re.search(rf"<{tag}>(.*?)</{tag}>", block, re.S)
    if not m:
        return ""
    text = m.group(1).strip()
    if text.startswith("<![CDATA["):
        text = text[9:-3]
    return html.unescape(text).strip()


def fetch_recent(session, since):
    """回傳 since 之後發布的文章（依發布日期往回翻頁）。資料來源：www.chinatimes.com/sitemaps/sitemap_todaynews*.xml（約 3 天）。"""
    items = []
    seen = set()
    for i, sitemap in enumerate(SITEMAPS):
        if i:
            time.sleep(REQUEST_DELAY)
        try:
            resp = session.get(sitemap, timeout=20)
            resp.raise_for_status()
        except Exception as exc:
            if not items:
                raise
            print(f"  [chinatimes] {sitemap} 失敗，先回傳已抓到的：{exc}")
            break

        any_new = False
        for block in re.findall(r"<url>(.*?)</url>", resp.text, re.S):
            try:
                dt = datetime.fromisoformat(_xml_text(block, "news:publication_date"))
            except ValueError:
                continue
            if dt.tzinfo is None or dt < since:
                continue
            any_new = True
            url = _strip_query(urljoin(URL, _xml_text(block, "loc")))
            title = " ".join(_xml_text(block, "news:title").split())
            if not title or "chinatimes.com" not in url or url in seen:
                continue
            seen.add(url)
            items.append({
                "title": title,
                "url": url,
                "time": dt.astimezone(TW).isoformat(),
                "thumbnail": _xml_text(block, "image:loc") or None,
            })
        if not any_new:  # 這份 sitemap 全都比 since 舊，下一份更舊
            break

    if not items:
        raise RuntimeError("中時新聞網：sitemap 沒有抓到任何新聞")
    items.sort(key=lambda x: x["time"], reverse=True)
    return items
