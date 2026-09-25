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
