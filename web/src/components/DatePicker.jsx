import { useState } from 'react'
import { formatDate, isoDate } from '../utils/dates'

const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六']

// 日曆：選擇要回看哪一天的新聞；有存檔的日子才能點
// info = dates.json 的內容 { today, dates: [{ date, articles }] }；date = 目前選的日子（null = 看最新）
export default function DatePicker({ info, date, setDate }) {
  const [open, setOpen] = useState(false)
  const today = info?.today
  const available = new Map((info?.dates ?? []).map((d) => [d.date, d.articles]))

  // 目前顯示的月份（年、月），預設是選的日子或今天所在的月份
  const base = (date ?? today ?? '').split('-').map(Number)
  const [view, setView] = useState(null)
  const [year, month] = view ?? base

  if (!info) return null

  const firstWeekday = new Date(year, month - 1, 1).getDay()
  const daysInMonth = new Date(year, month, 0).getDate()
  const cells = [...Array(firstWeekday).fill(null), ...Array.from({ length: daysInMonth }, (_, i) => i + 1)]

  // 只能切到有資料的月份
  const months = [...available.keys()].map((d) => d.slice(0, 7))
  const cur = isoDate(year, month, 1).slice(0, 7)
  const shift = (delta) => {
    const d = new Date(year, month - 1 + delta, 1)
    setView([d.getFullYear(), d.getMonth() + 1])
  }

  const pick = (iso) => {
    setDate(iso === today ? null : iso) // 選今天 = 回到即時資料
    setOpen(false)
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className={`rounded-lg border px-3 py-1.5 text-sm ${
          date
            ? 'border-orange-500 text-orange-600 dark:text-orange-400'
            : 'border-slate-300 dark:border-slate-700'
        }`}
      >
        📅<span className="hidden sm:inline"> {date ? formatDate(date, false) : '查看過去'}</span>
        {date && <span className="sm:hidden"> {formatDate(date, false)}</span>}
      </button>

      {open && (
        <div className="absolute right-0 z-30 mt-2 w-72 rounded-xl border border-slate-200 bg-white p-4 shadow-lg dark:border-slate-700 dark:bg-slate-900">
          <div className="mb-2 flex items-center justify-between">
            <button
              onClick={() => shift(-1)}
              disabled={!months.some((m) => m < cur)}
              className="px-2 text-slate-500 disabled:opacity-30"
              aria-label="上個月"
            >
              ‹
            </button>
            <span className="font-semibold">
              {year} 年 {month} 月
            </span>
            <button
              onClick={() => shift(1)}
              disabled={!months.some((m) => m > cur)}
              className="px-2 text-slate-500 disabled:opacity-30"
              aria-label="下個月"
            >
              ›
            </button>
          </div>

          <div className="grid grid-cols-7 gap-1 text-center text-sm">
            {WEEKDAYS.map((w) => (
              <span key={w} className="py-1 text-xs text-slate-400">
                {w}
              </span>
            ))}
            {cells.map((d, i) => {
              if (!d) return <span key={`blank-${i}`} />
              const iso = isoDate(year, month, d)
              const count = available.get(iso)
              const selected = iso === (date ?? today)
              return (
                <button
                  key={iso}
                  disabled={!count}
                  onClick={() => pick(iso)}
                  title={count ? `${count.toLocaleString()} 篇報導` : '沒有資料'}
                  className={`rounded-md py-1.5 ${
                    selected
                      ? 'bg-orange-500 font-semibold text-white'
                      : count
                        ? 'hover:bg-slate-100 dark:hover:bg-slate-800'
                        : 'text-slate-300 dark:text-slate-700'
                  } ${iso === today && !selected ? 'ring-1 ring-orange-400' : ''}`}
                >
                  {d}
                </button>
              )
            })}
          </div>

          <p className="mt-3 text-xs text-slate-500">可回看最近 30 天，資料從 {formatDate(info.dates[0].date, false)} 開始</p>
          {date && (
            <button
              onClick={() => pick(today)}
              className="mt-2 w-full rounded-lg bg-slate-900 py-1.5 text-sm text-white dark:bg-slate-100 dark:text-slate-900"
            >
              回到最新
            </button>
          )}
        </div>
      )}
    </div>
  )
}
