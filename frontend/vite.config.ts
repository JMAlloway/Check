import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// In Docker, use 'backend' hostname; locally use 'localhost'
const BACKEND_URL = process.env.DOCKER_ENV === 'true'
  ? 'http://backend:8000'
  : 'http://localhost:8000';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    host: '0.0.0.0', // Allow external connections in Docker
    allowedHosts: [
      'localhost',
      // Note: For Cloudflare tunnels, add your specific tunnel hostname to this list
      // e.g., 'my-tunnel-name.trycloudflare.com'
      // Wildcard '.trycloudflare.com' is intentionally NOT used to prevent host header attacks
    ],
    proxy: {
      '/api': {
        target: BACKEND_URL,
        changeOrigin: true,
      },
    },
  },
});
