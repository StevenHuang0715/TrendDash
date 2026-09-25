"""新聞分類：政治、社會、生活、財經、國際、娛樂、運動、科技。

判斷順序（越前面越準）：
1. 網址裡的分類路徑，例如 sports.ltn.com.tw、news.tvbs.com.tw/entertainment/...
2. 抓取時就知道的分類，例如 Google News 用「體育」搜尋到的、財經媒體的文章
3. 標題關鍵字

事件的分類 = 所有報導分類的多數決（1、2 的票比 3 重）。
"""

import re
from collections import Counter

CATEGORIES = [
    ("politics", "政治"),
    ("society", "社會"),
    ("life", "生活"),
    ("finance", "財經"),
    ("world", "國際"),
    ("entertainment", "娛樂"),
    ("sports", "運動"),
    ("tech", "科技"),
]

# 網址規則：(正規表示式, 分類)；由上往下比對，第一個符合的就採用
_URL_RULES = [
    # 子網域
    (r"//(sports|sport)\.", "sports"),
    (r"//(ent|star|stars)\.", "entertainment"),
    (r"//(ec|finance|money|house|tw\.stock)\.", "finance"),
    (r"//(health|fashion|travel|speed)\.", "life"),
    (r"//(game|ai|3c|technews)\.", "tech"),
    # TVBS、東森、華視、自由的分類路徑
    (r"/(politics)/", "politics"),
    (r"/(society)/", "society"),
    (r"/(world|international|china)/", "world"),
    (r"/(entertainment|entertain)/", "entertainment"),
    (r"/(sports?)/", "sports"),
    (r"/(money|business)/", "finance"),
    (r"/(tech)/", "tech"),
    (r"/(life|living|local|health|weather|cars?|general|arts|novelty)/", "life"),
    (r"news\.ltn\.com\.tw/news/[A-Z]", "life"),  # 自由的地方新聞：/news/Taipei/...
    # 中時的分類代碼在網址最後：...-260407
    (r"chinatimes\.com/.*-260407", "politics"),
    (r"chinatimes\.com/.*-260409", "politics"),
    (r"chinatimes\.com/.*-260402", "society"),
    (r"chinatimes\.com/.*-260405", "life"),
    (r"chinatimes\.com/.*-26041[78]", "life"),
    (r"chinatimes\.com/.*-260421", "life"),
    (r"chinatimes\.com/.*-260408", "world"),
    (r"chinatimes\.com/.*-260410", "finance"),
    (r"chinatimes\.com/.*-260404", "entertainment"),
    (r"chinatimes\.com/.*-260403", "sports"),
    (r"chinatimes\.com/.*-260412", "tech"),
    # 聯合的分類代碼：udn.com/news/story/<代碼>/...
    (r"udn\.com/news/story/(6656|124652)/", "politics"),
    (r"udn\.com/news/story/(7321)/", "society"),
    (r"udn\.com/news/story/(7266|6885|7270|7238|6928)/", "life"),
    (r"udn\.com/news/story/(123006|12806|6811)/", "finance"),
    (r"udn\.com/news/story/(124981)/", "sports"),
]
_URL_RULES = [(re.compile(p), c) for p, c in _URL_RULES]

# 標題關鍵字（最後手段）
_KEYWORDS = {
    "sports": "亞運|奧運|棒球|籃球|中職|職棒|MLB|NBA|足球|網球|羽球|桌球|高爾夫|馬拉松|田徑|游泳|舉重|體操|金牌|銀牌|銅牌|奪金|中華隊|大谷|世界盃|選手|教練|全壘打|開轟",
    "entertainment": "歌手|演唱會|偶像|男星|女星|藝人|綜藝|電影|影集|韓星|韓劇|戲劇|金曲|金鐘|金馬|票房|劇組|Netflix|女團|男團|主持人|網紅|緋聞|婚變|出道",
    "tech": "AI|人工智慧|晶片|半導體|輝達|NVIDIA|蘋果|iPhone|Google|OpenAI|手機|科技|機器人|演算法|資安|駭客|App|遊戲|Steam",
    "finance": "台股|股市|美股|港股|ETF|營收|央行|匯率|房市|房價|投資|股價|殖利率|加權指數|漲停|跌停|外資|降息|升息|通膨|財報|基金|理財|台積電",
    "politics": "立委|總統|行政院|立法院|國民黨|民進黨|民眾黨|選舉|參選|議員|市長|賴清德|鄭麗文|外交部|國防部|共軍|兩岸|陸委會|政院|藍白|綠委|藍委|罷免|公投|政黨",
    "society": "警方|檢方|起訴|判刑|詐騙|車禍|火警|身亡|命危|殺人|砍人|毒品|竊盜|法院|被捕|酒駕|搶案|性侵|遭逮|羈押|槍擊|溺水|墜樓",
    "world": "川普|美國|日本|韓國|烏克蘭|俄羅斯|以色列|伊朗|歐盟|聯合國|北約|白宮|普丁|中東|英國|德國|法國|印度|菲律賓|越南",
    "life": "天氣|颱風|地震|健保|疫苗|醫師|登革熱|中秋|連假|美食|旅遊|交通|高鐵|捷運|發票|氣溫|降雨|寒流|健康|飲食|學校|教育",
}
_KEYWORDS = {c: re.compile(p, re.I) for c, p in _KEYWORDS.items()}


def classify_url(url):
    for pattern, cat in _URL_RULES:
        if pattern.search(url):
            return cat
    return None


def classify_title(title):
    hits = Counter({c: len(p.findall(title)) for c, p in _KEYWORDS.items()})
    cat, n = hits.most_common(1)[0]
    return cat if n else None


def classify(url, title, hint=None, weak=None):
    """回傳這篇文章的分類票：[(分類, 權重)]。

    hint：抓取時就確定的分類（例如 Google News 搜尋關鍵字），權重 2
    weak：只能當參考的分類（例如「財經媒體」也會報政治新聞），權重 1
    """
    votes = []
    strong = classify_url(url) or hint
    if strong:
        votes.append((strong, 2))
    by_title = classify_title(title)
    if by_title:
        votes.append((by_title, 1))
    if weak and not strong:
        votes.append((weak, 1))
    return votes


def vote(article_votes):
    """article_votes：每篇文章的分類票；回傳多數決結果，都沒有就算「生活」。"""
    tally = Counter()
    for votes in article_votes:
        for cat, w in votes:
            tally[cat] += w
    return tally.most_common(1)[0][0] if tally else "life"
