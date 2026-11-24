import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => ({
  base: mode === "billing-test" ? "/__ielts-billing-test/" : "/",
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        // IELTS-Assist backend runs on 8001 to avoid collisions with other local services.
        // Override with VITE_BACKEND_PORT env var if needed.
        target: `http://localhost:${process.env.VITE_BACKEND_PORT ?? '8001'}`,
        changeOrigin: true,
      },
    },
  },
}))