import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "./src") } },
  server: {
    // Same-origin API calls: the session cookie and CSRF token work without CORS setup.
    proxy: { "/api": { target: "http://127.0.0.1:5001", changeOrigin: false } },
    // Allow HTTPS tunnels for phone demos: `cloudflared tunnel --url http://localhost:5173`
    // (or ngrok). Without this Vite rejects the tunnel's hostname.
    allowedHosts: [".trycloudflare.com", ".ngrok-free.app", ".ngrok.app"],
  },
});
