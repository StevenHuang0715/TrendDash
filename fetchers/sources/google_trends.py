"""Google 搜尋趨勢 台灣（RSS）。

這份 RSS 有巢狀的 <ht:news_item>，feedparser 會攤平弄丟，所以直接用 ElementTree 解析。
"""

import re
import xml.etree.ElementTree as ET
from urllib.parse import quote

from common import item

ID = "trends"
NAME = "Google 熱搜"
SECTION = "search"
URL = "https://trends.google.com/trending/rss?geo=TW"
NS = {"ht": "https://trends.google.com/trending/rss"}


def _traffic_to_int(text):
    # "2000+" -> 2000, "10萬+" -> 100000
    if not text:
        return None
    num = int(re.sub(r"[^\d]", "", text) or 0)
    if "萬" in text:
        num *= 10_000
    return num


def fetch(session):
    resp = session.get(URL, timeout=20)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    items = []
    for el in root.iter("item"):
        title = el.findtext("title")
        traffic = el.findtext("ht:approx_traffic", namespaces=NS)
        news_title = el.findtext("ht:news_item/ht:news_item_title", namespaces=NS)
        items.append(
            item(
                title,
                f"https://www.google.com/search?q={quote(title)}",
                thumbnail=el.findtext("ht:picture", namespaces=NS) or None,
                score=_traffic_to_int(traffic),
                score_label=f"{traffic} 次搜尋" if traffic else None,
                time=el.findtext("pubDate"),
                meta=news_title,
            )
        )
    items.sort(key=lambda x: x["score"] or 0, reverse=True)
    return items
