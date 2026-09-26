import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [
    react(),
    {
      name: 'rewrite-all-to-admin',
      enforce: 'pre',
      configureServer(server) {
        server.middlewares.use((req, res, next) => {
          // If requesting root or any route without an extension that expects HTML
          if (req.url === '/' || req.url === '/index.html' || (!req.url?.includes('.') && req.headers.accept?.includes('text/html'))) {
            req.url = '/admin.html';
          }
          next();
        });
      }
    }
  ],
  // Separate output so the admin app deploys as its own site (index.html is
  // produced by the build:admin script from admin.html).
  build: { outDir: 'dist-admin', rollupOptions: { input: 'admin.html' } },
  server: {
    port: 5174,
    strictPort: true,
    // Compile every admin page at startup, so the first click on each isn't a cold build.
    warmup: { clientFiles: ['./src/admin/main.tsx', './src/admin/pages/*.tsx'] },
    proxy: {
      '/api': process.env.API_PROXY_TARGET ?? 'http://localhost:8000',
      '/uploads': process.env.API_PROXY_TARGET ?? 'http://localhost:8000',
    },
  }
})
