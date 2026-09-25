// 把時間字串轉成「5 分鐘前」這種相對時間；解析不了就原樣回傳（例如 PTT 的 "9/25"）
export function timeAgo(value) {
  if (!value) return ''
  const t = new Date(value)
  if (Number.isNaN(t.getTime()) || !/\d{4}/.test(value)) return value

  const minutes = Math.round((Date.now() - t.getTime()) / 60000)
  if (minutes < 1) return '剛剛'
  if (minutes < 60) return `${minutes} 分鐘前`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} 小時前`
  return `${Math.round(hours / 24)} 天前`
}
