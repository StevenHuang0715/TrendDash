"""經濟日報 熱門新聞（money.udn.com/rank/pv 瀏覽量排行榜，讀頁面內的 JSON-LD ItemList）。"""

import json
import time
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup

NAME = "經濟日報"
RANK_URL = "https://money.udn.com/rank/pv/1001/0/1"
# 最新列表的無限捲動 ajax，每頁 60 則，涵蓋全站
NEWEST_URL = "https://money.udn.com/rank/ajax_newest/1001/0/{}"
MAX_PAGES = 300
REQUEST_DELAY = 0.3
TW = timezone(timedelta(hours=8))


def _find_item_list(soup):
    for tag in soup.select('script[type="application/ld+json"]'):
        try:
            # 描述欄位常夾帶未跳脫的換行，要用 strict=False
            data = json.loads(tag.string or "", strict=False)
        except ValueError:
            continue
        nodes = data if isinstance(data, list) else data.get("@graph", [data])
        for node in nodes:
            if isinstance(node, dict) and node.get("@type") == "ItemList":
                return node
    return None


def fetch(session):
    resp = session.get(RANK_URL, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    node = _find_item_list(soup)
    if not node:
        raise RuntimeError("經濟日報排行頁找不到 JSON-LD ItemList，版面可能改了")

    entries = sorted(node.get("itemListElement", []), key=lambda e: e.get("position", 999))
    results, seen = [], set()
    for entry in entries:
        art = entry.get("item") or {}
        title = (art.get("headline") or art.get("name") or "").strip()
        # 去掉 ?from=edn_hottestlist_rank 追蹤參數
        url = (art.get("url") or "").split("?")[0]
        if not title or not url or url in seen:
            continue
        seen.add(url)
        image = art.get("image")
        thumb = image.get("url") if isinstance(image, dict) else image
        results.append({
            "title": title,
            "url": url,
            "time": art.get("datePublished"),
            "thumbnail": thumb or None,
        })

    if not results:
        raise RuntimeError("經濟日報排行榜沒有抓到任何文章")
    return results[:20]


def _parse_newest(html):
    items = []
    for row in BeautifulSoup(html, "html.parser").select("li.story-headline-wrapper"):
        link = row.select_one(".story__content a[href]")
        head = row.select_one(".story__headline")
        stamp = row.select_one("time")
        if not link or not head or not stamp:
            continue
        try:
            # 列表時間是台灣時間 "2026-09-25 12:55"
            when = datetime.strptime(stamp.get_text(strip=True), "%Y-%m-%d %H:%M").replace(tzinfo=TW)
        except ValueError:
            continue
        img = row.select_one(".story__image img[src]")
        thumb = img["src"] if img and "noimg" not in img["src"] else None
        items.append({
            "title": head.get_text(strip=True),
            "url": link["href"].split("?")[0],
            "time": when,
            "thumbnail": thumb,
        })
    return items


def fetch_recent(session, since):
    """回傳 since 之後發布的文章（依發布日期往回翻頁）。來源：money.udn.com/rank/ajax_newest 全站最新列表。"""
    results, seen = [], set()
    for page in range(1, MAX_PAGES + 1):
        if page > 1:
            time.sleep(REQUEST_DELAY)
        try:
            resp = session.get(NEWEST_URL.format(page), timeout=20)
            resp.raise_for_status()
        except Exception as exc:  # 中途失敗就回傳已抓到的
            if not results:
                raise
            print(f"  [money_udn] 第 {page} 頁失敗：{exc}")
            break
        items = _parse_newest(resp.text)
        if not items:  # 翻到底了
            break
        for it in items:
            if it["time"] >= since and it["title"] and it["url"] not in seen:
                seen.add(it["url"])
                results.append(dict(it, time=it["time"].isoformat()))
        if all(it["time"] < since for it in items):
            break

    if not results:
        raise RuntimeError("經濟日報最新列表沒有抓到任何文章")
    return results
