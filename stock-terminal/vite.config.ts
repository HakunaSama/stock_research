import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tsconfigPaths from "vite-tsconfig-paths";

// https://vite.dev/config/
// 开发环境把 /api 反代到后端（默认 127.0.0.1:8000，可用 BACKEND_ORIGIN 覆盖），
// 与生产 nginx 同源架构一致 —— session cookie(SameSite=Lax) 在 dev 下同样生效，
// 无需 CORS 与 VITE_RESEARCH_API。
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: process.env.BACKEND_ORIGIN ?? 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/healthz': {
        target: process.env.BACKEND_ORIGIN ?? 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    sourcemap: 'hidden',
  },
  plugins: [
    react({
      babel: {
        plugins: [
          'react-dev-locator',
        ],
      },
    }),
    tsconfigPaths()
  ],
})
