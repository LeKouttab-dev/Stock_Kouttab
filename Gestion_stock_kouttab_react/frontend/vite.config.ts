/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import basicSsl from '@vitejs/plugin-basic-ssl';
import path from 'node:path';

// Le scanner de justificatifs et le lecteur de codes-barres appellent
// `getUserMedia`, que les navigateurs réservent aux origines sécurisées.
// `localhost` en fait partie, mais pas `http://192.168.x.x` : sans HTTPS, la
// caméra reste inaccessible depuis un téléphone du réseau local.
//
// `MOBILE=1 npm run dev` sert donc le front en HTTPS (certificat auto-signé, à
// accepter une fois sur le téléphone) et relaie `/api` vers le backend. Ce
// relais est indispensable : une page HTTPS ne peut pas appeler une API en
// clair — le navigateur bloque la requête en « contenu mixte ». En passant par
// la même origine, le problème disparaît, et le CORS avec.
const mobile = process.env.MOBILE === '1';

export default defineConfig({
  plugins: [react(), ...(mobile ? [basicSsl()] : [])],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    chunkSizeWarningLimit: 1500,
  },
  test: {
    environment: 'jsdom',
    globals: true,
    // Les tests interceptent une URL absolue ; sans cette valeur ils
    // hériteraient du `VITE_API_URL` relatif de `.env.local` (destiné au
    // relais mobile) et msw ne reconnaîtrait plus aucune requête.
    env: { VITE_API_URL: 'http://localhost:8000/api/v1' },
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      exclude: [
        'node_modules/',
        'src/test/',
        '**/*.config.*',
        'src/main.tsx',
        'dist/',
        '**/*.d.ts',
      ],
    },
  },
});
