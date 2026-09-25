"""商業周刊 最新文章（businessweekly.com.tw/channel/New 最新文章列表）。

備案：商周網站目前沒有任何熱門／排行區塊（頻道頁描述寫了「熱門文章排行」但頁面上沒有，
也找不到對應的 API 或 RSS），只能退而抓最新文章列表，順序是發布時間而非熱門度。
"""

import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from requests.exceptions import ConnectionError

NAME = "商業周刊"
BASE = "https://www.businessweekly.com.tw/"
LIST_URL = "https://www.businessweekly.com.tw/channel/New"
RETRIES = 4
MAX_PAGES = 300
REQUEST_DELAY = 0.3
TW = timezone(timedelta(hours=8))


def _get(session, url):
    # 商周的伺服器常隨機 reset 新連線（WinError 10054），重試幾次通常就好
    for attempt in range(RETRIES):
        try:
            resp = session.get(url, timeout=20)
            resp.raise_for_status()
            return resp
        except ConnectionError:
            if attempt == RETRIES - 1:
                raise
            time.sleep(1 + attempt)


def _parse_list(html):
    items = []
    for row in BeautifulSoup(html, "html.parser").select("li.news-item"):
        link = row.select_one(".news-item__title a[href]")
        if not link:
            continue
        href = link["href"]
        # /indep/100xxxx 是品牌合作的業配文
        if re.search(r"/indep/100\d+", href):
            continue
        meta = row.select_one(".news-item__meta")
        m = re.search(r"\d{4}-\d{2}-\d{2}", meta.get_text() if meta else "")
        items.append({
            "title": link.get_text(strip=True),
            "url": urljoin(BASE, href),
            "time": m.group(0) if m else None,
            "thumbnail": None,
        })
    return items


def fetch(session):
    results, seen = [], set()
    for it in _parse_list(_get(session, LIST_URL).text):
        if not it["title"] or it["url"] in seen:
            continue
        seen.add(it["url"])
        results.append(it)

    if not results:
        raise RuntimeError("商業周刊最新文章列表沒有抓到任何文章，版面可能改了")
    return results[:20]


def fetch_recent(session, since):
    """回傳 since 之後發布的文章（依發布日期往回翻頁）。來源：businessweekly.com.tw/channel/New?p=N 最新文章列表。

    列表只有日期，時間一律填當天 12:00（+08:00）；精確時間要逐篇抓文章頁，太重就不做。
    """
    results, seen = [], set()
    for page in range(1, MAX_PAGES + 1):
        if page > 1:
            time.sleep(REQUEST_DELAY)
        try:
            items = _parse_list(_get(session, f"{LIST_URL}?p={page}").text)
        except Exception as exc:  # 中途失敗就回傳已抓到的
            if not results:
                raise
            print(f"  [businessweekly] 第 {page} 頁失敗：{exc}")
            break
        if not items:  # 翻到底了
            break
        page_is_old = True
        for it in items:
            if not it["time"]:
                continue
            day = datetime.strptime(it["time"], "%Y-%m-%d").replace(tzinfo=TW)
            # 只有日期，比較時用當天結束，避免 since 那天的文章被切掉
            if day + timedelta(days=1) <= since:
                continue
            page_is_old = False
            if not it["title"] or it["url"] in seen:
                continue
            seen.add(it["url"])
            results.append(dict(it, time=day.replace(hour=12).isoformat()))
        if page_is_old:
            break

    if not results:
        raise RuntimeError("商業周刊最新文章列表沒有抓到任何文章")
    return results
