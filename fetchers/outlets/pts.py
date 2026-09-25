"""公視 熱門新聞（news.pts.org.tw 首頁「最多人閱讀」排行區塊）。

公視沒有獨立的排行頁或 API，首頁只列前 8 名。
"""

from datetime import datetime, timedelta, timezone
from time import sleep
from urllib.parse import urljoin

from bs4 import BeautifulSoup

NAME = "公視"
BASE = "https://news.pts.org.tw/"
MAX_PAGES = 300  # 每頁約 14 則，7 天約 30 頁
TW = timezone(timedelta(hours=8))


def _to_iso(text):
    # 頁面格式 "2026/9/22 13:20"，台灣時間
    try:
        return datetime.strptime(text.strip(), "%Y/%m/%d %H:%M").isoformat() + "+08:00"
    except ValueError:
        return None


def fetch(session):
    resp = session.get(BASE, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # 排行區塊沒有縮圖，借用首頁其他區塊同一篇文章的圖
    thumbs = {}
    for a in soup.select("a[href]"):
        img = a.find("img")
        src = img and (img.get("src") or img.get("data-src"))
        if src and not src.startswith("data:"):
            thumbs.setdefault(urljoin(BASE, a["href"]), urljoin(BASE, src))

    items, seen = [], set()
    for a in soup.select("ul.most-list a[href]"):
        url = urljoin(BASE, a["href"])
        content = a.select_one(".most-news-content")
        if not content or url in seen:
            continue
        seen.add(url)
        t = content.find("time")
        time_text = t.get_text(strip=True) if t else ""
        if t:
            t.extract()
        items.append({
            "title": content.get_text(strip=True),
            "url": url,
            "time": _to_iso(time_text) if time_text else None,
            "thumbnail": thumbs.get(url),
        })

    if not items:
        raise RuntimeError("公視首頁找不到「最多人閱讀」項目（版面可能改了）")
    return items[:20]


def fetch_recent(session, since):
    """回傳 since 之後發布的文章（依發布日期往回翻頁）。

    資料來源：即時新聞列表 news.pts.org.tw/dailynews?page=N（全站，HTML）。
    """
    items, seen = [], set()
    for page in range(1, MAX_PAGES + 1):
        if page > 1:
            sleep(0.3)
        try:
            resp = session.get(f"{BASE}dailynews", params={"page": page}, timeout=20)
            resp.raise_for_status()
        except Exception:
            if items:
                break
            raise
        soup = BeautifulSoup(resp.text, "html.parser")

        rows = soup.select("ul.news-list-update > li")
        if not rows:
            break
        any_new = False
        for li in rows:
            a = li.select_one("h2 a[href]")
            t = li.select_one("time[datetime]")
            if not a or not t:
                continue
            try:
                # datetime 屬性 "2026-09-25 14:09:39"，台灣時間
                published = datetime.strptime(t["datetime"].strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=TW)
            except ValueError:
                continue
            if published < since:
                continue
            any_new = True
            url = urljoin(BASE, a["href"])
            if url in seen:
                continue
            seen.add(url)
            img = li.select_one("img")
            src = img and img.get("src")
            items.append({
                "title": a.get_text(strip=True),
                "url": url,
                "time": published.isoformat(),
                "thumbnail": urljoin(BASE, src) if src and not src.startswith("data:") else None,
            })
        if not any_new:  # 整頁都比 since 舊
            break

    if not items:
        raise RuntimeError("公視即時新聞列表沒有抓到任何文章")
    items.sort(key=lambda x: x["time"], reverse=True)
    return items
