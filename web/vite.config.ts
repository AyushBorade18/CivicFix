import fs from 'node:fs'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Phones only allow the camera on https (or localhost). `npm run cert` makes a
// self-signed certificate for this machine's LAN address; when it exists the
// citizen app serves https on the network so a phone can open
// https://<laptop-ip>:5173 (accept the certificate warning once).
const certDir = new URL('./.cert/', import.meta.url)
// HTTP_ONLY=1 skips it for desktop work: localhost counts as secure for the camera.
const https = !process.env.HTTP_ONLY && fs.existsSync(new URL('cert.pem', certDir))
  ? { key: fs.readFileSync(new URL('key.pem', certDir)), cert: fs.readFileSync(new URL('cert.pem', certDir)) }
  : undefined

// Same-origin API: the phone never needs to reach port 8000 directly, and an
// https page can't call an http API anyway.
const api = process.env.API_PROXY_TARGET ?? 'http://localhost:8000'
const proxy = { '/api': api, '/uploads': api }

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    // Compile the public pages at startup, so the first visit isn't a cold build.
    warmup: { clientFiles: ['./src/main.tsx', './src/pages/*.tsx', './src/citizen/pages/*.tsx'] },
    host: https ? true : undefined,
    https,
    proxy,
  },
  preview: { port: 5173, strictPort: true, host: https ? true : undefined, https, proxy },
})
