import { useEffect, useState } from 'react'
import { getJson } from '../utils/api'

const cache = new Map()

export function clearDateCache() {
  cache.clear()
}

// 讀取某一天的存檔：新聞事件 + 熱門文章；date 為 null（看最新）時不下載
export function useDateData(date, version) {
  const [, setLoaded] = useState(0)

  useEffect(() => {
    if (!date || cache.has(date)) return
    Promise.all([
      getJson(`events_date_${date}.json`).catch(() => null),
      getJson(`rank_date_${date}.json`).catch(() => null), // 熱門文章紀錄比較晚才開始，較早的日子沒有
    ])
      .then(([events, rank]) => cache.set(date, { events, rank }))
      .finally(() => setLoaded((n) => n + 1))
  }, [date, version])

  if (!date) return null
  return cache.get(date) ?? { loading: true }
}
