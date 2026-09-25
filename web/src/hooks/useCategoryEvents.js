import { useEffect, useState } from 'react'
import { getJson } from '../utils/api'

// 已讀過的分類檔先存起來，切回同一個分類不用重新下載
const cache = new Map()

export function clearCategoryCache() {
  cache.clear()
}

// 讀取單一分類的完整事件列表（events_<期間>_<分類>.json）；點進分類分頁時才下載
// period 為 null 時不下載（總覽小卡片、看日曆時用不到）
export function useCategoryEvents(period, category, version) {
  const key = period && `${period}_${category}`
  const [, setLoaded] = useState(0)

  useEffect(() => {
    if (!key || cache.has(key)) return
    getJson(`events_${key}.json`)
      .then((data) => cache.set(key, data))
      .catch(() => cache.set(key, null))
      .finally(() => setLoaded((n) => n + 1)) // 觸發重新渲染，讓畫面讀到 cache 裡的新資料
  }, [key, version])

  if (!key) return { data: null, loading: false }
  return cache.has(key) ? { data: cache.get(key), loading: false } : { data: null, loading: true }
}
