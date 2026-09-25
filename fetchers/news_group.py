"""把多家媒體合併成一個來源區塊（例如「電視新聞」= TVBS + 東森 + 公視 + 華視）。

每家媒體是 fetchers/outlets/ 裡的一個模組，提供：
    NAME = "聯合新聞網"
    fetch(session) -> list[dict]   # 依熱門度排序（最熱門在前），每筆 {title, url, time, thumbnail}

合併方式：輪流取各家的第 1 名、第 2 名…，讓每家媒體的熱門文章公平排在一起。
某一家抓失敗只會少那一家，全部失敗才算這個區塊失敗。
"""

from itertools import zip_longest

from common import item

PER_OUTLET = 15


class NewsGroup:
    def __init__(self, id, name, outlets):
        self.ID = id
        self.SECTION = "news"
        self.NAME = name
        self.outlets = outlets

        self.popular = {}  # 最近一次抓到的各家熱門榜，events.py 用來標記「上熱門榜」

    def fetch(self, session):
        lists, errors = [], []
        self.popular = {}
        for outlet in self.outlets:
            try:
                entries = outlet.fetch(session)[:PER_OUTLET]
                self.popular[outlet] = entries
                lists.append([(outlet.NAME, e) for e in entries])
                print(f"    {outlet.NAME}：{len(entries)} 筆")
            except Exception as exc:
                errors.append(f"{outlet.NAME}：{exc}")
                print(f"    {outlet.NAME} 失敗：{exc}")

        if not lists:
            raise RuntimeError("；".join(errors))

        items, seen = [], set()
        for row in zip_longest(*lists):
            for pair in row:
                if pair is None:
                    continue
                name, e = pair
                if e["url"] in seen:
                    continue
                seen.add(e["url"])
                items.append(item(e["title"], e["url"], thumbnail=e.get("thumbnail"), time=e.get("time"), meta=name))
        return items
