/** Utilidades de las pruebas E2E: usuarios demo, login y datos de prueba. */
import { expect, request, type Page, type TestInfo } from "@playwright/test";

import { API_URL, SEED_PASSWORD } from "./entorno";

/** Usuarios del seed (backend/scripts/seed_dev.py), todos con SEED_PASSWORD. */
export const USUARIOS = {
  adminNorte: "admin.norte@odontonet-demo.com",
  recepcionNorte: "recepcion.norte@odontonet-demo.com",
  doctorNorte: "doctor1.norte@odontonet-demo.com",
  recepcionSur: "recepcion.sur@odontonet-demo.com",
} as const;

export const CLINICA_NORTE = "Clínica Demo Norte";
export const DOCTORA_NORTE = "Dra. Ana Morales";

/** Sufijo único por prueba (y por reintento) para nombres de datos nuevos. */
export function sufijoUnico(testInfo: TestInfo): string {
  const letras = "abcdefghijklmnopqrstuvwxyz";
  let n = Date.now() * 10 + testInfo.retry;
  let sufijo = "";
  while (n > 0) {
    sufijo = letras[n % 26] + sufijo;
    n = Math.floor(n / 26);
  }
  return sufijo;
}

/** Inicia sesión por la interfaz y espera la pantalla de Inicio. */
export async function iniciarSesion(page: Page, email: string): Promise<void> {
  await page.goto("/");
  await page.getByLabel("Correo electrónico").fill(email);
  await page.getByLabel("Contraseña", { exact: true }).fill(SEED_PASSWORD);
  await page.getByRole("button", { name: "Iniciar sesión" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Inicio" })).toBeVisible();
}

/** Menú lateral de la aplicación. */
export function menu(page: Page) {
  return page.getByRole("navigation");
}

/**
 * Crea un paciente directamente en la API, para pruebas cuyo objetivo es
 * otro flujo (agenda, expediente). El alta por la interfaz tiene su propia prueba.
 */
export async function crearPacienteApi(
  email: string,
  datos: { first_name: string; last_name: string },
): Promise<number> {
  const api = await request.newContext({ baseURL: API_URL });
  try {
    const login = await api.post("/auth/login", {
      data: { email, password: SEED_PASSWORD },
    });
    expect(login.ok(), "login de la API para preparar datos").toBeTruthy();
    const { access_token } = (await login.json()) as { access_token: string };

    const respuesta = await api.post("/patients/", {
      data: datos,
      headers: { Authorization: `Bearer ${access_token}` },
    });
    expect(respuesta.status(), "alta del paciente por la API").toBe(201);
    const paciente = (await respuesta.json()) as { id: number };
    return paciente.id;
  } finally {
    await api.dispose();
  }
}
