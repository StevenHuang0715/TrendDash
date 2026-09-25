import { useState } from 'react'
import { categoryById } from '../utils/categories'
import { timeAgo } from '../utils/time'

// 一個新聞事件：點一下展開，看各家媒體的報導
// showCategory：在跨分類的排行裡標示這個事件屬於哪一類
export default function EventRow({ event, rank, showCategory }) {
  // 每一列各自記得自己是否展開
  const [open, setOpen] = useState(false)
  const category = categoryById[event.category]

  return (
    <li className="rounded-lg transition hover:bg-slate-50 dark:hover:bg-slate-800/50">
      <button onClick={() => setOpen(!open)} className="flex w-full gap-2 p-2 text-left sm:gap-3">
        <span
          className={`w-6 shrink-0 pt-0.5 text-right font-black sm:w-7 tabular-nums ${
            rank <= 3 ? 'text-lg text-orange-500' : 'text-sm text-slate-400'
          }`}
        >
          {rank}
        </span>

        {event.thumbnail && (
          <img src={event.thumbnail} alt="" loading="lazy" className="h-12 w-16 shrink-0 rounded object-cover sm:h-14 sm:w-24" />
        )}

        <div className="min-w-0 flex-1">
          <p className="line-clamp-2 text-sm leading-snug font-medium">{event.title}</p>
          <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-500 dark:text-slate-400">
            {showCategory && category && (
              <span className={`rounded px-1.5 py-0.5 font-medium ${category.color}`}>{category.name}</span>
            )}
            <span className="font-semibold text-orange-600 dark:text-orange-400">🔥 {Math.round(event.heat)}</span>
            <span className="font-medium text-slate-700 dark:text-slate-300">{event.outlets} 家媒體</span>
            <span>{event.articles} 篇報導</span>
            {event.hot_outlets > 0 && <span>{event.hot_outlets} 家列入熱門榜</span>}
            <span>最新 {timeAgo(event.last_time)}</span>
          </p>
        </div>

        <span className={`shrink-0 self-center text-slate-400 transition ${open ? 'rotate-90' : ''}`}>›</span>
      </button>

      {open && (
        <ul className="mb-2 ml-8 border-l-2 sm:ml-12 border-slate-200 pl-3 dark:border-slate-700">
          {event.items.map((it) => (
            <li key={it.url}>
              <a
                href={it.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex gap-2 py-1 text-sm hover:text-blue-600 dark:hover:text-blue-400"
              >
                <span className="w-20 shrink-0 truncate text-xs leading-5 text-slate-500 sm:w-24">
                  {it.hot && '🔥'}
                  {it.outlet_name}
                </span>
                <span className="line-clamp-2 flex-1 sm:line-clamp-1">{it.title}</span>
                <span className="hidden shrink-0 text-xs leading-5 text-slate-400 sm:inline">{timeAgo(it.time)}</span>
              </a>
            </li>
          ))}
          {event.articles > event.items.length && (
            <li className="py-1 text-xs text-slate-400">…還有 {event.articles - event.items.length} 篇</li>
          )}
        </ul>
      )}
    </li>
  )
}
