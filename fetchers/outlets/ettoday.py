"""ETtoday 新聞雲 熱門新聞（www.ettoday.net/news/hot-news.htm 熱門新聞排行，解析 HTML）。

fetch_recent 翻「新聞總覽」：每一天先抓 news-list-YYYY-MM-DD-0.htm（前 100 則），
再 POST show_roll.php 往下捲（每次 10 則），直到捲到前一天為止。
"""

import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup

NAME = "ETtoday 新聞雲"
URL = "https://www.ettoday.net/news/hot-news.htm"
LIMIT = 20
TW = timezone(timedelta(hours=8))

LIST_URL = "https://www.ettoday.net/news/news-list-{date}-0.htm"
ROLL_URL = "https://www.ettoday.net/show_roll.php"
MAX_PAGES = 400  # 一次 10 則，一天約 40 次，7 天約 280 次
REQUEST_DELAY = 0.3


def _iso(text):
    # 時間是相對的："6小時前"、"45分鐘前"；超過一天變成 "9/24 16:05"（沒有年份）
    text = text.strip()
    now = datetime.now(TW)
    m = re.match(r"(\d+)\s*(分鐘|小時|天)前", text)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        delta = {"分鐘": timedelta(minutes=n), "小時": timedelta(hours=n), "天": timedelta(days=n)}[unit]
        return (now - delta).replace(second=0, microsecond=0).isoformat()
    m = re.match(r"(?:(\d{4})[-/])?(\d{1,2})[-/](\d{1,2})\s+(\d{1,2}):(\d{2})", text)
    if m:
        year, month, day, hour, minute = m.groups()
        try:
            d = datetime(int(year or now.year), int(month), int(day), int(hour), int(minute), tzinfo=TW)
        except ValueError:
            return None
        if not year and d > now + timedelta(days=1):  # 跨年：12/31 出現在 1 月
            d = d.replace(year=d.year - 1)
        return d.isoformat()
    return None


def fetch(session):
    resp = session.get(URL, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    items = []
    seen = set()
    # 主排行在 part_pictxt_3，每則前面有排名數字 em.number
    for piece in soup.select("div.part_pictxt_3 div.piece"):
        link = piece.select_one("h3 a[href]")
        if not link or not piece.select_one("em.number"):
            continue
        url = urljoin(URL, link["href"])
        title = link.get_text(strip=True)
        if not title or "ettoday.net" not in url or url in seen:
            continue
        seen.add(url)

        date_el = piece.select_one("span.date")
        img = piece.select_one("a.pic img")
        # 真正的圖在 data-original（lazy load），src 只是 loading 圖
        thumb = img.get("data-original") or img.get("src") if img else None
        items.append({
            "title": title,
            "url": url,
            "time": _iso(date_el.get_text()) if date_el else None,
            "thumbnail": urljoin(URL, thumb) if thumb else None,
        })
        if len(items) >= LIMIT:
            break

    if not items:
        raise RuntimeError("ETtoday：熱門頁解析不到任何新聞")
    return items


def _list_rows(html_text):
    # 每則是 <h3><span class="date">2026/09/20 23:55</span><em class="tag">…</em><a href=…>標題</a></h3>
    soup = BeautifulSoup(html_text, "html.parser")
    rows = []
    for h3 in soup.select("h3"):
        date_el = h3.select_one("span.date")
        link = h3.select_one("a[href]")
        if not date_el or not link:
            continue
        try:
            dt = datetime.strptime(date_el.get_text(strip=True), "%Y/%m/%d %H:%M").replace(tzinfo=TW)
        except ValueError:
            continue
        rows.append((dt, link.get_text(strip=True), urljoin(URL, link["href"])))
    return rows


def fetch_recent(session, since):
    """回傳 since 之後發布的文章（依發布日期往回翻頁）。資料來源：www.ettoday.net/news/news-list-<日期>-0.htm + show_roll.php。"""
    items = []
    seen = set()
    requests_made = 0
    day = datetime.now(TW).replace(hour=0, minute=0, second=0, microsecond=0)
    since_tw = since.astimezone(TW)

    # 同一條捲動鏈只能捲約 150 次，所以每天各自從當天的總覽頁開始捲
    while day + timedelta(days=1) > since_tw and requests_made < MAX_PAGES:
        day_start = max(day, since_tw)
        for offset in range(MAX_PAGES):
            if requests_made >= MAX_PAGES:
                break
            if requests_made:
                time.sleep(REQUEST_DELAY)
            requests_made += 1
            try:
                if offset == 0:
                    resp = session.get(LIST_URL.format(date=day.strftime("%Y-%m-%d")), timeout=20)
                else:
                    resp = session.post(ROLL_URL, data={
                        "offset": offset, "tPage": "3", "tFile": day.strftime("%Y%m%d") + ".xml",
                        "tOt": "0", "tSi": "100", "tAr": "0",
                    }, timeout=20)
                resp.raise_for_status()
            except Exception as exc:
                print(f"  [ettoday] {day:%m-%d} 第 {offset} 頁失敗，換下一天：{exc}")
                break

            rows = _list_rows(resp.text)
            if not rows:  # 捲到底時回傳 null
                break
            any_new = False
            for dt, title, url in rows:
                # 捲過頭會接到前一天，那些留給前一天的鏈處理
                if dt < day_start:
                    continue
                any_new = True
                if not title or "ettoday.net" not in url or url in seen:
                    continue
                seen.add(url)
                items.append({"title": title, "url": url, "time": dt.isoformat(), "thumbnail": None})
            if not any_new:  # 整頁都比這一天（或 since）早
                break
        day -= timedelta(days=1)

    if not items:
        raise RuntimeError("ETtoday：新聞總覽沒有抓到任何新聞")
    items.sort(key=lambda x: x["time"], reverse=True)
    return items
