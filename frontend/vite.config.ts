import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

// Same-origin API calls: the session cookie and CSRF token work without CORS setup.
const proxy = { "/api": { target: "http://127.0.0.1:5001", changeOrigin: false } };
// Allow HTTPS tunnels for phone demos: `cloudflared tunnel --url http://localhost:5173`
// (or ngrok). Without this Vite rejects the tunnel's hostname.
const allowedHosts = [".trycloudflare.com", ".ngrok-free.app", ".ngrok.app"];

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "./src") } },
  server: {
    proxy,
    allowedHosts,
    // Live reload over a tunnel drops and reconnects, and every reconnect reloads the page on
    // the phones (white flash). demo.sh turns it off when it has to use the dev server.
    hmr: process.env.WHERERU_NO_HMR ? false : undefined,
  },
  // demo.sh serves a production build with `vite preview` (no live reload, far fewer requests).
  preview: { proxy, allowedHosts },
});
