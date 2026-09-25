"""每個來源一個模組（或 NewsGroup 物件），都提供 ID、NAME 與 fetch(session) -> list[item]。
可選：enabled() 回傳 False 時整個來源隱藏（例如缺少 API Key）。
SECTION 決定前端放在哪個分頁：news（併入新聞分類）、social、search、video。

要新增來源：在這個資料夾新增一個 .py，然後加進下面的 SOURCES。
要新增媒體：在 fetchers/outlets/ 新增模組，加進 news.py 對應的區塊。
"""

from . import google_trends, ptt, youtube
from .news import GROUPS

SOURCES = [*GROUPS, ptt, google_trends, youtube]
