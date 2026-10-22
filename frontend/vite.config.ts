import path from "path"
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      // En desarrollo: redirige al backend FastAPI en :8000.
      // React corre en :5173 — el proxy evita problemas de CORS.
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      // Los endpoints de auth no tienen prefijo /api — necesitan su propia entrada.
      "/auth": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
})
