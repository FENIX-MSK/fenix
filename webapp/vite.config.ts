import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      // Like Caddy on the stand: photos from Garage's website endpoint.
      '/media': {
        target: 'http://127.0.0.1:3902',
        rewrite: (path) => path.replace(/^\/media/, ''),
        headers: { Host: 'media' },
      },
    },
  },
})
