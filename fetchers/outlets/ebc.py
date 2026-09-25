"""東森新聞 熱門新聞（news.ebc.net.tw/hot 熱門列表，第 2 頁起走 /list/load）。"""

from datetime import datetime
from time import sleep
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

NAME = "東森新聞"
BASE = "https://news.ebc.net.tw"
LIMIT = 20
MAX_PAGES = 3
# fetch_recent 用：即時列表只能翻約一天，再加各分類列表（每類最多 40 頁）補齊 7 天
CATEGORIES = ["politics", "society", "living", "world", "china", "business", "sport", "health", "story", "car"]
RECENT_MAX_PAGES = 300  # 所有列表合計的請求上限
XHR = {"X-Requested-With": "XMLHttpRequest"}


def _parse(html):
    results = []
    for a in BeautifulSoup(html, "html.parser").select("a.item[href]"):
        url = urljoin(BASE, a["href"])
        # 只留東森自家新聞（含 ent.ebc.net.tw 娛樂），廣告會連到外站
        if not urlparse(url).netloc.endswith("ebc.net.tw"):
            continue
        title_el = a.select_one(".item_title")
        title = (title_el.get_text(strip=True) if title_el else a.get("title", "")).strip()
        if not title:
            continue
        img = a.select_one("img")
        src = img and (img.get("data-src") or img.get("src"))
        t = a.select_one("time[datetime]")
        results.append({
            "title": title,
            "url": url,
            "time": t["datetime"] if t else None,
            "thumbnail": urljoin(BASE, src) if src else None,
        })
    return results


def fetch(session):
    resp = session.get(f"{BASE}/hot", timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    # 頁首輪播是最新新聞，排行只在 tab_content 裡
    box = soup.select_one('div.tab_content[data-type="hot"]')
    if not box:
        raise RuntimeError("東森熱門頁找不到 tab_content（版面可能改了）")
    items = _parse(str(box))

    # 首頁只有約 15 則，往下捲時網頁用 POST /list/load 載入下一頁
    page = 2
    while len(items) < LIMIT and page <= MAX_PAGES:
        r = session.post(
            f"{BASE}/list/load",
            data={"list_type": "hot", "cate_code": "", "page": page},
            headers={"X-Requested-With": "XMLHttpRequest", "Referer": f"{BASE}/hot"},
            timeout=20,
        )
        r.raise_for_status()
        more = _parse(r.text)
        if not more:
            break
        items.extend(more)
        page += 1

    results, seen = [], set()
    for it in items:
        if it["url"] not in seen:
            seen.add(it["url"])
            results.append(it)
    if not results:
        raise RuntimeError("東森熱門新聞解析不到任何項目")
    return results[:LIMIT]


def _older_than(it, since):
    return datetime.fromisoformat(it["time"]) < since


def fetch_recent(session, since):
    """回傳 since 之後發布的文章（依發布日期往回翻頁）。

    資料來源：即時列表 POST /list/load（list_type=realtime，約只到一天前），
    加上各分類列表 POST /category/load（每類最多 40 頁，約兩週）。
    娛樂新聞在 ent.ebc.net.tw 另一個站，只收得到出現在即時列表裡的。
    """
    sources = [("/list/load", {"list_type": "realtime", "cate_code": ""})]
    sources += [("/category/load", {"cate_code": c, "exclude": ""}) for c in CATEGORIES]

    items, seen = [], set()
    requests_left = RECENT_MAX_PAGES
    for path, form in sources:
        page = 1
        while requests_left > 0:
            requests_left -= 1
            sleep(0.3)
            try:
                resp = session.post(f"{BASE}{path}", data={**form, "page": page}, headers=XHR, timeout=20)
                resp.raise_for_status()
            except Exception:
                break  # 這個列表中途失敗就換下一個，已抓到的保留
            rows = [it for it in _parse(resp.text) if it["time"]]
            if not rows:
                break
            for it in rows:
                if not _older_than(it, since) and it["url"] not in seen:
                    seen.add(it["url"])
                    items.append(it)
            if all(_older_than(it, since) for it in rows):
                break
            page += 1

    if not items:
        raise RuntimeError("東森新聞列表沒有抓到任何文章")
    items.sort(key=lambda x: x["time"], reverse=True)
    return items
