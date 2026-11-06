import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The UI only talks to the read-only API on port 8000 (make api).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': 'http://127.0.0.1:8000' } },
})
