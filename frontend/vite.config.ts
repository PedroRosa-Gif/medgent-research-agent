import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// Dev proxy: the browser talks to the Vite origin (same-origin), and Vite
// forwards the API + SSE paths to the FastAPI backend on :8000. This keeps
// EventSource simple (no CORS, no cross-origin cookies) during development.
// `changeOrigin` rewrites the Host header; SSE streams pass through because
// http-proxy keeps the connection open and does not buffer the response.
// The `/research` rule also covers `/research/stream` (prefix match).
// Use 127.0.0.1 (not localhost): uvicorn binds IPv4 127.0.0.1 by default, while
// "localhost" can resolve to IPv6 ::1 on Windows and fail to connect.
const BACKEND = 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/research': { target: BACKEND, changeOrigin: true },
      '/health': { target: BACKEND, changeOrigin: true },
    },
  },
});
