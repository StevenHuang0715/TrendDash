"""自由時報 熱門新聞（news.ltn.com.tw/list/breakingnews/popular 背後的 ajax JSON：/ajax/breakingnews/popular/1）。

fetch_recent 回補過去幾天的文章，來源有兩種：
- 各子站的 Google News sitemap（有標題與精確發布時間）：news 只涵蓋約 2 天，ent / sports / ec / health 約 7 天。
- news 各分類的即時列表 ajax（/ajax/breakingnews/<分類>/<頁>），最多只能翻 25 頁，
  政治、生活、地方大約只回得到 1~2 天，社會、國際較深。所以 news 主站 2 天前的文章會有缺漏。
"""

import html
import json
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit

NAME = "自由時報"
API = "https://news.ltn.com.tw/ajax/breakingnews/popular/{page}"
LIMIT = 20

SITEMAPS = [
    "https://news.ltn.com.tw/sitemap.xml",
    "https://ent.ltn.com.tw/sitemap.xml",
    "https://sports.ltn.com.tw/sitemap.xml",
    "https://ec.ltn.com.tw/sitemap.xml",
    "https://health.ltn.com.tw/sitemap.xml",
]
RECENT_API = "https://news.ltn.com.tw/ajax/breakingnews/{cat}/{page}"
# 娛樂、體育、財經已由子站 sitemap 涵蓋 7 天，這裡只翻 news 主站的分類
RECENT_CATS = ["politics", "society", "world", "life", "local", "novelty"]
CAT_MAX_PAGES = 25  # 伺服器只給到第 25 頁
MAX_PAGES = 300  # 全部請求數上限
REQUEST_DELAY = 0.3
TW = timezone(timedelta(hours=8))


def _iso(text):
    # 格式通常是 "2026/09/24 16:25"；只有 "16:25" 時視為今天
    text = (text or "").strip()
    try:
        if len(text) == 5:
            text = datetime.now().strftime("%Y/%m/%d ") + text
        return datetime.strptime(text, "%Y/%m/%d %H:%M").strftime("%Y-%m-%dT%H:%M:00+08:00")
    except ValueError:
        return None


def fetch(session):
    items = []
    seen = set()
    for page in (1, 2):
        resp = session.get(API.format(page=page), timeout=20)
        resp.raise_for_status()
        # 回應開頭帶 UTF-8 BOM，resp.json() 會失敗
        data = json.loads(resp.content.decode("utf-8-sig"))
        rows = data.get("data") or []
        # 第 1 頁是 list，之後的頁是 {"20": {...}, ...} 的 dict
        if isinstance(rows, dict):
            rows = list(rows.values())

        for row in rows:
            url = (row.get("url") or "").strip()
            title = (row.get("title") or "").strip()
            if not url.startswith("http") or not title or url in seen:
                continue
            seen.add(url)
            items.append({
                "title": " ".join(title.split()),
                "url": url,
                "time": _iso(row.get("time")),
                "thumbnail": row.get("photo_L") or row.get("photo_S") or None,
            })
        if len(items) >= LIMIT:
            break

    if not items:
        raise RuntimeError("自由時報：熱門 API 沒有回傳任何新聞")
    return items[:LIMIT]


def _strip_query(url):
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


def _sitemap_items(text, since):
    results = []
    for block in re.findall(r"<url>(.*?)</url>", text, re.S):
        try:
            # 少數舊文日期是 "-001-11-30..." 這種壞值，直接略過
            dt = datetime.fromisoformat(_xml_text(block, "news:publication_date"))
        except ValueError:
            continue
        if dt.tzinfo is None or dt < since:
            continue
        results.append({
            "title": " ".join(_xml_text(block, "news:title").split()),
            "url": _strip_query(_xml_text(block, "loc")),
            "time": dt.astimezone(TW).isoformat(),
            "thumbnail": _xml_text(block, "image:loc") or None,
        })
    return results


def _ajax_time(text):
    # 今天的只有 "16:25"，較早的是 "2026/09/24 16:25"
    text = (text or "").strip()
    if len(text) == 5:
        text = datetime.now(TW).strftime("%Y/%m/%d ") + text
    try:
        return datetime.strptime(text, "%Y/%m/%d %H:%M").replace(tzinfo=TW)
    except ValueError:
        return None


def fetch_recent(session, since):
    """回傳 since 之後發布的文章（依發布日期往回翻頁）。資料來源：*.ltn.com.tw/sitemap.xml 與 news.ltn.com.tw/ajax/breakingnews/<分類>/<頁>。"""
    items = []
    seen = set()
    requests_made = 0

    def add(row):
        if row["title"] and row["url"].startswith("http") and row["url"] not in seen:
            seen.add(row["url"])
            items.append(row)

    def get(url):
        nonlocal requests_made
        if requests_made:
            time.sleep(REQUEST_DELAY)
        requests_made += 1
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
        return resp

    for sitemap in SITEMAPS:
        try:
            resp = get(sitemap)
        except Exception as exc:  # 單一 sitemap 失敗不影響其他來源
            print(f"  [ltn] {sitemap} 失敗：{exc}")
            continue
        for row in _sitemap_items(resp.content.decode("utf-8-sig", errors="replace"), since):
            add(row)

    for cat in RECENT_CATS:
        for page in range(1, CAT_MAX_PAGES + 1):
            if requests_made >= MAX_PAGES:
                break
            try:
                data = json.loads(get(RECENT_API.format(cat=cat, page=page)).content.decode("utf-8-sig"))
            except Exception as exc:
                print(f"  [ltn] {cat} 第 {page} 頁失敗，換下一個分類：{exc}")
                break
            rows = data.get("data") or []
            if isinstance(rows, dict):
                rows = list(rows.values())
            if not rows:
                break

            any_new = False
            for row in rows:
                dt = _ajax_time(row.get("time"))
                if dt is None or dt < since:
                    continue
                any_new = True
                add({
                    "title": " ".join((row.get("title") or "").split()),
                    "url": _strip_query((row.get("url") or "").strip()),
                    "time": dt.isoformat(),
                    "thumbnail": row.get("photo_S") or row.get("photo_L") or None,
                })
            if not any_new:  # 整頁都比 since 舊
                break

    if not items:
        raise RuntimeError("自由時報：sitemap 與即時列表都沒有抓到任何新聞")
    items.sort(key=lambda x: x["time"], reverse=True)
    return items
