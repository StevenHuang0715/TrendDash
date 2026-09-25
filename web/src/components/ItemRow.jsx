import { timeAgo } from '../utils/time'

// 一則新聞 / 影片 / 文章。props 是父元件傳進來的資料
export default function ItemRow({ item, rank }) {
  return (
    <li>
      <a
        href={item.url}
        target="_blank"
        rel="noopener noreferrer"
        className="flex gap-2 rounded-lg p-2 sm:gap-3 transition hover:bg-slate-100 dark:hover:bg-slate-800"
      >
        <span className="w-6 shrink-0 pt-0.5 text-right text-sm font-semibold tabular-nums text-slate-400">
          {rank}
        </span>

        {item.thumbnail && (
          <img
            src={item.thumbnail}
            alt=""
            loading="lazy"
            className="h-12 w-16 shrink-0 rounded object-cover sm:h-14 sm:w-24"
          />
        )}

        <div className="min-w-0 flex-1">
          <p className="line-clamp-2 text-sm leading-snug font-medium">{item.title}</p>
          <p className="mt-1 flex flex-wrap gap-x-2 text-xs text-slate-500 dark:text-slate-400">
            {item.score_label && (
              <span className="font-semibold text-orange-600 dark:text-orange-400">{item.score_label}</span>
            )}
            {item.meta && <span className="truncate">{item.meta}</span>}
            {item.time && <span>{timeAgo(item.time)}</span>}
          </p>
        </div>
      </a>
    </li>
  )
}
