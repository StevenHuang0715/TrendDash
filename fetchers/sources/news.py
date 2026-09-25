"""台灣與國際新聞：每個區塊由多家媒體的熱門排行合併而成（各家模組在 fetchers/outlets/）。"""

from news_group import NewsGroup
from outlets import (
    bbc_zh, businessweekly, chinatimes, cnyes, ctee, cts, cw, dw_zh, ebc, ettoday,
    ltn, money_udn, nikkei_zh, nyt_zh, pts, tvbs, udn, yahoo,
)

PAPER = NewsGroup("paper", "報紙新聞", [udn, ltn, chinatimes])
TV = NewsGroup("tv", "電視新聞", [tvbs, ebc, pts, cts])
WEB = NewsGroup("web", "網路新聞", [ettoday, yahoo])
FINANCE = NewsGroup("finance", "財經新聞", [money_udn, ctee, cnyes, cw, businessweekly])
WORLD = NewsGroup("world", "國際新聞", [bbc_zh, nyt_zh, nikkei_zh, dw_zh])

GROUPS = [PAPER, TV, WEB, FINANCE, WORLD]
