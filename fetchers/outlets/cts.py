"""華視 熱門新聞（news.cts.com.tw 網站自己的 JSON API：/api/news/rankings「熱門新聞排行」）。

API 只給前 5 名，且沒有時間與縮圖，所以再逐篇抓文章頁的 og:image 與發布時間。
"""

from datetime import datetime, timedelta, timezone
from time import sleep
from urllib.parse import urljoin

from bs4 import BeautifulSoup

NAME = "華視"
BASE = "https://news.cts.com.tw"
# fetch_recent 用：即時快訊只有最近約一天，所以再翻各分類（產業 pr 是業配，不收）
CATEGORIES = ["politics", "international", "society", "sports", "life", "money",
              "local", "general", "arts", "entertain", "weather"]
PAGE_LIMIT = 100  # API 的 limit 參數，超過 100 會回錯誤
RECENT_MAX_PAGES = 300  # 所有列表合計的請求上限
TW = timezone(timedelta(hours=8))


def _article_meta(session, url):
    # 補時間與縮圖；單篇失敗就留 None，不影響整個排行
    try:
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
    except Exception:
        return None, None
    soup = BeautifulSoup(resp.text, "html.parser")
    t = soup.select_one('meta[property="article:published_time"]')
    img = soup.select_one('meta[property="og:image"]')
    return (
        t["content"] if t and t.get("content") else None,
        urljoin(url, img["content"]) if img and img.get("content") else None,
    )


def fetch(session):
    resp = session.get(f"{BASE}/api/news/rankings", timeout=20)
    resp.raise_for_status()
    rankings = (resp.json().get("data") or {}).get("rankings") or []

    items, seen = [], set()
    for r in rankings:
        title = (r.get("title") or "").strip()
        if not title or not r.get("link"):
            continue
        url = urljoin(BASE, r["link"])
        if url in seen:
            continue
        seen.add(url)
        time, thumbnail = _article_meta(session, url)
        items.append({"title": title, "url": url, "time": time, "thumbnail": thumbnail})

    if not items:
        raise RuntimeError("華視熱門新聞排行 API 沒有回傳任何項目")
    return items[:20]


def _parse_time(text):
    # publishTime 有 "2026-09-25 16:52:29" 與 "2026/09/25 13:15" 兩種寫法，台灣時間
    text = (text or "").strip().replace("/", "-")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=TW)
        except ValueError:
            pass
    return None


def fetch_recent(session, since):
    """回傳 since 之後發布的文章（依發布日期往回翻頁）。

    資料來源：網站自己的 JSON API，/api/news/breaking-list（即時快訊，約一天）
    加上 /api/news/<分類>/list（各分類，可往回很久），參數 page、limit=100。
    """
    paths = ["/api/news/breaking-list"] + [f"/api/news/{c}/list" for c in CATEGORIES]

    items, seen = [], set()
    requests_left = RECENT_MAX_PAGES
    for path in paths:
        page = 1
        while requests_left > 0:
            requests_left -= 1
            sleep(0.3)
            try:
                resp = session.get(f"{BASE}{path}", params={"page": page, "limit": PAGE_LIMIT}, timeout=20)
                resp.raise_for_status()
                data = resp.json().get("data") or {}
            except Exception:
                break  # 這個列表中途失敗就換下一個，已抓到的保留
            rows = data.get("articles") or []
            any_new = False
            for r in rows:
                published = _parse_time(r.get("publishTime"))
                title = (r.get("title") or "").strip()
                if not published or not title or not r.get("link") or published < since:
                    continue
                any_new = True
                url = urljoin(BASE, r["link"])
                if url in seen:
                    continue
                seen.add(url)
                img = r.get("imageUrl")
                items.append({
                    "title": title,
                    "url": url,
                    "time": published.isoformat(),
                    "thumbnail": urljoin(BASE, img) if img else None,
                })
            total = (data.get("pagination") or {}).get("totalPages") or 0
            if not rows or not any_new or page >= total:
                break
            page += 1

    if not items:
        raise RuntimeError("華視新聞 API 沒有抓到任何文章")
    items.sort(key=lambda x: x["time"], reverse=True)
    return items
