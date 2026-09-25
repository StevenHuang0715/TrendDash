"""Google News 依日期補抓：每天用分類關鍵字各搜尋一次，收集當天發布的新聞。

Google News 的日期搜尋一定要有關鍵字，而且每次最多 100 則、依相關度排序，
所以這裡的資料只用在「新聞事件」分群（增加報導媒體數），不當作熱門排行。
"""

import time
from datetime import datetime, timedelta, timezone
from time import mktime
from urllib.parse import quote

import feedparser

# 搜尋關鍵字 → 分類（None = 不指定，交給 categories.py 判斷）
QUERIES = {
    "台灣": None, "政治": "politics", "兩岸": "politics", "社會": "society", "國際": "world",
    "財經": "finance", "股市": "finance", "科技": "tech", "娛樂": "entertainment", "體育": "sports",
    "生活": "life", "健康": "life",
}
URL = "https://news.google.com/rss/search?q={q}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
TW = timezone(timedelta(hours=8))

# Google News 上的媒體名稱 → 我們自己的媒體模組，避免同一家媒體被算兩次
ALIASES = {
    "udn": ["UDN", "聯合新聞網", "udn.com"],
    "ltn": ["自由時報", "自由時報電子報", "Liberty Times Net", "自由財經"],
    "chinatimes": ["中時新聞網", "中國時報", "China Times"],
    "ettoday": ["ETtoday新聞雲", "ETtoday", "ETtoday 新聞雲", "ETtoday財經雲", "ETtoday星光雲"],
    "yahoo": ["Yahoo新聞", "Yahoo奇摩新聞", "Yahoo 奇摩新聞", "Yahoo股市", "Yahoo奇摩股市"],
    "tvbs": ["TVBS", "TVBS新聞網", "TVBS News"],
    "ebc": ["東森新聞", "EBC東森新聞", "東森財經新聞", "EBC 東森新聞"],
    "pts": ["公視新聞網", "公視新聞網 PNN", "PNN 公視新聞議題中心"],
    "cts": ["華視新聞網", "華視新聞", "華視"],
    "money_udn": ["經濟日報"],
    "ctee": ["工商時報"],
    "cnyes": ["鉅亨網", "Anue鉅亨", "鉅亨"],
    "cw": ["天下雜誌", "CommonWealth Magazine"],
    "businessweekly": ["商業周刊", "商周"],
    "bbc_zh": ["BBC", "BBC News 中文", "BBC 中文"],
    "nyt_zh": ["紐約時報中文網", "The New York Times"],
    "nikkei_zh": ["日經中文網"],
    "dw_zh": ["DW", "德國之聲", "DW 德國之聲"],
    "cna": ["中央社 CNA", "中央社", "CNA", "中央通訊社"],
}
_ALIAS_TO_KEY = {name.lower(): key for key, names in ALIASES.items() for name in names}


def outlet_key(publisher):
    """回傳 (outlet key, 是否為我們已接的媒體)。"""
    key = _ALIAS_TO_KEY.get(publisher.strip().lower())
    return (key, True) if key else (f"gn:{publisher.strip()}", False)


def fetch_day(session, day):
    """抓 day（台灣日期）當天發布的新聞。"""
    after, before = day.isoformat(), (day + timedelta(days=1)).isoformat()
    results, seen = [], set()
    for q, category in QUERIES.items():
        try:
            resp = session.get(URL.format(q=quote(f"{q} after:{after} before:{before}")), timeout=20)
            resp.raise_for_status()
        except Exception as exc:
            print(f"      Google News「{q}」{day} 失敗：{exc}")
            continue
        for e in feedparser.parse(resp.content).entries:
            publisher = e.get("source", {}).get("title")
            if not publisher or e.link in seen or not e.get("published_parsed"):
                continue
            seen.add(e.link)
            title = e.title
            if title.endswith(f" - {publisher}"):
                title = title[: -len(f" - {publisher}")]
            published = datetime.fromtimestamp(mktime(e.published_parsed), timezone.utc)
            results.append({"title": title.strip(), "url": e.link, "time": published.isoformat(),
                            "publisher": publisher, "category": category})
        time.sleep(0.5)
    return results


def fetch_since(session, since):
    """從 since 那天到今天，逐日補抓。"""
    today = datetime.now(TW).date()
    day = since.astimezone(TW).date()
    results = []
    while day <= today:
        items = fetch_day(session, day)
        print(f"    [事件] Google News {day}：{len(items)} 則")
        results.extend(items)
        day += timedelta(days=1)
    return results
