"""聯合新聞網 熱門新聞（udn.com/rank/pv/2 即時新聞「最多瀏覽」排行，解析 HTML）。

fetch_recent 回補過去幾天的文章，合併兩個來源：
- udn.com/api/more 的即時新聞 JSON（全站即時列表）：翻得到 7 天前，但越舊的日子收錄越少（例如 1 天前約 480 則、6 天前只剩約 50 則）。
- Google News sitemap（udn.com/sitemap/gnews/2）：只有最近約 2 天，但較完整。
"""

import html
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

NAME = "聯合新聞網"
URL = "https://udn.com/rank/pv/2"
LIMIT = 20

RECENT_API = "https://udn.com/api/more"
SITEMAP_INDEX = "https://udn.com/sitemap/gnews/2"
MAX_PAGES = 300  # 一頁 20 則，7 天大約 50~100 頁
REQUEST_DELAY = 0.3
TW = timezone(timedelta(hours=8))


def _iso(text):
    # 頁面時間格式 "2026-09-24 17:28"（台灣時間）
    text = text.strip()
    if len(text) == 16:
        return text.replace(" ", "T") + ":00+08:00"
    return None


def fetch(session):
    resp = session.get(URL, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    items = []
    seen = set()
    for node in soup.select("div.story-list__news"):
        link = node.select_one("div.story-list__text a[href]")
        if not link:
            continue
        url = urljoin(URL, link["href"])
        title = link.get_text(strip=True)
        # 「猜你喜歡」等區塊是前端填的空殼（href="#"），要略過
        if not title or "/news/story/" not in url or url in seen:
            continue
        seen.add(url)

        time_el = node.select_one(".story-list__time")
        img = node.select_one(".story-list__image img[src]")
        items.append({
            "title": title,
            "url": url,
            "time": _iso(time_el.get_text()) if time_el else None,
            "thumbnail": urljoin(URL, img["src"]) if img else None,
        })
        if len(items) >= LIMIT:
            break

    if not items:
        raise RuntimeError("聯合新聞網：排行頁解析不到任何新聞")
    return items


def _strip_query(url):
    # 列表連結帶 ?from=udn-ch1_breaknews-... 追蹤參數
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _recent_time(row):
    # time.dateTime 雖然結尾是 Z，實際上是台灣時間，所以用 time.date 配 +08:00
    try:
        return datetime.strptime(row["time"]["date"], "%Y-%m-%d %H:%M").replace(tzinfo=TW)
    except (KeyError, TypeError, ValueError):
        return None


def _xml_text(block, tag):
    m = re.search(rf"<{tag}>(.*?)</{tag}>", block, re.S)
    if not m:
        return ""
    text = m.group(1).strip()
    if text.startswith("<![CDATA["):
        text = text[9:-3]
    return html.unescape(text).strip()


def _get(session, url, **kwargs):
    time.sleep(REQUEST_DELAY)
    resp = session.get(url, timeout=20, **kwargs)
    resp.raise_for_status()
    return resp


def fetch_recent(session, since):
    """回傳 since 之後發布的文章（依發布日期往回翻頁）。資料來源：udn.com/api/more?type=breaknews 與 udn.com/sitemap/gnews/2。"""
    items = []
    seen = set()

    def add(row):
        if row["title"] and "/news/story/" in row["url"] and row["url"] not in seen:
            seen.add(row["url"])
            items.append(row)

    # 1. 即時新聞 API：可翻到 7 天前，但越舊的日子收錄越少（不是完整清單）
    for page in range(1, MAX_PAGES + 1):
        try:
            resp = _get(session, RECENT_API, params={
                "page": page, "id": "", "channelId": 1, "cate_id": 0, "type": "breaknews", "totalRecNo": 100,
            })
            rows = resp.json().get("lists") or []
        except Exception as exc:
            print(f"  [udn] API 第 {page} 頁失敗，改用 sitemap：{exc}")
            break
        if not rows:
            break

        any_new = False
        for row in rows:
            dt = _recent_time(row)
            if dt is None or dt < since:
                continue
            any_new = True
            add({
                "title": (row.get("title") or "").strip(),
                "url": _strip_query(urljoin(URL, row.get("titleLink") or "")),
                "time": dt.isoformat(),
                "thumbnail": row.get("url") or None,
            })
        if not any_new:  # 整頁都比 since 舊，不用再翻
            break

    # 2. Google News sitemap：只有最近約 2 天，但很完整，補上 API 漏掉的
    try:
        index = _get(session, SITEMAP_INDEX).text
        for sitemap in re.findall(r"<loc>(.*?)</loc>", index)[:10]:
            text = _get(session, html.unescape(sitemap.strip())).text
            for block in re.findall(r"<url>(.*?)</url>", text, re.S):
                try:
                    dt = datetime.fromisoformat(_xml_text(block, "news:publication_date"))
                except ValueError:
                    continue
                if dt.tzinfo is None or dt < since:
                    continue
                add({
                    "title": " ".join(_xml_text(block, "news:title").split()),
                    "url": _strip_query(_xml_text(block, "loc")),
                    "time": dt.astimezone(TW).isoformat(),
                    "thumbnail": None,
                })
    except Exception as exc:
        print(f"  [udn] sitemap 失敗：{exc}")

    if not items:
        raise RuntimeError("聯合新聞網：即時新聞 API 與 sitemap 都沒有抓到任何新聞")
    items.sort(key=lambda x: x["time"], reverse=True)
    return items
