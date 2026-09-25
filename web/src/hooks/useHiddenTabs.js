import { useState } from 'react'

const KEY = 'trenddash.hiddenTabs'

// 存「隱藏了哪些」而不是「顯示哪些」：之後新增的分類預設會顯示
function read() {
  try {
    return new Set(JSON.parse(localStorage.getItem(KEY)) ?? [])
  } catch {
    return new Set()
  }
}

// 使用者自訂要顯示哪些分頁，記在瀏覽器的 localStorage，下次打開還在
export function useHiddenTabs() {
  const [hidden, setHidden] = useState(read)

  const toggle = (id) => {
    const next = new Set(hidden)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setHidden(next)
    try {
      localStorage.setItem(KEY, JSON.stringify([...next]))
    } catch {
      // 無痕模式等情況存不了，就只在這次瀏覽有效
    }
  }

  return { hidden, toggle }
}
