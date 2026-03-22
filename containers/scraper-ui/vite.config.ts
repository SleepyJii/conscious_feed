import path from "path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": {
        target: "http://db-restful:5000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
      "/conductor-api": {
        target: "http://conductor:8000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/conductor-api/, ""),
      },
      "/rss": {
        target: "http://db-restful:5000",
        changeOrigin: true,
      },
      "/json": {
        target: "http://db-restful:5000",
        changeOrigin: true,
      },
      "/yaml": {
        target: "http://db-restful:5000",
        changeOrigin: true,
      },
    },
  },
})
