import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 3000,
    proxy: {
      // Proxy /api/v1 directly to backend (port 8000)
      '/api/v1': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // Rewrite /api/dashboard to /api/v1/dashboard for legacy components
      '/api/dashboard': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/dashboard/, '/api/v1/dashboard'),
      },
      // Rewrite /api/ai to /api/v1/ai for AI components
      '/api/ai': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/ai/, '/api/v1/ai'),
      },
    },
  },
})
