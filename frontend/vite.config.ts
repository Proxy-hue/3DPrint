import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// Адрес backend для прокси: VITE_PROXY_TARGET (Docker: http://backend:8000, локально: http://localhost:8000)
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const target = process.env.VITE_PROXY_TARGET || env.VITE_PROXY_TARGET || 'http://localhost:8000'
  return {
    plugins: [react()],
    server: {
      port: 5173,
      host: true,
      watch: { usePolling: true }, // для Windows / Docker
      proxy: {
        '/api': { target, changeOrigin: true },
        '/admin': { target, changeOrigin: true },
        '/static': { target, changeOrigin: true },
      },
    },
  }
})
