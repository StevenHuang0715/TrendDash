# TrendDash 每日熱門

每天一頁看完：台灣與國際 18 家媒體的新聞事件（依政治、社會、生活、財經、國際、娛樂、運動、科技分類）、PTT 熱門、Google 熱搜、YouTube 熱門。

網頁右上角「⚙ 顯示分類」可以勾選要顯示哪些分頁，設定記在瀏覽器裡。每個分類最多列 100 個事件（`events.py` 的 `TOP_PER_CATEGORY`），分類頁網址會帶 `#分類`（例如 `#finance`），可加書籤。

下表是新聞來源（各家的熱門榜會標記在事件上，並用在「熱門文章」排行）：

| 區塊 | 媒體 |
|---|---|
| 報紙新聞 | 聯合新聞網、自由時報、中時新聞網 |
| 電視新聞 | TVBS、東森新聞、公視、華視 |
| 網路新聞 | ETtoday、Yahoo 奇摩新聞 |
| 財經新聞 | 經濟日報、工商時報、鉅亨網、天下雜誌、商業周刊（商周無熱門榜，用最新文章） |
| 國際新聞 | BBC 中文、紐約時報中文網、日經中文網、DW 中文 |

```
fetchers/   Python 抓資料 → 輸出到 web/public/data/*.json
web/        React + Vite + Tailwind 的 Dashboard，讀取上面的 JSON
```

## 第一次設定

```powershell
# Python 環境
python -m venv .venv
.\.venv\Scripts\python -m pip install -r fetchers\requirements.txt

# 前端套件
cd web
npm install
```

### YouTube API Key（選用，沒設定時不顯示 YouTube；填好後下次執行 fetchers 就會自動出現）

1. 到 https://console.cloud.google.com/ 建立專案
2. 「API 和服務」→「程式庫」→ 搜尋並啟用 **YouTube Data API v3**
3. 「憑證」→「建立憑證」→「API 金鑰」
4. 複製 `fetchers/.env.example` 成 `fetchers/.env`，填入 `YOUTUBE_API_KEY=你的金鑰`

## 每天使用

```powershell
# 1. 抓最新資料（在專案根目錄）
.\.venv\Scripts\python fetchers\main.py

# 2. 開網頁
cd web
npm run dev          # 打開 http://localhost:5173
```

只更新某幾個來源：`.\.venv\Scripts\python fetchers\main.py ptt news`

## 話題排行（今日 / 本週 / 本月）

每次執行 `fetchers/main.py` 都會把結果存進 `data/history.db`（SQLite，保留 35 天），並產生 `rank_day/week/month.json`。

**更新頻率：每 3 小時一次**（`fetchers/history.py` 的 `FETCH_INTERVAL_HOURS`）。每 3 小時算一個時段，同一時段內抓很多次只算一次，排行不會一直跳動。網頁也不會自動刷新，只有按「重新整理」才會重新讀取。

**話題度 = 期間內最高排名分 × (1 + ln(上榜時段數) / ln(每天時段數))**

- 排名分：在自己來源排第 1 名 = 100 分，越後面越低（推數、觀看數、搜尋量單位不同，所以比排名）
- 持續加成：只上榜 1 個時段 ×1、連續一整天 ×2、一整週 ×2.9。越常出現在榜上的話題排越前面
- **要定期抓**，本週 / 本月排行才有意義

## 日曆回看

右上角「📅 查看過去」可以選最近 30 天的任一天，排行與各分類會換成那天的新聞（網址會帶 `?date=2026-09-23`，可分享）。

- 每天一份存檔：`events_date_YYYY-MM-DD.json`（新聞事件）、`rank_date_YYYY-MM-DD.json`（熱門文章）
- 過完的日子不會再變，檔案存在就不重算；今天和昨天每次都重算（可能有晚到的報導）
- PTT、Google 熱搜只有即時資料，不能回看

## 新聞分類

`fetchers/categories.py` 依序用三種線索判斷每篇文章的分類，事件的分類是所有報導的多數決：

1. 網址的分類路徑（例如 `sports.ltn.com.tw`、`news.tvbs.com.tw/entertainment/`、中時網址結尾的分類代碼）
2. 抓取時已知的分類（Google News 的搜尋關鍵字）
3. 標題關鍵字

分類偶爾會判錯，可以在 `categories.py` 補網址規則或關鍵字。

## 新增媒體

在 `fetchers/outlets/` 新增一個模組（`NAME` + `fetch(session)`，回傳依熱門度排序的 `{title, url, time, thumbnail}`），再加進 `fetchers/sources/news.py` 對應的區塊。

## 新增來源

1. 在 `fetchers/sources/` 新增一個 `xxx.py`，提供 `ID`、`NAME`、`fetch(session)`，回傳用 `common.item()` 組成的清單
2. 加進 `fetchers/sources/__init__.py` 的 `SOURCES`

前端會自動多出一張卡片，不需要改。

## 部署到 GitHub Pages

`.github/workflows/update.yml` 每 3 小時自動執行：取回 `data` 分支的資料 → 抓新資料 → 存回 `data` 分支 → 建置網頁 → 部署。

- `main` 分支：程式碼。push 到 main 只會重新建置網頁，不會重新抓資料
- `data` 分支：壓縮的歷史資料庫（`history.db.gz`）與產生的 JSON，每次整個覆蓋、不留歷史
- 手動執行：GitHub → Actions →「更新資料並部署」→ Run workflow
- YouTube：在 repo 的 Settings → Secrets and variables → Actions 新增 `YOUTUBE_API_KEY`

第一次設定：Settings → Pages → Build and deployment → Source 選 **GitHub Actions**。

## 路線圖

- [x] 第一階段：Google News、Google Trends、YouTube、PTT
- [x] 台灣 14 家 + 國際 4 家媒體熱門新聞
- [x] 新聞事件歸類（多家媒體報導同一事件）＋ 依發布日期補抓過去 7 天
- [ ] 第二階段：Dcard
- [ ] 第三階段：Threads、AI 每日摘要
- [ ] 美食地圖（指定區域高評分 / 高評論數店家；Google Places API 需綁卡，待規劃）
- [x] 部署：GitHub Actions 定時抓取 + GitHub Pages
