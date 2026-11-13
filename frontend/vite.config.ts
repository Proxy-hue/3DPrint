import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite' 

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    port: 5173,
    watch: {
      usePolling: true, // IMPORTANT for Windows (HMR in Docker)
    },
    proxy: {
      '/api': {
        target: 'http://backend:8000', // Within a Docker network, we refer to the service name.
        changeOrigin: false,
      },
      '/admin': {
        target: 'http://backend:8000',
        changeOrigin: false,
      }
    }
  }
})
