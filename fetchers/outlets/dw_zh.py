"""DW 德國之聲中文（dw.com 網站「最多瀏覽」用的 recommendation.dw.com trending_tz 排行，標題取繁體版 dw.com/zh-hant）。

做法：排行 API 只給文章 ID，先用繁體首頁內嵌的 __APP_STATE__ 對照，對不到的再逐篇打開文章頁。
排行 API 失敗或是空的時候，退回繁體首頁的文章順序（編輯排序，非點閱排行）。
"""

import json
import re
import time
from datetime import datetime, timezone

import feedparser

NAME = "DW 德國之聲中文"
BASE = "https://www.dw.com"
HOME_URL = BASE + "/zh-hant/"
TRENDING_URL = "https://recommendation.dw.com/v2/trending_tz"
MAX_ITEMS = 15
CONTENT_TYPES = {"Article", "Video", "Audio", "Liveblog", "Gallery"}

# 近期文章：繁體各頻道頁（每頁內嵌 30~45 篇），再用 RSS 補漏
SECTIONS = [
    "/zh-hant/線上報導/s-9058", "/zh-hant/政治/s-1681", "/zh-hant/經濟/s-1682", "/zh-hant/文化/s-1683",
    "/zh-hant/科技創新/s-1686", "/zh-hant/中國/s-68398488", "/zh-hant/台灣/s-68398524", "/zh-hant/香港/s-68820324",
    "/zh-hant/亞洲/s-68398536", "/zh-hant/歐洲/s-68398532", "/zh-hant/德國/s-68398523", "/zh-hant/人權/s-68398577",
    "/zh-hant/氣候環境/s-68398593", "/zh-hant/法治國家/s-68398589", "/zh-hant/新聞自由/s-68398580",
]
RSS_URL = "https://rss.dw.com/xml/rss-chi-all"
MAX_PAGES = 40  # 所有請求合計上限（含補漏的單篇文章頁）
REQUEST_DELAY = 0.3


def _app_state(html):
    m = re.search(r"window\.__APP_STATE__\s*=\s*(\{.*?\})\s*;?\s*</script>", html, re.S)
    return json.loads(m.group(1)) if m else {}


def _contents(obj):
    # 內容物件散落在各個 graph-api 查詢結果裡，遞迴找出有標題與網址的
    if isinstance(obj, dict):
        if obj.get("__typename") in CONTENT_TYPES and obj.get("namedUrl") and obj.get("title"):
            yield obj
        for v in obj.values():
            yield from _contents(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _contents(v)


def _to_item(c):
    image = (c.get("mainContentImage") or {}).get("staticUrl")
    url = c["namedUrl"]
    return {
        "title": c["title"].strip(),
        "url": BASE + url if url.startswith("/") else url,
        "time": c.get("contentDate"),
        # staticUrl 裡的 ${formatId} 是圖片尺寸代號，602 約 380px 寬
        "thumbnail": image.replace("${formatId}", "602") if image else None,
    }


def _trending_ids(session):
    params = {"timezone": "Asia/Taipei", "lang": "chinese", "amount": 20}
    resp = session.get(TRENDING_URL, params=params, timeout=20)
    resp.raise_for_status()
    items = (resp.json().get("result") or {}).get("items") or []
    return [int(x["content_id"]) for x in items if x.get("model_type") in (None, "ARTICLE")]


def _fetch_article(session, content_id):
    resp = session.get(f"{BASE}/zh-hant/a-{content_id}", timeout=20)
    resp.raise_for_status()
    for c in _contents(_app_state(resp.text)):
        if c.get("id") == content_id:
            return c
    return None


def fetch(session):
    resp = session.get(HOME_URL, timeout=20)
    resp.raise_for_status()
    home = list(_contents(_app_state(resp.text)))
    known = {c["id"]: c for c in home}

    try:
        ids = _trending_ids(session)
    except Exception as exc:
        print(f"  [dw_zh] 排行 API 失敗，改用首頁順序：{exc}")
        ids = []

    ranked = []
    for content_id in ids[:MAX_ITEMS]:
        c = known.get(content_id)
        if c is None:
            try:
                c = _fetch_article(session, content_id)
            except Exception as exc:  # 單篇失敗就略過
                print(f"  [dw_zh] 文章 {content_id} 失敗：{exc}")
        if c:
            ranked.append(c)

    items, seen = [], set()
    for c in ranked or home:
        it = _to_item(c)
        if it["title"] and it["url"] not in seen:
            seen.add(it["url"])
            items.append(it)
    if not items:
        raise ValueError("DW 中文解析不到任何文章")
    return items[:20]


def _content_time(c):
    try:
        return datetime.fromisoformat(c["contentDate"].replace("Z", "+00:00"))
    except (KeyError, AttributeError, ValueError):
        return None


def fetch_recent(session, since):
    """回傳 since 之後發布的文章。來源：dw.com/zh-hant 各頻道頁內嵌的 __APP_STATE__（繁體），
    再用 RSS（rss.dw.com/xml/rss-chi-all，簡體，約 50 篇）找出頻道頁漏掉的文章 ID，逐篇打開繁體文章頁補上。"""
    found = {}
    requests_left = MAX_PAGES

    def get(url):
        nonlocal requests_left
        requests_left -= 1
        time.sleep(REQUEST_DELAY)
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
        return resp

    def add(c):
        published = _content_time(c)
        if published and published >= since and c["id"] not in found:
            found[c["id"]] = (published, c)

    try:
        for section in SECTIONS:
            if requests_left <= 0:
                break
            for c in _contents(_app_state(get(BASE + section).text)):
                add(c)

        # RSS 只拿文章 ID 與時間；標題是簡體，所以另開繁體頁
        missing = []
        for e in feedparser.parse(get(RSS_URL).content).entries:
            m = re.search(r"/a-(\d+)", e.get("link", ""))
            if not m or not e.get("published_parsed"):
                continue
            published = datetime(*e.published_parsed[:6], tzinfo=timezone.utc)
            if published >= since and int(m.group(1)) not in found:
                missing.append(int(m.group(1)))
        for content_id in missing:
            if requests_left <= 0:
                break
            requests_left -= 1
            time.sleep(REQUEST_DELAY)
            c = _fetch_article(session, content_id)
            if c:
                add(c)
    except Exception as exc:  # 中途失敗就回傳目前拿到的
        print(f"  [dw_zh] fetch_recent 中斷：{exc}")

    if not found:
        raise ValueError("DW 中文近期文章解析不到任何文章")
    items, seen = [], set()
    for published, c in sorted(found.values(), key=lambda x: x[0], reverse=True):
        it = _to_item(c)
        if it["url"] not in seen:
            seen.add(it["url"])
            it["time"] = published.isoformat()
            items.append(it)
    return items
