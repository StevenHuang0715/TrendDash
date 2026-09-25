"""日經中文網（zh.cn.nikkei.com 繁體版首頁的 HotNews「最近」點閱排行）。"""

import re
import time
from datetime import datetime, timedelta, timezone

import feedparser
from bs4 import BeautifulSoup

NAME = "日經中文網"
BASE = "https://zh.cn.nikkei.com"
URL = BASE + "/"

RSS_URL = BASE + "/rss.html"
# 近期文章：各大分類列表頁（含子分類文章），每頁 10 篇，用 ?start=10、20… 翻頁
CATEGORIES = ["politicsaeconomy", "china", "industry", "columnviewpoint", "trend", "career", "product"]
# CloudFront 快取常把翻頁參數弄錯、回傳別頁內容，同一頁輪流換幾種等價寫法重試
PAGE_FORMS = ["?start={}", "?start={}&lang=zh", "?start={}&layout=blog", "?start={}&tmpl=index"]
MAX_STALE = 2  # 連續幾頁都拿不到就放棄該分類
MAX_PAGES = 80  # 所有請求合計上限
REQUEST_DELAY = 0.3
CST = timezone(timedelta(hours=8))
ARTICLE_RE = re.compile(r"/\d+-(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})\.html$")


def _date_from_url(url):
    # 網址形如 /64137-2026-09-23-10-14-58.html；時區不明，只取日期
    m = re.search(r"/\d+-(\d{4}-\d{2}-\d{2})-\d{2}-\d{2}-\d{2}\.html", url)
    return m.group(1) if m else None


def fetch(session):
    resp = session.get(URL, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # #hnbox 下三個分頁依序是「最近 / 1周 / 1個月」，取第一個
    tab = soup.select_one("#hnbox > div")
    links = tab.select("ol li a") if tab else []

    items, seen = [], set()
    for a in links:
        title = a.get_text(strip=True)
        url = a.get("href") or ""
        if url.startswith("/"):
            url = BASE + url
        if not title or not url or url in seen:
            continue
        seen.add(url)
        items.append({"title": title, "url": url, "time": _date_from_url(url), "thumbnail": None})
    if not items:
        raise ValueError("日經中文網 HotNews 解析不到任何文章")
    return items[:20]


def _time_from_url(url):
    # 網址裡是建立時間（北京時間）；跟 Joomla 分類 RSS 的 UTC 時間對過，差剛好 8 小時
    m = ARTICLE_RE.search(url)
    if not m:
        return None
    return datetime(*(int(x) for x in m.groups()), tzinfo=CST)


def _abs_url(url):
    # RSS 給的是 http://cn.nikkei.com（簡體），換成繁體站
    url = url.split("?", 1)[0].split("#", 1)[0]
    url = re.sub(r"^https?://(zh\.)?cn\.nikkei\.com", BASE, url)
    return BASE + url if url.startswith("/") else url


def _list_items(html):
    """回傳 (主列表文章, 頁面所有文章)；主列表用來判斷翻頁要不要停。"""
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one("div.mainContent")
    if not main:
        return [], []
    thumbs = {}
    for img in main.select("a img"):
        href = img.find_parent("a").get("href") or ""
        if img.get("src"):
            thumbs[_abs_url(href)] = _abs_url(img["src"])
    items, listed = {}, []
    for a in main.select("a[href]"):
        url = _abs_url(a["href"])
        title = a.get_text(strip=True)
        published = _time_from_url(url)
        if not title or not published or url in items:
            continue
        items[url] = {"title": title, "url": url, "time": published, "thumbnail": thumbs.get(url)}
        if a.find_parent("dl", class_="newsContent02"):
            listed.append(items[url])
    return listed, list(items.values())


def fetch_recent(session, since):
    """回傳 since 之後發布的文章。來源：zh.cn.nikkei.com/rss.html（最新 10 篇）
    加上各大分類列表頁（zh.cn.nikkei.com/<分類>.html?start=N）往回翻頁；時間取自文章網址（北京時間）。"""
    found = {}
    requests_left = MAX_PAGES

    def get(url):
        nonlocal requests_left
        requests_left -= 1
        # 站方會把翻頁位置記在 session cookie 裡，每次都清掉
        for c in list(session.cookies):
            if "nikkei.com" in c.domain:
                session.cookies.clear(c.domain, c.path, c.name)
        time.sleep(REQUEST_DELAY)
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
        if "maintenance" in resp.url:  # 快取到的維護頁
            raise ValueError(f"維護頁：{url}")
        return resp

    def add(item):
        if item["time"] >= since and item["url"] not in found:
            found[item["url"]] = item

    try:
        for e in feedparser.parse(get(RSS_URL).content).entries:
            url = _abs_url(e.link)
            published = _time_from_url(url)
            if published:
                add({"title": e.title.strip(), "url": url, "time": published, "thumbnail": None})

        for category in CATEGORIES:
            seen = set()
            start, misses = 0, 0
            while requests_left > 0 and misses <= MAX_STALE:
                listed = None
                for form in PAGE_FORMS:
                    if requests_left <= 0:
                        break
                    try:
                        listed, everything = _list_items(get(f"{BASE}/{category}.html" + form.format(start)).text)
                    except ValueError:
                        continue
                    # 有沒看過的文章才算拿到正確的那一頁，否則換寫法重試
                    if any(it["url"] not in seen for it in listed):
                        break
                    listed = None
                if listed is None:
                    if start == 0:
                        break
                    misses += 1  # 這頁一直拿到舊快取，跳下一頁
                    start += 10
                    continue
                misses = 0
                for it in everything:
                    add(it)
                seen.update(it["url"] for it in listed)
                if not listed or all(it["time"] < since for it in listed):
                    break
                start += 10
    except Exception as exc:  # 中途失敗就回傳目前拿到的
        print(f"  [nikkei_zh] fetch_recent 中斷：{exc}")

    if not found:
        raise ValueError("日經中文網近期文章解析不到任何文章")
    items = sorted(found.values(), key=lambda x: x["time"], reverse=True)
    for it in items:
        it["time"] = it["time"].isoformat()
    return items
