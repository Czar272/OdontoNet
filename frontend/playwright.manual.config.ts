import { defineConfig, devices } from "@playwright/test";

import base from "./playwright.config";

/**
 * Capturas del manual de usuario (ODON-242): mismo entorno que las pruebas
 * E2E (base `odontonet_e2e_test`, seed sintético, puertos 8001 y 5174), con
 * ventana fija de 1280x800. Se ejecuta con `npm run manual:capturas`.
 */
export default defineConfig({
  ...base,
  testDir: "./e2e/manual",
  testMatch: "capturas.spec.ts",
  testIgnore: [],
  retries: 0,
  timeout: 240_000,
  outputDir: "test-results/manual",
  reporter: [["list"]],
  use: {
    ...base.use,
    trace: "off",
    screenshot: "off",
    video: "off",
    actionTimeout: 15_000,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } },
    },
  ],
});
