import { useCallback, useEffect, useState } from 'react'
import { getJson } from '../utils/api'
import { clearCategoryCache } from './useCategoryEvents'
import { clearDateCache } from './useDateData'

const PERIODS = ['day', 'week', 'month']

async function fetchAll() {
  const index = await getJson('index.json')
  // 每個來源各自讀取，某個檔案壞掉只影響那張卡片
  const sourcesP = Promise.all(
    // 合併 index.json 的設定（例如 section）和各來源檔案的內容
    index.map((s) =>
      getJson(`${s.id}.json`)
        .then((data) => ({ ...s, ...data }))
        .catch((e) => ({ ...s, ok: false, error: e.message, items: [] })),
    ),
  )
  // 排行檔還沒產生時給 null，畫面會顯示「資料累積中」
  const rankingsP = Promise.all(PERIODS.map((p) => getJson(`rank_${p}.json`).catch(() => null)))
  const eventsP = Promise.all(PERIODS.map((p) => getJson(`events_${p}.json`).catch(() => null)))

  const datesP = getJson('dates.json').catch(() => null) // 日曆可選的日子

  const [sources, rankList, eventList, dates] = await Promise.all([sourcesP, rankingsP, eventsP, datesP])
  const rankings = Object.fromEntries(PERIODS.map((p, i) => [p, rankList[i]]))
  const events = Object.fromEntries(PERIODS.map((p, i) => [p, eventList[i]]))
  return { sources, rankings, events, dates }
}

// 自訂 Hook：把「讀資料」的邏輯包起來，元件只要拿結果來用
export function useSources() {
  const [data, setData] = useState({ sources: [], rankings: {}, events: {}, dates: null })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [version, setVersion] = useState(0) // 每次重新整理 +1，讓分類分頁知道要重新下載

  // 資料回來後才更新 state
  const apply = useCallback((promise) => {
    promise
      .then((result) => {
        setData(result)
        setError(null)
      })
      .catch((e) => setError(`${e.message}，請先執行 python fetchers/main.py 產生資料`))
      .finally(() => setLoading(false))
  }, [])

  // 元件第一次出現時載入一次
  useEffect(() => {
    apply(fetchAll())
  }, [apply])

  // 按下「重新整理」時呼叫
  const reload = () => {
    setLoading(true)
    clearCategoryCache()
    clearDateCache()
    setVersion((v) => v + 1)
    apply(fetchAll())
  }

  return { ...data, loading, error, reload, version }
}
