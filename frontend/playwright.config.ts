import { defineConfig, devices } from "@playwright/test";

import {
  API_PORT,
  API_URL,
  BACKEND_DIR,
  FRONTEND_DIR,
  WEB_PORT,
  WEB_URL,
  entornoBackend,
  pythonDelBackend,
} from "./e2e/support/entorno";

/**
 * Pruebas de extremo a extremo (ODON-214): navegador real contra el backend
 * real y una base PostgreSQL propia (`odontonet_e2e_test`) que se recrea en
 * cada corrida. Puertos 8001 y 5174 para no chocar con los de desarrollo.
 */
export default defineConfig({
  testDir: "./e2e",
  // Las capturas del manual tienen su propia configuración (playwright.manual.config.ts).
  testIgnore: "**/manual/**",
  globalSetup: "./e2e/global-setup.ts",
  // Las pruebas comparten base: en serie, para que sean deterministas.
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  timeout: 45_000,
  expect: { timeout: 10_000 },
  // Salidas en carpetas ignoradas por git.
  outputDir: "test-results/e2e",
  reporter: [
    ["list"],
    ["html", { outputFolder: "playwright-report", open: "never" }],
  ],
  use: {
    baseURL: WEB_URL,
    locale: "es-GT",
    // Misma zona que la clínica demo: la hora del navegador coincide con su horario.
    timezoneId: "America/Guatemala",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } },
    },
  ],
  webServer: [
    {
      // Backend en 127.0.0.1:8001 con la base E2E. `/` no consulta la base.
      command: `"${pythonDelBackend()}" -m uvicorn app.main:app --host 127.0.0.1 --port ${API_PORT} --no-access-log`,
      cwd: BACKEND_DIR,
      url: `${API_URL}/`,
      env: entornoBackend(),
      reuseExistingServer: false,
      timeout: 120_000,
      stdout: "ignore",
      stderr: "pipe",
    },
    {
      // Frontend en 5174, que reenvía /api al backend E2E.
      command: `npx vite --host 127.0.0.1 --port ${WEB_PORT} --strictPort`,
      cwd: FRONTEND_DIR,
      url: WEB_URL,
      env: { VITE_API_PROXY: API_URL },
      reuseExistingServer: false,
      timeout: 120_000,
      stdout: "ignore",
      stderr: "pipe",
    },
  ],
});
