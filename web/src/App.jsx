import { useState } from 'react'
import CategoryPanel from './components/CategoryPanel'
import DatePicker from './components/DatePicker'
import RankingPanel from './components/RankingPanel'
import SettingsMenu from './components/SettingsMenu'
import SourceCard from './components/SourceCard'
import { useDateData } from './hooks/useDateData'
import { useHiddenTabs } from './hooks/useHiddenTabs'
import { useSources } from './hooks/useSources'
import { CATEGORIES, SECTIONS } from './utils/categories'
import { formatDate } from './utils/dates'
import { matches } from './utils/sources'

const OVERVIEW = 'overview'
const RANK = 'rank'

export default function App() {
  const { sources, rankings, events, dates, loading, error, reload, version } = useSources()
  const { hidden, toggle } = useHiddenTabs()
  // useState：會變動、且變動時要重新畫面的值
  // 目前分頁記在網址 # 後面（例如 #finance），可以加書籤或分享
  const [tab, setTabState] = useState(() => window.location.hash.slice(1) || OVERVIEW)
  const setTab = (id) => {
    setTabState(id)
    window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}${id === OVERVIEW ? '' : `#${id}`}`)
    window.scrollTo(0, 0)
  }
  const [keyword, setKeyword] = useState('')
  const [mode, setMode] = useState('events')
  const [period, setPeriod] = useState('day')
  const [rankSource, setRankSource] = useState('all')
  // 日曆選的日子；null = 看最新。也記在網址 ?date=2026-09-23，可以分享某一天
  const [date, setDateState] = useState(() => new URLSearchParams(window.location.search).get('date'))
  const setDate = (d) => {
    setDateState(d)
    const url = new URL(window.location.href)
    if (d) url.searchParams.set('date', d)
    else url.searchParams.delete('date')
    window.history.replaceState(null, '', url)
  }
  const dateData = useDateData(date, version)

  // 依關鍵字過濾每個來源的 items（每次重新渲染時計算，不必另外存）
  const kw = keyword.trim().toLowerCase()
  const filtered = sources.map((s) => ({ ...s, items: s.items.filter((it) => matches(it, kw)) }))

  // 非新聞來源依 section 分組；只列出目前有資料來源的 section（例如沒設 YouTube 金鑰就沒有「影音熱門」）
  const sections = SECTIONS.map((sec) => ({ ...sec, sources: filtered.filter((s) => s.section === sec.id) })).filter(
    (sec) => sec.sources.length > 0,
  )

  // 使用者可自訂的分頁 = 新聞分類 + 其他 section；再扣掉被隱藏的
  const visibleCategories = CATEGORIES.filter((c) => !hidden.has(c.id))
  const visibleSections = sections.filter((s) => !hidden.has(s.id))
  const tabs = [
    { id: OVERVIEW, name: '總覽' },
    { id: RANK, name: '🔥 話題排行' },
    ...visibleCategories,
    ...visibleSections,
  ]
  // 目前的分頁被隱藏了就回到總覽
  const current = tabs.some((t) => t.id === tab) ? tab : OVERVIEW

  const settingGroups = [
    { title: '新聞分類', options: CATEGORIES },
    { title: '其他', options: sections },
  ]

  // 總覽和完整排行頁共用同一組排行設定
  const rankingProps = {
    rankings,
    events,
    sources: sources.map((s) => ({ id: s.id, name: s.name })),
    mode,
    setMode,
    keyword: kw,
    period,
    setPeriod,
    source: rankSource,
    setSource: setRankSource,
    dateData,
  }
  const categoryProps = { events, period, setPeriod, keyword: kw, version, dateData }

  const activeCategory = visibleCategories.find((c) => c.id === current)
  const activeSection = visibleSections.find((s) => s.id === current)

  return (
    <div className="mx-auto max-w-7xl px-3 py-4 sm:px-4 sm:py-6">
      <header className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-2">
        {/* 點 Logo 回到總覽 */}
        <h1 className="text-2xl font-black tracking-tight">
          <button onClick={() => setTab(OVERVIEW)} className="cursor-pointer" title="回到總覽">
            Trend<span className="text-orange-500">Dash</span>
          </button>
        </h1>
        <span className="hidden text-sm text-slate-500 sm:inline">
          {new Date().toLocaleDateString('zh-TW', { month: 'long', day: 'numeric', weekday: 'long' })}
        </span>
        {/* 手機：搜尋框排到最後、佔滿一整排；桌機：放在按鈕左邊 */}
        <input
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          placeholder="搜尋關鍵字…"
          type="search"
          className="order-last w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm sm:order-none sm:ml-auto sm:w-56 dark:border-slate-700 dark:bg-slate-900"
        />
        <div className="ml-auto flex gap-2 sm:ml-0">
          <DatePicker info={dates} date={date} setDate={setDate} />
          <SettingsMenu groups={settingGroups} hidden={hidden} toggle={toggle} />
          <button
            onClick={reload}
            disabled={loading}
            className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm text-white disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900"
            aria-label="重新整理"
          >
            <span className={loading ? 'inline-block animate-spin' : ''}>↻</span>
            <span className="hidden sm:inline"> {loading ? '載入中…' : '重新整理'}</span>
          </button>
        </div>
      </header>

      <nav className="no-scrollbar sticky top-0 z-20 -mx-3 mb-4 flex gap-1 overflow-x-auto overflow-y-hidden border-b border-slate-200 bg-slate-50/95 px-3 backdrop-blur sm:-mx-4 sm:mb-5 sm:px-4 dark:border-slate-800 dark:bg-slate-950/95">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`-mb-px shrink-0 border-b-2 px-3 py-2 text-sm font-medium sm:px-4 ${
              current === t.id
                ? 'border-orange-500 text-orange-600 dark:text-orange-400'
                : 'border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
            }`}
          >
            {t.name}
          </button>
        ))}
      </nav>

      {date && (
        <div className="mb-5 flex flex-wrap items-center gap-3 rounded-lg bg-orange-50 px-4 py-2 text-sm text-orange-800 dark:bg-orange-950 dark:text-orange-200">
          <span>
            📅 正在看 <b>{formatDate(date)}</b> 的新聞
            {dateData?.events && ` · 共 ${dateData.events.total_articles.toLocaleString()} 篇報導`}
          </span>
          <button onClick={() => setDate(null)} className="ml-auto font-medium underline">
            回到最新
          </button>
        </div>
      )}

      {error && <p className="rounded-lg bg-red-50 p-4 text-red-700 dark:bg-red-950 dark:text-red-300">{error}</p>}

      {current === OVERVIEW && (
        <main className="space-y-5">
          <RankingPanel {...rankingProps} limit={10} onMore={() => setTab(RANK)} />
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
            {visibleCategories.map((c) => (
              <CategoryPanel key={c.id} category={c} {...categoryProps} compact onMore={() => setTab(c.id)} />
            ))}
            {/* PTT、Google 熱搜只有即時資料，看過去的日子時不顯示 */}
            {!date &&
              visibleSections.flatMap((sec) =>
                sec.sources.map((s) => <SourceCard key={s.id} source={s} limit={10} onMore={() => setTab(sec.id)} />),
              )}
          </div>
        </main>
      )}

      {current === RANK && (
        <main className="mx-auto max-w-3xl">
          <RankingPanel {...rankingProps} />
        </main>
      )}

      {activeCategory && (
        <main className="mx-auto max-w-3xl">
          {/* key 讓切換分類時重設媒體篩選 */}
          <CategoryPanel key={activeCategory.id} category={activeCategory} {...categoryProps} />
        </main>
      )}

      {activeSection && (
        <main className="mx-auto max-w-3xl space-y-5">
          {date && <p className="text-sm text-slate-500">{activeSection.name}只有即時資料，以下是最新內容。</p>}
          {activeSection.sources.map((s) => (
            <SourceCard key={s.id} source={s} />
          ))}
        </main>
      )}
    </div>
  )
}
