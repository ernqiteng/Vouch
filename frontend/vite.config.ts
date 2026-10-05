import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // In dev, /api/* is forwarded to the FastAPI backend, so the browser
    // only ever talks to one origin and no CORS setup is needed.
    proxy: {
      '/api': {
        // Override with VITE_PROXY_TARGET to use a backend on another port.
        target: process.env.VITE_PROXY_TARGET ?? 'http://127.0.0.1:8000',
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
