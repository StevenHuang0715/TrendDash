"""PTT 熱門文章（爬 ptt.cc 網頁版）。

做法：抓幾個熱門看板的最新幾頁，留下推文數夠高的文章，依推文數排序。
"""

import time
from datetime import date, timedelta

from bs4 import BeautifulSoup

from common import item, report

ID = "ptt"
NAME = "PTT 熱門"
SECTION = "social"
BASE = "https://www.ptt.cc"

BOARDS = ["Gossiping", "Stock", "C_Chat", "Baseball", "Lifeismoney", "HatePolitics", "Tech_Job"]
PAGES_PER_BOARD = 2
MIN_PUSH = 30
REQUEST_DELAY = 0.5  # 秒；別打太快
MAX_AGE_DAYS = 3


def _push_to_int(text):
    # 推文數欄位："爆" = 100 以上、"X1"~"XX" = 噓多、空白 = 0
    text = text.strip()
    if text == "爆":
        return 100
    if text.startswith("X"):
        return -1
    return int(text) if text.isdigit() else 0


def _is_recent(mmdd):
    # 列表頁日期只有 "9/25"，沒有年份；跨年時往前推一年
    today = date.today()
    try:
        month, day = (int(x) for x in mmdd.split("/"))
        d = date(today.year, month, day)
        if d > today:
            d = date(today.year - 1, month, day)
    except ValueError:  # 格式不對或 2/29 跨年
        return True
    return today - d <= timedelta(days=MAX_AGE_DAYS)


def _fetch_board(session, board):
    results = []
    url = f"{BASE}/bbs/{board}/index.html"
    for _ in range(PAGES_PER_BOARD):
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        if not soup.select("div.r-ent"):
            # 不是文章列表（可能被擋、或是 18 歲確認頁），把頁面標題記下來方便查原因
            title = soup.title.get_text(strip=True) if soup.title else "無標題"
            raise RuntimeError(f"頁面沒有文章列表（HTTP {resp.status_code}，標題：{title}，網址：{resp.url}）")

        # 第一頁底部的置底文（公告、舊爆文）在 r-list-sep 之後，要略過
        sep = soup.select_one("div.r-list-sep")
        rows = sep.find_all_previous("div", class_="r-ent")[::-1] if sep else soup.select("div.r-ent")

        for row in rows:
            link = row.select_one("div.title a")
            if not link:  # 已刪除的文章
                continue
            title = link.get_text(strip=True)
            if title.startswith("[公告]"):
                continue
            post_date = row.select_one("div.date").get_text(strip=True)
            if not _is_recent(post_date):
                continue
            push = _push_to_int(row.select_one("div.nrec").get_text())
            if push < MIN_PUSH:
                continue
            results.append(
                item(
                    title,
                    BASE + link["href"],
                    score=push,
                    score_label="爆" if push >= 100 else f"推 {push}",
                    time=post_date,
                    meta=board,
                )
            )

        prev = soup.find("a", string="‹ 上頁")
        if not prev or not prev.get("href"):
            break
        url = BASE + prev["href"]
        time.sleep(REQUEST_DELAY)
    return results


def fetch(session):
    # 18 禁看板（如八卦板）需要這個 cookie 才看得到
    session.cookies.set("over18", "1", domain=".ptt.cc")

    items = []
    for board in BOARDS:
        try:
            found = _fetch_board(session, board)
            items.extend(found)
            report("PTT 看板", board, True, len(found))
        except Exception as exc:  # 單一看板失敗不影響其他看板
            print(f"  [ptt] {board} 失敗：{exc}")
            report("PTT 看板", board, False, error=exc)
    items.sort(key=lambda x: x["score"], reverse=True)
    return items[:50]
