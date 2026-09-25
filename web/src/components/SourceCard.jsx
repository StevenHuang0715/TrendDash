import { timeAgo } from '../utils/time'
import ItemRow from './ItemRow'

// 一個來源的卡片。limit 決定顯示幾筆，onMore 有傳才顯示「看全部」
export default function SourceCard({ source, limit, onMore }) {
  const items = limit ? source.items.slice(0, limit) : source.items

  return (
    <section className="flex flex-col rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <header className="flex items-baseline justify-between border-b border-slate-200 px-3 py-3 sm:px-4 dark:border-slate-800">
        <h2 className="font-bold">{source.name}</h2>
        <span className="text-xs text-slate-500">更新於 {timeAgo(source.updated_at)}</span>
      </header>

      {!source.ok && (
        <p className="m-4 rounded bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          ⚠ {source.error}
        </p>
      )}

      {source.ok && items.length === 0 && <p className="p-4 text-sm text-slate-500">沒有符合的內容</p>}

      <ol className="flex-1 p-2">
        {items.map((item, i) => (
          <ItemRow key={item.url} item={item} rank={i + 1} />
        ))}
      </ol>

      {onMore && source.items.length > items.length && (
        <button
          onClick={onMore}
          className="border-t border-slate-200 py-2 text-sm text-blue-600 hover:bg-slate-50 dark:border-slate-800 dark:text-blue-400 dark:hover:bg-slate-800"
        >
          看全部 {source.items.length} 則 →
        </button>
      )}
    </section>
  )
}
