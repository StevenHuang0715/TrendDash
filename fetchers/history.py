"""歷史紀錄與熱門排行。

每次抓取都把結果存進 SQLite（data/history.db），再算出今日 / 本週 / 本月排行給前端。

話題度怎麼算：
1. 排名分：每個來源各自依熱度排好，第 1 名 100 分，越後面越低。
   推文數、觀看數、搜尋量單位不同無法直接比，所以改比「在自己來源裡排第幾」。
2. 持續加成：期間內上榜的時段越多，代表熱度越持久。
   話題度 = 期間內最高排名分 × (1 + ln(上榜時段數) / ln(每天時段數))
   → 只上榜 1 個時段 ×1、連續上榜一整天 ×2、一整週 ×2.9

時段：每 FETCH_INTERVAL_HOURS 小時為一個時段，同一時段抓很多次只算一次。
這樣排行不會因為頻繁抓取而一直跳動。
"""

import json
import math
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "history.db"
HOUR_FMT = "%Y-%m-%dT%H"
FETCH_INTERVAL_HOURS = 3  # 建議的抓取間隔，也是排行的時段長度；改這裡即可
SLOTS_PER_DAY = max(24 // FETCH_INTERVAL_HOURS, 2)
KEEP_DAYS = 35
PERIODS = {"day": 1, "week": 7, "month": 30}
TOP_N = 100
TW = timezone(timedelta(hours=8))

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
  url TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  title TEXT NOT NULL,
  thumbnail TEXT,
  meta TEXT,
  score_label TEXT,
  peak_score INTEGER,
  first_seen TEXT NOT NULL,
  last_seen TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sightings (
  url TEXT NOT NULL,
  hour TEXT NOT NULL,
  rank_score REAL NOT NULL,
  PRIMARY KEY (url, hour)
);
CREATE INDEX IF NOT EXISTS idx_sightings_hour ON sightings(hour);
"""


@contextmanager
def _connect():
    DB_PATH.parent.mkdir(exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    try:
        db.executescript(SCHEMA)
        yield db
        db.commit()
    finally:
        db.close()


def record(results):
    """把這次抓到的結果寫進歷史。results 是 main.py 產生的來源結果清單。"""
    now = datetime.now(timezone.utc)
    # 對齊到時段開頭，例如間隔 3 小時：07:40 → 06:00
    slot = now.replace(hour=now.hour - now.hour % FETCH_INTERVAL_HOURS).strftime(HOUR_FMT)
    ts = now.isoformat(timespec="seconds")

    with _connect() as db:
        for r in results:
            if not r["ok"] or not r["items"]:
                continue
            n = len(r["items"])
            for i, it in enumerate(r["items"]):
                rank_score = 100 * (n - i) / n
                db.execute(
                    """
                    INSERT INTO items (url, source, title, thumbnail, meta, score_label, peak_score, first_seen, last_seen)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(url) DO UPDATE SET
                      title = excluded.title,
                      thumbnail = COALESCE(excluded.thumbnail, items.thumbnail),
                      meta = COALESCE(excluded.meta, items.meta),
                      score_label = CASE WHEN COALESCE(excluded.peak_score, 0) >= COALESCE(items.peak_score, 0)
                                         THEN excluded.score_label ELSE items.score_label END,
                      peak_score = MAX(COALESCE(excluded.peak_score, 0), COALESCE(items.peak_score, 0)),
                      last_seen = excluded.last_seen
                    """,
                    (it["url"], r["id"], it["title"], it["thumbnail"], it["meta"],
                     it["score_label"], it["score"], ts, ts),
                )
                db.execute(
                    """
                    INSERT INTO sightings (url, hour, rank_score) VALUES (?, ?, ?)
                    ON CONFLICT(url, hour) DO UPDATE SET rank_score = MAX(rank_score, excluded.rank_score)
                    """,
                    (it["url"], slot, rank_score),
                )

        # 只保留最近 KEEP_DAYS 天，資料庫才不會無限長大
        cutoff = (now - timedelta(days=KEEP_DAYS)).strftime(HOUR_FMT)
        db.execute("DELETE FROM sightings WHERE hour < ?", (cutoff,))
        db.execute("DELETE FROM items WHERE url NOT IN (SELECT url FROM sightings)")


def _heat(peak, slots):
    return round(peak * (1 + math.log(slots) / math.log(SLOTS_PER_DAY)), 1)


def _ranked(db, source_names, start, end="9999"):
    """時段字串 [start, end) 之間的熱門文章排行，以及這段期間有幾個時段有資料。"""
    rows = db.execute(
        """
        SELECT i.*, MAX(s.rank_score) AS peak, COUNT(*) AS slots
        FROM sightings s JOIN items i ON i.url = s.url
        WHERE s.hour >= ? AND s.hour < ?
        GROUP BY s.url
        """,
        (start, end),
    ).fetchall()
    snapshots = db.execute(
        "SELECT COUNT(DISTINCT hour) FROM sightings WHERE hour >= ? AND hour < ?", (start, end)
    ).fetchone()[0]
    ranked = sorted(
        (
            {
                "title": r["title"],
                "url": r["url"],
                "thumbnail": r["thumbnail"],
                "meta": r["meta"],
                "score_label": r["score_label"],
                "source": r["source"],
                "source_name": source_names.get(r["source"], r["source"]),
                "heat": _heat(r["peak"], r["slots"]),
                "hours": r["slots"] * FETCH_INTERVAL_HOURS,  # 約略上榜小時數
                "first_seen": r["first_seen"],
                "last_seen": r["last_seen"],
            }
            for r in rows
        ),
        key=lambda x: x["heat"],
        reverse=True,
    )[:TOP_N]
    return ranked, snapshots


def _write(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def export(out_dir, source_names):
    """輸出 rank_day/week/month.json，以及日曆回看用的每日存檔 rank_date_YYYY-MM-DD.json。"""
    now = datetime.now(timezone.utc)
    with _connect() as db:
        db.row_factory = sqlite3.Row
        for key, days in PERIODS.items():
            cutoff = (now - timedelta(days=days)).strftime(HOUR_FMT)
            ranked, snapshots = _ranked(db, source_names, cutoff)
            _write(out_dir / f"rank_{key}.json", {
                "period": key,
                "days": days,
                "updated_at": now.isoformat(timespec="seconds"),
                "snapshots": snapshots,  # 期間內有幾個時段有抓資料，前端用來提示「資料累積中」
                "interval_hours": FETCH_INTERVAL_HOURS,
                "items": ranked,
            })

        # 每日存檔：時段是 UTC，換算成台灣日期的起訖；過完的日子檔案存在就跳過
        today = now.astimezone(TW).date()
        first_slot = db.execute("SELECT MIN(hour) FROM sightings").fetchone()[0]
        if first_slot:
            day = datetime.strptime(first_slot, HOUR_FMT).replace(tzinfo=timezone.utc).astimezone(TW).date()
            while day <= today:
                path = out_dir / f"rank_date_{day.isoformat()}.json"
                if not path.exists() or day >= today - timedelta(days=1):
                    start = datetime.combine(day, datetime.min.time(), TW).astimezone(timezone.utc)
                    ranked, snapshots = _ranked(db, source_names, start.strftime(HOUR_FMT),
                                                (start + timedelta(days=1)).strftime(HOUR_FMT))
                    _write(path, {"date": day.isoformat(), "snapshots": snapshots,
                                  "interval_hours": FETCH_INTERVAL_HOURS, "items": ranked})
                day += timedelta(days=1)
        for path in out_dir.glob("rank_date_*.json"):
            if path.stem.removeprefix("rank_date_") < (today - timedelta(days=KEEP_DAYS)).isoformat():
                path.unlink()
