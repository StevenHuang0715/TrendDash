import { useState } from 'react'
import { useCategoryEvents } from '../hooks/useCategoryEvents'
import EventRow from './EventRow'
import { PERIODS } from '../utils/periods'
import PeriodToggle from './PeriodToggle'

const PAGE_SIZE = 30

const eventMatches = (ev, kw) => !kw || [ev, ...ev.items].some((it) => it.title.toLowerCase().includes(kw))

// 單一新聞分類（政治、運動…）的事件列表
// compact = 總覽頁的小卡片（只顯示前幾名）；否則是完整分頁，可依媒體篩選
// dateData 有值 = 正在看日曆上的某一天
export default function CategoryPanel({ category, events, period, setPeriod, keyword, compact, onMore, version, dateData }) {
  const [outlet, setOutlet] = useState('')
  const [pages, setPages] = useState(1)

  // 小卡片用總覽檔就夠；完整分頁另外下載這個分類的完整列表（最多 100 個事件）
  const full = useCategoryEvents(compact || dateData ? null : period, category.id, version)
  const data = dateData ? dateData.events : compact ? events[period] : full.data
  const loading = dateData ? dateData.loading : !compact && full.loading
  const inCategory = (data?.events ?? []).filter((ev) => ev.category === category.id && eventMatches(ev, keyword))

  // 媒體篩選選單：列出這個分類裡報導最多事件的媒體
  const outletCounts = {}
  for (const ev of inCategory) {
    for (const name of new Set(ev.items.map((it) => it.outlet_name))) {
      outletCounts[name] = (outletCounts[name] ?? 0) + 1
    }
  }
  const outlets = Object.entries(outletCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 25)
    .map(([name]) => name)

  const filtered = outlet ? inCategory.filter((ev) => ev.items.some((it) => it.outlet_name === outlet)) : inCategory
  const shown = filtered.slice(0, compact ? 5 : pages * PAGE_SIZE)

  return (
    <section className="flex flex-col rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <header className="flex flex-wrap items-center gap-3 border-b border-slate-200 px-3 py-3 sm:px-4 dark:border-slate-800">
        <h2 className="font-bold">{category.name}</h2>
        {compact ? (
          <span className="ml-auto text-xs text-slate-500">
            {dateData ? '當日' : PERIODS.find((p) => p.id === period).label}焦點事件
          </span>
        ) : (
          <>
            {!dateData && <PeriodToggle period={period} setPeriod={setPeriod} />}
            <select
              value={outlet}
              onChange={(e) => {
                setOutlet(e.target.value)
                setPages(1)
              }}
              className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm dark:border-slate-700 dark:bg-slate-900"
            >
              <option value="">全部媒體</option>
              {outlets.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
            <span className="ml-auto hidden text-xs text-slate-500 sm:inline">同一件事只列一次，點開看各家報導</span>
          </>
        )}
      </header>

      {shown.length === 0 ? (
        <p className="p-4 text-sm text-slate-500">
          {loading ? '載入中…' : data ? '沒有符合的事件' : '尚未產生事件資料，請先執行 fetchers'}
        </p>
      ) : (
        <ol className="flex-1 p-2">
          {shown.map((ev, i) => (
            <EventRow key={ev.id} event={ev} rank={i + 1} />
          ))}
        </ol>
      )}

      {!compact && filtered.length > shown.length && (
        <button
          onClick={() => setPages(pages + 1)}
          className="border-t border-slate-200 py-2 text-sm text-blue-600 hover:bg-slate-50 dark:border-slate-800 dark:text-blue-400 dark:hover:bg-slate-800"
        >
          顯示更多（還有 {filtered.length - shown.length} 個事件）
        </button>
      )}

      {onMore && filtered.length > shown.length && (
        <button
          onClick={onMore}
          className="border-t border-slate-200 py-2 text-sm text-blue-600 hover:bg-slate-50 dark:border-slate-800 dark:text-blue-400 dark:hover:bg-slate-800"
        >
          看全部事件 →
        </button>
      )}
    </section>
  )
}
