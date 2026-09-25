"""新聞事件：把多家媒體報導同一件事的文章歸成一個「事件」，依報導規模排行。

流程
1. collect()：各家媒體依發布日期往回抓文章（outlet.fetch_recent），加上熱門榜文章，存進 articles 表。
   第一次會補抓過去 BACKFILL_DAYS 天，之後只抓上次之後的新文章。
2. export()：把最近 30 天的文章做標題相似度分群，輸出 events_day/week/month.json。

標題相似度
- 中文標題切成「兩字一組」（統一發票 → 統一、一發、發票），英數字整個當一個詞
- 很常見的詞（例如「記者」「快訊」）權重低，少見的詞（例如「89996565」）權重高（IDF）
- 和某個事件的相似度夠高就歸進去，否則自成一個新事件

事件熱度 = (報導媒體數 + 上熱門榜的媒體數) × (1 + ln(報導篇數))
→ 越多家媒體報導、越多家把它排上熱門榜、報導越多篇，熱度越高
→ 報導篇數每家最多算 MAX_PER_OUTLET 篇，避免 LINE TODAY 這類轉載平台灌量
"""

import hashlib
import json
import math
import re
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import categories
import google_news_archive
from history import _connect

BACKFILL_DAYS = 7
KEEP_DAYS = 35
PERIODS = {"day": 1, "week": 7, "month": 30}
TOP_N = 60  # 總覽用：全部分類合計前幾名
OVERVIEW_PER_CATEGORY = 5  # 總覽用：每個分類的前幾名（分類小卡片）
TOP_PER_CATEGORY = 100  # 分類分頁用：每個分類各自一個檔案，最多幾名
ITEMS_PER_EVENT = 10

# 日曆回看用的每日存檔
DATE_KEEP_DAYS = 30
DATE_PER_CATEGORY = 50
DATE_ITEMS_PER_EVENT = 6
MIN_OUTLETS = 2  # 至少兩家媒體報導才算「事件」
MAX_PER_OUTLET = 3

# 轉載其他媒體的文章：網址含特定字串時改算給原媒體（華視有大量中央社稿）
REPUBLISHED = {"cts": ("/cna/", "cna", "中央社")}

SIMILARITY = 0.30  # 標題相似度門檻；調高 = 分得更細，調低 = 合得更多
MAX_GAP_DAYS = 3  # 同一事件的文章，前後間隔不超過幾天
CANDIDATE_FEATURES = 8  # 每篇文章只用最有代表性的幾個詞去找候選事件，加快速度

TW = timezone(timedelta(hours=8))

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
  url TEXT PRIMARY KEY,
  outlet TEXT NOT NULL,
  outlet_name TEXT NOT NULL,
  grp TEXT NOT NULL,
  title TEXT NOT NULL,
  published TEXT NOT NULL,
  thumbnail TEXT,
  hot INTEGER NOT NULL DEFAULT 0,
  category TEXT
);
CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published);
CREATE TABLE IF NOT EXISTS archive_state (
  outlet TEXT PRIMARY KEY,
  last_fetch TEXT NOT NULL
);
"""


# 整個區塊都屬於同一分類的媒體
GROUP_CATEGORY = {"finance": "finance", "world": "world"}


def _init(db):
    db.executescript(SCHEMA)
    # 舊資料庫沒有 category 欄位時補上
    if "category" not in {r[1] for r in db.execute("PRAGMA table_info(articles)")}:
        db.execute("ALTER TABLE articles ADD COLUMN category TEXT")


def _to_utc(value, fallback):
    """各家時間格式不一，統一轉成 UTC ISO 字串；沒有時區的當作台灣時間。"""
    if not value:
        return fallback
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return fallback
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TW)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def _outlet_key(outlet):
    return outlet.__name__.rsplit(".", 1)[-1]


def _save(db, key, name, group_id, entries, now_iso, hot):
    for e in entries:
        db.execute(
            """
            INSERT INTO articles (url, outlet, outlet_name, grp, title, published, thumbnail, hot, category)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
              title = excluded.title,
              thumbnail = COALESCE(excluded.thumbnail, articles.thumbnail),
              hot = MAX(articles.hot, excluded.hot),
              category = COALESCE(articles.category, excluded.category)
            """,
            (e["url"], key, name, group_id, e["title"],
             _to_utc(e.get("time"), now_iso), e.get("thumbnail"), 1 if hot else 0, e.get("category")),
        )


def _mark_fetched(db, key, now_iso):
    db.execute(
        "INSERT INTO archive_state VALUES (?, ?) ON CONFLICT(outlet) DO UPDATE SET last_fetch = excluded.last_fetch",
        (key, now_iso),
    )
    db.commit()  # 每家抓完就存，中途中斷也不會白抓


def collect(session, groups):
    """抓各家最新文章存進資料庫。groups 是 NewsGroup 清單（要先跑過 fetch，才有熱門榜）。"""
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat(timespec="seconds")
    earliest = now - timedelta(days=BACKFILL_DAYS)

    with _connect() as db:
        _init(db)
        for group in groups:
            for outlet, entries in group.popular.items():
                _save(db, _outlet_key(outlet), outlet.NAME, group.ID, entries, now_iso, hot=True)

            for outlet in group.outlets:
                if not hasattr(outlet, "fetch_recent"):
                    continue
                key = _outlet_key(outlet)
                row = db.execute("SELECT last_fetch FROM archive_state WHERE outlet = ?", (key,)).fetchone()
                # 從上次抓取往前多抓 1 小時，避免漏掉；最多補到 BACKFILL_DAYS 天前
                since = max(datetime.fromisoformat(row[0]) - timedelta(hours=1), earliest) if row else earliest
                started = time.monotonic()
                try:
                    entries = outlet.fetch_recent(session, since)
                except Exception as exc:
                    print(f"    [事件] {outlet.NAME} 補抓失敗：{exc}")
                    continue
                if key in REPUBLISHED:
                    marker, orig_key, orig_name = REPUBLISHED[key]
                    _save(db, orig_key, orig_name, group.ID, [e for e in entries if marker in e["url"]], now_iso, hot=False)
                    entries = [e for e in entries if marker not in e["url"]]
                _save(db, key, outlet.NAME, group.ID, entries, now_iso, hot=False)
                _mark_fetched(db, key, now_iso)
                print(f"    [事件] {outlet.NAME}：{len(entries)} 篇（{time.monotonic() - started:.0f} 秒）")

        # Google News 依日期補抓：媒體最多，讓「報導媒體數」更準確
        from sources.news import GROUPS as ALL_GROUPS  # 放這裡避免循環匯入

        known = {_outlet_key(o): (o.NAME, g.ID) for g in ALL_GROUPS for o in g.outlets}
        row = db.execute("SELECT last_fetch FROM archive_state WHERE outlet = 'google_news'").fetchone()
        since = max(datetime.fromisoformat(row[0]) - timedelta(hours=1), earliest) if row else earliest
        for e in google_news_archive.fetch_since(session, since):
            key, is_known = google_news_archive.outlet_key(e["publisher"])
            name, group_id = known[key] if is_known and key in known else (e["publisher"], "google")
            _save(db, key, name, group_id, [e], now_iso, hot=False)
        _mark_fetched(db, "google_news", now_iso)

        cutoff = (now - timedelta(days=KEEP_DAYS)).isoformat(timespec="seconds")
        db.execute("DELETE FROM articles WHERE published < ?", (cutoff,))


# ---------- 分群 ----------

_TOKEN = re.compile(r"[a-z0-9]+|[㐀-䶿一-鿿]+")


def _features(title):
    feats = set()
    for tok in _TOKEN.findall(title.lower()):
        if tok[0].isascii():
            if len(tok) >= 2:
                feats.add(tok)
        elif len(tok) == 1:
            feats.add(tok)
        else:
            feats.update(tok[i : i + 2] for i in range(len(tok) - 1))
    return feats


def _cluster(articles):
    """articles 依時間排序；回傳 [(member_indexes, centroid)]。"""
    feats = [_features(a["title"]) for a in articles]
    df = defaultdict(int)
    for fs in feats:
        for f in fs:
            df[f] += 1
    n = len(articles)
    idf = {f: math.log(n / c) for f, c in df.items()}

    clusters = []  # 每個：{"members": [...], "centroid": {f: w}, "norm2": float, "last": datetime}
    index = defaultdict(set)  # 詞 → 含有這個詞的事件
    max_gap = timedelta(days=MAX_GAP_DAYS)

    for i, fs in enumerate(feats):
        vec = {f: idf[f] for f in fs if df[f] > 1}  # 只出現一次的詞不可能配對，略過
        if not vec:
            continue
        t = articles[i]["dt"]
        norm = math.sqrt(sum(w * w for w in vec.values()))
        top = sorted(vec, key=vec.get, reverse=True)[:CANDIDATE_FEATURES]

        best, best_sim = None, SIMILARITY
        for cid in set().union(*(index[f] for f in top)):
            c = clusters[cid]
            if t - c["last"] > max_gap:
                continue
            dot = sum(w * c["centroid"].get(f, 0) for f, w in vec.items())
            sim = dot / (norm * math.sqrt(c["norm2"]))
            if sim > best_sim:
                best, best_sim = cid, sim

        if best is None:
            clusters.append({"members": [], "centroid": {}, "norm2": 0.0, "last": t})
            best = len(clusters) - 1
        c = clusters[best]
        c["members"].append(i)
        c["last"] = max(c["last"], t)
        for f, w in vec.items():
            c["centroid"][f] = c["centroid"].get(f, 0) + w
            index[f].add(best)
        c["norm2"] = sum(w * w for w in c["centroid"].values())

    return [(c["members"], c["centroid"]) for c in clusters], feats, idf


def _representative(members, centroid, feats, idf):
    """最能代表事件的標題：和事件整體最相似的那篇。"""
    def score(i):
        vec = {f: idf[f] for f in feats[i] if f in centroid}
        norm = math.sqrt(sum(w * w for w in vec.values())) or 1
        return sum(w * centroid[f] for f, w in vec.items()) / norm
    return max(members, key=score)



def _write(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def _build_events(clusters, articles, feats, idf, start, end=None, items_per_event=ITEMS_PER_EVENT):
    """計算 [start, end) 期間內的事件，依熱度排序。同一群文章只算期間內的報導。"""
    events = []
    for members, centroid in clusters:
        inside = [i for i in members if articles[i]["dt"] >= start and (end is None or articles[i]["dt"] < end)]
        outlets = {articles[i]["outlet"] for i in inside}
        if len(outlets) < MIN_OUTLETS:
            continue
        hot_outlets = {articles[i]["outlet"] for i in inside if articles[i]["hot"]}
        per_outlet = defaultdict(int)
        for i in inside:
            per_outlet[articles[i]["outlet"]] += 1
        counted = sum(min(c, MAX_PER_OUTLET) for c in per_outlet.values())
        heat = (len(outlets) + len(hot_outlets)) * (1 + math.log(counted))
        rep = articles[_representative(inside, centroid, feats, idf)]
        ordered = sorted(inside, key=lambda i: articles[i]["dt"], reverse=True)
        thumb = next((articles[i]["thumbnail"] for i in ordered if articles[i]["thumbnail"]), None)
        events.append({
            "id": hashlib.md5(rep["url"].encode()).hexdigest()[:12],
            "category": categories.vote(articles[i]["vote"] for i in inside),
            "title": rep["title"],
            "url": rep["url"],
            "thumbnail": thumb,
            "heat": round(heat, 1),
            "outlets": len(outlets),
            "hot_outlets": len(hot_outlets),
            "articles": len(inside),
            "first_time": articles[ordered[-1]]["time"],
            "last_time": articles[ordered[0]]["time"],
            "items": [
                {k: articles[i][k] for k in ("title", "url", "outlet_name", "group", "time", "hot")}
                for i in ordered[:items_per_event]
            ],
        })
    events.sort(key=lambda e: e["heat"], reverse=True)
    return events


def _export_dates(out_dir, clusters, articles, feats, idf, now):
    """每天一份存檔（台灣日期），給前端日曆回看。

    已經過完的日子內容不會再變，檔案存在就跳過；今天和昨天每次重算（可能還有晚到的報導）。
    """
    today = now.astimezone(TW).date()
    first = today - timedelta(days=DATE_KEEP_DAYS - 1)
    counts = defaultdict(int)
    for a in articles:
        counts[a["dt"].astimezone(TW).date()] += 1

    index = []
    for day in sorted(d for d in counts if d >= first):
        path = out_dir / f"events_date_{day.isoformat()}.json"
        if not path.exists() or day >= today - timedelta(days=1):
            start = datetime.combine(day, datetime.min.time(), TW)
            events = _build_events(clusters, articles, feats, idf, start, start + timedelta(days=1),
                                   items_per_event=DATE_ITEMS_PER_EVENT)
            by_cat = defaultdict(list)
            for ev in events:
                by_cat[ev["category"]].append(ev)
            keep = {ev["id"]: ev for ev in events[:TOP_N]}
            for evs in by_cat.values():
                keep.update((ev["id"], ev) for ev in evs[:DATE_PER_CATEGORY])
            _write(path, {
                "date": day.isoformat(),
                "updated_at": now.isoformat(timespec="seconds"),
                "total_articles": counts[day],
                "events": sorted(keep.values(), key=lambda e: e["heat"], reverse=True),
            })
        index.append({"date": day.isoformat(), "articles": counts[day]})

    # 刪掉超過保留天數的舊檔
    for path in out_dir.glob("events_date_*.json"):
        if path.stem.removeprefix("events_date_") < first.isoformat():
            path.unlink()
    _write(out_dir / "dates.json", {"today": today.isoformat(), "dates": index})


def export(out_dir):
    now = datetime.now(timezone.utc)
    started = time.monotonic()
    month_cutoff = (now - timedelta(days=max(PERIODS.values()))).isoformat(timespec="seconds")

    with _connect() as db:
        _init(db)
        rows = db.execute(
            "SELECT url, outlet, outlet_name, grp, title, published, thumbnail, hot, category FROM articles "
            "WHERE published >= ? ORDER BY published",
            (month_cutoff,),
        ).fetchall()

    articles = [
        {"url": r[0], "outlet": r[1], "outlet_name": r[2], "group": r[3], "title": r[4],
         "time": r[5], "thumbnail": r[6], "hot": bool(r[7]), "dt": datetime.fromisoformat(r[5]),
         "vote": categories.classify(r[0], r[4], hint=r[8], weak=GROUP_CATEGORY.get(r[3]))}
        for r in rows
    ]
    clusters, feats, idf = _cluster(articles) if articles else ([], [], {})

    for key, days in PERIODS.items():
        cutoff = now - timedelta(days=days)
        events = _build_events(clusters, articles, feats, idf, cutoff)

        # 總覽檔：全部的前 TOP_N 名 + 每個分類的前幾名；分類檔：每個分類前 TOP_PER_CATEGORY 名
        keep, by_cat = [], defaultdict(list)
        for rank, ev in enumerate(events):
            by_cat[ev["category"]].append(ev)
            if rank < TOP_N or len(by_cat[ev["category"]]) <= OVERVIEW_PER_CATEGORY:
                keep.append(ev)
        for cat, _ in categories.CATEGORIES:
            _write(out_dir / f"events_{key}_{cat}.json",
                   {"period": key, "category": cat, "updated_at": now.isoformat(timespec="seconds"),
                    "events": by_cat[cat][:TOP_PER_CATEGORY]})

        _write(out_dir / f"events_{key}.json", {
            "period": key,
            "days": days,
            "updated_at": now.isoformat(timespec="seconds"),
            "total_articles": sum(1 for a in articles if a["dt"] >= cutoff),
            "categories": [{"id": c, "name": n} for c, n in categories.CATEGORIES],
            "events": keep,
        })

    _export_dates(out_dir, clusters, articles, feats, idf, now)
    print(f"✓ 新聞事件：{len(articles)} 篇文章 → {len(clusters)} 群（{time.monotonic() - started:.1f} 秒）")
