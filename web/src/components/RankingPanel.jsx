import { matches, sourceColor } from '../utils/sources'
import { timeAgo } from '../utils/time'
import EventRow from './EventRow'
import { PERIODS } from '../utils/periods'
import PeriodToggle from './PeriodToggle'


// 期間內有資料的時段太少時，排行參考價值低，提示使用者
const MIN_SNAPSHOTS = { day: 3, week: 14, month: 60 }

function RankRow({ item, rank }) {
  return (
    <li>
      <a
        href={item.url}
        target="_blank"
        rel="noopener noreferrer"
        className="flex gap-2 rounded-lg p-2 sm:gap-3 transition hover:bg-slate-100 dark:hover:bg-slate-800"
      >
        <span
          className={`w-6 shrink-0 pt-0.5 text-right font-black sm:w-7 tabular-nums ${
            rank <= 3 ? 'text-lg text-orange-500' : 'text-sm text-slate-400'
          }`}
        >
          {rank}
        </span>

        {item.thumbnail && (
          <img src={item.thumbnail} alt="" loading="lazy" className="h-12 w-16 shrink-0 rounded object-cover sm:h-14 sm:w-24" />
        )}

        <div className="min-w-0 flex-1">
          <p className="line-clamp-2 text-sm leading-snug font-medium">{item.title}</p>
          <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-500 dark:text-slate-400">
            <span className={`rounded px-1.5 py-0.5 font-medium ${sourceColor(item.source)}`}>{item.source_name}</span>
            {/* 新聞區塊的 meta 是媒體名（例如 TVBS）；Google 熱搜的 meta 是相關新聞標題，太長就不顯示 */}
            {item.meta && item.meta.length <= 8 && <span className="font-medium">{item.meta}</span>}
            <span className="font-semibold text-orange-600 dark:text-orange-400">🔥 {Math.round(item.heat)}</span>
            <span>上榜約 {item.hours} 小時</span>
            {item.score_label && <span>{item.score_label}</span>}
            <span>首次出現 {timeAgo(item.first_seen)}</span>
          </p>
        </div>
      </a>
    </li>
  )
}

const MODES = [
  { id: 'events', label: '新聞事件' },
  { id: 'articles', label: '熱門文章' },
]

// 事件符合搜尋：事件標題或任一篇報導標題包含關鍵字
const eventMatches = (ev, kw) => !kw || [ev, ...ev.items].some((it) => it.title.toLowerCase().includes(kw))

// 話題排行區塊：新聞事件 / 熱門文章 兩種模式，今日 / 本週 / 本月切換
// limit 有傳 = 總覽頁的精簡版；沒傳 = 完整排行頁
// mode / period / source 由 App 管理（狀態提升），切到完整排行頁時選擇才不會被重設
// dateData 有值 = 正在看日曆上的某一天，改用那天的存檔、不顯示期間切換
export default function RankingPanel({
  rankings, events, sources, keyword, limit, onMore,
  mode, setMode, period, setPeriod, source, setSource, dateData,
}) {
  const isEvents = mode === 'events'
  const live = isEvents ? events[period] : rankings[period]
  const data = dateData ? (isEvents ? dateData.events : dateData.rank) : live
  const all = isEvents
    ? (data?.events ?? []).filter((ev) => eventMatches(ev, keyword))
    : (data?.items ?? []).filter((it) => (source === 'all' || it.source === source) && matches(it, keyword))
  const items = limit ? all.slice(0, limit) : all
  const current = PERIODS.find((p) => p.id === period)
  const sparse = !dateData && !isEvents && data && data.snapshots < MIN_SNAPSHOTS[period]

  return (
    <section className="rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <header className="flex flex-wrap items-center gap-3 border-b border-slate-200 px-3 py-3 sm:px-4 dark:border-slate-800">
        <h2 className="font-bold">🔥 話題排行</h2>

        {/* 模式切換 */}
        <div className="flex gap-3 text-sm">
          {MODES.map((m) => (
            <button
              key={m.id}
              onClick={() => setMode(m.id)}
              className={`border-b-2 pb-0.5 font-medium ${
                mode === m.id ? 'border-orange-500 text-slate-900 dark:text-slate-100' : 'border-transparent text-slate-500'
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>

        {!dateData && <PeriodToggle period={period} setPeriod={setPeriod} />}

        {/* 來源篩選（只有熱門文章模式有） */}
        {!isEvents && <div className="flex flex-wrap gap-1">
          {[{ id: 'all', name: '全部' }, ...sources].map((s) => (
            <button
              key={s.id}
              onClick={() => setSource(s.id)}
              className={`rounded-full border px-2.5 py-0.5 text-xs ${
                source === s.id
                  ? 'border-orange-500 text-orange-600 dark:text-orange-400'
                  : 'border-slate-300 text-slate-500 dark:border-slate-700'
              }`}
            >
              {s.name}
            </button>
          ))}
        </div>}

        <span className="ml-auto text-xs text-slate-500">
          {!dateData && current.hint}
          {!dateData && data && !isEvents && ` · 每 ${data.interval_hours} 小時更新 · 已累積 ${data.snapshots} 個時段`}
          {data && isEvents && ` · ${data.total_articles.toLocaleString()} 篇報導 · 依報導媒體數排序`}
        </span>
      </header>

      {sparse && (
        <p className="mx-4 mt-3 rounded bg-amber-50 p-2 text-xs text-amber-800 dark:bg-amber-950 dark:text-amber-300">
          資料累積中：{current.label}排行需要累積多個時段才準確（目前 {data.snapshots} 個，建議至少{' '}
          {MIN_SNAPSHOTS[period]} 個）。同一時段內重複抓取不會重複計分。
        </p>
      )}

      {items.length === 0 ? (
        <p className="p-4 text-sm text-slate-500">
          {dateData?.loading
            ? '載入中…'
            : data
              ? '沒有符合的內容'
              : dateData
                ? '這一天沒有熱門文章紀錄（熱門文章從開始定時抓取後才有）'
                : '尚未產生排行資料，請先執行 fetchers'}
        </p>
      ) : (
        <ol className={`grid grid-cols-1 p-2 ${limit ? 'lg:grid-cols-2 lg:gap-x-4' : ''}`}>
          {items.map((item, i) =>
            isEvents ? (
              <EventRow key={item.id} event={item} rank={i + 1} showCategory />
            ) : (
              <RankRow key={item.url} item={item} rank={i + 1} />
            ),
          )}
        </ol>
      )}

      {onMore && all.length > items.length && (
        <button
          onClick={onMore}
          className="w-full border-t border-slate-200 py-2 text-sm text-blue-600 hover:bg-slate-50 dark:border-slate-800 dark:text-blue-400 dark:hover:bg-slate-800"
        >
          看完整排行 →
        </button>
      )}
    </section>
  )
}
