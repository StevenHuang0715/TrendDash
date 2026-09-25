"""鉅亨網 熱門新聞（api.cnyes.com 人氣新聞 JSON，即 news.cnyes.com/trending 的資料來源）。"""

import time
from datetime import datetime, timedelta, timezone

NAME = "鉅亨網"
API_URL = "https://api.cnyes.com/media/api/v1/newslist/popular"
NEWS_URL = "https://news.cnyes.com/news/id/{}"
# 「即時頭條」涵蓋大部分即時新聞；台股、國際股各有一些沒進頭條，一起抓；limit 上限 30
LIST_URL = "https://api.cnyes.com/media/api/v1/newslist/category/{}"
CATEGORIES = ["headline", "tw_stock", "wd_stock"]
PAGE_SIZE = 30
MAX_PAGES = 300
REQUEST_DELAY = 0.3
TW = timezone(timedelta(hours=8))


def _thumbnail(news):
    cover = news.get("coverSrc") or {}
    for size in ("m", "l", "s"):
        src = (cover.get(size) or {}).get("src")
        if src:
            return src
    return None


def fetch(session):
    resp = session.get(API_URL, timeout=20)
    resp.raise_for_status()
    groups = resp.json().get("items") or {}

    # "all" 是總排行但只有 10 則；不足的用各分類（台股、國際股、外匯…）輪流補上
    # 分類清單沒有瀏覽數，無法跟總排行混排
    # "_order" 是分類名稱字串清單，不是文章
    lists = [v for k, v in groups.items() if k not in ("all", "_order") and isinstance(v, list)]
    ranked = list(groups.get("all") or [])
    for i in range(max(map(len, lists), default=0)):
        ranked += [lst[i] for lst in lists if i < len(lst)]

    seen = set()
    results = []
    for news in ranked:
        if not isinstance(news, dict):
            continue
        news_id = news.get("newsId")
        title = (news.get("title") or "").strip()
        if not news_id or not title or news_id in seen:
            continue
        seen.add(news_id)
        ts = news.get("publishAt")
        results.append({
            "title": title,
            "url": NEWS_URL.format(news_id),
            "time": datetime.fromtimestamp(ts, timezone.utc).isoformat() if ts else None,
            "thumbnail": _thumbnail(news),
        })

    if not results:
        raise RuntimeError("鉅亨網人氣新聞 API 沒有回傳任何文章")
    return results[:20]


def _day_windows(since):
    # 台灣時間逐日切段，從今天往回到 since 那天
    day = datetime.now(TW).replace(hour=0, minute=0, second=0, microsecond=0)
    while day + timedelta(days=1) > since:
        yield int(max(day, since).timestamp()), int((day + timedelta(days=1)).timestamp()) - 1
        day -= timedelta(days=1)


def fetch_recent(session, since):
    """回傳 since 之後發布的文章（依發布日期往回翻頁）。來源：api.cnyes.com newslist/category/{headline,tw_stock,wd_stock}（startAt/endAt 限定時間範圍）。"""
    # API 的 endAt 實際上以「天」為單位、page 最多 30 頁，所以一天一段分開翻頁
    start_at = int(since.timestamp())
    results, seen = [], set()
    requests_made = 0
    failed = False
    windows = [(cat, w) for cat in CATEGORIES for w in _day_windows(since)]
    for category, (day_start, day_end) in windows:
        page = 1
        while not failed and requests_made < MAX_PAGES:
            if requests_made:
                time.sleep(REQUEST_DELAY)
            requests_made += 1
            try:
                resp = session.get(
                    LIST_URL.format(category),
                    params={"startAt": day_start, "endAt": day_end, "limit": PAGE_SIZE, "page": page},
                    timeout=20,
                )
                resp.raise_for_status()
                data = resp.json()["items"]
            except Exception as exc:  # 中途失敗就回傳已抓到的
                if not results:
                    raise
                print(f"  [cnyes] {category} {day_start} 第 {page} 頁失敗：{exc}")
                failed = True
                break
            for news in data.get("data") or []:
                news_id = news.get("newsId")
                title = (news.get("title") or "").strip()
                ts = news.get("publishAt")
                if not news_id or not title or not ts or ts < start_at or news_id in seen:
                    continue
                seen.add(news_id)
                results.append({
                    "title": title,
                    "url": NEWS_URL.format(news_id),
                    "time": datetime.fromtimestamp(ts, TW).isoformat(),
                    "thumbnail": _thumbnail(news),
                })
            if page >= (data.get("last_page") or 0) or page >= 30:
                break
            page += 1

    if not results:
        raise RuntimeError("鉅亨網新聞列表 API 沒有回傳任何文章")
    results.sort(key=lambda x: x["time"], reverse=True)
    return results
