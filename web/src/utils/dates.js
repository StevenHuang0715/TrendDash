// 台灣日期字串（2026-09-23）↔ 顯示用文字
export function formatDate(iso, withWeekday = true) {
  return new Date(`${iso}T12:00:00+08:00`).toLocaleDateString('zh-TW', {
    timeZone: 'Asia/Taipei',
    month: 'long',
    day: 'numeric',
    ...(withWeekday && { weekday: 'short' }),
  })
}

// 補零組成 YYYY-MM-DD
export const isoDate = (y, m, d) => `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`
