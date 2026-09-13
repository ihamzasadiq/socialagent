import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";
import { fileURLToPath } from "node:url";

const dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@shared": path.resolve(dirname, "../shared"),
    },
  },
  server: {
    // Forwards /api/* to the FastAPI backend in dev so the browser never
    // has to deal with CORS (see backend/orchestrator/main.py for the
    // CORSMiddleware fallback used when this proxy isn't in play).
    proxy: {
      "/api": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});
