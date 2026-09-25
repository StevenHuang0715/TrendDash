"""共用工具：HTTP session 與統一的資料格式。

每個來源都輸出同一種格式，前端就能用同一套元件顯示：
{
  "id": "ptt", "name": "PTT 熱門", "updated_at": "...", "ok": true, "error": null,
  "items": [
    {"title": ..., "url": ..., "thumbnail": ..., "score": 123,
     "score_label": "推 123", "time": "...", "meta": "看板 / 頻道 / 媒體"}
  ]
}
"""

from datetime import datetime, timezone

import requests

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "zh-TW,zh;q=0.9"})
    return s


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# 每次執行的抓取狀況，main.py 最後寫成 status.json，方便從網站檢查哪個來源壞了
STATUS = []


def report(kind, name, ok, count=None, error=None):
    """kind：熱門榜 / 補抓文章 / 來源 / PTT 看板 等分類；name：媒體或來源名稱。"""
    STATUS.append({"kind": kind, "name": name, "ok": ok, "count": count, "error": str(error)[:200] if error else None})


def item(title, url, *, thumbnail=None, score=None, score_label=None, time=None, meta=None):
    return {
        "title": title,
        "url": url,
        "thumbnail": thumbnail,
        "score": score,
        "score_label": score_label,
        "time": time,
        "meta": meta,
    }
