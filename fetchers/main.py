"""執行所有來源，把結果寫到 web/public/data/*.json，並更新歷史排行。

用法：python fetchers/main.py            # 全部
     python fetchers/main.py ptt news   # 只跑指定來源
"""

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

import events
import history
from common import STATUS, make_session, now_iso, report
from news_group import NewsGroup
from sources import SOURCES

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT.parent / "web" / "public" / "data"


def run_source(src):
    result = {"id": src.ID, "name": src.NAME, "updated_at": now_iso(), "ok": True, "error": None, "items": []}
    try:
        result["items"] = src.fetch(make_session())
        print(f"✓ {src.NAME}：{len(result['items'])} 筆")
        report("來源", src.NAME, True, len(result["items"]))
    except Exception as exc:  # 一個來源掛掉，其他照跑
        result["ok"] = False
        result["error"] = str(exc)
        print(f"✗ {src.NAME}：{exc}")
        report("來源", src.NAME, False, error=exc)
    return result


def main():
    load_dotenv(ROOT / ".env")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 停用的來源（例如還沒設定 API Key）不抓、也不顯示
    active = [s for s in SOURCES if getattr(s, "enabled", lambda: True)()]
    for src in SOURCES:
        if src not in active:
            (OUT_DIR / f"{src.ID}.json").unlink(missing_ok=True)

    wanted = set(sys.argv[1:])
    results, ran = [], []
    for src in active:
        if wanted and src.ID not in wanted:
            continue
        result = run_source(src)
        results.append(result)
        ran.append(src)
        (OUT_DIR / f"{src.ID}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    # 存進歷史，並重新計算今日 / 本週 / 本月排行
    history.record(results)
    history.export(OUT_DIR, {s.ID: s.NAME for s in SOURCES})
    print("✓ 話題排行已更新")

    # 新聞事件：補抓各家最新文章 → 分群 → 輸出事件排行
    groups = [s for s in ran if isinstance(s, NewsGroup)]
    if groups:
        print("… 抓取新聞文章（第一次會補抓過去 7 天，需要幾分鐘）")
        events.collect(make_session(), groups)
    events.export(OUT_DIR)

    # 前端靠這個清單知道要顯示哪些來源、順序為何
    index = [{"id": s.ID, "name": s.NAME, "section": getattr(s, "SECTION", "other")} for s in active]
    (OUT_DIR / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    # 這次執行的抓取狀況：打開 <網站>/data/status.json 就能看到哪個來源失敗
    status = {"updated_at": now_iso(), "failed": [s for s in STATUS if not s["ok"]], "all": STATUS}
    (OUT_DIR / "status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ 狀態：{len(STATUS) - len(status['failed'])} 成功、{len(status['failed'])} 失敗（見 status.json）")


if __name__ == "__main__":
    main()
