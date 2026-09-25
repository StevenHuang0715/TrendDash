import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // 相對路徑：本機或 GitHub Pages 的 /TrendDash/ 子路徑都能直接用
  base: './',
})
