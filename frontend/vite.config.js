import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/chat': 'http://localhost:8000',
      '/generate-image': 'http://localhost:8000',
      '/static': 'http://localhost:8000'
    }
  }
})
