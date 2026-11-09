import { configDefaults } from "vitest/config";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Como en producción, la API se ve bajo /api en el mismo origen: la cookie
    // de sesión es SameSite=Strict (ODON-265).
    proxy: {
      "/api": {
        target: process.env.VITE_API_PROXY ?? "http://127.0.0.1:8000",
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    // Margen para equipos lentos: mayor que asyncUtilTimeout (src/test/setup.ts).
    testTimeout: 15000,
    // Las pruebas E2E (Playwright, e2e/) corren aparte con `npm run e2e`.
    exclude: [...configDefaults.exclude, "e2e/**"],
  },
});
