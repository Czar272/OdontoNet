/**
 * Configuración compartida de las pruebas E2E (ODON-214).
 *
 * Todo lo de aquí son valores de prueba desechables: la base dedicada
 * `odontonet_e2e_test`, puertos distintos a los de desarrollo y credenciales
 * ficticias. Nunca apunta a la base de desarrollo `odontonet`.
 */
import { existsSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const AQUI = path.dirname(fileURLToPath(import.meta.url));

export const FRONTEND_DIR = path.resolve(AQUI, "..", "..");
export const BACKEND_DIR = path.resolve(FRONTEND_DIR, "..", "backend");

export const API_PORT = 8001;
export const WEB_PORT = 5174;
export const API_URL = `http://127.0.0.1:${API_PORT}`;
export const WEB_URL = `http://127.0.0.1:${WEB_PORT}`;

/** Nombre de la base E2E: debe terminar en _test (igual que la de pytest). */
export const E2E_DB_NAME = "odontonet_e2e_test";

/** Contraseña ficticia de los usuarios demo del seed. No es una credencial real. */
export const SEED_PASSWORD = "E2e-Prueba-2026!";

/** Clave JWT solo para E2E (≥ 32 bytes). */
export const E2E_SECRET_KEY = "e2e-only-secret-key-not-for-production-0001";

/** Archivos de imágenes clínicas de la corrida, fuera del repositorio. */
export const IMAGE_STORAGE_DIR = path.join(tmpdir(), "odontonet-e2e-imagenes");

/** Contenedor de PostgreSQL de desarrollo (modo docker). */
export const DB_CONTAINER = process.env.E2E_DB_CONTAINER ?? "odontonet-db";

/**
 * Cómo se recrea la base: "docker" (local, docker exec al contenedor) o
 * "service" (CI, psql contra el servicio postgres del job).
 */
export const DB_MODE: "docker" | "service" =
  process.env.E2E_DB_MODE === "service" ? "service" : "docker";

/** Python del backend: el venv local si existe; en CI, el del sistema. */
export function pythonDelBackend(): string {
  if (process.env.E2E_PYTHON) return process.env.E2E_PYTHON;
  const venv =
    process.platform === "win32"
      ? path.join(BACKEND_DIR, "odonto_venv", "Scripts", "python.exe")
      : path.join(BACKEND_DIR, "odonto_venv", "bin", "python");
  return existsSync(venv) ? venv : "python";
}

/** DATABASE_URL de backend/.env, sin cargar el resto del archivo. */
function databaseUrlDelEnv(): string | undefined {
  const archivo = path.join(BACKEND_DIR, ".env");
  if (!existsSync(archivo)) return undefined;
  for (const linea of readFileSync(archivo, "utf-8").split(/\r?\n/)) {
    const m = linea.match(/^\s*DATABASE_URL\s*=\s*(.+?)\s*$/);
    if (m) return m[1].replace(/^["']|["']$/g, "");
  }
  return undefined;
}

/**
 * URL de la base E2E. En CI llega completa en E2E_DATABASE_URL; en local se
 * toma el servidor y las credenciales de backend/.env y solo se cambia el
 * nombre de la base. Nunca se imprime (lleva la contraseña).
 */
export function databaseUrlE2E(): string {
  const base = process.env.E2E_DATABASE_URL ?? databaseUrlDelEnv();
  if (!base) {
    throw new Error(
      "No se encontró DATABASE_URL en backend/.env ni E2E_DATABASE_URL en el entorno.",
    );
  }
  const url = new URL(base);
  url.pathname = `/${E2E_DB_NAME}`;
  return url.toString();
}

/** Variables del backend para alembic, el seed y uvicorn. */
export function entornoBackend(): Record<string, string> {
  return {
    DATABASE_URL: databaseUrlE2E(),
    SECRET_KEY: E2E_SECRET_KEY,
    // El seed solo corre en desarrollo y contra una base local (no se relaja).
    APP_ENV: "development",
    ALLOWED_HOSTS: "127.0.0.1,localhost",
    CORS_ORIGINS: WEB_URL,
    FRONTEND_URL: WEB_URL,
    IMAGE_STORAGE_DIR,
    // Hash rápido: solo afecta a los usuarios ficticios de esta base.
    BCRYPT_ROUNDS: "4",
    // Sin correo real: el restablecimiento de contraseña no sale de la máquina.
    SMTP_HOST: "",
    PYTHONUTF8: "1",
    PYTHONIOENCODING: "utf-8",
  };
}
