import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // No frontend environment variables are needed during the foundation milestone.
  // In particular, do not expose the compromised legacy VITE_* provider keys.
  envPrefix: [],
  test: { include: ['src/**/*.test.ts'] },
  server: {
    host: '127.0.0.1',
    strictPort: true,
    proxy: { '/api': process.env.API_PROXY_TARGET || 'http://127.0.0.1:8000' },
  },
})
