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
    // Forwards /api, /media and /health to the FastAPI backend in dev so the
    // browser never has to deal with CORS (see backend/orchestrator/main.py
    // for the CORSMiddleware fallback used when this proxy isn't in play).
    // /oauth/callback is NOT proxied on purpose: LinkedIn hits the backend
    // through the public tunnel, and the backend redirects back to the
    // frontend's FRONTEND_SUCCESS_URL.
    proxy: {
      "/api": "http://localhost:8000",
      "/media": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});
