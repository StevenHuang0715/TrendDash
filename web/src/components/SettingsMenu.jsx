import { useState } from 'react'

// 「顯示分類」設定：勾選要出現在上方分頁與總覽的分類
// groups: [{ title, options: [{ id, name }] }]
export default function SettingsMenu({ groups, hidden, toggle }) {
  const [open, setOpen] = useState(false)

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-700"
        aria-expanded={open}
        aria-label="顯示分類"
      >
        ⚙<span className="hidden sm:inline"> 顯示分類</span>
      </button>

      {open && (
        <div className="absolute right-0 z-30 mt-2 w-64 rounded-xl border border-slate-200 bg-white p-4 shadow-lg dark:border-slate-700 dark:bg-slate-900">
          {groups.map((g) => (
            <fieldset key={g.title} className="mb-3">
              <legend className="mb-1 text-xs font-semibold text-slate-500">{g.title}</legend>
              <div className="grid grid-cols-2 gap-1">
                {g.options.map((o) => (
                  <label key={o.id} className="flex cursor-pointer items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={!hidden.has(o.id)}
                      onChange={() => toggle(o.id)}
                      className="accent-orange-500"
                    />
                    {o.name}
                  </label>
                ))}
              </div>
            </fieldset>
          ))}
          <button
            onClick={() => setOpen(false)}
            className="w-full rounded-lg bg-slate-900 py-1.5 text-sm text-white dark:bg-slate-100 dark:text-slate-900"
          >
            完成
          </button>
        </div>
      )}
    </div>
  )
}
