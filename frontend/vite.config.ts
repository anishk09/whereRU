import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  server: {
    // Same-origin API calls: the session cookie and CSRF token work without CORS setup.
    proxy: { "/api": { target: "http://127.0.0.1:5001", changeOrigin: false } },
  },
});
