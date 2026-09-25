"""天下雜誌 熱門文章（cw.com.tw 首頁「訂戶最愛」排行＋「全站熱門」，再補 /today 頁的「熱門文章」）。

天下沒有公開的完整排行頁或 API，只能合併這幾個小區塊，約 10 則左右。
"""

from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup

NAME = "天下雜誌"
BASE = "https://www.cw.com.tw/"
TODAY_URL = "https://www.cw.com.tw/today"
TW = timezone(timedelta(hours=8))


def _get_soup(session, url):
    resp = session.get(url, timeout=20)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def _clean_url(href):
    # 去掉 ?rec=es 之類的推薦追蹤參數
    return urljoin(BASE, href).split("?")[0]


def _home_items(soup):
    items = []
    # 訂戶最愛：有編號 1~5 的排行
    for a in soup.select("div.cw-popular-articles a[href]"):
        title = a.select_one(".popular-card-title")
        if title:
            items.append((title.get_text(strip=True), _clean_url(a["href"]), None))
    # 全站熱門：放在搜尋下拉選單裡，有縮圖
    for a in soup.select("#channel_hot_article a.card__item[href]"):
        title = a.select_one(".card__title")
        img = a.select_one("img[data-src]")
        if title:
            items.append((title.get_text(strip=True), _clean_url(a["href"]), img["data-src"] if img else None))
    return items


def _today_items(soup):
    items = []
    for h3 in soup.find_all("h3", string=lambda s: s and s.strip() == "熱門文章"):
        for a in h3.parent.select("a[href]"):
            items.append((a.get_text(strip=True), _clean_url(a["href"]), None))
    return items


def fetch(session):
    candidates = _home_items(_get_soup(session, BASE))
    try:
        candidates += _today_items(_get_soup(session, TODAY_URL))
    except Exception as exc:  # 補充來源失敗不影響首頁結果
        print(f"  [cw] /today 失敗：{exc}")

    results, seen = [], {}
    for title, url, thumb in candidates:
        if not title or "/article/" not in url:
            continue
        if url in seen:
            # 同一篇在別的區塊有縮圖就補上
            if thumb and not seen[url]["thumbnail"]:
                seen[url]["thumbnail"] = thumb
            continue
        entry = {"title": title, "url": url, "time": None, "thumbnail": thumb}
        seen[url] = entry
        results.append(entry)

    if not results:
        raise RuntimeError("天下雜誌首頁找不到熱門文章區塊，版面可能改了")
    return results[:20]


def fetch_recent(session, since):
    """回傳 since 之後發布的文章。來源：cw.com.tw/today 最新文章頁（一次給約 70 則、涵蓋 8 天左右）。

    限制：/today 不能翻頁（「更多」只是展開頁面裡藏起來的區塊），RSS 停在 2021 年；
    列表只有日期，時間一律填當天 12:00（+08:00）。要精確時間得逐篇抓文章頁，太重就不做。
    """
    soup = _get_soup(session, TODAY_URL)

    results, seen = [], set()
    for row in soup.select("section.subArticle"):
        link = row.select_one("h3 a[href]")
        stamp = row.select_one("time")
        if not link or not stamp:
            continue
        try:
            day = datetime.strptime(stamp.get_text(strip=True), "%Y-%m-%d")
        except ValueError:
            continue
        when = day.replace(hour=12, tzinfo=TW)
        # 只有日期，比較時用當天結束，避免 since 那天的文章被切掉
        if day.replace(tzinfo=TW) + timedelta(days=1) <= since:
            continue
        url = _clean_url(link["href"])
        title = link.get_text(strip=True)
        if not title or "/article/" not in url or url in seen:
            continue
        seen.add(url)
        img = row.select_one(".pic img[src]")
        results.append({
            "title": title,
            "url": url,
            "time": when.isoformat(),
            "thumbnail": img["src"] if img else None,
        })

    if not results:
        raise RuntimeError("天下雜誌 /today 沒有抓到任何文章，版面可能改了")
    return results
