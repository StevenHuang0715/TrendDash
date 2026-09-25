// 新聞分類（和 fetchers/categories.py 對應）
export const CATEGORIES = [
  { id: 'politics', name: '政治', color: 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300' },
  { id: 'society', name: '社會', color: 'bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300' },
  { id: 'life', name: '生活', color: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300' },
  { id: 'finance', name: '財經', color: 'bg-lime-100 text-lime-800 dark:bg-lime-950 dark:text-lime-300' },
  { id: 'world', name: '國際', color: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300' },
  { id: 'entertainment', name: '娛樂', color: 'bg-pink-100 text-pink-700 dark:bg-pink-950 dark:text-pink-300' },
  { id: 'sports', name: '運動', color: 'bg-orange-100 text-orange-700 dark:bg-orange-950 dark:text-orange-300' },
  { id: 'tech', name: '科技', color: 'bg-cyan-100 text-cyan-700 dark:bg-cyan-950 dark:text-cyan-300' },
]

// 非新聞的來源依 section 分頁（和 fetchers 各來源的 SECTION 對應）
export const SECTIONS = [
  { id: 'social', name: '社群熱議' },
  { id: 'search', name: '搜尋熱度' },
  { id: 'video', name: '影音熱門' },
]

export const categoryById = Object.fromEntries(CATEGORIES.map((c) => [c.id, c]))
