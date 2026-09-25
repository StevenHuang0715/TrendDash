// 各來源的標籤顏色（Tailwind class 要寫完整字串，編譯時才抓得到）
const COLORS = {
  news: 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300',
  trends: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300',
  youtube: 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300',
  ptt: 'bg-violet-100 text-violet-700 dark:bg-violet-950 dark:text-violet-300',
  paper: 'bg-sky-100 text-sky-700 dark:bg-sky-950 dark:text-sky-300',
  tv: 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300',
  web: 'bg-cyan-100 text-cyan-700 dark:bg-cyan-950 dark:text-cyan-300',
  finance: 'bg-lime-100 text-lime-800 dark:bg-lime-950 dark:text-lime-300',
  world: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300',
}
const FALLBACK = 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300'

export const sourceColor = (id) => COLORS[id] ?? FALLBACK

// 搜尋框用：標題或附註包含關鍵字就算符合
export const matches = (item, kw) => !kw || `${item.title} ${item.meta ?? ''}`.toLowerCase().includes(kw)
