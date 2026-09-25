import { PERIODS } from '../utils/periods'

// 今日 / 本週 / 本月 分段按鈕
export default function PeriodToggle({ period, setPeriod }) {
  return (
    <div className="flex rounded-lg bg-slate-100 p-0.5 dark:bg-slate-800">
      {PERIODS.map((p) => (
        <button
          key={p.id}
          onClick={() => setPeriod(p.id)}
          className={`rounded-md px-3 py-1 text-sm font-medium transition ${
            period === p.id
              ? 'bg-white text-orange-600 shadow-sm dark:bg-slate-950 dark:text-orange-400'
              : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
          }`}
        >
          {p.label}
        </button>
      ))}
    </div>
  )
}
