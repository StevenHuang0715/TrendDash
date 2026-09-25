"""TVBS 熱門新聞（news.tvbs.com.tw 首頁「熱門新聞」Top 10 排行區塊）。

TVBS 沒有獨立的排行頁，首頁伺服器端直接輸出前 10 名，所以最多 10 則。
"""

from datetime import datetime, timedelta, timezone
from time import sleep
from urllib.parse import urljoin

from bs4 import BeautifulSoup

NAME = "TVBS"
BASE = "https://news.tvbs.com.tw/"
REALTIME_API = "https://api.news.tvbs.app/v1/articles/realtime"
MAX_PAGES = 300  # 每頁固定 16 則，7 天約 200 頁
TW = timezone(timedelta(hours=8))


def fetch(session):
    resp = session.get(BASE, timeout=20)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    soup = BeautifulSoup(resp.text, "html.parser")

    box = soup.select_one('aside[data-section="top-ten-section"]')
    if not box:
        raise RuntimeError("TVBS 首頁找不到熱門新聞區塊（版面可能改了）")

    items, seen = [], set()
    for a in box.select("a[href]"):
        url = urljoin(BASE, a["href"])
        title_el = a.select_one("p")
        if not title_el or url in seen:
            continue
        # 只收新聞文章（網址結尾是數字 ID），略過影音、活動頁
        if not url.rstrip("/").rsplit("/", 1)[-1].isdigit():
            continue
        seen.add(url)
        img = a.select_one("img")
        items.append({
            "title": title_el.get_text(strip=True),
            "url": url,
            "time": None,  # 排行區塊沒有時間
            "thumbnail": urljoin(BASE, img["src"]) if img and img.get("src") else None,
        })

    if not items:
        raise RuntimeError("TVBS 熱門新聞解析不到任何項目")
    return items[:20]


def fetch_recent(session, since):
    """回傳 since 之後發布的文章（依發布日期往回翻頁）。

    資料來源：即時新聞頁背後的 JSON API api.news.tvbs.app/v1/articles/realtime（全站），
    用 next_cursor 往回翻。
    """
    items, seen = [], set()
    cursor = None
    for page in range(MAX_PAGES):
        if page:
            sleep(0.3)
        try:
            resp = session.get(REALTIME_API, params={"cursor": cursor} if cursor else None, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            if items:  # 中途失敗就回傳已抓到的
                break
            raise

        rows = data.get("data") or []
        any_new = False
        for r in rows:
            try:
                # published_at 是 unix 秒數
                published = datetime.fromtimestamp(int(r["published_at"]), TW)
            except (KeyError, TypeError, ValueError):
                continue
            if published < since:
                continue
            any_new = True
            url = urljoin(BASE, r.get("article_url") or "")
            title = (r.get("title") or "").strip()
            if not title or url == BASE or url in seen:
                continue
            seen.add(url)
            items.append({
                "title": title,
                "url": url,
                "time": published.isoformat(),
                "thumbnail": r.get("featured_image_url") or None,
            })

        cursor = ((data.get("meta") or {}).get("pagination") or {}).get("next_cursor")
        if not rows or not any_new or not cursor:
            break

    if not items:
        raise RuntimeError("TVBS 即時新聞 API 沒有抓到任何文章")
    items.sort(key=lambda x: x["time"], reverse=True)
    return items
