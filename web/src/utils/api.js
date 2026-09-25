// import.meta.env.BASE_URL 會依 vite.config.js 的 base 自動調整路徑
const DATA_URL = `${import.meta.env.BASE_URL}data`
export async function getJson(path) {
  // 加時間戳避免瀏覽器快取到舊資料
  const res = await fetch(`${DATA_URL}/${path}?t=${Date.now()}`)
  if (!res.ok) throw new Error(`${path} 讀取失敗（${res.status}）`)
  return res.json()
}
