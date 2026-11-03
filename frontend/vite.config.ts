/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    // Margen para equipos lentos: mayor que asyncUtilTimeout (src/test/setup.ts).
    testTimeout: 15000,
  },
});
