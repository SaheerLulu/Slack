import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// In dev, proxy API + WebSocket calls to the Django backend on :8000 so the
// frontend can be served from Vite (:5173) without CORS headaches.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/media': { target: 'http://localhost:8000', changeOrigin: true },
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
  build: {
    outDir: 'dist',
  },
});
